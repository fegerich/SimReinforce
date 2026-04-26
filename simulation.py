import simpy
import random

# ── Konfiguration ────────────────────────────────────────────────────────────
NUM_ETAGEN      = 5
NUM_FAHRGAESTE  = 10
SIM_DAUER       = 200   # Simulationszeit in Sekunden
FAHRT_ZEIT      = 5     # Sekunden pro Etage
SEED            = 42    # Reproduzierbare Zufallszahlen

random.seed(SEED)

# ── Klassen ──────────────────────────────────────────────────────────────────
class Etage:
    def __init__(self, env, nummer):
        self.nummer     = nummer
        self.store_up   = simpy.Store(env)  # Fahrgäste die hoch wollen
        self.store_down = simpy.Store(env)  # Fahrgäste die runter wollen


class Fahrgast:
    def __init__(self, id, start, ziel):
        self.id           = id
        self.start        = start
        self.ziel         = ziel
        self.wartezeit    = None  # wird gesetzt wenn Aufzug kommt
        self.ankunftszeit = None  # wird gesetzt wenn Ziel erreicht


# ── Prozesse ─────────────────────────────────────────────────────────────────
def fahrgast_prozess(env, fahrgast, etagen):
    """Fahrgast spawnt, stellt sich in Store, wartet auf Abholung."""
    etage = etagen[fahrgast.start]
    spawn_zeit = env.now

    if fahrgast.ziel > fahrgast.start:
        print(f"[{env.now:4.0f}s] 🧍 Fahrgast {fahrgast.id:02d} wartet auf Etage "
              f"{fahrgast.start} → will HOCH zu Etage {fahrgast.ziel}")
        yield etage.store_up.put(fahrgast)
    else:
        print(f"[{env.now:4.0f}s] 🧍 Fahrgast {fahrgast.id:02d} wartet auf Etage "
              f"{fahrgast.start} → will RUNTER zu Etage {fahrgast.ziel}")
        yield etage.store_down.put(fahrgast)

    # Hier wird der Prozess von SimPy pausiert bis der Aufzug
    # den Fahrgast über fahrgast.abgeholt.succeed() aufweckt
    fahrgast.abgeholt = env.event()
    yield fahrgast.abgeholt

    fahrgast.wartezeit = env.now - spawn_zeit
    print(f"[{env.now:4.0f}s] 🚪 Fahrgast {fahrgast.id:02d} eingestiegen "
          f"(Wartezeit: {fahrgast.wartezeit}s)")

    # Warten bis Zieletage erreicht (Aufzug signalisiert Ankunft)
    fahrgast.angekommen = env.event()
    yield fahrgast.angekommen

    fahrgast.ankunftszeit = env.now
    print(f"[{env.now:4.0f}s] ✅ Fahrgast {fahrgast.id:02d} ausgestiegen auf Etage "
          f"{fahrgast.ziel} (Gesamtzeit: {env.now - spawn_zeit}s)")


def aufzug_prozess(env, etagen):
    """SCAN-Algorithmus: fährt in einer Richtung bis keine Ziele mehr da sind."""
    aktuelle_etage = 0
    fahrtrichtung  = "up"
    # Fahrgäste die aktuell im Aufzug sitzen
    im_aufzug: list[Fahrgast] = []

    while True:
        etage = etagen[aktuelle_etage]

        # 1. Fahrgäste aussteigen lassen die hier raus wollen
        aussteiger = [f for f in im_aufzug if f.ziel == aktuelle_etage]
        for fahrgast in aussteiger:
            im_aufzug.remove(fahrgast)
            fahrgast.angekommen.succeed()  # Fahrgast-Prozess aufwecken

        # 2. Wartende Fahrgäste einladen (nur passende Richtung)
        store = etage.store_up if fahrtrichtung == "up" else etage.store_down
        while len(store.items) > 0:
            fahrgast = yield store.get()
            fahrgast.abgeholt.succeed()    # Fahrgast-Prozess aufwecken
            im_aufzug.append(fahrgast)
            print(f"[{env.now:4.0f}s] 🛗  Aufzug lädt Fahrgast {fahrgast.id:02d} ein "
                  f"auf Etage {aktuelle_etage} (im Aufzug: {len(im_aufzug)})")

        # 3. Prüfen ob noch Ziele in aktueller Fahrtrichtung vorhanden
        ziele_in_richtung = any(
            (fahrtrichtung == "up"   and f.ziel > aktuelle_etage) or
            (fahrtrichtung == "down" and f.ziel < aktuelle_etage)
            for f in im_aufzug
        )
        wartende_in_richtung = any(
            len(etagen[e].store_up.items) > 0
            for e in range(aktuelle_etage + 1, NUM_ETAGEN)
        ) if fahrtrichtung == "up" else any(
            len(etagen[e].store_down.items) > 0
            for e in range(0, aktuelle_etage)
        )

        if not ziele_in_richtung and not wartende_in_richtung:
            # Richtung umkehren
            fahrtrichtung = "down" if fahrtrichtung == "up" else "up"
            print(f"[{env.now:4.0f}s] 🔄 Aufzug kehrt Richtung um → {fahrtrichtung.upper()} "
                  f"auf Etage {aktuelle_etage}")

        # 4. Eine Etage in Fahrtrichtung fahren
        yield env.timeout(FAHRT_ZEIT)
        if fahrtrichtung == "up":
            aktuelle_etage = min(aktuelle_etage + 1, NUM_ETAGEN - 1)
        else:
            aktuelle_etage = max(aktuelle_etage - 1, 0)


def fahrgast_generator(env, etagen):
    """Erzeugt regelmäßig neue Fahrgäste mit zufälligen Start- und Zieletagen."""
    fahrgast_id = 0
    while True:
        # Zufällige Wartezeit zwischen Spawns (5–20 Sekunden)
        yield env.timeout(random.randint(5, 20))

        start = random.randint(0, NUM_ETAGEN - 1)
        ziel  = random.randint(0, NUM_ETAGEN - 1)
        # Sicherstellen dass Start != Ziel
        while ziel == start:
            ziel = random.randint(0, NUM_ETAGEN - 1)

        fahrgast = Fahrgast(fahrgast_id, start, ziel)
        env.process(fahrgast_prozess(env, fahrgast, etagen))
        fahrgast_id += 1


# ── Simulation starten ───────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("   Fahrstuhlsimulation — SCAN-Algorithmus mit SimPy")
    print("=" * 55)

    env    = simpy.Environment()
    etagen = [Etage(env, i) for i in range(NUM_ETAGEN)]

    # Prozesse registrieren
    env.process(aufzug_prozess(env, etagen))
    env.process(fahrgast_generator(env, etagen))

    # Simulation laufen lassen
    env.run(until=SIM_DAUER)

    print("=" * 55)
    print(f"   Simulation beendet nach {SIM_DAUER}s")
    print("=" * 55)


if __name__ == "__main__":
    main()