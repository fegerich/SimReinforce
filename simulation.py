import simpy
import numpy as np
import random
import sys
import os
from datetime import datetime
from etage import Etage
from fahrgast import Fahrgast
from aufzug import Aufzug
from logger import Logger


# Simulations Konfiguration
NUM_ETAGEN   = 10
NUM_AUFZUEGE = 3
SIM_DAUER    = 300
FAHRT_ZEIT   = 5
SEED         = 42

random.seed(SEED)

# Spawning Konfigurationen
DEFAULT_SPAWN = (30.0, "Default", list(range(NUM_ETAGEN)), list(range(NUM_ETAGEN)))
TAGESZEITEN = [
  # (start_zeit, end_zeit, spawn_rate, beschreibung, start_etagen, ziel_etagen)
    (0,   40,  10.0, "Morgens",              [0],                    list(range(1, NUM_ETAGEN))),
    (80,  120, 15.0, "Anfang Mittagspause",  list(range(1, NUM_ETAGEN)), [0]),
    (140, 180, 15.0, "Ende Mittagspause",    [0],                    list(range(1, NUM_ETAGEN))),
    (260, 300, 10.0, "Feierabend",           list(range(1, NUM_ETAGEN)), [0]),
]


# Prozesse
def fahrgast_prozess(env, fahrgast, etagen, aufzuege):
    etage      = etagen[fahrgast.start]
    spawn_zeit = env.now

    if fahrgast.ziel > fahrgast.start:
        yield etage.store_up.put(fahrgast)
    else:
        yield etage.store_down.put(fahrgast)

    for a in aufzuege:
        a.aufwecken()

    fahrgast.abgeholt = env.event()
    yield fahrgast.abgeholt
    fahrgast.wartezeit = env.now - spawn_zeit

    fahrgast.angekommen = env.event()
    yield fahrgast.angekommen
    fahrgast.ankunftszeit = env.now


def get_tageszeit(now):
    for start, ende, rate, name, starts, ziele in TAGESZEITEN:
        if start <= now < ende:
            return rate, name, starts, ziele
    return DEFAULT_SPAWN


def fahrgast_generator(env, etagen, aufzuege):
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

        fahrgast = Fahrgast(fahrgast_id, start, ziel)
        env.process(fahrgast_prozess(env, fahrgast, etagen, aufzuege))
        fahrgast_id += 1


# Simulation starten
def main():
    zeitstempel = datetime.now().strftime("%Y%m%d_%H%M%S")
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

            env.process(fahrgast_generator(env, etagen, aufzuege))

            env.run(until=SIM_DAUER)
            print(f"\n✅ Simulation beendet. Log gespeichert: {log_pfad}")
        finally:
            sys.stdout = sys.stdout._konsole


if __name__ == "__main__":
    main()
