from dataclasses import dataclass


@dataclass
class Tageszeit:
    start:        int
    ende:         int
    spawn_rate:   float
    beschreibung: str
    start_etagen: list
    start_gewichtung:    list
    ziel_etagen:  list
    ziel_gewichtung:     list
