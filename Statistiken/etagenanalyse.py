import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from collections import Counter

# ── Konfiguration ─────────────────────────────────────────────────────────────
SIM_START_STUNDE = 8
CSV_PFAD = "output/fahrgaeste_2026_05_01-16_53_56.csv"

# ── Daten laden ───────────────────────────────────────────────────────────────
with open(CSV_PFAD, newline="") as f:
    rows = list(csv.DictReader(f))

aufzug_rows = [r for r in rows if r["Nimmt_Treppenhaus"] == "False"]

startetagen  = np.array([int(r["Startetage"]) for r in aufzug_rows])
zieletagen   = np.array([int(r["Zieletage"])  for r in aufzug_rows])
wartezeiten  = np.array([float(r["Wartezeit"]) for r in aufzug_rows])
alle_etagen  = sorted(set(startetagen) | set(zieletagen))
num_etagen   = len(alle_etagen)

# ── Berechnungen ──────────────────────────────────────────────────────────────

# Häufigkeit Start- und Zieletagen
start_counts = Counter(startetagen)
ziel_counts  = Counter(zieletagen)

# Häufigste Routen
routen = Counter(zip(startetagen.tolist(), zieletagen.tolist()))
top_routen = routen.most_common(10)

# Durchschnittliche Wartezeit pro Startetage
avg_wartezeit_pro_etage = {
    e: wartezeiten[startetagen == e].mean() for e in alle_etagen
}
std_wartezeit_pro_etage = {
    e: wartezeiten[startetagen == e].std() for e in alle_etagen
}

# Heatmap-Matrix: Routen (Start × Ziel)
heatmap = np.zeros((num_etagen, num_etagen))
for (s, z), count in routen.items():
    heatmap[s][z] = count

# ── Plot ──────────────────────────────────────────────────────────────────────
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

# ── 1. Häufigste Startetagen ──────────────────────────────────────────────────
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

# ── 2. Häufigste Zieletagen ───────────────────────────────────────────────────
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

# ── 3. Durchschnittliche Wartezeit pro Startetage ─────────────────────────────
avg_werte = [avg_wartezeit_pro_etage[e] for e in alle_etagen]
std_werte = [std_wartezeit_pro_etage[e] for e in alle_etagen]

# Farbe je nach Wartezeit (grün = kurz, rot = lang)
norm   = mcolors.Normalize(vmin=min(avg_werte), vmax=max(avg_werte))
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


# ── Zusammenfassung ───────────────────────────────────────────────────────────
top_start = max(start_counts, key=start_counts.get)
top_ziel  = max(ziel_counts,  key=ziel_counts.get)
top_route = top_routen[0]
zusammenfassung = (
    f"Beliebteste Startetage: E{top_start} ({start_counts[top_start]}×)  |  "
    f"Beliebteste Zieletage: E{top_ziel} ({ziel_counts[top_ziel]}×)  |  "
    f"Häufigste Route: E{top_route[0][0]}→E{top_route[0][1]} ({top_route[1]}×)"
)
fig.text(0.5, 0.005, zusammenfassung,
         ha="center", fontsize=10, color="#555")

plt.savefig("etagenanalyse.png", dpi=150, bbox_inches="tight")
plt.show()
print("✅ Gespeichert als etagenanalyse.png")