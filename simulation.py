import simpy
import random
from etage import Etage
from fahrgast import Fahrgast
from aufzug import Aufzug

# ── Konfiguration ────────────────────────────────────────────────────────────
NUM_ETAGEN  = 5
SIM_DAUER   = 200
FAHRT_ZEIT  = 5
SEED        = 42

random.seed(SEED)


# ── Prozesse ─────────────────────────────────────────────────────────────────
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


def fahrgast_generator(env, etagen, aufzug):
    fahrgast_id = 0
    while True:
        yield env.timeout(random.randint(5, 20))

        start = random.randint(0, NUM_ETAGEN - 1)
        ziel  = random.randint(0, NUM_ETAGEN - 1)
        while ziel == start:
            ziel = random.randint(0, NUM_ETAGEN - 1)

        fahrgast = Fahrgast(fahrgast_id, start, ziel)
        env.process(fahrgast_prozess(env, fahrgast, etagen, aufzug))
        fahrgast_id += 1


# ── Simulation starten ───────────────────────────────────────────────────────
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