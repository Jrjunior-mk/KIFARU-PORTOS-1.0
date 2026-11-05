"""Charts for the project proposal, built from the simulation outputs in ./assets (all figures are MODELLED)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = Path(__file__).resolve().parent
A = HERE / "assets"
chain = json.loads((A / "chain-results.json").read_text(encoding="utf8"))
simpy = json.loads((A / "simpy-comparison.json").read_text(encoding="utf8"))

TEAL, NAVY, AMBER, RED, GREY, GREEN, MAG = "#0d9488", "#1e293b", "#d97706", "#dc2626", "#94a3b8", "#16a34a", "#c026d3"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 160})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(A / name, bbox_inches="tight")
    plt.close(fig)


# 1. port trucks by loading
rows = chain["port_table"]
x = [r["avg_loading_pct"] for r in rows]
fig, ax = plt.subplots(figsize=(7, 3.4))
w = 1.0
keys = [("road_only_static", "Road-only screening", GREY), ("road_only_with_allowance", "Road-only + 5 % allowance", NAVY), ("v2_road_static", "RCS v2: road static stops", TEAL), ("v2_port_reweigh", "RCS v2: port re-weigh", AMBER)]
for i, (k, lab, c) in enumerate(keys):
    ax.bar([xi + (i - 1.5) * w for xi in x], [r[k] for r in rows], width=w, label=lab, color=c)
ax.set_xlabel("Average load (% of legal limit)")
ax.set_ylabel("% of all trucks")
ax.set_title("Port trucks: static-scale visits by policy (modelled, 600 000 trucks per point)")
ax.legend(fontsize=8, ncol=2)
save(fig, "fig-port-table.png")

# 2. mixed traffic by coverage
rows = chain["mixed_table"]
cov = [int(r["token_coverage"] * 100) for r in rows]
fig, ax = plt.subplots(figsize=(7, 3.2))
ax.plot(cov, [r["road_only_baseline_static"] for r in rows], "--", color=GREY, marker="o", label="Road-only baseline: static stops")
ax.plot(cov, [r["first_station_lane"] for r in rows], color=AMBER, marker="o", label="First station: rolling verification lane")
ax.plot(cov, [r["first_station_static"] for r in rows], color=RED, marker="o", label="First station: static scale")
ax.plot(cov, [r["later_station_lane"] for r in rows], ":", color=TEAL, marker="s", label="Later stations: lane")
ax.plot(cov, [r["later_station_static"] for r in rows], ":", color=NAVY, marker="s", label="Later stations: static")
ax.set_xlabel("Share of trucks carrying a port or origin token (%)")
ax.set_ylabel("% of all trucks")
ax.set_title("Mixed traffic at 85 % loading: where trucks are checked (modelled)")
ax.legend(fontsize=8)
save(fig, "fig-mixed-coverage.png")

# 3. sensitivity panels
fig, axs = plt.subplots(1, 3, figsize=(8.2, 2.8))
sw = chain["sweep_coverage"]["rows"]
axs[0].plot([r["value"] * 100 for r in sw], [r["v2_road_static"] for r in sw], color=TEAL, marker="o")
axs[0].set_title("Token coverage -> road stops"); axs[0].set_xlabel("coverage (%)"); axs[0].set_ylabel("% trucks")
sw = chain["sweep_port_error"]["rows"]
axs[1].plot([r["value"] for r in sw], [r["v2_port_reweigh"] for r in sw], color=AMBER, marker="o")
axs[1].set_title("Port scale error -> port re-weigh"); axs[1].set_xlabel("port error (%)")
sw = chain["sweep_allowance"]["rows"]
axs[2].plot([r["value"] for r in sw], [r["v2_port_reweigh"] for r in sw], color=RED, marker="o")
axs[2].set_title("Allowance -> port re-weigh"); axs[2].set_xlabel("discretion allowance (%)")
save(fig, "fig-sensitivity.png")

# 4. tornado
t = sorted(chain["tornado"], key=lambda r: r.get("swing", 0))
fig, ax = plt.subplots(figsize=(7, 3.2))
labels = [f'{r["factor"]} ({r["low"]} to {r["high"]})' for r in t]
lo = [r["output_low"] for r in t]
hi = [r["output_high"] for r in t]
basev = chain["defaults"]["shares"]["v2_road_static"]
for i, r in enumerate(t):
    a, b = sorted((lo[i], hi[i]))
    ax.barh(i, max(b - a, 0.05), left=a, color=TEAL if hi[i] >= lo[i] else AMBER, alpha=0.85)
    ax.text(b + 0.1, i, f"{lo[i]:.1f} -> {hi[i]:.1f}", va="center", fontsize=7, color=NAVY)
ax.axvline(basev, color=NAVY, lw=1)
ax.set_xlim(0, max(hi + lo) + 2.2)
ax.set_yticks(range(len(t))); ax.set_yticklabels(labels)
ax.set_xlabel("RCS v2 road static stops (% of trucks) across the factor's low-high range")
ax.set_title("Sensitivity of the road stop share (tornado, modelled)")
save(fig, "fig-tornado.png")

# 5. SimPy scenarios
order = ["baseline_all_stop", "rolling_clearance", "arrivals_+50", "rcs_v2_untokened", "rcs_v2_tokens_50", "rcs_v2_tokens_90", "rcs_v2_allowance_5pct", "rcs_v2_lane_closure"]
o = simpy["outcomes"]
names = [n for n in order if n in o]
fig, ax = plt.subplots(figsize=(7.6, 3.4))
xs = range(len(names))
ax.bar([i - 0.2 for i in xs], [o[n]["summary"]["pct_stopped"]["mean"] for n in names], width=0.4, color=RED, label="% trucks stopped (static scale)")
ax.bar([i + 0.2 for i in xs], [o[n]["summary"]["pct_lane"]["mean"] for n in names], width=0.4, color=AMBER, label="% via rolling verification lane (no stop)")
ax.set_xticks(list(xs)); ax.set_xticklabels([n.replace("_", "\n") for n in names], fontsize=7)
ax.set_ylabel("% of trucks"); ax.set_title("Station queue model (SimPy, 12 h, 3 replications): stops and lane use by scenario")
ax.legend(fontsize=8)
save(fig, "fig-simpy-scenarios.png")

# 6. static queue over time
fig, ax = plt.subplots(figsize=(7.6, 3.0))
for n, c in (("baseline_all_stop", GREY), ("rolling_clearance", NAVY), ("rcs_v2_tokens_90", TEAL)):
    if n in o:
        series = o[n]["static_queue_mean_by_minute"]
        ax.plot([m / 60 for m in range(len(series))], series, color=c, label=n)
ax.set_xlabel("hours since 06:00"); ax.set_ylabel("trucks waiting for the static scale")
ax.set_title("Mean static-scale queue through the day (modelled)")
ax.legend(fontsize=8)
save(fig, "fig-simpy-queue.png")

# 7. replication CI chart
rep = chain["replicate"]["outputs"]
fig, ax = plt.subplots(figsize=(7, 2.6))
keys = [k for k in ("road_only_static", "v2_road_static", "v2_port_reweigh", "first_station_lane", "first_station_static") if k in rep]
means = [rep[k]["mean"] for k in keys]
err = [[rep[k]["mean"] - rep[k]["ci_low"] for k in keys], [rep[k]["ci_high"] - rep[k]["mean"] for k in keys]]
ax.bar(range(len(keys)), means, yerr=err, capsize=4, color=[GREY, TEAL, AMBER, AMBER, RED][: len(keys)])
ax.set_xticks(range(len(keys))); ax.set_xticklabels([k.replace("_", " ") for k in keys], fontsize=8)
ax.set_ylabel("% of trucks"); ax.set_title("30 replications x 200 000 trucks: means with 95 % confidence intervals")
save(fig, "fig-replications.png")

# 8. chain flow diagram
fig, ax = plt.subplots(figsize=(8, 3.3))
ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 40)


def box(x, y, w, h, text, color, fc="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5", ec=color, fc=fc, lw=1.6))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.6, color=NAVY, wrap=True)


def arrow(x1, y1, x2, y2, color=NAVY, text=None):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10, color=color, lw=1.2))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 1.6, text, ha="center", fontsize=6.8, color=color)


box(1, 25, 18, 11, "A. Port gate-out\nweigh node\n(token, tier 1)", TEAL, "#f0fdfa")
box(1, 5, 18, 11, "B. Origin weigh node\nmine / quarry / factory\n(token, tier 2)", TEAL, "#f0fdfa")
box(30, 15, 20, 11, "C. Road screening node\nhigh-speed WIM + ANPR/RFID\ntoken consistency check", NAVY)
box(61, 27, 20, 10, "GREEN: continue\n(token honoured)", GREEN, "#f0fdf4")
box(61, 14, 20, 10, "D. Rolling verification lane\n~10 km/h, per-wheel scales,\nLiDAR portal", AMBER, "#fffbeb")
box(61, 1, 20, 10, "E. Static scale + officer\nrelease order (Reg 14)", RED, "#fef2f2")
box(84, 14, 15, 10, "Clearance\nregistry\n(tokens, orders,\npermits)", MAG, "#fdf4ff")
arrow(19, 30, 30, 22); arrow(19, 10, 30, 18); arrow(50, 22, 61, 32, GREEN); ax.text(55.5, 29.5, "consistent", fontsize=6.8, color=GREEN); arrow(50, 20, 61, 19, AMBER); ax.text(51, 16.2, "doubtful / audit", fontsize=6.8, color=AMBER)
arrow(50, 18, 61, 6, RED); ax.text(51.5, 9.5, "certain overload", fontsize=6.8, color=RED); arrow(81, 19, 84, 19, MAG); arrow(71, 14, 71, 11, RED); ax.text(72, 11.8, "fail", fontsize=6.8, color=RED); arrow(81, 24, 81, 27, GREEN)
ax.text(50, 38, "Weigh once at the first trusted point; later stations honour the Load Compliance Token", ha="center", fontsize=8.5, color=NAVY, weight="bold")
save(fig, "fig-chain.png")
print("charts written")
