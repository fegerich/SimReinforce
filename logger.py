import sys


class Logger:
    """Leitet print()-Ausgaben gleichzeitig an Konsole und Datei weiter."""
    def __init__(self, datei):
        self._konsole = sys.stdout
        self._datei   = datei

    def write(self, text):
        self._konsole.write(text)
        self._datei.write(text)

    def flush(self):
        self._konsole.flush()
        self._datei.flush()
