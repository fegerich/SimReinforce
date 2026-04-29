import simpy
import numpy as np
import random
from etage import Etage
from fahrgast import Fahrgast
from aufzug import Aufzug

# Simulations Konfiguration
NUM_ETAGEN  = 5
SIM_DAUER   = 300
FAHRT_ZEIT  = 5
SEED        = 42

random.seed(SEED)

# Spwaning Konfigurationen
DEFAULT_SPAWN = (30.0, "Default", list(range(NUM_ETAGEN)), list(range(NUM_ETAGEN)))
TAGESZEITEN = [
  # (start_zeit, end_zeit, spawn_rate, beschreibung, start_etagen, ziel_etagen)
    (0,   40,  10.0, "Morgens",        [0],                    list(range(1, NUM_ETAGEN))),
    (80,  120,  15.0, "Anfang Mittagspause",   list(range(1, NUM_ETAGEN)), [0]),
    (140,  180, 15.0, "Ende Mittagspause", [0],                    list(range(1, NUM_ETAGEN))),
    (260, 300, 10.0, "Feierabend",         list(range(1, NUM_ETAGEN)), [0]),
]




# Prozesse 
def fahrgast_prozess(env, fahrgast, etagen, aufzug):
    etage      = etagen[fahrgast.start]
    spawn_zeit = env.now

    if fahrgast.ziel > fahrgast.start:
        yield etage.store_up.put(fahrgast)
    else:
        yield etage.store_down.put(fahrgast)

    aufzug.aufwecken()

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


def fahrgast_generator(env, etagen, aufzug):
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
        env.process(fahrgast_prozess(env, fahrgast, etagen, aufzug))
        fahrgast_id += 1

# Simulation starten 
def main():
    env    = simpy.Environment()
    etagen = [Etage(env, i) for i in range(NUM_ETAGEN)]

    aufzug = Aufzug(env, etagen, NUM_ETAGEN, FAHRT_ZEIT)
    env.process(aufzug.run())
    env.process(fahrgast_generator(env, etagen, aufzug))

    env.run(until=SIM_DAUER)
    print("\n✅ Simulation beendet.")


if __name__ == "__main__":
    main()