import simpy
class Etage:
    def __init__(self, env, nummer):
        self.nummer     = nummer
        self.store_up   = simpy.Store(env)
        self.store_down = simpy.Store(env)