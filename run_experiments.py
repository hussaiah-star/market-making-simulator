"""Reproduce every number and chart in the README.

    python run_experiments.py

Writes summary.csv and the four charts into this folder.
"""

import csv
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from simulator import (
    MarketParams, as_quotes, symmetric_quotes, simulate_day, run,
)

OUT = "."
p = MarketParams()
N_DAYS = 1000
INK, ACCENT, GREY = "#1b1b1b", "#0b4ea2", "#9aa3ad"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

# 1. Head-to-head at one risk-aversion level --------------------------------
GAMMA = 0.1
sym = run(symmetric_quotes, GAMMA, p, N_DAYS, seed=1)
inv = run(as_quotes, GAMMA, p, N_DAYS, seed=1)

rows = [("strategy", "gamma", "mean_pnl", "std_pnl", "mean_over_std", "mean_abs_inventory")]
for name, r in (("symmetric", sym), ("inventory_aware", inv)):
    rows.append((name, GAMMA, round(r["mean_pnl"], 2), round(r["std_pnl"], 2),
                 round(r["ratio"], 2), round(r["mean_abs_inventory"], 2)))

# 2. Risk-aversion sweep: the trade-off between profit and risk --------------
gammas = [0.01, 0.05, 0.1, 0.5, 1.0]
sweep = []
for g in gammas:
    r = run(as_quotes, g, p, N_DAYS, seed=2)
    sweep.append((g, r["mean_pnl"], r["std_pnl"], r["mean_abs_inventory"]))
    rows.append(("inventory_aware_sweep", g, round(r["mean_pnl"], 2), round(r["std_pnl"], 2),
                 round(r["ratio"], 2), round(r["mean_abs_inventory"], 2)))

# 3. Extension: volatility doubles, quotes stay calibrated to the old level --
from dataclasses import replace
shock = replace(p, sigma=4.0)
shock_rows = []
for name, strat in (("symmetric", symmetric_quotes), ("inventory_aware", as_quotes)):
    stale = run(strat, GAMMA, shock, N_DAYS, seed=3, quote_p=p)       # still quoting for sigma = 2
    fresh = run(strat, GAMMA, shock, N_DAYS, seed=3, quote_p=shock)   # recalibrated to sigma = 4
    for label, r in (("stale", stale), ("recalibrated", fresh)):
        shock_rows.append((name, label, r["mean_pnl"], r["std_pnl"], r["mean_abs_inventory"]))
        rows.append((f"vol_shock_{name}_{label}", GAMMA, round(r["mean_pnl"], 2), round(r["std_pnl"], 2),
                     round(r["ratio"], 2), round(r["mean_abs_inventory"], 2)))

with open(os.path.join(OUT, "summary.csv"), "w", newline="") as f:
    csv.writer(f).writerows(rows)

# Chart A: P&L distributions
fig, ax = plt.subplots(figsize=(7, 3.6))
bins = np.linspace(min(sym["pnls"].min(), inv["pnls"].min()),
                   max(sym["pnls"].max(), inv["pnls"].max()), 50)
ax.hist(sym["pnls"], bins=bins, color=GREY, alpha=0.85, label=f"Symmetric (sd {sym['std_pnl']:.1f})")
ax.hist(inv["pnls"], bins=bins, color=ACCENT, alpha=0.75, label=f"Inventory-aware (sd {inv['std_pnl']:.1f})")
ax.set_xlabel("End-of-day P&L")
ax.set_ylabel("Days (out of 1,000)")
ax.set_title("Same spread, same markets: reacting to inventory narrows the range of outcomes", loc="left", fontsize=10)
ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "pnl_distribution.png"), dpi=160); plt.close(fig)

# Chart B: one sample day of inventory
rng_a, rng_b = np.random.default_rng(7), np.random.default_rng(7)
_, _, path_sym = simulate_day(symmetric_quotes, GAMMA, p, rng_a)
_, _, path_inv = simulate_day(as_quotes, GAMMA, p, rng_b)
t = np.arange(len(path_sym)) * p.dt
fig, ax = plt.subplots(figsize=(7, 3.2))
ax.step(t, path_sym, color=GREY, where="post", label="Symmetric")
ax.step(t, path_inv, color=ACCENT, where="post", label="Inventory-aware")
ax.axhline(0, color=INK, lw=0.6)
ax.set_xlabel("Time through the trading day"); ax.set_ylabel("Inventory (units)")
ax.set_title("One sample day: the inventory-aware quotes keep pulling inventory back to zero", loc="left", fontsize=10)
ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "inventory_path.png"), dpi=160); plt.close(fig)

# Chart C: risk-aversion frontier
fig, ax = plt.subplots(figsize=(7, 3.6))
xs = [s[2] for s in sweep]; ys = [s[1] for s in sweep]
ax.plot(xs, ys, color=ACCENT, marker="o")
offsets = {0.01: (6, 4), 0.05: (2, 8), 0.1: (-8, -14), 0.5: (8, -2), 1.0: (8, -2)}
for g, m, sd, _ in sweep:
    ax.annotate(f"γ = {g}", (sd, m), textcoords="offset points", xytext=offsets[g], fontsize=8.5)
ax.scatter([sym["std_pnl"]], [sym["mean_pnl"]], color=GREY, zorder=3)
ax.annotate("Symmetric, γ = 0.1", (sym["std_pnl"], sym["mean_pnl"]), textcoords="offset points", xytext=(6, -12), fontsize=8.5, color="#555")
ax.set_xlabel("Risk: standard deviation of daily P&L"); ax.set_ylabel("Average daily P&L")
ax.set_title("Turning the risk-aversion dial trades profit for stability", loc="left", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "risk_frontier.png"), dpi=160); plt.close(fig)

# Chart D: volatility shock
fig, ax = plt.subplots(figsize=(7, 3.4))
labels = ["Symmetric\nstale", "Symmetric\nrecalibrated", "Inventory-aware\nstale", "Inventory-aware\nrecalibrated"]
sds = [r[3] for r in shock_rows]
cols = [GREY, GREY, ACCENT, ACCENT]
bars = ax.bar(labels, sds, color=cols)
for b, (_, lab, m, sd, _) in zip(bars, shock_rows):
    b.set_alpha(0.55 if lab == "stale" else 1.0)
    ax.text(b.get_x() + b.get_width() / 2, sd + 0.4, f"sd {sd:.1f}\nmean {m:.1f}", ha="center", fontsize=8.5)
ax.set_ylabel("Std. dev. of daily P&L")
ax.set_title("Volatility doubles: what recalibrating the quotes is worth", loc="left", fontsize=10)
ax.set_ylim(0, max(sds) * 1.3)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "vol_shock.png"), dpi=160); plt.close(fig)

for r in rows:
    print(r)
