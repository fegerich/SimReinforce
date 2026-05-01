import csv
import matplotlib.pyplot as plt
import numpy as np

# Statistiken zu Wartezeiten der Fahrgäste

# 0 Sekunden Simulationszeit entspricht dieser Uhrzeit
SIM_START_STUNDE  = 8   # 08:00 Uhr
SIM_START_MINUTE  = 0

DATEI_PFAD = "output/fahrgaeste_2026_05_01-16_53_56.csv"


def sekunden_zu_uhrzeit(sekunden: float) -> str:
    """Rechnet Simulationssekunden in eine Uhrzeit um (0s = 08:00 Uhr)."""
    gesamt_minuten = int(SIM_START_STUNDE * 60 + SIM_START_MINUTE + sekunden / 60)
    stunde  = (gesamt_minuten // 60) % 24
    minute  = gesamt_minuten % 60
    return f"{stunde:02d}:{minute:02d}"



def visualisiere_wartezeiten(csv_pfad: str, intervall_sekunden: int = 300):
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
    tick_beschriftungen = [sekunden_zu_uhrzeit(s) for s in tick_positionen]
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
                     linestyle="--", label="Gleitender Ø (5 Fenster)", zorder=4)

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
    hist_bins = np.arange(0, 65, 5)  # 0–60s in 5s-Schritten
    ax_hist.hist(wartezeit_aufzug, bins=hist_bins,
                 color="#4A90D9", alpha=0.85, edgecolor="white", zorder=3,
                 label="Aufzug genutzt")
    ax_hist.hist(wartezeit_treppe, bins=hist_bins,
                 color="#E05C5C", alpha=0.75, edgecolor="white", zorder=3,
                 label="Treppenhaus (60s)")

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
    median_wz = np.median(wartezeit_aufzug)
    zusammenfassung = (
        f"Aufzug: {len(aufzug_rows)} Fahrgäste  |  "
        f"Ø Wartezeit: {gesamt_avg:.1f}s  |  "
        f"Median: {median_wz:.1f}s  |  "
        f"Max: {wartezeit_aufzug.max():.0f}s  |  "
        f"Treppenhaus: {len(treppenhaus_rows)} Fahrgäste (immer 60s)"
    )
    fig.text(0.5, 0.01, zusammenfassung,
             ha="center", fontsize=10, color="#555555")

    plt.savefig("wartezeiten.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("✅ Gespeichert als wartezeiten.png")


# Direkt ausführen
visualisiere_wartezeiten(
    csv_pfad=DATEI_PFAD,
    intervall_sekunden=300
)