class Fahrgast:
    """
    Repräsentiert einen einzelnen Fahrgast in der Simulation.

    Wird vom Buero erzeugt und durchläuft den Prozess: Spawn -> Warten -> Einsteigen -> Ankommen.
    Die SimPy-Events abgeholt und angekommen werden erst während des Prozesses gesetzt.

    id:                 Eindeutige Fahrgast-ID
    start:              Startetage 
    ziel:               Zieletage 
    max_patience:       Maximale Wartezeit in Sekunden bevor die Treppe genommen wird
    spawnzeit:          Simulationszeit beim Erscheinen
    einsteigzeit:       Simulationszeit beim Einsteigen in den Aufzug
    ankunftszeit:       Simulationszeit beim Erreichen der Zieletage
    wartezeit:          Gesamtzeit vom Spawn bis zur Ankunft (bzw. bis Treppenhaus)
    nimmt_treppenhaus:  True wenn der Fahrgast wegen Ungeduld die Treppe nimmt
    abgeholt:           SimPy-Event — wird getriggert wenn der Aufzug den Fahrgast einlädt
    angekommen:         SimPy-Event — wird getriggert wenn der Aufzug die Zieletage erreicht
    """
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
        self.abgeholt          = None  # SimPy-Event, gesetzt in fahrgast_prozess
        self.angekommen        = None  # SimPy-Event, gesetzt in _einladen