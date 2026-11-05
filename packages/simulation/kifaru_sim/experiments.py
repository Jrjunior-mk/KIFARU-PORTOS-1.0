"""Experiment design for the RCS v2 chain model (RCS v2 plan, Sections 10.4, 10.5 and 10.9).

* ``sweep``       — one factor at a time, matching ``RcsSweepOut`` of the API contract.
* ``replicate``   — K replications with seeds ``seed + k``; mean and 95 % confidence interval (Student t) per output.
                    Common random numbers inside each run keep policy differences paired.
* ``tornado``     — swing of the v2 road stop share when each factor moves between a low and a high value.
* ``evaluate_gate`` — the Section 10.9 go/no-go gate.

All figures are modelled.
"""
from __future__ import annotations

import math
from dataclasses import asdict, fields

import numpy as np
from scipy import stats

from .rcs_v2 import SHARE_KEYS, ChainParams, ChainResult, run_chain

OUTPUT_KEYS = ("truck_hours_saved_per_day", "truck_hours_saved_first_station", "false_clear_rate")
FACTOR_NAMES = {f.name for f in fields(ChainParams)} - {"stream_mix", "n", "seed"}

# Default factor ranges for the tornado chart (Section 10.4 factor list)
DEFAULT_TORNADO_FACTORS: dict[str, tuple[float, float]] = {
    "avg_loading_pct": (75.0, 90.0),
    "port_error_pct": (0.5, 2.0),
    "road_error_pct": (1.5, 4.0),
    "token_coverage": (0.5, 1.0),
    "audit_rate": (0.01, 0.05),
    "allowance_pct": (0.0, 5.0),
    "overload_prob": (0.005, 0.03),
    "lane_margin_pct": (0.0, 3.0),
}


def _with(base: ChainParams, **kw) -> ChainParams:
    d = asdict(base)
    d.update(kw)
    return ChainParams(**d)


def _flat(r: ChainResult) -> dict[str, float]:
    out = {k: float(r.shares[k]) for k in SHARE_KEYS}
    out["truck_hours_saved_per_day"] = float(r.truck_hours_saved_per_day)
    out["truck_hours_saved_first_station"] = float(r.truck_hours_saved_first_station)
    out["false_clear_rate"] = float(r.false_clear_rate)
    return out


def sweep(factor: str, values: list[float], base: ChainParams | dict | None = None) -> dict:
    """One-factor sweep. Returns the ``RcsSweepOut`` shape: {factor, rows: [{value, <shares>, <outputs>}], label}."""
    if factor not in FACTOR_NAMES:
        raise ValueError(f"unknown factor '{factor}'; choose one of {sorted(FACTOR_NAMES)}")
    base_p = base if isinstance(base, ChainParams) else ChainParams(**(base or {}))
    rows = []
    for v in values:
        kw = {factor: bool(v) if factor in ("port_legal_grade", "lane_legal_grade") else v}
        if factor == "token_coverage":
            kw["stream_mix"] = None  # coverage sweeps re-derive the stream mix
        r = run_chain(_with(base_p, **kw))
        rows.append({"value": v, **_flat(r)})
    return {"factor": factor, "rows": rows, "label": "MODELLED"}


def replicate(params: ChainParams, reps: int = 30, level: float = 0.95) -> dict:
    """K replications with seeds params.seed + k. Returns {outputs: {key: {mean, ci_low, ci_high, n}}, reps, seeds}."""
    reps = max(int(reps), 1)
    samples: dict[str, list[float]] = {}
    seeds = []
    for k in range(reps):
        r = run_chain(_with(params, seed=int(params.seed) + k))
        seeds.append(int(params.seed) + k)
        for key, val in _flat(r).items():
            samples.setdefault(key, []).append(val)
    out = {}
    for key, vals in samples.items():
        arr = np.asarray(vals, dtype=float)
        m = float(arr.mean())
        if len(arr) < 2:
            out[key] = {"mean": m, "ci_low": math.nan, "ci_high": math.nan, "n": len(arr)}
            continue
        se = float(arr.std(ddof=1)) / math.sqrt(len(arr))
        t = float(stats.t.ppf(0.5 + level / 2, len(arr) - 1))
        out[key] = {"mean": m, "ci_low": m - t * se, "ci_high": m + t * se, "n": len(arr)}
    return {"outputs": out, "reps": reps, "seeds": seeds, "ci_level": level, "label": "MODELLED"}


