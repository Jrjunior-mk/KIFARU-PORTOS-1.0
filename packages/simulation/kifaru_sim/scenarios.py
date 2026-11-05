"""Named scenarios (RTM DT-02). Each scenario = BASE config + overrides.

The base describes one direction of a Mariakani-type station: 2 high-speed WIM lanes, 5 static bays (median 4 min each,
~ 69 trucks/h), 2 inspection bays, 60 trucks/h mean demand with the synthetic time-of-day profile in ``model.py``.
These are engineering assumptions until Phase 7 baseline data exists; override them with ``--set key=value``.
"""
from __future__ import annotations

from collections.abc import Callable

from kifaru.services.limits import LimitSet

from .model import SimConfig

BASE = SimConfig(policy="rolling", label="base")

ScenarioFn = Callable[[SimConfig], SimConfig]


def _scn(**overrides) -> ScenarioFn:
    def apply(base: SimConfig) -> SimConfig:
        return base.with_overrides(**overrides)

    return apply


def _lane_failure(base: SimConfig) -> SimConfig:
    # one of two WIM lanes down for 2 h in the middle of the run
    start = max(0.0, base.horizon_s / 2 - 3600.0)
    return base.with_overrides(lane_failures=((start, 7200.0, 1),))


def _lane_closure(base: SimConfig) -> SimConfig:
    # the rolling verification lane closed for 2 h in the middle of the run: AMBER trucks fall back to the static scale
    start = max(0.0, base.horizon_s / 2 - 3600.0)
    return base.with_overrides(policy="rcs_v2", token_coverage=0.9, lane_closures=((start, 7200.0),))


ALLOWANCE_LIMITS = LimitSet(version=BASE.limits.version + "+allowance5", discretion_allowance_pct=5.0)

SCENARIOS: dict[str, ScenarioFn] = {
    "baseline_all_stop": _scn(policy="all_stop"),
    "rolling_clearance": _scn(policy="rolling"),
    "arrivals_+20": _scn(policy="rolling", arrival_multiplier=1.2),
    "arrivals_+30": _scn(policy="rolling", arrival_multiplier=1.3),
    "arrivals_+50": _scn(policy="rolling", arrival_multiplier=1.5),
    "station_lane_failure": _lane_failure,
    "inspection_rate_x2": _scn(policy="rolling", inspection_rate=BASE.inspection_rate * 2, audit_rate=BASE.audit_rate * 2),
    "static_capacity_-1": _scn(policy="rolling", static_bays=BASE.static_bays - 1),
    "delayed_cargo_release": _scn(policy="rolling", release_hold_prob=0.15, release_hold_median_s=900.0),
    "dynamic_slot_allocation": _scn(policy="rolling", slot_cap_per_15min=int(round(BASE.arrivals_per_hour * 1.1 / 4))),
    "queue_policy_priority": _scn(policy="rolling", priority_queue=True),
    # RCS v2: Load Compliance Tokens + rolling verification lane
    "rcs_v2_tokens_50": _scn(policy="rcs_v2", token_coverage=0.5),
    "rcs_v2_tokens_90": _scn(policy="rcs_v2", token_coverage=0.9),
    "rcs_v2_untokened": _scn(policy="rcs_v2", token_coverage=0.0),
    "rcs_v2_allowance_5pct": _scn(policy="rcs_v2", token_coverage=0.9, limits=ALLOWANCE_LIMITS),
    "rcs_v2_lane_closure": _lane_closure,
}

DESCRIPTIONS: dict[str, str] = {
    "baseline_all_stop": "Pre-platform situation: every truck queues for the static scale; no WIM pre-screen (engine decision is shadow only).",
    "rolling_clearance": "Platform: WIM pre-screen, GREEN continues, AMBER to static scale, RED to static + inspection.",
    "arrivals_+20": "Rolling clearance with +20 % demand.",
    "arrivals_+30": "Rolling clearance with +30 % demand.",
    "arrivals_+50": "Rolling clearance with +50 % demand.",
    "station_lane_failure": "One of two WIM lanes down for 2 h mid-run; its trucks fall back to the static scale.",
    "inspection_rate_x2": "Physical inspection sampling and random audit rate doubled.",
    "static_capacity_-1": "One static bay fewer (maintenance).",
    "delayed_cargo_release": "15 % of trucks held at the gate (median 15 min) awaiting cargo release.",
    "dynamic_slot_allocation": "Arrivals smoothed by a booking cap of ~110 % of mean demand per 15-min window.",
    "queue_policy_priority": "Perishable / hazardous cargo (12 %) gets priority at the static scale.",
    "rcs_v2_tokens_50": "RCS v2: 50 % of trucks carry a port/origin token; AMBER rolls through the verification lane (1 lane, ~1.5 min) instead of stopping.",
    "rcs_v2_tokens_90": "RCS v2: 90 % token coverage, verification lane for the rest.",
    "rcs_v2_untokened": "RCS v2 lane only: no tokens (first-time traffic), every AMBER rolls through the verification lane.",
    "rcs_v2_allowance_5pct": "RCS v2 at 90 % coverage with the 5 % Second Schedule discretion allowance applied (policy decision for KeNHA).",
    "rcs_v2_lane_closure": "RCS v2 at 90 % coverage with the verification lane closed for 2 h mid-run (AMBER falls back to the static scale).",
}


def list_scenarios() -> list[str]:
    return list(SCENARIOS)


def build(name: str, base: SimConfig = BASE, hours: float | None = None, seed: int | None = None, **extra) -> SimConfig:
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario '{name}'; known: {', '.join(SCENARIOS)}")
    cfg = SCENARIOS[name](base)
    kw: dict = {"label": name}
    if hours is not None:
        kw["hours"] = hours
    if seed is not None:
        kw["seed"] = seed
    kw.update(extra)
    cfg = cfg.with_overrides(**kw)
    if name == "station_lane_failure" and hours is not None:
        cfg = _lane_failure(cfg).with_overrides(label=name)
    if name == "rcs_v2_lane_closure" and hours is not None:
        cfg = _lane_closure(cfg).with_overrides(label=name)
    return cfg
