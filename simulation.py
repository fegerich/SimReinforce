import simpy
import random

# ── Konfiguration ────────────────────────────────────────────────────────────
NUM_ETAGEN  = 5
SIM_DAUER   = 200
FAHRT_ZEIT  = 5
SEED        = 42

random.seed(SEED)

# ── Zustände ─────────────────────────────────────────────────────────────────
WARTEND        = "WARTEND"
EINLADEN       = "EINLADEN"
AUSSTEIGEN     = "AUSSTEIGEN"
FAHREND_HOCH   = "FAHREND_HOCH"
FAHREND_RUNTER = "FAHREND_RUNTER"

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
def visualisiere(env, etagen, aktuelle_etage, fahrtrichtung, im_aufzug, zustand):
    zustand_symbol = {
        WARTEND:        "💤 WARTEND",
        EINLADEN:       "🚪 EINLADEN",
        AUSSTEIGEN:     "🚶 AUSSTEIGEN",
        FAHREND_HOCH:   "▲  FAHREND HOCH",
        FAHREND_RUNTER: "▼  FAHREND RUNTER",
    }
    pfeil = "▲" if fahrtrichtung == "up" else "▼"

    print()
    print(f"╔══════════════════════════════════════╗")
    print(f"║  🕐 Zeit: {env.now:>4.0f}s                       ║")
    print(f"║  {zustand_symbol[zustand]:<36}║")
    print(f"║  🚶 Im Aufzug: {len(im_aufzug)} Fahrgast{'  ' if len(im_aufzug) == 1 else 'e '}            ║")
    if im_aufzug:
        ziele = ", ".join(f"F{f.id:02d}→E{f.ziel}" for f in im_aufzug)
        print(f"║  ({ziele[:36]:<36})║")
    print(f"╠══════════════════════════════════════╣")

    for e in range(NUM_ETAGEN - 1, -1, -1):
        etage          = etagen[e]
        aufzug_hier    = (e == aktuelle_etage)
        wartend_hoch   = len(etage.store_up.items)
        wartend_runter = len(etage.store_down.items)

        aufzug_symbol = f"[{pfeil}]" if aufzug_hier else "   "
        hoch_str      = f"▲×{wartend_hoch}"   if wartend_hoch   > 0 else "   "
        runter_str    = f"▼×{wartend_runter}" if wartend_runter > 0 else "   "

        print(f"║  E{e}  {aufzug_symbol}  {hoch_str}  {runter_str}               ║")

    print(f"╚══════════════════════════════════════╝")


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────
def irgendwo_wartende(etagen):
    """Gibt True zurück wenn irgendwo in einem Store ein Fahrgast wartet."""
    return any(
        len(etagen[e].store_up.items) > 0 or len(etagen[e].store_down.items) > 0
        for e in range(NUM_ETAGEN)
    )

def ziele_in_richtung(aktuelle_etage, fahrtrichtung, im_aufzug, etagen):
    """Gibt True zurück wenn es noch Ziele in der aktuellen Fahrtrichtung gibt."""
    if fahrtrichtung == "up":
        im_aufzug_ziele = any(f.ziel > aktuelle_etage for f in im_aufzug)
        wartende        = any(len(etagen[e].store_up.items) > 0
                              for e in range(aktuelle_etage + 1, NUM_ETAGEN))
    else:
        im_aufzug_ziele = any(f.ziel < aktuelle_etage for f in im_aufzug)
        wartende        = any(len(etagen[e].store_down.items) > 0
                              for e in range(0, aktuelle_etage))
    return im_aufzug_ziele or wartende

def bestimme_richtung(aktuelle_etage, etagen):
    """
    Bestimmt die sinnvollste Fahrtrichtung wenn der Aufzug neu startet.
    Schaut wo die nächsten wartenden Fahrgäste sind.
    """
    # Nächsten wartenden Fahrgast über oder unter aktueller Etage suchen
    for delta in range(1, NUM_ETAGEN):
        oben  = aktuelle_etage + delta
        unten = aktuelle_etage - delta
        if oben < NUM_ETAGEN and len(etagen[oben].store_up.items) > 0:
            return "up"
        if unten >= 0 and len(etagen[unten].store_down.items) > 0:
            return "down"
        if oben < NUM_ETAGEN and len(etagen[oben].store_down.items) > 0:
            return "up"
        if unten >= 0 and len(etagen[unten].store_up.items) > 0:
            return "down"
    # Fallback: aktuelle Etage selbst prüfen
    if len(etagen[aktuelle_etage].store_up.items) > 0:
        return "up"
    return "down"


