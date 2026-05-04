import simpy


class Etage:
    """
    Repräsentiert eine Etage im Gebäude.
    Hält zwei SimPy-Stores für wartende Fahrgäste — einen pro Fahrtrichtung.
    Der Aufzug holt Fahrgäste je nach seiner aktuellen Fahrtrichtung aus dem passenden Store.

    nummer:      Etagennummer (0 = Erdgeschoss)
    store_up:    Wartende Fahrgäste die nach oben wollen
    store_down:  Wartende Fahrgäste die nach unten wollen
    """
    def __init__(self, env, nummer):
        self.nummer     = nummer
        self.store_up   = simpy.Store(env)
        self.store_down = simpy.Store(env)