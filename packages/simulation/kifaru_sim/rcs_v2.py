"""RCS v2 — port-anchored clearance chain model (Monte Carlo, vectorised NumPy).

Everything produced here is MODELLED. The model reproduces the method of the RCS v2 plan, Section 9: a population of
heavy trucks with a load distribution expressed as a fraction of the legal limit, measured at a port gate-out node, an
approved origin scale, a high-speed road screening node, a rolling verification lane and a static scale, each with its
own relative error. Three truck streams (port, origin, untokened) and a Load Compliance Token issued at the first
verified weighing point and honoured downstream.

Conventions
-----------
* Loads are fractions of the legal limit (1.0 = limit). Every scale error is a relative standard deviation.
* A screening node sends a truck for a closer look when ``reading × (1 + k·error) > limit``, with k = 2 (expanded
  uncertainty, k = 2, the same convention as the clearance engine). With the plan's defaults (85 % loading, 12 % spread,
  2.5 % road error, 3 % audits, 1.5 % overloaded) this gives a road-only static share of about 23 %, matching the plan.
* A tokened truck on the road is only checked for consistency: ``|road − token| ≤ 3·σ_combined`` where σ_combined is the
  quadrature sum of the two scale errors (about 8 % for port/origin tokens, about 11 % for road tokens).
* Common random numbers: all policies in one run share the same loads, scale errors and audit draws, so differences
  between policies are paired, not noise.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np

K_EXPANDED = 2.0  # expanded-uncertainty coverage factor used by the screening rule
MISMATCH_SIGMAS = 3.0  # token consistency tolerance = 3 combined standard deviations
OVERLOAD_MAX_FRAC = 0.15  # overloaded trucks are uniformly 0–15 % over the limit
POLICY_ALLOWANCE_PCT = 5.0  # Second Schedule discretion allowance upper bound, used for the "with allowance" comparison column
LANE_SPEED_KMH = 10.0
LANE_HEADWAY_M = 27.0  # 17 m truck + 10 m gap

SHARE_KEYS = (
    "road_only_static",
    "road_only_with_allowance",
    "v2_road_static",
    "v2_port_reweigh",
    "first_station_lane",
    "first_station_static",
    "later_station_lane",
    "later_station_static",
    "untokened_lane",
    "untokened_static",
)


@dataclass
class ChainParams:
    """Mirrors ``RcsModelIn`` in docs/02-architecture/rcs-v2-api-contract.md (same field names)."""

    avg_loading_pct: float = 85.0
    load_spread_pct: float = 12.0
    overload_prob: float = 0.015
    token_coverage: float = 0.9
    stream_mix: dict[str, float] | None = None  # {"port", "origin", "untokened"}; derived from coverage when None
    port_error_pct: float = 1.0
    origin_error_pct: float = 1.0
    road_error_pct: float = 2.5
    lane_error_pct: float = 1.0
    lane_margin_pct: float = 2.0
    allowance_pct: float = 0.0
    audit_rate: float = 0.03
    port_legal_grade: bool = False
    lane_legal_grade: bool = False
    trucks_per_day: float = 8000.0
    stop_minutes: float = 6.0
    lane_minutes: float = 1.5
    peak_per_hour: float = 500.0
    n: int = 200_000
    seed: int = 1

    def resolved_mix(self) -> dict[str, float]:
        if self.stream_mix:
            m = {k: float(self.stream_mix.get(k, 0.0)) for k in ("port", "origin", "untokened")}
            tot = sum(m.values())
            if tot <= 0:
                raise ValueError("stream_mix must have a positive total")
            return {k: v / tot for k, v in m.items()}
        c = min(max(self.token_coverage, 0.0), 1.0)
        return {"port": 0.6 * c, "origin": 0.4 * c, "untokened": 1.0 - c}

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stream_mix"] = self.resolved_mix()
        return d


@dataclass
class ChainResult:
    params: ChainParams
    shares: dict[str, float]
    truck_hours_saved_per_day: float
    truck_hours_saved_first_station: float
    baseline_first_station_static: float
    false_clear_rate: float
    lane_peak_per_hour: float
    lane_capacity_per_hour: float
    total_reweighs_v1: float
    total_reweighs_v2: float
    assumptions: list[str] = field(default_factory=list)

    @property
    def lane_ok(self) -> bool:
        return self.lane_peak_per_hour <= self.lane_capacity_per_hour

    def to_dict(self) -> dict:
        """Exactly the ``RcsModelOut`` shape of the API contract."""
        return {
            "inputs": self.params.to_dict(),
            "shares": {k: round(float(self.shares[k]), 3) for k in SHARE_KEYS},
            "truck_hours_saved_per_day": round(float(self.truck_hours_saved_per_day), 1),
            "truck_hours_saved_first_station": round(float(self.truck_hours_saved_first_station), 1),
            "baseline_first_station_static": round(float(self.baseline_first_station_static), 3),
            "false_clear_rate": round(float(self.false_clear_rate), 4),
            "lane_peak_per_hour": round(float(self.lane_peak_per_hour), 1),
            "lane_capacity_per_hour": round(float(self.lane_capacity_per_hour), 1),
            "lane_ok": bool(self.lane_ok),
            "total_reweighs_v1": round(float(self.total_reweighs_v1), 3),
            "total_reweighs_v2": round(float(self.total_reweighs_v2), 3),
            "assumptions": list(self.assumptions),
            "label": "MODELLED",
        }


def lane_capacity_per_hour(speed_kmh: float = LANE_SPEED_KMH, headway_m: float = LANE_HEADWAY_M) -> float:
    """Trucks per hour through one rolling verification lane: 10 km/h = 2.78 m/s, 27 m per truck -> 9.7 s -> ~370/h."""
    return 3600.0 / (headway_m / (speed_kmh / 3.6))


def _screen_over(reading: np.ndarray, rel_err: float, limit: float) -> np.ndarray:
    """Screening rule: the reading plus its expanded uncertainty reaches the limit."""
    return reading * (1.0 + K_EXPANDED * rel_err) > limit


def _certain_over(reading: np.ndarray, rel_err: float, limit: float) -> np.ndarray:
    return reading * (1.0 - K_EXPANDED * rel_err) > limit


def run_chain(params: ChainParams) -> ChainResult:
    p = params
    n = int(p.n)
    if n <= 0:
        raise ValueError("n must be positive")
    rng = np.random.default_rng(int(p.seed))
    mix = p.resolved_mix()

    e_port = p.port_error_pct / 100.0
    e_origin = p.origin_error_pct / 100.0
    e_road = p.road_error_pct / 100.0
    e_lane = p.lane_error_pct / 100.0
    allowance = p.allowance_pct / 100.0
    limit_alw = 1.0 + allowance  # the adjusted limit when the discretion allowance is applied
    lane_margin = 0.0 if p.lane_legal_grade else p.lane_margin_pct / 100.0
    port_k = 0.0 if p.port_legal_grade else K_EXPANDED

    # --------------------------------------------------------------- common random numbers
    mean = p.avg_loading_pct / 100.0
    sd = p.load_spread_pct / 100.0
    true = rng.normal(mean, sd, n)
    true = np.minimum(true, 0.999)  # loads that would exceed the limit are capped just below it (fleets bunch at the limit)
    true = np.maximum(true, 0.05)
    over = rng.random(n) < p.overload_prob
    true[over] = 1.0 + rng.uniform(0.0, OVERLOAD_MAX_FRAC, int(over.sum()))

    z_port, z_origin, z_road, z_lane, z_road2 = (rng.standard_normal(n) for _ in range(5))
    u_stream = rng.random(n)
    u_audit1 = rng.random(n)
    u_audit2 = rng.random(n)

    r_port = true * (1.0 + e_port * z_port)
    r_origin = true * (1.0 + e_origin * z_origin)
    r_road = true * (1.0 + e_road * z_road)  # first road station
    r_road2 = true * (1.0 + e_road * z_road2)  # a later road station
    r_lane = true * (1.0 + e_lane * z_lane)
    audit1 = u_audit1 < p.audit_rate
    audit2 = u_audit2 < p.audit_rate

    stream = np.full(n, 2, dtype=np.int8)  # 0 port, 1 origin, 2 untokened
    stream[u_stream < mix["port"]] = 0
    stream[(u_stream >= mix["port"]) & (u_stream < mix["port"] + mix["origin"])] = 1
    tokened_by_coverage = u_stream < p.token_coverage  # port-truck table: 'coverage' share carries a token

    # --------------------------------------------------------------- road-only screening (v1 baseline)
    road_only_rule = _screen_over(r_road, e_road, 1.0)
    road_only_static = road_only_rule | audit1
    # comparison column "road-only with the discretion allowance": the plan compares against the Second Schedule's
    # upper bound (5 %) whenever no allowance is configured; with a configured allowance that value is used instead
    alw_cmp = allowance if allowance > 0 else POLICY_ALLOWANCE_PCT / 100.0
    road_only_alw = _screen_over(r_road, e_road, 1.0 + alw_cmp) | audit1

    # --------------------------------------------------------------- port gate-out node (every truck is a port truck)
    port_green = r_port * (1.0 + port_k * e_port) <= limit_alw
    port_reweigh = ~port_green

    # token consistency on the road: |road / token − 1| ≤ 3 σ_combined
    tol_port = MISMATCH_SIGMAS * math.hypot(e_port, e_road)
    tol_origin = MISMATCH_SIGMAS * math.hypot(e_origin, e_road)
    tol_road = MISMATCH_SIGMAS * math.hypot(e_road, e_road)
    tol_lane = MISMATCH_SIGMAS * math.hypot(e_lane, e_road)
    mism_port = np.abs(r_road / r_port - 1.0) > tol_port
    mism_origin = np.abs(r_road / r_origin - 1.0) > tol_origin

    # v2 for port trucks (table 1): tokened trucks stop only on audit or mismatch; untokened use the absolute rule
    tokened_stop = audit1 | mism_port
    untokened_stop = _screen_over(r_road, e_road, limit_alw) | audit1  # absolute rule with the configured allowance
    v2_road_static = np.where(tokened_by_coverage, tokened_stop, untokened_stop)
    # false clears in the port-truck policy: trucks that continued whose true load is over the (adjusted) limit
    continued_v2 = ~v2_road_static
    truly_over = true > limit_alw
    false_clear = float(np.mean(truly_over & continued_v2 & ~(tokened_by_coverage & port_reweigh)))

    # --------------------------------------------------------------- mixed traffic at the first road station (table 2)
    is_port, is_origin, is_untok = stream == 0, stream == 1, stream == 2
    tokened = is_port | is_origin
    token_reading = np.where(is_port, r_port, r_origin)
    mism_tok = np.where(is_port, mism_port, mism_origin)
    tok_to_lane = tokened & (audit1 | mism_tok)
    # in the lane a tokened truck is checked for lane-vs-token consistency and certain overload only (token covers margin)
    tok_lane_static = tok_to_lane & (_certain_over(r_lane, e_lane, limit_alw) | (np.abs(r_lane / token_reading - 1.0) > MISMATCH_SIGMAS * math.hypot(e_lane, e_port)))

    untok_rule = _screen_over(r_road, e_road, limit_alw)
    untok_to_lane = is_untok & (untok_rule | audit1)
    untok_static = untok_to_lane & (r_lane * (1.0 + lane_margin) > limit_alw)

    first_lane = tok_to_lane | untok_to_lane
    first_static = tok_lane_static | untok_static
    baseline_first_static = untok_rule | (tokened & _screen_over(r_road, e_road, limit_alw))  # road-only, audits excluded

    n_untok = max(int(is_untok.sum()), 1)
    untok_lane_share = float(untok_to_lane.sum() / n_untok)
    untok_static_share = float(untok_static.sum() / n_untok)

    # --------------------------------------------------------------- later station: every truck carries a token
    # tokens now come from the port/origin node, the first road node (untokened greens) or the lane (lane greens)
    token2 = np.where(tokened, token_reading, np.where(untok_to_lane, r_lane, r_road))
    tol2 = np.where(is_port, tol_port, np.where(is_origin, tol_origin, np.where(untok_to_lane, tol_lane, tol_road)))
    mism2 = np.abs(r_road2 / token2 - 1.0) > tol2
    later_lane = audit2 | mism2
    later_static = later_lane & _certain_over(r_lane, e_lane, limit_alw) & ~first_static

    # --------------------------------------------------------------- aggregate
    shares = {
        "road_only_static": 100.0 * float(road_only_static.mean()),
        "road_only_with_allowance": 100.0 * float(road_only_alw.mean()),
        "v2_road_static": 100.0 * float(v2_road_static.mean()),
        "v2_port_reweigh": 100.0 * float(port_reweigh.mean()),
        "first_station_lane": 100.0 * float(first_lane.mean()),
        "first_station_static": 100.0 * float(first_static.mean()),
        "later_station_lane": 100.0 * float(later_lane.mean()),
        "later_station_static": 100.0 * float(later_static.mean()),
        "untokened_lane": 100.0 * untok_lane_share,
        "untokened_static": 100.0 * untok_static_share,
    }
    baseline_mixed = 100.0 * float(baseline_first_static.mean())

    per_point_hours = p.trucks_per_day / 100.0 / 60.0  # truck-hours per percentage point per minute of stop
    saved_v1_v2 = (shares["road_only_static"] - shares["v2_road_static"]) * per_point_hours * p.stop_minutes
    hours_base = baseline_mixed * per_point_hours * p.stop_minutes
    hours_v2 = shares["first_station_lane"] * per_point_hours * p.lane_minutes + shares["first_station_static"] * per_point_hours * p.stop_minutes
    saved_first = hours_base - hours_v2

    cap = lane_capacity_per_hour()
    lane_peak = p.peak_per_hour * untok_lane_share  # conservative: a peak hour made up of untokened trucks

    assumptions = [
        f"Loads ~ Normal({p.avg_loading_pct:g} % of limit, spread {p.load_spread_pct:g} % of limit), capped just below the limit; "
        f"{100 * p.overload_prob:g} % of trucks are overloaded by 0–{100 * OVERLOAD_MAX_FRAC:g} %.",
        f"Scale errors (relative SD): port {p.port_error_pct:g} %, origin {p.origin_error_pct:g} %, road WIM {p.road_error_pct:g} %, lane {p.lane_error_pct:g} %.",
        f"Screening rule: reading × (1 + {K_EXPANDED:g} × error) > limit. Token consistency: |road − token| ≤ {MISMATCH_SIGMAS:g} combined SD "
        f"({100 * tol_port:.1f} % port/origin tokens, {100 * tol_road:.1f} % road tokens).",
        f"Lane margin {p.lane_margin_pct:g} % ({'legal-grade lane, margin 0' if p.lane_legal_grade else 'lane not legal-grade'}); "
        f"port scale {'legal-grade, margin 0' if p.port_legal_grade else 'not legal-grade'}; discretion allowance {p.allowance_pct:g} %.",
        f"Random audits {100 * p.audit_rate:g} % of mainline greens. Stream mix: port {100 * mix['port']:.0f} %, origin {100 * mix['origin']:.0f} %, untokened {100 * mix['untokened']:.0f} %.",
        f"Truck-hours: {p.trucks_per_day:g} trucks/day, {p.stop_minutes:g} min per static stop, {p.lane_minutes:g} min per lane pass. "
        f"Lane peak assumes a {p.peak_per_hour:g} trucks/h peak of untokened trucks; lane capacity {cap:.0f}/h at {LANE_SPEED_KMH:g} km/h and {LANE_HEADWAY_M:g} m headway.",
        "'untokened_lane' and 'untokened_static' are shares of untokened trucks only; every other share is a share of all trucks.",
        "Fraud (plate swaps, cargo added after the first weighing) and legitimate weight changes are not modelled; they are covered by audits in the design.",
        "All figures are modelled under these assumptions and must be replaced with measured data (RCS v2 plan, Section 10).",
    ]
    return ChainResult(
        params=p,
        shares=shares,
        truck_hours_saved_per_day=saved_v1_v2,
        truck_hours_saved_first_station=saved_first,
        baseline_first_station_static=baseline_mixed,
        false_clear_rate=false_clear,
        lane_peak_per_hour=lane_peak,
        lane_capacity_per_hour=cap,
        total_reweighs_v1=shares["road_only_static"],
        total_reweighs_v2=shares["v2_road_static"] + shares["v2_port_reweigh"],
        assumptions=assumptions,
    )


# --------------------------------------------------------------------------------------------- Section 9 tables
def port_truck_table(base: ChainParams | None = None, loadings: tuple[float, ...] = (75.0, 80.0, 85.0, 90.0)) -> list[dict]:
    """Section 9, first table: port trucks at several average loadings (one run per row, same seed)."""
    base = base or ChainParams()
    rows = []
    for ld in loadings:
        r = run_chain(ChainParams(**{**asdict(base), "avg_loading_pct": ld}))
        s = r.shares
        rows.append({
            "avg_loading_pct": ld,
            "road_only_static": s["road_only_static"],
            "road_only_with_allowance": s["road_only_with_allowance"],
            "v2_road_static": s["v2_road_static"],
            "v2_port_reweigh": s["v2_port_reweigh"],
            "truck_hours_saved_per_day": r.truck_hours_saved_per_day,
        })
    return rows


def mixed_traffic_table(base: ChainParams | None = None, coverages: tuple[float, ...] = (0.3, 0.5, 0.7, 0.9)) -> list[dict]:
    """Section 9, second table: first road station with a rolling verification lane, by token coverage."""
    base = base or ChainParams()
    rows = []
    for c in coverages:
        r = run_chain(ChainParams(**{**asdict(base), "token_coverage": c, "stream_mix": None}))
        s = r.shares
        rows.append({
            "token_coverage": c,
            "first_station_lane": s["first_station_lane"],
            "first_station_static": s["first_station_static"],
            "road_only_baseline_static": r.baseline_first_station_static,
            "later_station_lane": s["later_station_lane"],
            "later_station_static": s["later_station_static"],
            "truck_hours_saved_first_station": r.truck_hours_saved_first_station,
        })
    return rows


def tables_markdown(base: ChainParams | None = None) -> str:
    base = base or ChainParams()
    t1 = port_truck_table(base)
    t2 = mixed_traffic_table(base)
    r85 = run_chain(ChainParams(**{**asdict(base), "avg_loading_pct": 85.0}))
    lines = [
        "# RCS v2 chain model — Section 9 tables (modelled)",
        "",
        f"`kifaru-sim v2` · {base.n:,} trucks per row · seed {base.seed} · **MODELLED under stated assumptions, not measured.**",
        "",
        "## Port trucks by average loading (shares of all trucks at the road station)",
        "",
        "| Average load (% of limit) | Road-only screening | Road-only with allowance | RCS v2 road stops | RCS v2 port re-weigh | Road truck-hours saved per day (v1 to v2) |",
        "|---|---|---|---|---|---|",
    ]
    for r in t1:
        lines.append(f"| {r['avg_loading_pct']:.0f} % | {r['road_only_static']:.1f} % | {r['road_only_with_allowance']:.1f} % | {r['v2_road_static']:.1f} % | {r['v2_port_reweigh']:.1f} % | about {r['truck_hours_saved_per_day']:.0f} |")
    lines += [
        "",
        f"The 'with allowance' column applies a {base.allowance_pct if base.allowance_pct > 0 else POLICY_ALLOWANCE_PCT:g} % discretion allowance to the road-only rule; "
        "the other columns use the configured allowance (`--set allowance_pct=5` applies it everywhere, including the port node).",
        "",
        "## Mixed traffic at the first station with a rolling verification lane (85 % loading)",
        "",
        "| Trucks with a port or origin token | Sent to the lane | Sent to a static scale | Road-only baseline (static) | Later station: lane | Later station: static | Truck-hours saved per day at the first station |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in t2:
        lines.append(f"| {100 * r['token_coverage']:.0f} % | {r['first_station_lane']:.1f} % | {r['first_station_static']:.1f} % | {r['road_only_baseline_static']:.1f} % | {r['later_station_lane']:.1f} % | {r['later_station_static']:.1f} % | about {r['truck_hours_saved_first_station']:.0f} |")
    s = r85.shares
    lines += [
        "",
        f"Untokened trucks alone (85 % loading): lane {s['untokened_lane']:.1f} %, static {s['untokened_static']:.1f} % of untokened trucks. "
        f"Lane peak {r85.lane_peak_per_hour:.0f} trucks/h against a capacity of {r85.lane_capacity_per_hour:.0f}/h "
        f"({'one lane per station is enough' if r85.lane_ok else 'a second lane is needed'}). False-clear rate {100 * r85.false_clear_rate:.2f} %.",
        "",
        "## Assumptions",
        "",
        *[f"- {a}" for a in r85.assumptions],
        "",
    ]
    return "\n".join(lines)
