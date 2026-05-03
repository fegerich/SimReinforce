import numpy as np
import random
from fahrgast import Fahrgast


class Office:
    def __init__(self, env, etagen, aufzuege, abgeschlossene,
                 spawn_ende, max_patience, tageszeiten, default_spawn,
                 schrittlogger=None):
        self.env            = env
        self.etagen         = etagen
        self.aufzuege       = aufzuege
        self.abgeschlossene = abgeschlossene
        self.spawn_ende     = spawn_ende
        self.max_patience   = max_patience
        self.tageszeiten    = tageszeiten
        self.default_spawn  = default_spawn
        self.schrittlogger  = schrittlogger

        self._aktive        = 0
        self._spawn_fertig  = False
        self.fertig         = env.event()

    # ── SimEnde-Logik ─────────────────────────────────────────────────────────

    def fahrgast_gestartet(self):
        self._aktive += 1

    def fahrgast_abgeschlossen(self):
        self._aktive -= 1
        self._pruefen()

    def spawning_beendet(self):
        self._spawn_fertig = True
        self._pruefen()

    def _pruefen(self):
        if self._spawn_fertig and self._aktive == 0 and not self.fertig.triggered:
            self.fertig.succeed()

    # ── Tageszeit ─────────────────────────────────────────────────────────────

    def _get_tageszeit(self, now):
        for start, ende, rate, name, starts, ziele in self.tageszeiten:
            if start <= now < ende:
                return rate, name, starts, ziele
        return self.default_spawn

    # ── Prozesse ──────────────────────────────────────────────────────────────

    def fahrgast_prozess(self, fahrgast):
        etage              = self.etagen[fahrgast.start]
        fahrgast.spawnzeit = self.env.now
        store              = etage.store_up if fahrgast.ziel > fahrgast.start else etage.store_down

        yield store.put(fahrgast)
        if self.schrittlogger:
            self.schrittlogger.fahrgast_spawn(self.env.now, fahrgast)

        for a in self.aufzuege:
            a.aufwecken()

        fahrgast.abgeholt = self.env.event()
        yield fahrgast.abgeholt | self.env.timeout(fahrgast.max_patience)

        if not fahrgast.abgeholt.triggered:
            # Geduld abgelaufen → Treppenhaus
            fahrgast.nimmt_treppenhaus = True
            fahrgast.wartezeit         = self.env.now - fahrgast.spawnzeit
            if fahrgast in store.items:
                store.items.remove(fahrgast)
            if self.schrittlogger:
                self.schrittlogger.fahrgast_treppenhaus(self.env.now, fahrgast)
            self.abgeschlossene.append(fahrgast)
            self.fahrgast_abgeschlossen()
            return

        fahrgast.einsteigzeit = self.env.now
        fahrgast.wartezeit    = fahrgast.einsteigzeit - fahrgast.spawnzeit

        yield fahrgast.angekommen
        fahrgast.ankunftszeit = self.env.now
        self.abgeschlossene.append(fahrgast)
        self.fahrgast_abgeschlossen()

    def fahrgast_generator(self):
        fahrgast_id = 0

        while True:
            rate, _, mögliche_starts, mögliche_ziele = self._get_tageszeit(self.env.now)

            wartezeit = np.random.exponential(rate)
            yield self.env.timeout(max(1, wartezeit))

            if self.env.now >= self.spawn_ende:
                break

            start = random.choice(mögliche_starts)
            ziel  = random.choice(mögliche_ziele)
            while ziel == start:
                ziel = random.choice(mögliche_ziele)

            fahrgast = Fahrgast(fahrgast_id, start, ziel, max_patience=self.max_patience)
            self.fahrgast_gestartet()
            self.env.process(self.fahrgast_prozess(fahrgast))
            fahrgast_id += 1

        self.spawning_beendet()
