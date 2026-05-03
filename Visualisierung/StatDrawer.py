import csv
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from collections import Counter
import numpy as np
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D

# 0 Sekunden Simulationszeit entspricht dieser Uhrzeit
SIM_START_STUNDE  = 8   # 08:00 Uhr
SIM_START_MINUTE  = 0

class StatDrawer:
    def __init__(self):
        pass

    def sekunden_zu_uhrzeit(self, sekunden: float):
        """Rechnet Simulationssekunden in eine Uhrzeit um (0s = 08:00 Uhr)."""
        gesamt_minuten = int(SIM_START_STUNDE * 60 + SIM_START_MINUTE + sekunden / 60)
        stunde  = (gesamt_minuten // 60) % 24
        minute  = gesamt_minuten % 60
        return f"{stunde:02d}:{minute:02d}"
    

    def visualisiere_aufkommen(self, csv_pfad: str, zeitstempel: str, intervall_sekunden: int = 300):
        """
        Liest eine Fahrgast-Log-CSV und visualisiert das durchschnittliche
        Fahrgastaufkommen über die Simulationszeit mit Uhrzeiten auf der X-Achse.

        Parameter:
            csv_pfad           : Pfad zur CSV-Datei
            intervall_sekunden : Breite der Zeitfenster in Sekunden (Standard: 300s = 5 min)
        """

        # ── Daten laden ───────────────────────────────────────────────────────────
        with open(csv_pfad, newline="") as f:
            rows = list(csv.DictReader(f))

        spawns      = np.array([float(r["Spawnzeit"]) for r in rows])
        treppenhaus = np.array([r["Nimmt_Treppenhaus"] == "True" for r in rows])

        sim_start = spawns.min()
        sim_end   = spawns.max()

        # ── Zeitfenster aufteilen ─────────────────────────────────────────────────
        bins      = np.arange(sim_start, sim_end + intervall_sekunden, intervall_sekunden)
        bin_mitte = (bins[:-1] + bins[1:]) / 2  # Mittelpunkt jedes Fensters in Sekunden

        # Fahrgäste pro Zeitfenster zählen
        gesamt_counts,      _ = np.histogram(spawns,               bins=bins)
        treppenhaus_counts, _ = np.histogram(spawns[treppenhaus],  bins=bins)
        aufzug_counts         = gesamt_counts - treppenhaus_counts

        # ── X-Achse: Uhrzeiten berechnen ─────────────────────────────────────────
        # Wir verwenden die Sekunden als numerische X-Werte intern,
        # zeigen aber Uhrzeiten als Beschriftung an
        tick_abstand = 3600  # alle 60 Minuten ein Tick
        tick_positionen = np.arange(
            (int(sim_start / tick_abstand)) * tick_abstand,
            sim_end + tick_abstand,
            tick_abstand
        )
        tick_beschriftungen = [self.sekunden_zu_uhrzeit(s) for s in tick_positionen]

        # Balkenbreite in Sekunden
        breite = (bins[1] - bins[0]) * 0.85

        # ── Plot ──────────────────────────────────────────────────────────────────
        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                gridspec_kw={"height_ratios": [3, 1]})
        fig.suptitle("Fahrgastaufkommen über die Simulationszeit",
                    fontsize=15, fontweight="bold", y=0.98)

        # ── Oberes Diagramm: Aufkommen gestapelt ─────────────────────────────────
        ax1 = axes[0]
        ax1.bar(bin_mitte, aufzug_counts,
                width=breite, label="Aufzug genutzt",
                color="#4A90D9", alpha=0.85, zorder=3)
        ax1.bar(bin_mitte, treppenhaus_counts,
                width=breite, bottom=aufzug_counts,
                label="Treppenhaus genommen",
                color="#E05C5C", alpha=0.85, zorder=3)

        # Gleitender Durchschnitt (3 Fenster)
        if len(gesamt_counts) >= 3:
            gleitend = np.convolve(gesamt_counts, np.ones(3) / 3, mode="same")
            ax1.plot(bin_mitte, gleitend,
                    color="#F5A623", linewidth=2.5,
                    linestyle="--", label="Gleitender Ø (3 Fenster)", zorder=4)

        ax1.set_ylabel(f"Fahrgäste pro {intervall_sekunden // 60} min", fontsize=11)
        ax1.legend(loc="upper right", fontsize=10)
        ax1.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
        ax1.set_ylim(bottom=0)
        ax1.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

        # Maximalwert markieren
        max_idx = np.argmax(gesamt_counts)
        ax1.annotate(f"  Max: {gesamt_counts[max_idx]}",
                    xy=(bin_mitte[max_idx], gesamt_counts[max_idx]),
                    fontsize=9, color="#333333",
                    xytext=(bin_mitte[max_idx] + tick_abstand * 0.1,
                            gesamt_counts[max_idx] + 0.3))

        # ── Unteres Diagramm: Treppenhaus-Anteil in % ────────────────────────────
        ax2 = axes[1]
        anteil = np.where(gesamt_counts > 0,
                        treppenhaus_counts / gesamt_counts * 100, 0)
        ax2.bar(bin_mitte, anteil,
                width=breite, color="#E05C5C", alpha=0.75, zorder=3)
        ax2.axhline(anteil[anteil > 0].mean() if anteil[anteil > 0].size > 0 else 0,
                    color="#333", linewidth=1.2, linestyle=":",
                    label=f"Ø {anteil[anteil>0].mean():.1f}%")
        ax2.set_ylabel("Treppenhaus %", fontsize=10)
        ax2.set_xlabel("Uhrzeit", fontsize=11)
        ax2.set_ylim(0, 100)
        ax2.legend(fontsize=9)
        ax2.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)

        # ── X-Achsen-Ticks auf Uhrzeiten setzen ──────────────────────────────────
        # Limits explizit setzen damit Ticks nicht von sharex überschrieben werden
        x_min = bins[0]  - breite
        x_max = bins[-1] + breite

        # Nur Ticks die im sichtbaren Bereich liegen
        ticks_im_bereich = [(p, l) for p, l in zip(tick_positionen, tick_beschriftungen)
                            if x_min <= p <= x_max]
        ticks_pos = [t[0] for t in ticks_im_bereich]
        ticks_lab = [t[1] for t in ticks_im_bereich]

        for ax in [ax1, ax2]:
            ax.set_xlim(x_min, x_max)
            ax.set_xticks(ticks_pos)

        ax1.set_xticklabels([])                     # oben keine Beschriftung
        ax2.set_xticklabels(ticks_lab, fontsize=9)  # unten Uhrzeiten

        # ── Zusammenfassung als Text ──────────────────────────────────────────────
        gesamt      = len(spawns)
        treppe_n    = int(treppenhaus.sum())
        treppe_pct  = treppe_n / gesamt * 100
        durchschnitt = gesamt_counts.mean()

        zusammenfassung = (
            f"Gesamt: {gesamt} Fahrgäste  |  "
            f"Ø {durchschnitt:.1f} pro {intervall_sekunden//60} min  |  "
            f"Treppenhaus: {treppe_n} ({treppe_pct:.1f}%)"
        )
        fig.text(0.5, 0.01, zusammenfassung,
                ha="center", fontsize=10, color="#555555")

        plt.tight_layout(rect=[0, 0.04, 1, 0.97])
        plt.savefig(f"Visualisierung/Abbildungen/aufkommen_{zeitstempel}.png", dpi=150, bbox_inches="tight")
        plt.show()


    def visualisiere_wartezeiten(self, csv_pfad: str, zeitstempel: str, max_wartezeit, intervall_sekunden: int = 300):
        """
        Visualisiert die durchschnittliche Wartezeit der Fahrgäste in drei Ansichten:
        1. Durchschnittliche Wartezeit über die Tageszeit
        2. Verteilung der Wartezeiten als Histogramm
        3. Durchschnittliche Wartezeit pro Startetage
        """

        # ── Daten laden ───────────────────────────────────────────────────────────
        with open(csv_pfad, newline="") as f:
            rows = list(csv.DictReader(f))

        # Treppenhaus-Fahrgäste separat behandeln (haben keine Einsteigzeit)
        aufzug_rows     = [r for r in rows if r["Nimmt_Treppenhaus"] == "False"]
        treppenhaus_rows = [r for r in rows if r["Nimmt_Treppenhaus"] == "True"]

        spawns_aufzug   = np.array([float(r["Spawnzeit"])  for r in aufzug_rows])
        wartezeit_aufzug = np.array([float(r["Wartezeit"]) for r in aufzug_rows])
        startetagen      = np.array([int(r["Startetage"])  for r in aufzug_rows])

        spawns_treppe    = np.array([float(r["Spawnzeit"])  for r in treppenhaus_rows])
        wartezeit_treppe = np.array([float(r["Wartezeit"])  for r in treppenhaus_rows])

        sim_start = min(spawns_aufzug.min(), spawns_treppe.min())
        sim_end   = max(spawns_aufzug.max(), spawns_treppe.max())

        # ── Zeitfenster für Tageszeit-Ansicht ────────────────────────────────────
        bins      = np.arange(sim_start, sim_end + intervall_sekunden, intervall_sekunden)
        bin_mitte = (bins[:-1] + bins[1:]) / 2

        # Durchschnittliche Wartezeit pro Zeitfenster (Aufzug-Fahrgäste)
        avg_wartezeit = np.zeros(len(bin_mitte))
        for i in range(len(bins) - 1):
            maske = (spawns_aufzug >= bins[i]) & (spawns_aufzug < bins[i + 1])
            if maske.sum() > 0:
                avg_wartezeit[i] = wartezeit_aufzug[maske].mean()

        # ── X-Achse Uhrzeiten ─────────────────────────────────────────────────────
        tick_abstand    = 3600
        tick_positionen = np.arange(
            (int(sim_start / tick_abstand)) * tick_abstand,
            sim_end + tick_abstand,
            tick_abstand
        )
        tick_beschriftungen = [self.sekunden_zu_uhrzeit(s) for s in tick_positionen]
        x_min = bins[0]  - (bins[1] - bins[0]) * 0.85
        x_max = bins[-1] + (bins[1] - bins[0]) * 0.85
        ticks_im_bereich = [(p, l) for p, l in zip(tick_positionen, tick_beschriftungen)
                            if x_min <= p <= x_max]
        ticks_pos = [t[0] for t in ticks_im_bereich]
        ticks_lab = [t[1] for t in ticks_im_bereich]

        # ── Plot aufbauen ─────────────────────────────────────────────────────────
        fig = plt.figure(figsize=(16, 10))
        fig.suptitle("Wartezeiten der Fahrgäste", fontsize=15, fontweight="bold", y=0.98)

        gs = fig.add_gridspec(2, 2, hspace=0.4, wspace=0.35)
        ax_zeit  = fig.add_subplot(gs[0, :])   # oben: volle Breite
        ax_hist  = fig.add_subplot(gs[1, 0])   # unten links
        ax_etage = fig.add_subplot(gs[1, 1])   # unten rechts

        # ── 1. Wartezeit über Tageszeit ───────────────────────────────────────────
        breite = (bins[1] - bins[0]) * 0.85
        ax_zeit.bar(bin_mitte, avg_wartezeit,
                    width=breite, color="#4A90D9", alpha=0.75,
                    label="Ø Wartezeit (Aufzug)", zorder=3)

        # Gleitender Durchschnitt
        if len(avg_wartezeit) >= 5:
            gleitend = np.convolve(avg_wartezeit, np.ones(5) / 5, mode="same")
            ax_zeit.plot(bin_mitte, gleitend,
                        color="#F5A623", linewidth=2.5,
                        linestyle="--", label="Gleitender Ø (5 min. Fenster)", zorder=4)

        # Gesamtdurchschnitt als Linie
        gesamt_avg = wartezeit_aufzug.mean()
        ax_zeit.axhline(gesamt_avg, color="#E05C5C", linewidth=1.5,
                        linestyle=":", label=f"Gesamtdurchschnitt: {gesamt_avg:.1f}s", zorder=4)

        ax_zeit.set_ylabel("Ø Wartezeit (Sekunden)", fontsize=11)
        ax_zeit.set_xlabel("Uhrzeit", fontsize=11)
        ax_zeit.set_xlim(x_min, x_max)
        ax_zeit.set_xticks(ticks_pos)
        ax_zeit.set_xticklabels(ticks_lab, fontsize=9)
        ax_zeit.set_ylim(bottom=0)
        ax_zeit.legend(fontsize=10)
        ax_zeit.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
        ax_zeit.set_title("Durchschnittliche Wartezeit über die Tageszeit", fontsize=12)

        # ── 2. Histogramm der Wartezeiten ─────────────────────────────────────────
        hist_bins = np.arange(0, max_wartezeit + 5, 5)  # 0 – MAX_Wartezeit  in 5s-Schritten
        ax_hist.hist(wartezeit_aufzug, bins=hist_bins,
                    color="#4A90D9", alpha=0.85, edgecolor="white", zorder=3,
                    label="Aufzug genutzt")
        ax_hist.hist(wartezeit_treppe, bins=hist_bins,
                    color="#E05C5C", alpha=0.75, edgecolor="white", zorder=3,
                    label=f"Treppenhaus ({max_wartezeit}s)")

        ax_hist.axvline(gesamt_avg, color="#F5A623", linewidth=2,
                        linestyle="--", label=f"Ø {gesamt_avg:.1f}s")
        ax_hist.set_xlabel("Wartezeit (Sekunden)", fontsize=11)
        ax_hist.set_ylabel("Anzahl Fahrgäste", fontsize=11)
        ax_hist.set_title("Verteilung der Wartezeiten", fontsize=12)
        ax_hist.legend(fontsize=9)
        ax_hist.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)

        # Prozentangaben über den Balken
        n_sofort = (wartezeit_aufzug == 0).sum()
        ax_hist.annotate(f"{n_sofort/len(aufzug_rows)*100:.0f}% sofort\neingestiegen",
                        xy=(0, n_sofort), xytext=(8, n_sofort * 0.85),
                        fontsize=8, color="#333",
                        arrowprops=dict(arrowstyle="->", color="#999", lw=1))

        # ── 3. Wartezeit pro Startetage ───────────────────────────────────────────
        etagen_nummern = sorted(set(startetagen))
        avg_pro_etage  = [wartezeit_aufzug[startetagen == e].mean() for e in etagen_nummern]
        std_pro_etage  = [wartezeit_aufzug[startetagen == e].std()  for e in etagen_nummern]

        farben = plt.cm.RdYlGn_r(
            np.linspace(0.1, 0.9, len(etagen_nummern))
        )
        bars = ax_etage.bar(etagen_nummern, avg_pro_etage,
                            color=farben, alpha=0.85, zorder=3,
                            yerr=std_pro_etage, capsize=4,
                            error_kw={"elinewidth": 1.2, "ecolor": "#555"})

        # Wert über jedem Balken
        for bar, avg in zip(bars, avg_pro_etage):
            ax_etage.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                        f"{avg:.1f}s", ha="center", va="bottom", fontsize=8)

        ax_etage.set_xlabel("Startetage", fontsize=11)
        ax_etage.set_ylabel("Ø Wartezeit (Sekunden)", fontsize=11)
        ax_etage.set_title("Ø Wartezeit pro Startetage\n(Fehlerbalken = Standardabweichung)",
                            fontsize=12)
        ax_etage.set_xticks(etagen_nummern)
        ax_etage.set_xticklabels([f"E{e}" for e in etagen_nummern])
        ax_etage.set_ylim(bottom=0)
        ax_etage.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)

        # ── Zusammenfassung ───────────────────────────────────────────────────────
        zusammenfassung = (
            f"Aufzug: {len(aufzug_rows)} Fahrgäste  |  "
            f"Ø Wartezeit: {gesamt_avg:.1f}s  |  "
            f"Min: {wartezeit_aufzug.min():.0f}s  |  "
            f"Max: {wartezeit_aufzug.max():.0f}s  |  "
            f"Treppenhaus: {len(treppenhaus_rows)} Fahrgäste (immer {max_wartezeit}s)"
        )
        fig.text(0.5, 0.01, zusammenfassung,
                ha="center", fontsize=10, color="#555555")

        plt.savefig(f"Visualisierung/Abbildungen/Wartezeiten_{zeitstempel}.png", dpi=150, bbox_inches="tight")
        plt.show()

    def visualisiere_etagenanalyse(self, csv_pfad: str, zeitstempel: str):
        """
        Visualisiert drei Diagramme zur Etagennutzung:
        1. Häufigste Startetagen
        2. Häufigste Zieletagen
        3. Durchschnittliche Wartezeit pro Startetage (± Standardabweichung)
        """

        # ── Daten laden ───────────────────────────────────────────────────────────
        with open(csv_pfad, newline="") as f:
            rows = list(csv.DictReader(f))

        aufzug_rows = [r for r in rows if r["Nimmt_Treppenhaus"] == "False"]

        startetagen  = np.array([int(r["Startetage"])   for r in aufzug_rows])
        zieletagen   = np.array([int(r["Zieletage"])    for r in aufzug_rows])
        wartezeiten  = np.array([float(r["Wartezeit"])  for r in aufzug_rows])
        alle_etagen  = sorted(set(startetagen) | set(zieletagen))
        num_etagen   = len(alle_etagen)

        # ── Berechnungen ──────────────────────────────────────────────────────────
        start_counts = Counter(startetagen)
        ziel_counts  = Counter(zieletagen)
        routen       = Counter(zip(startetagen.tolist(), zieletagen.tolist()))
        top_routen   = routen.most_common(10)

        avg_wartezeit_pro_etage = {e: wartezeiten[startetagen == e].mean() for e in alle_etagen}
        std_wartezeit_pro_etage = {e: wartezeiten[startetagen == e].std()  for e in alle_etagen}

        heatmap = np.zeros((num_etagen, num_etagen))
        for (s, z), count in routen.items():
            heatmap[s][z] = count

        # ── Plot ──────────────────────────────────────────────────────────────────
        fig = plt.figure(figsize=(18, 6))
        fig.suptitle("Etagenanalyse der Fahrstuhlsimulation",
                     fontsize=16, fontweight="bold", y=1.02)

        gs = fig.add_gridspec(1, 3, wspace=0.4)
        ax_start = fig.add_subplot(gs[0, 0])
        ax_ziel  = fig.add_subplot(gs[0, 1])
        ax_warte = fig.add_subplot(gs[0, 2])

        etagen_labels = [f"E{e}" for e in alle_etagen]
        farben_blau   = plt.cm.Blues(np.linspace(0.4, 0.9, num_etagen))
        farben_gruen  = plt.cm.Greens(np.linspace(0.4, 0.9, num_etagen))

        # ── 1. Häufigste Startetagen ──────────────────────────────────────────────
        start_werte = [start_counts.get(e, 0) for e in alle_etagen]
        bars = ax_start.barh(etagen_labels, start_werte,
                             color=farben_blau, alpha=0.85, zorder=3)
        for bar, val in zip(bars, start_werte):
            ax_start.text(val + 0.5, bar.get_y() + bar.get_height() / 2,
                          str(val), va="center", fontsize=8)
        ax_start.set_xlabel("Anzahl Fahrgäste", fontsize=10)
        ax_start.set_title("Häufigste Startetagen", fontsize=12, fontweight="bold")
        ax_start.grid(axis="x", linestyle="--", alpha=0.4, zorder=0)
        ax_start.set_xlim(right=max(start_werte) * 1.15)

        # ── 2. Häufigste Zieletagen ───────────────────────────────────────────────
        ziel_werte = [ziel_counts.get(e, 0) for e in alle_etagen]
        bars = ax_ziel.barh(etagen_labels, ziel_werte,
                            color=farben_gruen, alpha=0.85, zorder=3)
        for bar, val in zip(bars, ziel_werte):
            ax_ziel.text(val + 0.5, bar.get_y() + bar.get_height() / 2,
                         str(val), va="center", fontsize=8)
        ax_ziel.set_xlabel("Anzahl Fahrgäste", fontsize=10)
        ax_ziel.set_title("Häufigste Zieletagen", fontsize=12, fontweight="bold")
        ax_ziel.grid(axis="x", linestyle="--", alpha=0.4, zorder=0)
        ax_ziel.set_xlim(right=max(ziel_werte) * 1.15)

        # ── 3. Durchschnittliche Wartezeit pro Startetage ─────────────────────────
        avg_werte = [avg_wartezeit_pro_etage[e] for e in alle_etagen]
        std_werte = [std_wartezeit_pro_etage[e] for e in alle_etagen]

        norm         = mcolors.Normalize(vmin=min(avg_werte), vmax=max(avg_werte))
        farben_warte = plt.cm.RdYlGn_r(norm(avg_werte))

        bars = ax_warte.barh(etagen_labels, avg_werte,
                             color=farben_warte, alpha=0.85, zorder=3,
                             xerr=std_werte, capsize=4,
                             error_kw={"elinewidth": 1.2, "ecolor": "#555"})
        for bar, val in zip(bars, avg_werte):
            ax_warte.text(val + 0.3, bar.get_y() + bar.get_height() / 2,
                          f"{val:.1f}s", va="center", fontsize=8)

        gesamt_avg = wartezeiten.mean()
        ax_warte.axvline(gesamt_avg, color="#333", linewidth=1.5,
                         linestyle=":", label=f"Gesamt-Ø: {gesamt_avg:.1f}s")
        ax_warte.set_xlabel("Ø Wartezeit (Sekunden)", fontsize=10)
        ax_warte.set_title("Ø Wartezeit pro Startetage\n(± Standardabweichung)",
                           fontsize=12, fontweight="bold")
        ax_warte.legend(fontsize=8)
        ax_warte.grid(axis="x", linestyle="--", alpha=0.4, zorder=0)
        ax_warte.set_xlim(right=max(avg_werte) + max(std_werte) + 3)

        # ── Zusammenfassung ───────────────────────────────────────────────────────
        top_start  = max(start_counts, key=start_counts.get)
        top_ziel   = max(ziel_counts,  key=ziel_counts.get)
        top_route  = top_routen[0]
        zusammenfassung = (
            f"Beliebteste Startetage: E{top_start} ({start_counts[top_start]}×)  |  "
            f"Beliebteste Zieletage: E{top_ziel} ({ziel_counts[top_ziel]}×)  |  "
            f"Häufigste Route: E{top_route[0][0]}→E{top_route[0][1]} ({top_route[1]}×)"
        )
        fig.text(0.5, 0.005, zusammenfassung,
                 ha="center", fontsize=10, color="#555")

        plt.savefig(f"Visualisierung/Abbildungen/Etagenanalyse_{zeitstempel}.png", dpi=150, bbox_inches="tight")
        plt.show()


    def draw_aufzug_routen(self, csv_pfad, zeitstempel):
        # Farben und Symbole pro Aufzug
        AUFZUG_FARBEN = {"A": "#4A90D9", "B": "#E05C5C", "C": "#2ECC71"}
        
        with open(csv_pfad, newline="") as f:
            rows = list(csv.DictReader(f))
        
        # Nur Aufzug-Zeilen mit Etageninfo
        aufzug_rows = [r for r in rows if r["aufzug_id"] and r["aufzug_etage"]]
        
        # Pro Aufzug: Zeit, Etage, Zustand
        aufzuege = {}
        for aid in ["A", "B", "C"]:
            gefiltert = [r for r in aufzug_rows if r["aufzug_id"] == aid]
            aufzuege[aid] = {
                "t":       np.array([float(r["t"])              for r in gefiltert]),
                "etage":   np.array([int(r["aufzug_etage"])     for r in gefiltert]),
                "zustand": [r["aufzug_zustand"]                 for r in gefiltert],
                "fahrgaeste": np.array([int(r["aufzug_fahrgaeste"]) for r in gefiltert]),
            }
        
        sim_end = max(d["t"].max() for d in aufzuege.values())
        
        # ── X-Achsen Ticks ────────────────────────────────────────────────────────────
        tick_pos = np.arange(0, sim_end + 3600, 3600)
        tick_lab = [self.sekunden_zu_uhrzeit(s) for s in tick_pos]
        
        # ── Plot ──────────────────────────────────────────────────────────────────────
        fig, axes = plt.subplots(3, 1, figsize=(18, 12), sharex=True)
        fig.suptitle("Fahrtrouten der Aufzüge über die Simulationszeit",
                    fontsize=15, fontweight="bold", y=0.99)
        
        for idx, (aid, ax) in enumerate(zip(["A", "B", "C"], axes)):
            data    = aufzuege[aid]
            t       = data["t"]
            etage   = data["etage"]
            zustand = data["zustand"]
            fahrgaeste = data["fahrgaeste"]
            farbe   = AUFZUG_FARBEN[aid]
        
            # ── Fahrtlinie ────────────────────────────────────────────────────────────
            ax.plot(t, etage,
                    color=farbe, linewidth=1.5, zorder=2, alpha=0.9)
        
            # ── Fahrgastanzahl als Linienstärke-Variante: Punkte bei Stops ────────────
            # Halte markieren (EINLADEN oder AUSSTEIGEN)
            halt_maske = np.array([z in ("EINLADEN", "AUSSTEIGEN") for z in zustand])
            if halt_maske.any():
                ax.scatter(t[halt_maske], etage[halt_maske],
                        s=fahrgaeste[halt_maske] * 12 + 15,
                        color=farbe, zorder=4, alpha=0.7,
                        edgecolors="white", linewidths=0.5)
        
            # Wartend markieren
            warte_maske = np.array([z == "WARTEND" for z in zustand])
            if warte_maske.any():
                ax.scatter(t[warte_maske], etage[warte_maske],
                        s=20, color="#95A5A6", marker="s",
                        zorder=3, alpha=0.5)
        
            # ── Achsen formatieren ────────────────────────────────────────────────────
            ax.set_ylabel("Etage", fontsize=10)
            ax.set_yticks(range(10))
            ax.set_yticklabels([f"E{e}" for e in range(10)], fontsize=8)
            ax.set_ylim(-0.5, 9.5)
            ax.grid(axis="y", linestyle="--", alpha=0.3, zorder=1)
            ax.grid(axis="x", linestyle=":", alpha=0.2, zorder=1)
        
            # Aufzug-Label links
            ax.set_title(f"Aufzug {aid}", fontsize=12, fontweight="bold",
                        loc="left", pad=4, color=farbe)
        
            # Statistik rechts
            fahrten_hoch   = sum(1 for z in zustand if z == "FAHREND_HOCH")
            fahrten_runter = sum(1 for z in zustand if z == "FAHREND_RUNTER")
            wartezeit_n    = sum(1 for z in zustand if z == "WARTEND")
            ax.set_title(f"▲ {fahrten_hoch}×  ▼ {fahrten_runter}×  W {wartezeit_n}×",
                        fontsize=9, loc="right", pad=4, color="#555")
        
        # ── X-Achse ───────────────────────────────────────────────────────────────────
        axes[-1].set_xlabel("Uhrzeit", fontsize=11)
        axes[-1].set_xticks(tick_pos)
        axes[-1].set_xticklabels(tick_lab, fontsize=9)
        axes[-1].set_xlim(0, sim_end)
        
        # ── Legende ───────────────────────────────────────────────────────────────────
        legende_elemente = [
            Line2D([0], [0], marker="o", color="gray", markersize=8,
                label="Halt (Größe = Fahrgäste im Aufzug)", linestyle="None"),
        ]
        fig.legend(handles=legende_elemente, loc="lower center",
                ncol=6, fontsize=9, bbox_to_anchor=(0.5, -0.02),
                frameon=True, framealpha=0.9)
        
        plt.tight_layout(rect=[0, 0.04, 1, 0.98])
        plt.savefig(f"Visualisierung/Abbildungen/Fahrstuhlrouten_{zeitstempel}.png", dpi=150, bbox_inches="tight")
        plt.show()


    def draw_fahrstuhlauslastung(self, csv_pfad, zeitstempel):
        MAX_KAPAZITAET   = 5
        AUFZUG_FARBEN    = {"A": "#4A90D9", "B": "#E05C5C", "C": "#2ECC71"}
        # ── Daten laden ───────────────────────────────────────────────────────────────
        with open(csv_pfad, newline="") as f:
            rows = list(csv.DictReader(f))
        
        aufzug_rows = [r for r in rows if r["aufzug_id"] and r["aufzug_etage"]]
        
        # ── Durchschnittliche Auslastung pro Aufzug berechnen ─────────────────────────
        # Gewichteter Durchschnitt: Fahrgäste × Zeitdauer des Intervalls
        auslastung = {}
        for aid in ["A", "B", "C"]:
            gefiltert = [r for r in aufzug_rows if r["aufzug_id"] == aid]
            zeiten    = np.array([float(r["t"])                for r in gefiltert])
            fahrgaeste = np.array([int(r["aufzug_fahrgaeste"]) for r in gefiltert])
        
            # Zeitdauer jedes Intervalls
            dauern = np.diff(zeiten)
        
            # Gewichteter Durchschnitt (letzten Eintrag weglassen da keine Dauer bekannt)
            auslastung[aid] = np.sum(fahrgaeste[:-1] * dauern) / zeiten[-1]
        
        # ── Plot ──────────────────────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(10, 5))
        
        aufzug_ids = ["A", "B", "C"]
        werte      = [auslastung[aid] for aid in aufzug_ids]
        farben     = [AUFZUG_FARBEN[aid] for aid in aufzug_ids]
        
        bars = ax.bar(aufzug_ids, werte, color=farben, width=0.5, alpha=0.9, zorder=3)
        
        # Wert über jedem Balken
        for bar, val in zip(bars, werte):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.02,
                    f"{val:.6f}",
                    ha="center", va="bottom", fontsize=10, color="#333")
        
        ax.set_xlabel("Fahrstuhl-ID", fontsize=11)
        ax.set_ylabel("Fahrstuhlkapazität", fontsize=11)
        ax.set_title("Durchschnittliche Fahrstuhlauslastung über alle Tageszeiten",
                    fontsize=13)
        ax.set_ylim(0, MAX_KAPAZITAET)
        ax.set_yticks(range(MAX_KAPAZITAET + 1))
        ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
        ax.set_facecolor("#F0F2F5")
        fig.patch.set_facecolor("#F0F2F5")
        
        plt.tight_layout()
        plt.savefig(f"Visualisierung/Abbildungen/Fahrstuhlauslastung{zeitstempel}.png", dpi=150, bbox_inches="tight")
        plt.show()




