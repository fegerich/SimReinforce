class Fahrgast:
    def __init__(self, id, start, ziel, max_patience):
        self.id                = id
        self.start             = start
        self.ziel              = ziel
        self.max_patience      = max_patience
        self.spawnzeit         = None
        self.einsteigzeit      = None
        self.wartezeit         = None
        self.ankunftszeit      = None
        self.nimmt_treppenhaus = False
        self.abgeholt          = None
        self.angekommen        = None