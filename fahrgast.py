class Fahrgast:
    def __init__(self, id, start, ziel):
        self.id           = id
        self.start        = start
        self.ziel         = ziel
        self.wartezeit    = None
        self.ankunftszeit = None