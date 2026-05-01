import sys
import csv

# Zustände für Simulationslog Schritte.csv
FAHRGAST_SPAWN        = "FAHRGAST_SPAWN"
EINGESTIEGEN          = "EINGESTIEGEN"
ANGEKOMMEN            = "ANGEKOMMEN"
TREPPENHAUS           = "TREPPENHAUS"
AUFZUG_FAHREND_HOCH   = "AUFZUG_FAHREND_HOCH"
AUFZUG_FAHREND_RUNTER = "AUFZUG_FAHREND_RUNTER"
AUFZUG_WARTEND        = "AUFZUG_WARTEND"

# Spalten für Simulationslog Schritte.csv
_SPALTEN = [
    "t", "ereignis", "aufzug_id", "aufzug_etage", "aufzug_zustand",
    "aufzug_fahrgaeste", "wartend_hoch", "wartend_runter",
    "fahrgast_id", "fahrgast_etage", "fahrgast_ziel",
]


class Logger:
    """Leitet print()-Ausgaben gleichzeitig an Konsole und Datei weiter
    und schreibt Simulationsschritte in eine CSV-Datei."""

    def __init__(self, datei):
        self._konsole   = sys.stdout
        self._datei     = datei
        self._etagen    = None
        self._csv_datei = None
        self._writer    = None

    # ── stdout-Weiterleitung ──────────────────────────────────────────────────

    def write(self, text):
        self._konsole.write(text)
        self._datei.write(text)

    def flush(self):
        self._konsole.flush()
        self._datei.flush()

    # ── Schrittlog-Initialisierung ────────────────────────────────────────────

    def init_schritte(self, pfad, etagen):
        self._etagen    = etagen
        self._csv_datei = open(pfad, "w", newline="", encoding="utf-8")
        self._writer    = csv.DictWriter(self._csv_datei, fieldnames=_SPALTEN)
        self._writer.writeheader()

    def schliessen(self):
        if self._csv_datei:
            self._csv_datei.close()

    # ── Interne Hilfsmethoden ─────────────────────────────────────────────────

    def _wartend(self):
        hoch   = sum(len(e.store_up.items)   for e in self._etagen)
        runter = sum(len(e.store_down.items) for e in self._etagen)
        return hoch, runter

    def _schreibe(self, t, ereignis, aufzug=None, fahrgast=None):
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

    # ── Ereignis-Methoden ─────────────────────────────────────────────────────

    def fahrgast_spawn(self, t, fahrgast):
        self._schreibe(t, FAHRGAST_SPAWN, fahrgast=fahrgast)

    def fahrgast_eingestiegen(self, t, aufzug, fahrgast):
        self._schreibe(t, EINGESTIEGEN, aufzug=aufzug, fahrgast=fahrgast)

    def fahrgast_angekommen(self, t, aufzug, fahrgast):
        self._schreibe(t, ANGEKOMMEN, aufzug=aufzug, fahrgast=fahrgast)

    def fahrgast_treppenhaus(self, t, fahrgast):
        self._schreibe(t, TREPPENHAUS, fahrgast=fahrgast)

    def aufzug_fahrend(self, t, aufzug):
        ereignis = AUFZUG_FAHREND_HOCH if aufzug.fahrtrichtung == "up" else AUFZUG_FAHREND_RUNTER
        self._schreibe(t, ereignis, aufzug=aufzug)

    def aufzug_wartend(self, t, aufzug):
        self._schreibe(t, AUFZUG_WARTEND, aufzug=aufzug)
