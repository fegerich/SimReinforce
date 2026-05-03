import simpy
import random
import os
import csv
from datetime import datetime
from etage import Etage
from aufzug import Aufzug
from logger import Logger
from office import Office
from Visualisierung.StatDrawer import StatDrawer
from Visualisierung.visualisierung_v1 import SimVisualisierung


# Simulations Konfiguration
NUM_ETAGEN     = 10
NUM_AUFZUEGE   = 3
SPAWN_ENDE     = 36_000   # Sekunde ab der keine neuen Fahrgäste mehr spawnen
FAHRT_ZEIT     = 5
MAX_KAPAZITAET = 5        # Maximale Anzahl Fahrgäste pro Aufzug
MAX_PATIENCE   = 240      # Sekunden bis ein Fahrgast die Treppe nimmt
SEED           = 17

ZEIGE_VISUALISERUNG = False
ZEIGE_STATISTIKEN   = True

# Spawning Konfigurationen
DEFAULT_SPAWN = (10.0, "Default", list(range(NUM_ETAGEN)), list(range(NUM_ETAGEN)))
TAGESZEITEN = [
  # (start_zeit, end_zeit, spawn_rate, beschreibung, start_etagen, ziel_etagen)
    (0,      3_600,  4.5, "Morgens",             [0],                        list(range(1, NUM_ETAGEN))),
    (14_400, 15_600, 6.0, "Anfang Mittagspause", list(range(1, NUM_ETAGEN)), [0, 0, 2]),
    (16_800, 18_000, 5.0, "Ende Mittagspause",   [0],                        list(range(1, NUM_ETAGEN))),
    (32_400, 36_000, 7.0, "Feierabend",          list(range(1, NUM_ETAGEN)), [0]),
]


# Simulation starten
def main():
    random.seed(SEED)

    zeitstempel = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")
    os.makedirs("output", exist_ok=True)

    env    = simpy.Environment()
    etagen = [Etage(env, i) for i in range(NUM_ETAGEN)]

    logger       = Logger()
    schritt_pfad = os.path.join("output", f"schritte_{zeitstempel}.csv")
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

    csv_pfad = os.path.join("output", f"fahrgaeste_{zeitstempel}.csv")
    with open(csv_pfad, "w", newline="", encoding="utf-8") as csv_datei:
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
        SimVisualisierung(schritt_pfad).run()
    if ZEIGE_STATISTIKEN:
        statdrawer = StatDrawer()
        statdrawer.visualisiere_aufkommen(csv_pfad, zeitstempel)
        statdrawer.visualisiere_wartezeiten(csv_pfad, zeitstempel, MAX_PATIENCE)
        statdrawer.visualisiere_etagenanalyse(csv_pfad, zeitstempel)
        statdrawer.draw_aufzug_routen(schritt_pfad, zeitstempel)
        statdrawer.draw_fahrstuhlauslastung(schritt_pfad, zeitstempel)


if __name__ == "__main__":
    main()
