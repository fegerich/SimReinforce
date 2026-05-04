from dataclasses import dataclass


@dataclass
class Tageszeit:
    """
    Konfiguriert einen Zeitabschnitt des Simulationstages mit eigenen Spawn- und Verteilungsregeln.

    start / ende:            Simulationszeitpunkte in Sekunden (0 = 08:00 Uhr)
    spawn_rate:              Mittelwert der Exponentialverteilung für den Abstand zwischen zwei Spawns (in Sekunden)
    beschreibung:            Anzeigename z.B. für die Visualisierung
    start_etagen:            Liste der möglichen Startetagen
    start_gewichtung:        Relative Gewichte für start_etagen (None = Gleichverteilung)
    ziel_etagen:             Liste der möglichen Zieletagen
    ziel_gewichtung:         Relative Gewichte für ziel_etagen (None = Gleichverteilung)
    """
    start:            int
    ende:             int
    spawn_rate:       float
    beschreibung:     str
    start_etagen:     list
    start_gewichtung: list
    ziel_etagen:      list
    ziel_gewichtung:  list