def tornado(base: ChainParams | None = None, factors: dict[str, tuple[float, float]] | None = None, output: str = "v2_road_static") -> list[dict]:
    """Per-factor swing of ``output`` (default: v2 road stop share) between a low and a high value, sorted by swing."""
    base = base or ChainParams()
    factors = factors or DEFAULT_TORNADO_FACTORS
    ref = _flat(run_chain(base))[output]
    rows = []
    for name, (lo, hi) in factors.items():
        if name not in FACTOR_NAMES:
            raise ValueError(f"unknown factor '{name}'")
        kw_lo, kw_hi = {name: lo}, {name: hi}
        if name == "token_coverage":
            kw_lo["stream_mix"] = kw_hi["stream_mix"] = None
        v_lo = _flat(run_chain(_with(base, **kw_lo)))[output]
        v_hi = _flat(run_chain(_with(base, **kw_hi)))[output]
        rows.append({"factor": name, "low": lo, "high": hi, "output_low": v_lo, "output_high": v_hi, "swing": abs(v_hi - v_lo), "reference": ref})
    rows.sort(key=lambda r: r["swing"], reverse=True)
    return rows


def evaluate_gate(result: ChainResult | dict, baseline_share: float | None = None, min_cut_points: float = 10.0,
                  max_false_clear: float = 0.01, max_port_reweigh_pct: float = 20.0) -> dict:
    """Section 10.9 go/no-go gate.

    Proceed to the shadow pilot when the model cuts the road stop share by at least ``min_cut_points`` percentage points
    against the road-only baseline (measured baseline when available, otherwise the model's own road-only share), the
    false-clear rate is at or below ``max_false_clear`` and the port re-weigh share is practical for KPA
    (``max_port_reweigh_pct``, a policy threshold to agree with KPA).
    """
    d = result.to_dict() if isinstance(result, ChainResult) else result
    shares = d["shares"]
    base = float(baseline_share) if baseline_share is not None else float(shares["road_only_static"])
    cut = base - float(shares["v2_road_static"])
    checks = [
        {"name": "road_stop_share_cut_points", "value": round(cut, 2), "threshold": min_cut_points, "ok": cut >= min_cut_points,
         "detail": f"road-only {base:.1f} % → v2 {shares['v2_road_static']:.1f} %"},
        {"name": "false_clear_rate", "value": round(float(d["false_clear_rate"]), 4), "threshold": max_false_clear, "ok": float(d["false_clear_rate"]) <= max_false_clear,
         "detail": "share of trucks allowed through without a stop that were over the limit"},
        {"name": "port_reweigh_share_pct", "value": round(float(shares["v2_port_reweigh"]), 2), "threshold": max_port_reweigh_pct, "ok": float(shares["v2_port_reweigh"]) <= max_port_reweigh_pct,
         "detail": "port re-weigh volume must be practical for KPA (threshold to be agreed)"},
        {"name": "lane_capacity", "value": round(float(d["lane_peak_per_hour"]), 1), "threshold": round(float(d["lane_capacity_per_hour"]), 1), "ok": bool(d["lane_ok"]),
         "detail": "peak lane demand against one rolling verification lane"},
    ]
    proceed = all(c["ok"] for c in checks)
    return {
        "proceed": proceed,
        "checks": checks,
        "recommendation": "Proceed to the shadow pilot (Phase 4)." if proceed else "Do not proceed as designed: narrow the project to a vehicle-side or registry-only offering, or revisit the assumptions that fail.",
        "label": "MODELLED",
    }
