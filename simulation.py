import simpy
import random

# ── Konfiguration ────────────────────────────────────────────────────────────
NUM_ETAGEN      = 5
SIM_DAUER       = 200
FAHRT_ZEIT      = 5
SEED            = 42

random.seed(SEED)

# ── Klassen ──────────────────────────────────────────────────────────────────
class Etage:
    def __init__(self, env, nummer):
        self.nummer     = nummer
        self.store_up   = simpy.Store(env)
        self.store_down = simpy.Store(env)


class Fahrgast:
    def __init__(self, id, start, ziel):
        self.id           = id
        self.start        = start
        self.ziel         = ziel
        self.wartezeit    = None
        self.ankunftszeit = None


# ── Visualisierung ───────────────────────────────────────────────────────────
def visualisiere(env, etagen, aktuelle_etage, fahrtrichtung, im_aufzug):
    """Gibt den aktuellen Simulationszustand übersichtlich in der Konsole aus."""
    pfeil = "▲" if fahrtrichtung == "up" else "▼"

    print()
    print(f"╔══════════════════════════════════════╗")
    print(f"║  🕐 Zeit: {env.now:>4.0f}s   {pfeil} Richtung: {'HOCH  ' if fahrtrichtung == 'up' else 'RUNTER'}   ║")
    print(f"║  🚶 Im Aufzug: {len(im_aufzug)} Fahrgast{'  ' if len(im_aufzug) == 1 else 'e '}            ║")
    if im_aufzug:
        ziele = ", ".join(f"F{f.id:02d}→E{f.ziel}" for f in im_aufzug)
        # Zeilenumbruch falls zu lang
        print(f"║     ({ziele[:34]}{'…' if len(ziele) > 34 else ' ' * (34 - len(ziele))})  ║")
    print(f"╠══════════════════════════════════════╣")

    for e in range(NUM_ETAGEN - 1, -1, -1):
        etage        = etagen[e]
        aufzug_hier  = (e == aktuelle_etage)
        wartend_hoch = len(etage.store_up.items)
        wartend_runter = len(etage.store_down.items)

        # Aufzug-Symbol
        aufzug_symbol = f"[{pfeil}]" if aufzug_hier else "   "

        # Wartende Fahrgäste
        hoch_str   = f"▲×{wartend_hoch}"   if wartend_hoch   > 0 else "   "
        runter_str = f"▼×{wartend_runter}" if wartend_runter > 0 else "   "

        print(f"║  E{e}  {aufzug_symbol}  {hoch_str}  {runter_str}               ║")

    print(f"╚══════════════════════════════════════╝")


# ── Prozesse ─────────────────────────────────────────────────────────────────
def fahrgast_prozess(env, fahrgast, etagen):
    etage      = etagen[fahrgast.start]
    spawn_zeit = env.now

    if fahrgast.ziel > fahrgast.start:
        yield etage.store_up.put(fahrgast)
    else:
        yield etage.store_down.put(fahrgast)

    fahrgast.abgeholt = env.event()
    yield fahrgast.abgeholt

    fahrgast.wartezeit = env.now - spawn_zeit

    fahrgast.angekommen = env.event()
    yield fahrgast.angekommen

    fahrgast.ankunftszeit = env.now


def aufzug_prozess(env, etagen):
    aktuelle_etage = 0
    fahrtrichtung  = "up"
    im_aufzug      = []

    while True:
        etage = etagen[aktuelle_etage]

        # 1. Fahrgäste aussteigen lassen
        aussteiger = [f for f in im_aufzug if f.ziel == aktuelle_etage]
        for fahrgast in aussteiger:
            im_aufzug.remove(fahrgast)
            fahrgast.angekommen.succeed()

        # 2. Wartende Fahrgäste einladen
        store = etage.store_up if fahrtrichtung == "up" else etage.store_down
        while len(store.items) > 0:
            fahrgast = yield store.get()
            fahrgast.abgeholt.succeed()
            im_aufzug.append(fahrgast)

        # 3. Prüfen ob noch Ziele in aktueller Richtung
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
            fahrtrichtung = "down" if fahrtrichtung == "up" else "up"

        # 4. Zustand visualisieren (nach jedem Schritt einmal)
        visualisiere(env, etagen, aktuelle_etage, fahrtrichtung, im_aufzug)

        # 5. Eine Etage fahren
        yield env.timeout(FAHRT_ZEIT)

        if fahrtrichtung == "up":
            aktuelle_etage = min(aktuelle_etage + 1, NUM_ETAGEN - 1)
        else:
            aktuelle_etage = max(aktuelle_etage - 1, 0)


def fahrgast_generator(env, etagen):
    fahrgast_id = 0
    while True:
        yield env.timeout(random.randint(5, 20))

        start = random.randint(0, NUM_ETAGEN - 1)
        ziel  = random.randint(0, NUM_ETAGEN - 1)
        while ziel == start:
            ziel = random.randint(0, NUM_ETAGEN - 1)

        fahrgast = Fahrgast(fahrgast_id, start, ziel)
        env.process(fahrgast_prozess(env, fahrgast, etagen))
        fahrgast_id += 1


# ── Simulation starten ───────────────────────────────────────────────────────
def main():
    env    = simpy.Environment()
    etagen = [Etage(env, i) for i in range(NUM_ETAGEN)]

    env.process(aufzug_prozess(env, etagen))
    env.process(fahrgast_generator(env, etagen))

    env.run(until=SIM_DAUER)

    print("\n✅ Simulation beendet.")


if __name__ == "__main__":
    main()