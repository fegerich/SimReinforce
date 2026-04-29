import simpy

# Zustände
WARTEND        = "WARTEND"
EINLADEN       = "EINLADEN"
AUSSTEIGEN     = "AUSSTEIGEN"
FAHREND_HOCH   = "FAHREND_HOCH"
FAHREND_RUNTER = "FAHREND_RUNTER"


class Aufzug:
    def __init__(self, env, etagen, num_etagen, fahrt_zeit):
        self.env            = env
        self.etagen         = etagen
        self.num_etagen     = num_etagen
        self.fahrt_zeit     = fahrt_zeit

        self.aktuelle_etage = 0
        self.fahrtrichtung  = "up"
        self.im_aufzug      = []
        self.zustand        = WARTEND
        self.warte_event    = env.event()

    def aufwecken(self):
        """Wird vom Fahrgast aufgerufen um den wartenden Aufzug zu wecken."""
        if not self.warte_event.triggered:
            self.warte_event.succeed()

    def irgendwo_wartende(self):
        return any(
            len(self.etagen[e].store_up.items) > 0 or
            len(self.etagen[e].store_down.items) > 0
            for e in range(self.num_etagen)
        )

    def ziele_in_richtung(self):
        if self.fahrtrichtung == "up":
            im_aufzug_ziele = any(f.ziel > self.aktuelle_etage for f in self.im_aufzug)
            wartende        = any(
                len(self.etagen[e].store_up.items) > 0 or
                len(self.etagen[e].store_down.items) > 0
                for e in range(self.aktuelle_etage + 1, self.num_etagen)
            )
        else:
            im_aufzug_ziele = any(f.ziel < self.aktuelle_etage for f in self.im_aufzug)
            wartende        = any(
                len(self.etagen[e].store_up.items) > 0 or
                len(self.etagen[e].store_down.items) > 0
                for e in range(0, self.aktuelle_etage)
            )
        return im_aufzug_ziele or wartende

    def bestimme_richtung(self):
        for delta in range(1, self.num_etagen):
            oben  = self.aktuelle_etage + delta
            unten = self.aktuelle_etage - delta
            if oben < self.num_etagen and len(self.etagen[oben].store_up.items) > 0:
                return "up"
            if unten >= 0 and len(self.etagen[unten].store_down.items) > 0:
                return "down"
            if oben < self.num_etagen and len(self.etagen[oben].store_down.items) > 0:
                return "up"
            if unten >= 0 and len(self.etagen[unten].store_up.items) > 0:
                return "down"
        if len(self.etagen[self.aktuelle_etage].store_up.items) > 0:
            return "up"
        return "down"

    def _einladen(self, store):
        """Hilfsgenerator: lädt alle Fahrgäste aus dem Store."""
        if len(store.items) > 0:
            self.zustand = EINLADEN
            self.visualisiere()
            while len(store.items) > 0:
                fahrgast = yield store.get()
                fahrgast.abgeholt.succeed()
                self.im_aufzug.append(fahrgast)

    def run(self):
        """Hauptprozess - wird von SimPy als Prozess gestartet."""
        while True:

            # ── AUSSTEIGEN ───────────────────────────────────────────────
            aussteiger = [f for f in self.im_aufzug if f.ziel == self.aktuelle_etage]
            if aussteiger:
                self.zustand = AUSSTEIGEN
                self.visualisiere()
                for fahrgast in aussteiger:
                    self.im_aufzug.remove(fahrgast)
                    fahrgast.angekommen.succeed()

            # ── EINLADEN (aktuelle Richtung) ──────────────────────────────
            store = self.etagen[self.aktuelle_etage].store_up \
                    if self.fahrtrichtung == "up" \
                    else self.etagen[self.aktuelle_etage].store_down
            yield from self._einladen(store)

            # ── WARTEND ──────────────────────────────────────────────────
            # Aufzug ist leer und keine Ziele mehr in aktueller Richtung →
            # auf dieser Etage warten bis ein Fahrgast ruft.
            if not self.im_aufzug and not self.ziele_in_richtung():
                self.zustand = WARTEND
                self.visualisiere()
                if not self.irgendwo_wartende():
                    self.warte_event = self.env.event()
                    yield self.warte_event
                self.fahrtrichtung = self.bestimme_richtung()
                # Sofort einladen falls jemand auf dieser Etage in die neue
                # Richtung wartet (z.B. Wendemanöver genau hier)
                store2 = self.etagen[self.aktuelle_etage].store_up \
                         if self.fahrtrichtung == "up" \
                         else self.etagen[self.aktuelle_etage].store_down
                yield from self._einladen(store2)

            # ── FAHREND ──────────────────────────────────────────────────
            self.zustand = FAHREND_HOCH if self.fahrtrichtung == "up" else FAHREND_RUNTER
            self.visualisiere()
            yield self.env.timeout(self.fahrt_zeit)

            if self.fahrtrichtung == "up":
                self.aktuelle_etage = min(self.aktuelle_etage + 1, self.num_etagen - 1)
            else:
                self.aktuelle_etage = max(self.aktuelle_etage - 1, 0)


    def visualisiere(self):
        zustand_symbol = {
        WARTEND:        "💤 WARTEND",
        EINLADEN:       "🚪 EINLADEN",
        AUSSTEIGEN:     "🚶 AUSSTEIGEN",
        FAHREND_HOCH:   "▲  FAHREND HOCH",
        FAHREND_RUNTER: "▼  FAHREND RUNTER",

        }
        pfeil = "▲" if self.fahrtrichtung == "up" else "▼"

        print()
        print(f"╔══════════════════════════════════════╗")
        print(f"║  🕐 Zeit: {self.env.now:>4.0f}s                       ║")
        print(f"║  {zustand_symbol[self.zustand]:<36}║")
        print(f"║  🚶 Im Aufzug: {len(self.im_aufzug)} Fahrgast{'  ' if len(self.im_aufzug) == 1 else 'e '}            ║")
        if self.im_aufzug:
            ziele = ", ".join(f"F{f.id:02d}→E{f.ziel}" for f in self.im_aufzug)
            print(f"║  ({ziele[:36]:<36})║")
        print(f"╠══════════════════════════════════════╣")

        for e in range(self.num_etagen - 1, -1, -1):
            etage          = self.etagen[e]
            aufzug_hier    = (e == self.aktuelle_etage)
            wartend_hoch   = len(etage.store_up.items)
            wartend_runter = len(etage.store_down.items)

            aufzug_symbol = f"[{pfeil}]" if aufzug_hier else "   "
            hoch_str      = f"▲×{wartend_hoch}"   if wartend_hoch   > 0 else "   "
            runter_str    = f"▼×{wartend_runter}" if wartend_runter > 0 else "   "

            print(f"║  E{e}  {aufzug_symbol}  {hoch_str}  {runter_str}               ║")

        print(f"╚══════════════════════════════════════╝")
