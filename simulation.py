import simpy
import numpy as np
import random
import sys
import os
import csv
from datetime import datetime
from etage import Etage
from fahrgast import Fahrgast
from aufzug import Aufzug
from logger import Logger


# Simulations Konfiguration
NUM_ETAGEN    = 10
NUM_AUFZUEGE  = 3
SPAWN_ENDE    = 36_000   # Sekunde ab der keine neuen Fahrgäste mehr spawnen
FAHRT_ZEIT    = 5
MAX_KAPAZITAET = 5       # Maximale Anzahl Fahrgäste pro Aufzug
MAX_PATIENCE  = 60       # Sekunden bis ein Fahrgast die Treppe nimmt
SEED          = 69

random.seed(SEED)

# Spawning Konfigurationen
DEFAULT_SPAWN = (30.0, "Default", list(range(NUM_ETAGEN)), list(range(NUM_ETAGEN)))
TAGESZEITEN = [
  # (start_zeit, end_zeit, spawn_rate, beschreibung, start_etagen, ziel_etagen)
    (0,      3_600,  10.0, "Morgens",             [0],                    list(range(1, NUM_ETAGEN))),
    (14_400, 15_600, 15.0, "Anfang Mittagspause", list(range(1, NUM_ETAGEN)), [0]),
    (16_800, 18_000, 15.0, "Ende Mittagspause",   [0],                    list(range(1, NUM_ETAGEN))),
    (32_400, 36_000, 10.0, "Feierabend",          list(range(1, NUM_ETAGEN)), [0]),
]


class SimEnde:
    """Feuert ein SimPy-Event sobald das Spawnen gestoppt wurde
    und alle Fahrgäste ihr Ziel erreicht oder die Treppe genommen haben."""

    def __init__(self, env):
        self._env          = env
        self._aktive       = 0
        self._spawn_fertig = False
        self.fertig        = env.event()

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


# Prozesse
def fahrgast_prozess(env, fahrgast, etagen, aufzuege, abgeschlossene, sim_ende, schrittlogger=None):
    etage              = etagen[fahrgast.start]
    fahrgast.spawnzeit = env.now
    store              = etage.store_up if fahrgast.ziel > fahrgast.start else etage.store_down

    yield store.put(fahrgast)
    if schrittlogger:
        schrittlogger.fahrgast_spawn(env.now, fahrgast)

    for a in aufzuege:
        a.aufwecken()

    fahrgast.abgeholt = env.event()
    yield fahrgast.abgeholt | env.timeout(fahrgast.max_patience)

    if not fahrgast.abgeholt.triggered:
        # Geduld abgelaufen → Treppenhaus
        fahrgast.nimmt_treppenhaus = True
        fahrgast.wartezeit         = env.now - fahrgast.spawnzeit
        if fahrgast in store.items:
            store.items.remove(fahrgast)
        if schrittlogger:
            schrittlogger.fahrgast_treppenhaus(env.now, fahrgast)
        abgeschlossene.append(fahrgast)
        sim_ende.fahrgast_abgeschlossen()
        return

    fahrgast.einsteigzeit = env.now
    fahrgast.wartezeit    = fahrgast.einsteigzeit - fahrgast.spawnzeit

    yield fahrgast.angekommen
    fahrgast.ankunftszeit = env.now
    abgeschlossene.append(fahrgast)
    sim_ende.fahrgast_abgeschlossen()


def get_tageszeit(now):
    for start, ende, rate, name, starts, ziele in TAGESZEITEN:
        if start <= now < ende:
            return rate, name, starts, ziele
    return DEFAULT_SPAWN


def fahrgast_generator(env, etagen, aufzuege, abgeschlossene, sim_ende, schrittlogger=None):
    fahrgast_id      = 0
    letzte_tageszeit = ""

    while True:
        rate, name, mögliche_starts, mögliche_ziele = get_tageszeit(env.now)

        if name != letzte_tageszeit:
            print(f"\n  ⏰ Tageszeit: {name}  (Spawn-Rate: alle ~{rate:.1f}s)")
            letzte_tageszeit = name

        wartezeit = np.random.exponential(rate)
        yield env.timeout(max(1, wartezeit))

        if env.now >= SPAWN_ENDE:
            break

        start = random.choice(mögliche_starts)
        ziel  = random.choice(mögliche_ziele)
        while ziel == start:
            ziel = random.choice(mögliche_ziele)

        fahrgast = Fahrgast(fahrgast_id, start, ziel, max_patience=MAX_PATIENCE)
        sim_ende.fahrgast_gestartet()
        env.process(fahrgast_prozess(env, fahrgast, etagen, aufzuege, abgeschlossene, sim_ende, schrittlogger))
        fahrgast_id += 1

    print(f"\n  🚫 Spawning gestoppt bei t={env.now:.0f}s — warte auf {sim_ende._aktive} verbleibende Fahrgäste ...")
    sim_ende.spawning_beendet()


# Simulation starten
def main():
    zeitstempel = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
    os.makedirs("output", exist_ok=True)
    log_pfad = os.path.join("output", f"simulation_{zeitstempel}.txt")

    with open(log_pfad, "w", encoding="utf-8") as log_datei:
        logger     = Logger(log_datei)
        sys.stdout = logger
        try:
            env    = simpy.Environment()
            etagen = [Etage(env, i) for i in range(NUM_ETAGEN)]

            schritt_pfad = os.path.join("output", f"schritte_{zeitstempel}.csv")
            logger.init_schritte(schritt_pfad, etagen)

            aufzuege = [
                Aufzug(env, etagen, NUM_ETAGEN, FAHRT_ZEIT, aufzug_id=chr(ord("A") + i), kapazitaet=MAX_KAPAZITAET, schrittlogger=logger)
                for i in range(NUM_AUFZUEGE)
            ]
            for a in aufzuege:
                a.alle_aufzuege = aufzuege
                env.process(a.run())

            abgeschlossene = []
            sim_ende       = SimEnde(env)
            env.process(fahrgast_generator(env, etagen, aufzuege, abgeschlossene, sim_ende, logger))

            env.run(until=sim_ende.fertig)
            logger.schliessen()

            csv_pfad = os.path.join("output", f"fahrgaeste_{zeitstempel}.csv")
            with open(csv_pfad, "w", newline="", encoding="utf-8") as csv_datei:
                writer = csv.writer(csv_datei)
                writer.writerow(["Fahrgast_ID", "Spawnzeit", "Einsteigzeit", "Austeigezeit", "Wartezeit", "Startetage", "Zieletage", "Nimmt_Treppenhaus"])
                for fg in abgeschlossene:
                    writer.writerow([
                        fg.id,
                        fg.spawnzeit,
                        fg.einsteigzeit if fg.einsteigzeit is not None else "",
                        fg.ankunftszeit if fg.ankunftszeit is not None else "",
                        fg.wartezeit,
                        fg.start,
                        fg.ziel,
                        fg.nimmt_treppenhaus,
                    ])

            print(f"\n✅ Simulation beendet bei t={env.now:.0f}s. Log: {log_pfad} | Fahrgäste: {csv_pfad} | Schritte: {schritt_pfad}")
        finally:
            sys.stdout = logger._konsole


if __name__ == "__main__":
    main()
