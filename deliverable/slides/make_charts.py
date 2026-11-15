# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "pandas"]
# ///
"""Build slide charts from results/ files. Run: uv run make_charts.py"""
import re
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RES = HERE.parent.parent / "results"
IMG = HERE / "img"
IMG.mkdir(exist_ok=True)
NAVY, RED, GREY, MID = "#1d2a44", "#b3261e", "#eef0f3", "#6b7686"
plt.rcParams.update({"font.family": ["Arial", "DejaVu Sans"], "font.size": 15,
                     "axes.edgecolor": MID, "axes.labelcolor": NAVY, "text.color": NAVY,
                     "xtick.color": NAVY, "ytick.color": NAVY})

d = pd.read_csv(RES / "unified_kanto_loo.csv", encoding="utf-8-sig")
c = d.columns
col = dict(typhoon=c[0], rain=c[3], dmg=c[9], p=c[15], harv=c[16])
dmg = d[col["dmg"]].astype(bool)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


# A: rain strip plot ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.4, 6.0), dpi=200)
rng = np.random.default_rng(1)
for i, (flag, color, label) in enumerate([(False, MID, "No damage"), (True, RED, "Damage (>=100 ha)")]):
    v = d.loc[dmg == flag, col["rain"]]
    ax.scatter(i + rng.uniform(-0.17, 0.17, len(v)), v, s=70, color=color, alpha=0.85,
               edgecolor="white", linewidth=0.8, zorder=3)
    m = v.median()
    ax.hlines(m, i - 0.32, i + 0.32, color=NAVY, lw=2.5, zorder=4)
    ax.text(i + 0.36, m, f"median\n{m:.0f} mm", va="center", fontsize=15, fontweight="bold", color=color)
ax.set_xticks([0, 1])
ax.set_xticklabels([f"No damage\n(n={int((~dmg).sum())})", f"Damage\n(n={int(dmg.sum())})"], fontsize=16)
ax.set_xlim(-0.5, 1.8)
ax.set_ylabel("IMERG rain per typhoon (mm)")
ax.grid(axis="y", color="#d5d9e0", lw=0.8, zorder=0)
clean(ax)
fig.tight_layout()
fig.savefig(IMG / "chart_rain.png")
plt.close(fig)

# B: LOO probability sorted ---------------------------------------------------
s = d.sort_values(col["p"]).reset_index(drop=True)
thr = 0.1674
fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=200)
colors = [RED if f else MID for f in s[col["dmg"]].astype(bool)]
ax.bar(range(len(s)), s[col["p"]] * 100, color=colors, width=0.78, zorder=3)
ax.axhline(thr * 100, color=NAVY, lw=2, ls="--", zorder=4)
ax.text(0.2, thr * 100 + 3, "threshold 16.7%", fontsize=14, fontweight="bold", color=NAVY)
ax.set_xticks([])
ax.set_xlabel("23 typhoons, sorted by leave-one-out probability")
ax.set_ylabel("Damage probability (%)")
ax.grid(axis="y", color="#d5d9e0", lw=0.8, zorder=0)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=RED, label="Damage"), Patch(color=MID, label="No damage")],
          loc="upper left", frameon=False, fontsize=14, bbox_to_anchor=(0.0, 0.88))
clean(ax)
fig.tight_layout()
fig.savefig(IMG / "chart_loo.png")
plt.close(fig)

# C: sensitivity heatmap (risky direction), parsed from robustness_report.txt --
txt = (RES / "robustness_report.txt").read_text(encoding="utf-8")
blk = txt.split("[雨 × 風の格子]")[1].split("[被害あり 7 個")[0]
rows, rl = [], []
for line in blk.splitlines():
    m = re.match(r"\s*(x[\d.]+)\s+((?:\d+/\d+ \(\d+\)\s*)+)$", line)
    if m:
        rl.append(m.group(1).lstrip("x"))
        rows.append([int(x) for x in re.findall(r"(\d+)/\d+ \(", m.group(2))])
grid = np.array(rows)
winds = ["0.7", "0.85", "1", "1.15", "1.3"]
fig, ax = plt.subplots(figsize=(5.3, 3.0), dpi=200)
from matplotlib.colors import LinearSegmentedColormap
cm = LinearSegmentedColormap.from_list("r", ["#ffffff", "#e8a49f", RED])
ax.imshow(grid, cmap=cm, vmin=0, vmax=9)
for i in range(grid.shape[0]):
    for j in range(grid.shape[1]):
        v = grid[i, j]
        ax.text(j, i, str(v), ha="center", va="center", fontsize=15, fontweight="bold",
                color="white" if v >= 6 else NAVY)
ax.set_xticks(range(len(winds)))
ax.set_xticklabels(winds, fontsize=12)
ax.set_yticks(range(len(rl)))
ax.set_yticklabels(rl, fontsize=12)
ax.set_xlabel("Wind multiplier (x)", fontsize=13)
ax.set_ylabel("Rain multiplier (x)", fontsize=13)
ax.xaxis.set_label_position("bottom")
ax.add_patch(plt.Rectangle((1.5, 1.5), 1, 1, fill=False, ec=NAVY, lw=2.5))  # original decision (x1, x1)
fig.tight_layout()
fig.savefig(IMG / "chart_sens.png")
plt.close(fig)

# D: planting bars ------------------------------------------------------------
p = pd.read_csv(RES / "planting_strategies.csv", encoding="utf-8-sig")
pc = p.columns
vals = p[pc[7]].tolist()
n = int(p[pc[6]].iloc[0])
labels = ["Existing practice\n(Koshihikari)", "Plant 3 weeks later\n(Koshihikari)",
          "Early variety\n(Akitakomachi)", "Late variety\n(Nijinokirameki)"]
fig, ax = plt.subplots(figsize=(8.6, 4.8), dpi=200)
cols = [MID, MID, RED, MID]
b = ax.bar(range(4), vals, color=cols, width=0.62, zorder=3)
for i, v in enumerate(vals):
    ax.text(i, v + 1.2, f"{v}/{n}", ha="center", fontsize=17, fontweight="bold", color=cols[i] if cols[i] == RED else NAVY)
ax.set_xticks(range(4))
ax.set_xticklabels(labels, fontsize=13)
ax.set_ylim(0, 70)
ax.set_ylabel("Typhoons overlapping\nthe vulnerable stage")
ax.grid(axis="y", color="#d5d9e0", lw=0.8, zorder=0)
clean(ax)
fig.tight_layout()
fig.savefig(IMG / "chart_planting.png")
plt.close(fig)
print("ok", vals, n, grid.tolist())
