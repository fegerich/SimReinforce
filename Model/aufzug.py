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

    def aufwecken(self):
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
        return self.fahrtrichtung

    def _einladen(self, store):
        if len(store.items) > 0 and len(self.im_aufzug) < self.kapazitaet:
            self.zustand = EINLADEN
            while len(store.items) > 0 and len(self.im_aufzug) < self.kapazitaet:
                fahrgast = yield store.get()
                if fahrgast.nimmt_treppenhaus:
                    continue
                fahrgast.angekommen = self.env.event()
                fahrgast.abgeholt.succeed()
                self.im_aufzug.append(fahrgast)
                if self.schrittlogger:
                    self.schrittlogger.fahrgast_eingestiegen(self.env.now, self, fahrgast)
            yield self.env.timeout(self.halt_zeit)

    def run(self):
        while True:

            # ── AUSSTEIGEN ───────────────────────────────────────────────
            aussteiger = [f for f in self.im_aufzug if f.ziel == self.aktuelle_etage]
            if aussteiger:
                self.zustand = AUSSTEIGEN
                for fahrgast in aussteiger:
                    self.im_aufzug.remove(fahrgast)
                    fahrgast.angekommen.succeed()
                    if self.schrittlogger:
                        self.schrittlogger.fahrgast_angekommen(self.env.now, self, fahrgast)
                yield self.env.timeout(self.halt_zeit)

            # ── EINLADEN (aktuelle Richtung) ──────────────────────────────
            store = (
                self.etagen[self.aktuelle_etage].store_up
                if self.fahrtrichtung == "up"
                else self.etagen[self.aktuelle_etage].store_down
            )
            yield from self._einladen(store)

            # ── WARTEND ──────────────────────────────────────────────────
            if not self.im_aufzug and not self.ziele_in_richtung():
                self.zustand = WARTEND
                if self.schrittlogger:
                    self.schrittlogger.aufzug_wartend(self.env.now, self)
                self.warte_event = self.env.event()
                if not self.irgendwo_wartende():
                    yield self.warte_event
                else:
                    self.warte_event.succeed()
                    yield self.warte_event
                self.fahrtrichtung = self.bestimme_richtung()
                store2 = (
                    self.etagen[self.aktuelle_etage].store_up
                    if self.fahrtrichtung == "up"
                    else self.etagen[self.aktuelle_etage].store_down
                )
                yield from self._einladen(store2)

            # ── FAHREND ──────────────────────────────────────────────────
            if not self.im_aufzug and not self.ziele_in_richtung():
                continue

            self.zustand = FAHREND_HOCH if self.fahrtrichtung == "up" else FAHREND_RUNTER
            if self.schrittlogger:
                self.schrittlogger.aufzug_fahrend(self.env.now, self)
            yield self.env.timeout(self.fahrt_zeit)

            if self.fahrtrichtung == "up":
                self.aktuelle_etage = min(self.aktuelle_etage + 1, self.num_etagen - 1)
            else:
                self.aktuelle_etage = max(self.aktuelle_etage - 1, 0)