# ── Prozesse ─────────────────────────────────────────────────────────────────
def fahrgast_prozess(env, fahrgast, etagen, aufzug_event):
    etage      = etagen[fahrgast.start]
    spawn_zeit = env.now

    if fahrgast.ziel > fahrgast.start:
        yield etage.store_up.put(fahrgast)
    else:
        yield etage.store_down.put(fahrgast)

    # Aufzug aufwecken falls er wartet
    if not aufzug_event.triggered:
        aufzug_event.succeed()

    fahrgast.abgeholt = env.event()
    yield fahrgast.abgeholt
    fahrgast.wartezeit = env.now - spawn_zeit

    fahrgast.angekommen = env.event()
    yield fahrgast.angekommen
    fahrgast.ankunftszeit = env.now


def aufzug_prozess(env, etagen, aufzug_event_container):
    aktuelle_etage = 0
    fahrtrichtung  = "up"
    im_aufzug      = []
    zustand        = WARTEND

    while True:

        # ── WARTEND ──────────────────────────────────────────────────────────
        if not irgendwo_wartende(etagen) and not im_aufzug:
            zustand = WARTEND
            visualisiere(env, etagen, aktuelle_etage, fahrtrichtung, im_aufzug, zustand)

            # Neues Event erstellen und im Container speichern
            # damit fahrgast_prozess es aufwecken kann
            warte_event = env.event()
            aufzug_event_container[0] = warte_event
            yield warte_event  # ← blockiert bis ein Fahrgast den Knopf drückt

            # Richtung neu bestimmen basierend auf wo Fahrgäste warten
            fahrtrichtung = bestimme_richtung(aktuelle_etage, etagen)
            continue

        # ── AUSSTEIGEN ───────────────────────────────────────────────────────
        aussteiger = [f for f in im_aufzug if f.ziel == aktuelle_etage]
        if aussteiger:
            zustand = AUSSTEIGEN
            visualisiere(env, etagen, aktuelle_etage, fahrtrichtung, im_aufzug, zustand)
            for fahrgast in aussteiger:
                im_aufzug.remove(fahrgast)
                fahrgast.angekommen.succeed()

        # ── EINLADEN ─────────────────────────────────────────────────────────
        store = etagen[aktuelle_etage].store_up if fahrtrichtung == "up" \
                else etagen[aktuelle_etage].store_down
        if len(store.items) > 0:
            zustand = EINLADEN
            visualisiere(env, etagen, aktuelle_etage, fahrtrichtung, im_aufzug, zustand)
            while len(store.items) > 0:
                fahrgast = yield store.get()
                fahrgast.abgeholt.succeed()
                im_aufzug.append(fahrgast)

        # ── RICHTUNG PRÜFEN ──────────────────────────────────────────────────
        if not ziele_in_richtung(aktuelle_etage, fahrtrichtung, im_aufzug, etagen):
            # Gegenrichtung prüfen
            gegenteil = "down" if fahrtrichtung == "up" else "up"
            if ziele_in_richtung(aktuelle_etage, gegenteil, im_aufzug, etagen):
                fahrtrichtung = gegenteil
            # sonst: nächste Iteration landet in WARTEND

        # ── FAHREND ──────────────────────────────────────────────────────────
        if fahrtrichtung == "up":
            zustand = FAHREND_HOCH
        else:
            zustand = FAHREND_RUNTER

        visualisiere(env, etagen, aktuelle_etage, fahrtrichtung, im_aufzug, zustand)
        yield env.timeout(FAHRT_ZEIT)

        if fahrtrichtung == "up":
            aktuelle_etage = min(aktuelle_etage + 1, NUM_ETAGEN - 1)
        else:
            aktuelle_etage = max(aktuelle_etage - 1, 0)


def fahrgast_generator(env, etagen, aufzug_event_container):
    fahrgast_id = 0
    while True:
        yield env.timeout(random.randint(5, 20))

        start = random.randint(0, NUM_ETAGEN - 1)
        ziel  = random.randint(0, NUM_ETAGEN - 1)
        while ziel == start:
            ziel = random.randint(0, NUM_ETAGEN - 1)

        fahrgast = Fahrgast(fahrgast_id, start, ziel)
        # aufzug_event_container[0] ist immer das aktuelle Warte-Event
        env.process(fahrgast_prozess(env, fahrgast, etagen, aufzug_event_container[0]))
        fahrgast_id += 1


# ── Simulation starten ───────────────────────────────────────────────────────
def main():
    env    = simpy.Environment()
    etagen = [Etage(env, i) for i in range(NUM_ETAGEN)]

    # Container für das aktuelle Warte-Event des Aufzugs
    # (Liste mit einem Element damit fahrgast_prozess es per Referenz updaten kann)
    aufzug_event_container = [env.event()]

    env.process(aufzug_prozess(env, etagen, aufzug_event_container))
    env.process(fahrgast_generator(env, etagen, aufzug_event_container))

    env.run(until=SIM_DAUER)
    print("\n✅ Simulation beendet.")


if __name__ == "__main__":
    main()