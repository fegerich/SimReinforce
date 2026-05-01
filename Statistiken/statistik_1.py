import csv
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# Statistiken zum Aufkommen der Fahrgäste

# 0 Sekunden Simulationszeit entspricht dieser Uhrzeit
SIM_START_STUNDE  = 8   # 08:00 Uhr
SIM_START_MINUTE  = 0


def sekunden_zu_uhrzeit(sekunden: float) -> str:
    """Rechnet Simulationssekunden in eine Uhrzeit um (0s = 08:00 Uhr)."""
    gesamt_minuten = int(SIM_START_STUNDE * 60 + SIM_START_MINUTE + sekunden / 60)
    stunde  = (gesamt_minuten // 60) % 24
    minute  = gesamt_minuten % 60
    return f"{stunde:02d}:{minute:02d}"


def visualisiere_aufkommen(csv_pfad: str, intervall_sekunden: int = 300):
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
    tick_beschriftungen = [sekunden_zu_uhrzeit(s) for s in tick_positionen]

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
    plt.savefig("aufkommen.png", dpi=150, bbox_inches="tight")
    plt.show()
    print("✅ Gespeichert als aufkommen.png")


# ── Aufruf ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    visualisiere_aufkommen(
        csv_pfad="output/fahrgaeste_2026_05_01-16_53_56.csv",
        intervall_sekunden=300   # 5-Minuten-Fenster
    )