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
SIM_DAUER     = 36_000
FAHRT_ZEIT    = 5
MAX_PATIENCE  = 60   # Sekunden bis ein Fahrgast die Treppe nimmt
SEED          = 42

random.seed(SEED)

# Spawning Konfigurationen
DEFAULT_SPAWN = (30.0, "Default", list(range(NUM_ETAGEN)), list(range(NUM_ETAGEN)))
TAGESZEITEN = [
  # (start_zeit, end_zeit, spawn_rate, beschreibung, start_etagen, ziel_etagen)
    (0,   3_600,  10.0, "Morgens",              [0],                    list(range(1, NUM_ETAGEN))),
    (14_400,  15_600, 15.0, "Anfang Mittagspause",  list(range(1, NUM_ETAGEN)), [0]),
    (16_800, 18_000, 15.0, "Ende Mittagspause",    [0],                    list(range(1, NUM_ETAGEN))),
    (32_400, 36_000, 10.0, "Feierabend",           list(range(1, NUM_ETAGEN)), [0]),
]


# Prozesse
def fahrgast_prozess(env, fahrgast, etagen, aufzuege, abgeschlossene):
    etage              = etagen[fahrgast.start]
    fahrgast.spawnzeit = env.now
    store              = etage.store_up if fahrgast.ziel > fahrgast.start else etage.store_down

    yield store.put(fahrgast)

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
        abgeschlossene.append(fahrgast)
        return

    fahrgast.einsteigzeit = env.now
    fahrgast.wartezeit    = fahrgast.einsteigzeit - fahrgast.spawnzeit

    fahrgast.angekommen = env.event()
    yield fahrgast.angekommen
    fahrgast.ankunftszeit = env.now
    abgeschlossene.append(fahrgast)


def get_tageszeit(now):
    for start, ende, rate, name, starts, ziele in TAGESZEITEN:
        if start <= now < ende:
            return rate, name, starts, ziele
    return DEFAULT_SPAWN


def fahrgast_generator(env, etagen, aufzuege, abgeschlossene):
    fahrgast_id = 0
    letzte_tageszeit = ""

    while True:
        rate, name, mögliche_starts, mögliche_ziele = get_tageszeit(env.now)

        # Tageszeit-Wechsel anzeigen
        if name != letzte_tageszeit:
            print(f"\n  ⏰ Tageszeit: {name}  (Spawn-Rate: alle ~{rate:.1f}s)")
            letzte_tageszeit = name

        # Exponentialverteilung: Zeit bis zum nächsten Fahrgast
        wartezeit = np.random.exponential(rate)
        yield env.timeout(max(1, wartezeit))  # mindestens 1s warten

        # Start und Ziel aus der aktuellen Tageszeit wählen
        start = random.choice(mögliche_starts)
        ziel  = random.choice(mögliche_ziele)
        while ziel == start:
            ziel = random.choice(mögliche_ziele)

        fahrgast = Fahrgast(fahrgast_id, start, ziel, max_patience=MAX_PATIENCE)
        env.process(fahrgast_prozess(env, fahrgast, etagen, aufzuege, abgeschlossene))
        fahrgast_id += 1


# Simulation starten
def main():
    zeitstempel = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
    os.makedirs("output", exist_ok=True)
    log_pfad    = os.path.join("output", f"simulation_{zeitstempel}.txt")

    with open(log_pfad, "w", encoding="utf-8") as log_datei:
        sys.stdout = Logger(log_datei)
        try:
            env    = simpy.Environment()
            etagen = [Etage(env, i) for i in range(NUM_ETAGEN)]

            aufzuege = [
                Aufzug(env, etagen, NUM_ETAGEN, FAHRT_ZEIT, aufzug_id=chr(ord("A") + i))
                for i in range(NUM_AUFZUEGE)
            ]
            for a in aufzuege:
                a.alle_aufzuege = aufzuege
                env.process(a.run())

            abgeschlossene = []
            env.process(fahrgast_generator(env, etagen, aufzuege, abgeschlossene))

            env.run(until=SIM_DAUER)

            csv_pfad = os.path.join("output", f"fahrgaeste_{zeitstempel}.csv")
            with open(csv_pfad, "w", newline="", encoding="utf-8") as csv_datei:
                writer = csv.writer(csv_datei)
                writer.writerow(["Fahrgast_ID", "Spawnzeit", "Einsteigzeit", "Austeigezeit", "Wartezeit", "Startetage", "Zieletage", "Nimmt_Treppenhaus"])
                for fg in abgeschlossene:
                    writer.writerow([
                        fg.id,
                        fg.spawnzeit,
                        fg.einsteigzeit  if fg.einsteigzeit  is not None else "",
                        fg.ankunftszeit  if fg.ankunftszeit  is not None else "",
                        fg.wartezeit,
                        fg.start,
                        fg.ziel,
                        fg.nimmt_treppenhaus,
                    ])

            print(f"\n✅ Simulation beendet. Log: {log_pfad} | Fahrgäste: {csv_pfad}")
        finally:
            sys.stdout = sys.stdout._konsole


if __name__ == "__main__":
    main()
