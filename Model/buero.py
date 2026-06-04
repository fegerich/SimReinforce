import numpy as np
import random
from Model.fahrgast import Fahrgast
from Model.tageszeit import Tageszeit


class Buero:
    """
    Koordiniert den gesamten Fahrgastbetrieb im Gebäude.
    Erzeugt Fahrgäste, steuert deren Prozesse und erkennt das Simulationsende.

    Verantwortlichkeiten:
        - Fahrgäste zeitgesteuert spawnen (fahrgast_generator)
        - Jeden Fahrgast durch seinen Lebenszyklus führen (fahrgast_prozess)
        - Tageszeiten auswerten für Spawn-Rate und Etagen-Gewichtung
        - Simulation beenden sobald alle Fahrgäste abgeschlossen sind
    """
    def __init__(self, env, etagen, aufzuege, abgeschlossene,
                 spawn_ende, max_patience, tageszeiten, default_spawn,
                 schrittlogger=None, aufgenommene=None):
        self.env            = env
        self.etagen         = etagen
        self.aufzuege       = aufzuege
        self.abgeschlossene = abgeschlossene  # Sammelliste aller abgeschlossenen Fahrgäste
        self.aufgenommene   = aufgenommene    # Sammelliste aller eingestiegenen Fahrgäste (optional)
        self.spawn_ende     = spawn_ende       # Simulationszeit ab der kein Spawning mehr stattfindet
        self.max_patience   = max_patience     # Sekunden bis ein Fahrgast die Treppe nimmt
        self.tageszeiten    = tageszeiten
        self.default_spawn  = default_spawn    # Fallback-Tageszeit wenn keine Tageszeit aktiv ist
        self.schrittlogger  = schrittlogger

        self._aktive       = 0          # Anzahl laufender Fahrgast-Prozesse
        self._spawn_fertig = False      # True sobald fahrgast_generator() beendet ist
        self.fertig        = env.event()  # Wird getriggert wenn alle Fahrgäste abgeschlossen sind

    # Logik für bestimmen des Simualtionsendes

    def fahrgast_gestartet(self):
        """Zählt einen neu gestarteten Fahrgast-Prozess."""
        self._aktive += 1

    def fahrgast_abgeschlossen(self):
        """Zählt einen abgeschlossenen Fahrgast-Prozess und prüft ob die Simulation enden kann."""
        self._aktive -= 1
        self._pruefen()

    def spawning_beendet(self):
        """Signalisiert dass der Generator keine neuen Fahrgäste mehr erzeugt."""
        self._spawn_fertig = True
        self._pruefen()

    def _pruefen(self):
        """
        Triggert das fertig-Event wenn Spawning abgeschlossen ist und keine
        Fahrgast-Prozesse mehr laufen. Beide Bedingungen müssen erfüllt sein,
        da sonst noch aktive Fahrgäste verloren gehen würden.
        """
        if self._spawn_fertig and self._aktive == 0 and not self.fertig.triggered:
            self.fertig.succeed()

    # Tageszeit 

    def _get_tageszeit(self, now) -> Tageszeit:
        """Gibt die aktive Tageszeit für den aktuellen Simulationszeitpunkt zurück.
        Fällt auf default_spawn zurück wenn kein Zeitfenster passt."""
        for tz in self.tageszeiten:
            if tz.start <= now < tz.ende:
                return tz
        return self.default_spawn

    # Simulationsprozesse 

    def fahrgast_prozess(self, fahrgast):
        """
        SimPy-Prozess für einen einzelnen Fahrgast.
        Legt ihn in den Store seiner Startetage, wartet auf Abholung oder Geduldsablauf,
        und verfolgt ihn bis zur Ankunft an der Zieletage.
        """
        etage              = self.etagen[fahrgast.start]
        fahrgast.spawnzeit = self.env.now
        store              = etage.store_up if fahrgast.ziel > fahrgast.start else etage.store_down

        yield store.put(fahrgast)
        if self.schrittlogger:
            self.schrittlogger.fahrgast_spawn(self.env.now, fahrgast)

        for a in self.aufzuege:
            a.aufwecken()

        # Wartet entweder auf Abholung durch Aufzug oder bis max_patience abgelaufen ist
        fahrgast.abgeholt = self.env.event()
        yield fahrgast.abgeholt | self.env.timeout(fahrgast.max_patience)

        if not fahrgast.abgeholt.triggered:
            # Geduld abgelaufen → Treppenhaus
            fahrgast.nimmt_treppenhaus = True
            fahrgast.wartezeit         = self.env.now - fahrgast.spawnzeit
            # Fahrgast manuell aus dem Store entfernen, da er diesen nie verlassen hat
            if fahrgast in store.items:
                store.items.remove(fahrgast)
            if self.schrittlogger:
                self.schrittlogger.fahrgast_treppenhaus(self.env.now, fahrgast)
            self.abgeschlossene.append(fahrgast)
            self.fahrgast_abgeschlossen()
            return

        fahrgast.einsteigzeit = self.env.now
        if self.aufgenommene is not None:
            self.aufgenommene.append(fahrgast)

        yield fahrgast.angekommen
        fahrgast.ankunftszeit = self.env.now
        fahrgast.wartezeit    = fahrgast.ankunftszeit - fahrgast.spawnzeit
        self.abgeschlossene.append(fahrgast)
        self.fahrgast_abgeschlossen()

    def fahrgast_generator(self):
        """
        SimPy-Prozess der kontinuierlich neue Fahrgäste erzeugt.
        Spawn-Intervall folgt einer Exponentialverteilung mit dem Mittelwert spawn_rate der aktiven Tageszeit.
        Nach spawn_ende werden keine neuen Fahrgäste mehr erstellt.
        """
        fahrgast_id = 0

        while True:
            tz = self._get_tageszeit(self.env.now)

            wartezeit = np.random.exponential(tz.spawn_rate)
            yield self.env.timeout(max(1, wartezeit))

            if self.env.now >= self.spawn_ende:
                break

            start = random.choices(tz.start_etagen, weights=tz.start_gewichtung, k=1)[0]
            ziel  = random.choices(tz.ziel_etagen,  weights=tz.ziel_gewichtung,  k=1)[0]
            # Sicherstellen dass Start und Ziel nicht gleich sind
            while ziel == start:
                ziel = random.choices(tz.ziel_etagen, weights=tz.ziel_gewichtung, k=1)[0]

            fahrgast = Fahrgast(fahrgast_id, start, ziel, max_patience=self.max_patience)
            self.fahrgast_gestartet()
            self.env.process(self.fahrgast_prozess(fahrgast))
            fahrgast_id += 1

        self.spawning_beendet()
