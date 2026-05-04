# Zustände
WARTEN         = "WARTEN"
EINLADEN       = "EINLADEN"
AUSLADEN       = "AUSLADEN"
FAHREND_HOCH   = "FAHREND_HOCH"
FAHREND_RUNTER = "FAHREND_RUNTER"


class Aufzug:
    """
    Simuliert einen einzelnen Aufzug im Gebäude als SimPy-Prozess.
    Implementiert den SCAN-Algorithmus: fährt in einer Richtung bis keine Ziele mehr
    in dieser Richtung vorhanden sind, bestimmt dann die neue Richtung und wartet
    bei Bedarf auf den nächsten Fahrgast.

    Zustände: WARTEN -> EINLADEN -> FAHREND_HOCH/FAHREND_RUNTER -> AUSLADEN -> ...
    """
    def __init__(self, env, etagen, num_etagen, fahrt_zeit, halt_zeit=5, aufzug_id="A", kapazitaet=5, schrittlogger=None):
        self.env            = env
        self.etagen         = etagen
        self.num_etagen     = num_etagen
        self.fahrt_zeit     = fahrt_zeit  # Sekunden pro Etage
        self.halt_zeit      = halt_zeit   # Sekunden für Ein-/Aussteigen
        self.aufzug_id      = aufzug_id
        self.kapazitaet     = kapazitaet
        self.schrittlogger  = schrittlogger

        self.aktuelle_etage = 0
        self.fahrtrichtung  = "up"
        self.im_aufzug      = []          # Aktuell mitfahrende Fahrgäste
        self.zustand        = WARTEN
        self.warte_event    = env.event() # Wird von aufwecken() getriggert wenn ein Fahrgast spawnt

    def aufwecken(self):
        """Weckt den Aufzug aus dem WARTEN-Zustand, wenn ein neuer Fahrgast gespawnt wurde."""
        if not self.warte_event.triggered:
            self.warte_event.succeed()

    def irgendwo_wartende(self):
        """Prüft ob irgendwo im Gebäude Fahrgäste warten (richtungsunabhängig)."""
        return any(
            len(self.etagen[e].store_up.items) > 0 or
            len(self.etagen[e].store_down.items) > 0
            for e in range(self.num_etagen)
        )

    def ziele_in_richtung(self):
        """
        Prüft ob es noch Gründe gibt, in der aktuellen Fahrtrichtung weiterzufahren:
        entweder Fahrgäste im Aufzug mit Ziel in dieser Richtung,
        oder wartende Fahrgäste in einer Etage in dieser Richtung.
        """
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
        """
        Bestimmt die optimale Fahrtrichtung wenn der Aufzug leer wartet.
        Scannt mit wachsendem Abstand abwechselnd nach oben und unten.
        Priorität pro Distanz: gleiche Richtung vor Gegenrichtung
        """
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
        # Fahrgäste auf der aktuellen Etage als letztes prüfen
        if len(self.etagen[self.aktuelle_etage].store_up.items) > 0:
            return "up"
        if len(self.etagen[self.aktuelle_etage].store_down.items) > 0:
            return "down"
        return self.fahrtrichtung

    def _einladen(self, store):
        """
        Lädt Fahrgäste aus dem gegebenen Store ein, bis der Aufzug voll ist oder der Store leer ist.
        Fahrgäste die zwischenzeitlich die Treppe genommen haben werden übersprungen.
        Danach wartet der Aufzug halt_zeit Sekunden (Türen öffnen/schließen).
        """
        if len(store.items) > 0 and len(self.im_aufzug) < self.kapazitaet:
            self.zustand = EINLADEN
            while len(store.items) > 0 and len(self.im_aufzug) < self.kapazitaet:
                fahrgast = yield store.get()
                if fahrgast.nimmt_treppenhaus:
                    # Fahrgast hat während der Wartezeit die Treppe genommen
                    continue
                fahrgast.angekommen = self.env.event()
                fahrgast.abgeholt.succeed()
                self.im_aufzug.append(fahrgast)
                if self.schrittlogger:
                    self.schrittlogger.fahrgast_eingestiegen(self.env.now, self, fahrgast)
            yield self.env.timeout(self.halt_zeit)

    def run(self):
        """
        Haupt-Prozess des Aufzugs. Läuft als SimPy-Prozess für die gesamte Simulationsdauer.
        Pro Iteration: Aussteigen -> Einladen -> ggf. Warten -> Fahren.
        Aussteigen vor Einladen damit der freiwerdende Platz sofort genutzt werden kann.
        """
        while True:

            # AUSSTEIGEN 
            aussteiger = [f for f in self.im_aufzug if f.ziel == self.aktuelle_etage]
            if aussteiger:
                self.zustand = AUSLADEN
                for fahrgast in aussteiger:
                    self.im_aufzug.remove(fahrgast)
                    fahrgast.angekommen.succeed()
                    if self.schrittlogger:
                        self.schrittlogger.fahrgast_angekommen(self.env.now, self, fahrgast)
                yield self.env.timeout(self.halt_zeit)

            # EINLADEN (aktuelle Richtung) 
            store = (
                self.etagen[self.aktuelle_etage].store_up
                if self.fahrtrichtung == "up"
                else self.etagen[self.aktuelle_etage].store_down
            )
            yield from self._einladen(store)

            # WARTEN 
            if not self.im_aufzug and not self.ziele_in_richtung():
                self.zustand = WARTEN
                if self.schrittlogger:
                    self.schrittlogger.aufzug_wartend(self.env.now, self)
                # warte_event wird neu erstellt damit aufwecken() erneut verwendet werden kann
                self.warte_event = self.env.event()
                if not self.irgendwo_wartende():
                    yield self.warte_event
                else:
                    # Bereits Wartende vorhanden: sofort weitermachen ohne zu blockieren
                    self.warte_event.succeed()
                    yield self.warte_event
                self.fahrtrichtung = self.bestimme_richtung()
                store2 = (
                    self.etagen[self.aktuelle_etage].store_up
                    if self.fahrtrichtung == "up"
                    else self.etagen[self.aktuelle_etage].store_down
                )
                yield from self._einladen(store2)

            # FAHREND 
            # Nochmal prüfen: nach dem Einladen könnte der Aufzug noch leer sein
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
