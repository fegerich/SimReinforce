# Zustände
WARTEND        = "WARTEND"
EINLADEN       = "EINLADEN"
AUSSTEIGEN     = "AUSSTEIGEN"
FAHREND_HOCH   = "FAHREND_HOCH"
FAHREND_RUNTER = "FAHREND_RUNTER"


class Aufzug:
    def __init__(self, env, etagen, num_etagen, fahrt_zeit, halt_zeit=5, aufzug_id="A", kapazitaet=5, schrittlogger=None):
        self.env            = env
        self.etagen         = etagen
        self.num_etagen     = num_etagen
        self.fahrt_zeit     = fahrt_zeit
        self.halt_zeit      = halt_zeit
        self.aufzug_id      = aufzug_id
        self.kapazitaet     = kapazitaet
        self.schrittlogger  = schrittlogger

        self.aktuelle_etage = 0
        self.fahrtrichtung  = "up"
        self.im_aufzug      = []
        self.zustand        = WARTEND
        self.warte_event    = env.event()
        self.alle_aufzuege  = []   # wird nach Erstellung von außen gesetzt
        self._letzte_vis_zeit = -1  # Timestamp-Guard gegen doppelte Ausgabe

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
        if len(self.etagen[self.aktuelle_etage].store_down.items) > 0:
            return "down"
        return self.fahrtrichtung  # niemand wartet → Richtung beibehalten

    def _einladen(self, store):
        """Hilfsgenerator: lädt Fahrgäste aus dem Store bis zur Kapazitätsgrenze."""
        if len(store.items) > 0 and len(self.im_aufzug) < self.kapazitaet:
            self.zustand = EINLADEN
            self.visualisiere()
            while len(store.items) > 0 and len(self.im_aufzug) < self.kapazitaet:
                fahrgast = yield store.get()
                # Race condition: fahrgast_prozess kann den Treppenhaus-Pfad
                # genommen haben bevor wir abgeholt.succeed() aufrufen konnten.
                if fahrgast.nimmt_treppenhaus:
                    continue
                fahrgast.angekommen = self.env.event()
                fahrgast.abgeholt.succeed()
                self.im_aufzug.append(fahrgast)
                if self.schrittlogger:
                    self.schrittlogger.fahrgast_eingestiegen(self.env.now, self, fahrgast)
            yield self.env.timeout(self.halt_zeit)

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
                    if self.schrittlogger:
                        self.schrittlogger.fahrgast_angekommen(self.env.now, self, fahrgast)
                yield self.env.timeout(self.halt_zeit)

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
                if self.schrittlogger:
                    self.schrittlogger.aufzug_wartend(self.env.now, self)
                self.warte_event = self.env.event()
                if not self.irgendwo_wartende():
                    yield self.warte_event
                else:
                    # Event sofort auslösen aber trotzdem yielden,
                    # damit andere SimPy-Prozesse noch laufen können
                    self.warte_event.succeed()
                    yield self.warte_event
                self.fahrtrichtung = self.bestimme_richtung()
                # Sofort einladen falls jemand auf dieser Etage in die neue
                # Richtung wartet (z.B. Wendemanöver genau hier)
                store2 = self.etagen[self.aktuelle_etage].store_up \
                         if self.fahrtrichtung == "up" \
                         else self.etagen[self.aktuelle_etage].store_down
                yield from self._einladen(store2)

            # ── FAHREND ──────────────────────────────────────────────────
            # Kein Ziel mehr (z.B. Fahrgast von anderem Aufzug geholt) → nicht fahren
            if not self.im_aufzug and not self.ziele_in_richtung():
                continue

            self.zustand = FAHREND_HOCH if self.fahrtrichtung == "up" else FAHREND_RUNTER
            self.visualisiere()
            if self.schrittlogger:
                self.schrittlogger.aufzug_fahrend(self.env.now, self)
            yield self.env.timeout(self.fahrt_zeit)

            if self.fahrtrichtung == "up":
                self.aktuelle_etage = min(self.aktuelle_etage + 1, self.num_etagen - 1)
            else:
                self.aktuelle_etage = max(self.aktuelle_etage - 1, 0)

    # ── Visualisierung ────────────────────────────────────────────────────────

    def visualisiere(self):
        if len(self.alle_aufzuege) > 1:
            master = self.alle_aufzuege[0]
            if master._letzte_vis_zeit == self.env.now:
                return
            master._letzte_vis_zeit = self.env.now
            self._visualisiere_multi()
        else:
            self._visualisiere_single()

    def _visualisiere_single(self):
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

    def _visualisiere_multi(self):
        aufzuege = self.alle_aufzuege

        ZUSTAND_KURZ = {
            WARTEND:        "💤 WARTEND      ",
            EINLADEN:       "🚪 EINLADEN     ",
            AUSSTEIGEN:     "🚶 AUSSTEIGEN   ",
            FAHREND_HOCH:   "▲  FAHREND HOCH ",
            FAHREND_RUNTER: "▼  FAHREND RUNTER ",
        }

        GITTER_PFEIL = {
            FAHREND_HOCH:   "▲",
            FAHREND_RUNTER: "▼",
            WARTEND:        "○",
            EINLADEN:       "●",
            AUSSTEIGEN:     "●",
        }

        SEP = "═" * 54
        print()
        print(f"╔{SEP}╗")
        print(f"║  🕐 Zeit: {self.env.now:>4.0f}s" + " " * 41 + "║")
        print(f"╠{SEP}╣")

        for a in aufzuege:
            zst = ZUSTAND_KURZ[a.zustand]
            n = len(a.im_aufzug)
            ziele = ", ".join(f"F{f.id:02d}→E{f.ziel}" for f in a.im_aufzug)
            pax = f"({n}) {ziele}" if ziele else f"({n})"
            inhalt = f"  {a.aufzug_id}  {zst}  {pax}"
            print(f"║{inhalt:<55}║")

        print(f"╠{SEP}╣")

        for e in range(self.num_etagen - 1, -1, -1):
            etage = self.etagen[e]

            syms = []
            for a in aufzuege:
                if a.aktuelle_etage == e:
                    p = GITTER_PFEIL.get(a.zustand, "?")
                    syms.append(f"[{p}{a.aufzug_id}]")
                else:
                    syms.append("[   ]")
            sym_str = "  ".join(syms)

            wh = len(etage.store_up.items)
            wr = len(etage.store_down.items)
            hoch_s   = f"▲×{wh}" if wh > 0 else "   "
            runter_s = f"▼×{wr}" if wr > 0 else "   "

            inhalt = f"  E{e}  {sym_str}  {hoch_s}  {runter_s}"
            print(f"║{inhalt:<55}║")

        print(f"╚{SEP}╝")
