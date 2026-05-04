import simpy
import random
import os
from datetime import datetime
from Model.etage import Etage
from Model.aufzug import Aufzug
from Visualisierung.logger import Logger
from Model.buero import Office
from Model.tageszeit import Tageszeit
from Visualisierung.StatDrawer import StatDrawer
from Visualisierung.visualisierung_v2 import SimVisualisierung_v2


# Simulations Konfiguration
NUM_ETAGEN     = 10
NUM_AUFZUEGE   = 3
SPAWN_ENDE     = 36_000   # Sekunde ab der keine neuen Fahrgäste mehr spawnen
FAHRT_ZEIT     = 5
MAX_KAPAZITAET = 5        # Maximale Anzahl Fahrgäste pro Aufzug
MAX_PATIENCE   = 240      # Sekunden bis ein Fahrgast die Treppe nimmt
SEED           = 17

ZEIGE_VISUALISERUNG = True
ZEIGE_STATISTIKEN   = True

# Spawning Konfigurationen — Gewichte: Liste (z.B. [70, 30]) oder None für Gleichverteilung
DEFAULT_SPAWN = Tageszeit(
    start        = 0,
    ende         = 0,
    spawn_rate   = 10.0,
    beschreibung = "Normalbetrieb",
    start_etagen = list(range(NUM_ETAGEN)),
    start_gewichtung    = None,
    ziel_etagen  = list(range(NUM_ETAGEN)),
    ziel_gewichtung     = None,
)
TAGESZEITEN = [
    Tageszeit(
        start            = 0,
        ende             = 3_600,
        spawn_rate       = 4.5,
        beschreibung     = "Arbeitsbeginn",
        start_etagen     = [0],
        start_gewichtung = None,
        ziel_etagen      = list(range(1, NUM_ETAGEN)),
        ziel_gewichtung  = None,
    ),
    Tageszeit(
        start            = 14_400,
        ende             = 15_600,
        spawn_rate       = 6.0,
        beschreibung     = "Anfang Mittagspause",
        start_etagen     = list(range(1, NUM_ETAGEN)),
        start_gewichtung = None,
        ziel_etagen      = [0, 2],
        ziel_gewichtung  = [0.7, 0.3],
    ),
    Tageszeit(
        start            = 16_800,
        ende             = 18_000,
        spawn_rate       = 5.0,
        beschreibung     = "Ende Mittagspause",
        start_etagen     = [0, 2],
        start_gewichtung = [0.7, 0.3],
        ziel_etagen      = list(range(1, NUM_ETAGEN)),
        ziel_gewichtung  = None,
    ),
    Tageszeit(
        start            = 32_400,
        ende             = 36_000,
        spawn_rate       = 4.0,
        beschreibung     = "Feierabend",
        start_etagen     = list(range(1, NUM_ETAGEN)),
        start_gewichtung = None,
        ziel_etagen      = [0, random.randint(1, 9)],
        ziel_gewichtung  = [0.95, 0.5],
    ),
]


# Simulation starten
def main():
    random.seed(SEED)

    zeitstempel = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
    os.makedirs("Output", exist_ok=True)

    env    = simpy.Environment()
    etagen = [Etage(env, i) for i in range(NUM_ETAGEN)]

    logger       = Logger()
    schritt_pfad = os.path.join("Output", f"schritte_{zeitstempel}.csv")
    logger.init_schritte(schritt_pfad, etagen)

    aufzuege = [
        Aufzug(env, etagen, NUM_ETAGEN, FAHRT_ZEIT, aufzug_id=chr(ord("A") + i), kapazitaet=MAX_KAPAZITAET, schrittlogger=logger)
        for i in range(NUM_AUFZUEGE)
    ]
    for a in aufzuege:
        env.process(a.run())

    abgeschlossene = []
    office         = Office(env, etagen, aufzuege, abgeschlossene,
                            SPAWN_ENDE, MAX_PATIENCE, TAGESZEITEN, DEFAULT_SPAWN, logger)
    env.process(office.fahrgast_generator())

    env.run(until=office.fertig)
    logger.schliessen()

    csv_pfad = os.path.join("Output", f"fahrgaeste_{zeitstempel}.csv")
    logger.schreibe_fahrgaeste(csv_pfad, abgeschlossene)

    end_sek  = env.now
    end_uhr  = f"{8 + end_sek // 3600:02.0f}:{(end_sek % 3600) // 60:02.0f}:{end_sek % 60:02.0f}"

    total_fahrgäste    = len(abgeschlossene)
    angekommen         = sum(1 for fg in abgeschlossene if not fg.nimmt_treppenhaus)
    treppenhaus        = sum(1 for fg in abgeschlossene if fg.nimmt_treppenhaus)
    anteil_treppenhaus = round((treppenhaus / total_fahrgäste) * 100, 2) if total_fahrgäste > 0 else 0
    avg_wartezeit      = sum(fg.wartezeit for fg in abgeschlossene) / total_fahrgäste if total_fahrgäste > 0 else 0

    print()
    print("-" * 12, "Simulation gestartet um 08:00:00", "-" * 12)
    print(f"Fahrgäste gesamt:               {total_fahrgäste}")
    print(f"Erfolgreich angekommen:         {angekommen}")
    print(f"Treppenhaus genommen:           {treppenhaus}")
    print(f"Anteil Treppenhaus:             {anteil_treppenhaus}%")
    print(f"Durchschnittliche Wartezeit:    {avg_wartezeit:.1f}s")
    print("-" * 12, f"Simulation beendet um {end_uhr}", "-" * 12)

    if ZEIGE_VISUALISERUNG:
        SimVisualisierung_v2(schritt_pfad, tageszeiten=TAGESZEITEN).run()
    if ZEIGE_STATISTIKEN:
        statdrawer = StatDrawer()
        statdrawer.visualisiere_aufkommen(csv_pfad, zeitstempel)
        statdrawer.visualisiere_wartezeiten(csv_pfad, zeitstempel, MAX_PATIENCE)
        statdrawer.draw_aufzug_routen(schritt_pfad, zeitstempel)
        statdrawer.draw_fahrstuhlauslastung(schritt_pfad, zeitstempel)


if __name__ == "__main__":
    main()
