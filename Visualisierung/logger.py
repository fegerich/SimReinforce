import csv

# Ereignistypen die in der Schritte-CSV geloggt werden
FAHRGAST_SPAWN        = "FAHRGAST_SPAWN"
EINGESTIEGEN          = "EINGESTIEGEN"
ANGEKOMMEN            = "ANGEKOMMEN"
TREPPENHAUS           = "TREPPENHAUS"
AUFZUG_FAHREND_HOCH   = "AUFZUG_FAHREND_HOCH"
AUFZUG_FAHREND_RUNTER = "AUFZUG_FAHREND_RUNTER"
AUFZUG_WARTEND        = "AUFZUG_WARTEND"

# Spaltenstruktur der Schritte-CSV
_SPALTEN = [
    "t", "ereignis", "aufzug_id", "aufzug_etage", "aufzug_zustand",
    "aufzug_fahrgaeste", "wartend_hoch", "wartend_runter",
    "fahrgast_id", "fahrgast_etage", "fahrgast_ziel",
]


class Logger:
    """
    Zuständig für das Schreiben beider Ausgabe-CSV-Dateien der Simulation:

    1. Schritte-CSV (schritte_*.csv):
       Ereignisbasiertes Log das während der Simulation befüllt wird.
       Jedes Ereignis (Spawn, Einsteigen, Fahren, etc.) erzeugt eine Zeile mit dem
       aktuellen Zustand des Aufzugs und Fahrgasts sowie den globalen Wartendenzahlen.

    2. Fahrgäste-CSV (fahrgaeste_*.csv):
       Zusammenfassung aller Fahrgäste, einmalig nach Simulationsende geschrieben.

    Verwendung:
        logger = Logger()
        logger.init_schritte(schritt_pfad, etagen)
        ...                                          # Simulation läuft
        logger.schliessen()
        logger.schreibe_fahrgaeste(csv_pfad, abgeschlossene)
    """

    def __init__(self):
        self._etagen    = None   # Referenz auf alle Etagen für Wartendenabfrage
        self._csv_datei = None
        self._writer    = None

    # Initialisierung und Abschluss 

    def init_schritte(self, pfad, etagen):
        """Öffnet die CSV-Datei und schreibt den Header. Muss vor allen Ereignis-Methoden aufgerufen werden."""
        self._etagen    = etagen
        self._csv_datei = open(pfad, "w", newline="", encoding="utf-8")
        self._writer    = csv.DictWriter(self._csv_datei, fieldnames=_SPALTEN)
        self._writer.writeheader()

    def schreibe_fahrgaeste(self, pfad, abgeschlossene):
        """Schreibt alle abgeschlossenen Fahrgäste in eine CSV-Datei. Wird einmalig nach Simulationsende aufgerufen."""
        with open(pfad, "w", newline="", encoding="utf-8") as csv_datei:
            writer = csv.writer(csv_datei)
            writer.writerow(["Fahrgast_ID", "Spawnzeit", "Einsteigzeit", "Austeigezeit", "Wartezeit", "Startetage", "Zieletage", "Nimmt_Treppenhaus"])
            for fg in abgeschlossene:
                writer.writerow([
                    fg.id,
                    fg.spawnzeit,
                    fg.einsteigzeit if fg.einsteigzeit is not None else "",
                    fg.ankunftszeit if fg.ankunftszeit is not None else "",
                    fg.wartezeit,
                    fg.start,
                    fg.ziel,
                    fg.nimmt_treppenhaus,
                ])

    def schliessen(self):
        """Schließt die CSV-Datei. Muss am Ende der Simulation aufgerufen werden."""
        if self._csv_datei:
            self._csv_datei.close()

    # Interne Hilfsmethoden 

    def _wartend(self):
        """Zählt die aktuell wartenden Fahrgäste aller Etagen, aufgeteilt nach Richtung."""
        hoch   = sum(len(e.store_up.items)   for e in self._etagen)
        runter = sum(len(e.store_down.items) for e in self._etagen)
        return hoch, runter

    def _schreibe(self, t, ereignis, aufzug=None, fahrgast=None):
        """
        Schreibt eine Ereigniszeile in die CSV. Felder die nicht zum Ereignis gehören
        (z.B. Fahrgastdaten bei einem reinen Aufzugereignis) werden als leerer String gespeichert.
        """
        if not self._writer:
            return
        hoch, runter = self._wartend()
        self._writer.writerow({
            "t":                 t,
            "ereignis":          ereignis,
            "aufzug_id":         aufzug.aufzug_id      if aufzug   else "",
            "aufzug_etage":      aufzug.aktuelle_etage if aufzug   else "",
            "aufzug_zustand":    aufzug.zustand        if aufzug   else "",
            "aufzug_fahrgaeste": len(aufzug.im_aufzug) if aufzug   else "",
            "wartend_hoch":      hoch,
            "wartend_runter":    runter,
            "fahrgast_id":       fahrgast.id    if fahrgast else "",
            "fahrgast_etage":    fahrgast.start if fahrgast else "",
            "fahrgast_ziel":     fahrgast.ziel  if fahrgast else "",
        })

    #  Ereignis-Methoden 

    def fahrgast_spawn(self, t, fahrgast):
        """Fahrgast erscheint erstmals in einer Etage und wartet auf den Aufzug."""
        self._schreibe(t, FAHRGAST_SPAWN, fahrgast=fahrgast)

    def fahrgast_eingestiegen(self, t, aufzug, fahrgast):
        """Fahrgast wurde vom Aufzug eingeladen und fährt mit."""
        self._schreibe(t, EINGESTIEGEN, aufzug=aufzug, fahrgast=fahrgast)

    def fahrgast_angekommen(self, t, aufzug, fahrgast):
        """Fahrgast hat seine Zieletage erreicht und verlässt den Aufzug."""
        self._schreibe(t, ANGEKOMMEN, aufzug=aufzug, fahrgast=fahrgast)

    def fahrgast_treppenhaus(self, t, fahrgast):
        """Fahrgast hat die Geduld verloren und nimmt stattdessen die Treppe."""
        self._schreibe(t, TREPPENHAUS, fahrgast=fahrgast)

    def aufzug_fahrend(self, t, aufzug):
        """Aufzug bewegt sich eine Etage in seiner aktuellen Fahrtrichtung."""
        ereignis = AUFZUG_FAHREND_HOCH if aufzug.fahrtrichtung == "up" else AUFZUG_FAHREND_RUNTER
        self._schreibe(t, ereignis, aufzug=aufzug)

    def aufzug_wartend(self, t, aufzug):
        """Aufzug wechselt in den Wartezustand weil keine Fahrgäste mehr in seiner Richtung warten."""
        self._schreibe(t, AUFZUG_WARTEND, aufzug=aufzug)
