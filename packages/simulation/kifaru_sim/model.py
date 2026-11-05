"""Discrete-event model of a weighing station (SimPy) — Phase 5 DT-02.

Everything produced here is MODELLED, not measured. Arrivals are synthetic (non-homogeneous Poisson with a
time-of-day profile); service times are lognormal with documented medians; truck masses come from
``kifaru_wim_dsp.signal_gen.random_truck``; clearance decisions come from the deterministic engine
``kifaru.services.clearance_engine.decide`` so the simulation and the live platform can never disagree on policy.

Station layout (one direction of travel):

    arrivals --> [WIM pre-screen, N lanes] --GREEN--> exit
                           |-- AMBER --> [static scale, M bays] --> exit
                           |-- RED   --> [static scale] --> [inspection bay] --> exit
                           (optional gate hold for a share of trucks: delayed cargo release)

Baseline policy ``all_stop`` = the pre-platform situation: every truck queues for the static scale (no WIM
pre-screen); the engine decision is still computed as a "shadow" so the GREEN/AMBER/RED mix is comparable.

RCS v2 policy ``rcs_v2`` adds the Load Compliance Token and the rolling verification lane:

    arrivals --> [WIM screening node] --GREEN (token consistent / clear with margin)--> exit
                           |-- AMBER --> [rolling verification lane, L bays, ~10 km/h] --GREEN--> exit (lane token)
                           |                                            |-- AMBER/RED --> [static scale] ...
                           |-- RED   --> [static scale] --> [inspection bay] --> exit

A share ``token_coverage`` of arriving trucks carries a port or origin token (weight known to ``token_error``); on the
road they are only checked for consistency with the token. ``cargo_change_prob`` of tokened trucks changed their load
after the token was issued, which the consistency check catches. When the lane is closed (``lane_closures``) AMBER
trucks fall back to the static scale, as in v1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Literal

import numpy as np
import simpy

from kifaru.services import clearance_engine as ce
from kifaru.services.limits import DEFAULT_LIMITS, LimitSet
from kifaru_wim_dsp.signal_gen import random_truck

Policy = Literal["all_stop", "rolling", "rcs_v2"]

# Hour-of-day multipliers (index = hour 0..23, mean = 1.0). Shape: quiet night, morning build-up from the port
# gate opening, mid-morning peak, afternoon plateau, evening peak as port gates release the day's trucks.
# SYNTHETIC — to be replaced by observed Mariakani counts in Phase 7.
DEFAULT_TOD_PROFILE: tuple[float, ...] = (
    0.35, 0.30, 0.30, 0.35, 0.50, 0.75,  # 00-05
    1.05, 1.30, 1.45, 1.40, 1.30, 1.20,  # 06-11
    1.10, 1.15, 1.25, 1.35, 1.45, 1.40,  # 12-17
    1.25, 1.05, 0.85, 0.65, 0.50, 0.40,  # 18-23
)

AXLE_GROUP_GAP_M = 2.0  # axles closer than this belong to the same group (tandem/tridem)


@dataclass
class SimConfig:
    # horizon
    hours: float = 12.0
    start_hour: int = 6  # local time-of-day at t = 0
    # arrivals
    arrivals_per_hour: float = 60.0  # mean arrival rate (one direction) before the time-of-day profile is applied
    arrival_multiplier: float = 1.0  # scenario knob (+20 % => 1.2)
    tod_profile: tuple[float, ...] = DEFAULT_TOD_PROFILE
    slot_cap_per_15min: int | None = None  # dynamic slot allocation: max arrivals per 15-min window
    # WIM pre-screen
    wim_lanes: int = 2
    wim_service_median_s: float = 6.0
    wim_service_sigma: float = 0.25
    # (start_s, duration_s, lanes_down). While a lane is down its share of trucks cannot be pre-screened and is
    # sent to the static scale (fallback = all-stop for that lane), and the WIM capacity is reduced accordingly.
    lane_failures: tuple[tuple[float, float, int], ...] = ()
    # static scale
    static_bays: int = 5
    static_service_median_s: float = 240.0
    static_service_sigma: float = 0.40
    # inspection bay
    inspection_bays: int = 2
    inspection_median_s: float = 1500.0
    inspection_sigma: float = 0.50
    inspection_rate: float = 0.01  # share of trucks selected for physical inspection regardless of weight
    # policy
    policy: Policy = "rolling"
    priority_queue: bool = False  # priority for perishable / hazardous cargo at the static scale
    priority_share: float = 0.12
    # RCS v2 (policy "rcs_v2"): tokens and the rolling verification lane
    token_coverage: float = 0.9  # share of arriving trucks with a port or origin Load Compliance Token
    token_port_share: float = 0.6  # of tokened trucks, share from the port (rest: approved origin scales)
    token_error: float = 0.01  # relative 1-sigma error of the port / origin scale behind the token
    cargo_change_prob: float = 0.02  # tokened trucks whose load changed after the token (caught by the consistency check)
    lane_bays: int = 1  # rolling verification lanes
    lane_service_median_s: float = 90.0  # a lane pass costs about 1.5 min (plan assumption)
    lane_service_sigma: float = 0.3
    lane_rel_uncertainty: float = 0.01  # expanded (k=2) relative uncertainty of the lane's per-wheel scales
    lane_closures: tuple[tuple[float, float], ...] = ()  # (start_s, duration_s): lane closed, AMBER falls back to static
    # gate hold (delayed cargo release)
    release_hold_prob: float = 0.0
    release_hold_median_s: float = 900.0
    release_hold_sigma: float = 0.5
    # truck population and measurement model
    overload_prob: float = 0.15
    sensor_fault_prob: float = 0.03
    sensor_degraded_prob: float = 0.02
    unregistered_prob: float = 0.05
    identity_p_both: float = 0.80  # RFID + ANPR agree
    identity_p_rfid_only: float = 0.10
    identity_p_anpr_only: float = 0.08  # remainder => low-confidence / unknown reads
    wim_rel_uncertainty: float = 0.025  # expanded (k=2) relative uncertainty of WIM loads
    identity_min_confidence: float = 0.90
    audit_rate: float = 0.02
    limits: LimitSet = DEFAULT_LIMITS
    # misc
    seed: int = 0
    monitor_interval_s: float = 60.0
    label: str = "custom"

    @property
    def horizon_s(self) -> float:
        return self.hours * 3600.0

    def with_overrides(self, **kw) -> SimConfig:
        return replace(self, **kw)


@dataclass
class TruckRecord:
    truck_id: int
    arrival_s: float
    exit_s: float = math.nan
    wait_wim_s: float = 0.0
    wait_static_s: float = 0.0
    wait_inspection_s: float = 0.0
    hold_s: float = 0.0
    decision: str = ""
    stopped: bool = False
    stop_reason: str = ""  # all_stop_policy | amber | red | inspection_sample | lane_down | hold | ""
    priority: bool = False
    gvm_kg: float = 0.0
    axle_config: str = ""
    rules_fired: tuple[str, ...] = ()
    # RCS v2
    stream: str = "untokened"  # port | origin | untokened
    route: str = "continue"
    lane_pass: bool = False
    wait_lane_s: float = 0.0

    @property
    def time_in_system_s(self) -> float:
        return self.exit_s - self.arrival_s


@dataclass
class SimResult:
    config: SimConfig
    trucks: list[TruckRecord]
    series_t_s: np.ndarray
    queue_wim: np.ndarray
    queue_static: np.ndarray
    queue_inspection: np.ndarray
    static_busy_s: float
    wim_busy_s: float
    inspection_busy_s: float
    end_s: float
    queue_lane: np.ndarray = field(default_factory=lambda: np.zeros(0))
    lane_busy_s: float = 0.0

    # ---- convenience metrics ---------------------------------------------------------------------------
    def tis_minutes(self) -> np.ndarray:
        return np.array([t.time_in_system_s for t in self.trucks]) / 60.0

    def metrics(self) -> dict:
        n = len(self.trucks)
        tis = self.tis_minutes()
        decisions = [t.decision for t in self.trucks]
        stopped = sum(1 for t in self.trucks if t.stopped)
        waits_static = np.array([t.wait_static_s for t in self.trucks if t.stopped]) if stopped else np.zeros(1)
        prio = [t for t in self.trucks if t.priority]
        lane = [t for t in self.trucks if t.lane_pass]
        return {
            "pct_lane": 100.0 * len(lane) / n if n else 0.0,
            "pct_tokened": 100.0 * sum(1 for t in self.trucks if t.stream != "untokened") / n if n else 0.0,
            "mean_wait_lane_s": float(np.mean([t.wait_lane_s for t in lane])) if lane else 0.0,
            "max_queue_lane": int(self.queue_lane.max()) if len(self.queue_lane) else 0,
            "lane_utilisation": self.lane_busy_s / (self.config.lane_bays * self.end_s) if self.config.lane_bays and self.end_s else 0.0,
            "trucks": n,
            "mean_tis_min": float(tis.mean()) if n else 0.0,
            "p90_tis_min": float(np.percentile(tis, 90)) if n else 0.0,
            "p90_tis_priority_min": float(np.percentile([t.time_in_system_s for t in prio], 90) / 60.0) if prio else 0.0,
            "mean_wait_static_s": float(waits_static.mean()),
            "mean_queue_static": float(self.queue_static.mean()) if len(self.queue_static) else 0.0,
            "max_queue_static": int(self.queue_static.max()) if len(self.queue_static) else 0,
            "mean_queue_wim": float(self.queue_wim.mean()) if len(self.queue_wim) else 0.0,
            "max_queue_wim": int(self.queue_wim.max()) if len(self.queue_wim) else 0,
            "pct_stopped": 100.0 * stopped / n if n else 0.0,
            "n_stopped": stopped,
            "n_not_stopped": n - stopped,
            "pct_green": 100.0 * decisions.count("GREEN") / n if n else 0.0,
            "pct_amber": 100.0 * decisions.count("AMBER") / n if n else 0.0,
            "pct_red": 100.0 * decisions.count("RED") / n if n else 0.0,
            "static_utilisation": self.static_busy_s / (self.config.static_bays * self.end_s) if self.config.static_bays and self.end_s else 0.0,
            "wim_utilisation": self.wim_busy_s / (self.config.wim_lanes * self.end_s) if self.config.wim_lanes and self.end_s else 0.0,
            "inspection_utilisation": self.inspection_busy_s / (self.config.inspection_bays * self.end_s) if self.end_s else 0.0,
            "drain_min": max(0.0, (self.end_s - self.config.horizon_s) / 60.0),
        }


# ------------------------------------------------------------------------------------------------------ arrivals
def tod_rate(cfg: SimConfig, t_s: float) -> float:
    """Instantaneous arrival rate (per hour) at simulation time t."""
    hour = (cfg.start_hour + t_s / 3600.0) % 24.0
    i = int(hour) % 24
    frac = hour - int(hour)
    p = cfg.tod_profile
    mult = p[i] * (1 - frac) + p[(i + 1) % 24] * frac  # linear interpolation between hours
    return cfg.arrivals_per_hour * cfg.arrival_multiplier * mult


def generate_arrivals(cfg: SimConfig, rng: np.random.Generator) -> np.ndarray:
    """Non-homogeneous Poisson arrivals by thinning; optionally smoothed by a per-15-min booking cap."""
    lam_max = cfg.arrivals_per_hour * cfg.arrival_multiplier * max(cfg.tod_profile)
    if lam_max <= 0:
        return np.array([])
    t = 0.0
    out: list[float] = []
    while True:
        t += rng.exponential(3600.0 / lam_max)
        if t >= cfg.horizon_s:
            break
        if rng.random() < tod_rate(cfg, t) / lam_max:
            out.append(t)
    arrivals = np.array(out)
    if cfg.slot_cap_per_15min is not None:
        arrivals = apply_slot_cap(arrivals, cfg.slot_cap_per_15min, rng)
    return arrivals


def apply_slot_cap(arrivals: np.ndarray, cap: int, rng: np.random.Generator, window_s: float = 900.0) -> np.ndarray:
    """Dynamic slot allocation: trucks beyond the booking cap in a 15-min window are shifted to the next window.
    Models a booking system that smooths demand; the shift is a booking delay, not time at the station."""
    if len(arrivals) == 0:
        return arrivals
    arrivals = np.sort(arrivals)
    out: list[float] = []
    carry: list[float] = []
    n_windows = int(arrivals.max() // window_s) + 1 + len(arrivals) // max(cap, 1) + 1
    idx = 0
    for w in range(n_windows):
        _lo, hi = w * window_s, (w + 1) * window_s
        current = list(carry)
        carry = []
        while idx < len(arrivals) and arrivals[idx] < hi:
            current.append(arrivals[idx])
            idx += 1
        current.sort()
        kept, pushed = current[:cap], current[cap:]
        out.extend(kept)
        # pushed trucks arrive uniformly in the next window
        carry = [hi + rng.uniform(0, window_s) for _ in pushed]
        if idx >= len(arrivals) and not carry:
            break
    out.extend(carry)
    return np.sort(np.array(out))


# -------------------------------------------------------------------------------------------- truck + measurement
def _lognormal(rng: np.random.Generator, median: float, sigma: float) -> float:
    return float(rng.lognormal(math.log(max(median, 1e-6)), sigma))


def _group_axles(spacings: list[float]) -> list[int]:
    groups = [1]
    for s in spacings:
        if s < AXLE_GROUP_GAP_M:
            groups[-1] += 1
        else:
            groups.append(1)
    return groups


def build_measurement_and_identity(cfg: SimConfig, rng: np.random.Generator) -> tuple[ce.MeasurementInput, ce.IdentityInput, ce.VehicleInput | None, dict]:
    """Synthetic truck -> engine inputs. Uses random_truck for the mass/axle model, no 8 kHz waveform synthesis
    (that path is exercised by the API simulator; here we need thousands of trucks per second)."""
    truck = random_truck(rng, overload_prob=cfg.overload_prob)
    group_sizes = _group_axles(truck.axle_spacings_m)
    axle_config = "+".join(str(g) for g in group_sizes)
    axles: list[ce.AxleInput] = []
    g_no, remaining = 1, group_sizes[0]
    for i, load in enumerate(truck.axle_loads_kg):
        if remaining == 0:
            g_no += 1
            remaining = group_sizes[g_no - 1]
        u = cfg.wim_rel_uncertainty * load
        axles.append(ce.AxleInput(index=i, load_kg=float(load), u_kg=float(u), group_no=g_no))
        remaining -= 1
    gvm = float(sum(a.load_kg for a in axles))
    gvm_u = float(math.sqrt(sum(a.u_kg**2 for a in axles)))

    flags: list[str] = []
    health = {k: "ok" for k in ("P1", "P2", "P3", "BP")}
    if rng.random() < cfg.sensor_fault_prob:
        k = str(rng.choice(list(health)))
        health[k] = "fault"
        flags.append("sensor_fault")
    elif rng.random() < cfg.sensor_degraded_prob:
        flags.append("sensor_degraded")
    m = ce.MeasurementInput(gvm_kg=gvm, gvm_u_kg=gvm_u, axles=axles, detected_axle_config=axle_config, quality_flags=flags, sensor_health=health, speed_mps=truck.speed_mps, source="simulated")

    # identity
    registered = rng.random() >= cfg.unregistered_prob
    vehicle = None
    if registered:
        max_gvm = cfg.limits.gvm_limit_for_config(group_sizes)
        vehicle = ce.VehicleInput(vehicle_id=f"SIMV{int(rng.integers(1, 5000)):05d}", plate=f"KD{rng.choice(list('ABCDEFGH'))} {int(rng.integers(100, 999))}X", axle_config=axle_config, tare_kg=int(gvm * 0.35), max_gvm_kg=int(max_gvm))
        r = rng.random()
        if r < cfg.identity_p_both:
            conf, method = float(1 - (1 - rng.uniform(0.85, 0.99)) * (1 - rng.uniform(0.95, 0.999))), "rfid+anpr"
        elif r < cfg.identity_p_both + cfg.identity_p_rfid_only:
            conf, method = float(rng.uniform(0.90, 0.97)), "rfid"
        elif r < cfg.identity_p_both + cfg.identity_p_rfid_only + cfg.identity_p_anpr_only:
            conf, method = float(rng.uniform(0.80, 0.95)), "anpr"
        else:
            conf, method = float(rng.uniform(0.4, 0.8)), "anpr"
        identity = ce.IdentityInput(confidence=conf, vehicle_id=vehicle.vehicle_id, method=method)
    else:
        identity = ce.IdentityInput(confidence=float(rng.uniform(0.6, 0.95)), vehicle_id=None, method="anpr")
    meta = {"gvm_kg": gvm, "axle_config": axle_config, "truck": truck}
    return m, identity, vehicle, meta


# ----------------------------------------------------------------------------------------------------- the model
class StationModel:
    def __init__(self, cfg: SimConfig, arrivals: np.ndarray | None = None) -> None:
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.env = simpy.Environment()
        self.wim = simpy.Resource(self.env, capacity=max(1, cfg.wim_lanes))
        self.static = simpy.PriorityResource(self.env, capacity=max(1, cfg.static_bays)) if cfg.priority_queue else simpy.Resource(self.env, capacity=max(1, cfg.static_bays))
        self.inspection = simpy.Resource(self.env, capacity=max(1, cfg.inspection_bays))
        self.lane = simpy.Resource(self.env, capacity=max(1, cfg.lane_bays))
        self.lane_closed = False
        self.arrivals = np.asarray(arrivals) if arrivals is not None else generate_arrivals(cfg, self.rng)
        self.trucks: list[TruckRecord] = []
        self.in_system = 0
        self.arrivals_done = False
        self.series_t: list[float] = []
        self.q_wim: list[int] = []
        self.q_static: list[int] = []
        self.q_insp: list[int] = []
        self.q_lane: list[int] = []
        self.lane_busy = 0.0
        self.static_busy = 0.0
        self.wim_busy = 0.0
        self.insp_busy = 0.0
        self.lanes_down = 0

    # --- processes ------------------------------------------------------------------------------------------
    def _source(self):
        for i, t in enumerate(self.arrivals):
            delay = t - self.env.now
            if delay > 0:
                yield self.env.timeout(delay)
            rec = TruckRecord(truck_id=i, arrival_s=float(self.env.now))
            rec.priority = bool(self.rng.random() < self.cfg.priority_share)
            self.trucks.append(rec)
            self.in_system += 1
            self.env.process(self._truck(rec))
        self.arrivals_done = True

    def _lane_failure(self, start_s: float, duration_s: float, lanes_down: int):
        yield self.env.timeout(start_s)
        n = min(lanes_down, self.wim.capacity)
        reqs = [self.wim.request() for _ in range(n)]
        for r in reqs:
            yield r
        self.lanes_down += n
        yield self.env.timeout(duration_s)
        self.lanes_down -= n
        for r in reqs:
            self.wim.release(r)

    def _lane_closure(self, start_s: float, duration_s: float):
        yield self.env.timeout(start_s)
        self.lane_closed = True
        yield self.env.timeout(duration_s)
        self.lane_closed = False

    def _routed_to_failed_lane(self) -> bool:
        """A truck arriving while a lane is down is in that lane with probability lanes_down / lanes."""
        if self.lanes_down <= 0:
            return False
        return bool(self.rng.random() < self.lanes_down / max(1, self.cfg.wim_lanes))

    def _monitor(self):
        while True:
            self.series_t.append(float(self.env.now))
            self.q_wim.append(len(self.wim.queue))
            self.q_static.append(len(self.static.queue))
            self.q_insp.append(len(self.inspection.queue))
            self.q_lane.append(len(self.lane.queue))
            if self.arrivals_done and self.in_system == 0 and self.env.now >= self.cfg.horizon_s:
                return
            yield self.env.timeout(self.cfg.monitor_interval_s)

    def _decide(self, rec: TruckRecord) -> ce.ClearanceResult:
        m, ident, veh, meta = build_measurement_and_identity(self.cfg, self.rng)
        rec.gvm_kg, rec.axle_config = meta["gvm_kg"], meta["axle_config"]
        self._last_inputs = (m, ident, veh)
        token = None
        if self.cfg.policy == "rcs_v2" and veh is not None and self.rng.random() < self.cfg.token_coverage:
            src = "port" if self.rng.random() < self.cfg.token_port_share else "origin"
            rec.stream = src
            true_gvm = meta["gvm_kg"]
            # the token holds the weight at the first trusted point; a share of trucks changed cargo since (detected on the road)
            at_issue = true_gvm * (1 - self.rng.uniform(0.10, 0.30)) if self.rng.random() < self.cfg.cargo_change_prob else true_gvm
            token_gvm = at_issue * (1 + self.rng.normal(0, self.cfg.token_error))
            token = ce.TokenInput(f"SIMT{rec.truck_id}", f"LCT-SIM{rec.truck_id:06d}", src, ce.TRUST_TIER_BY_SOURCE[src], gvm_kg=float(token_gvm))
        lane_available = self.cfg.policy == "rcs_v2" and self.cfg.lane_bays > 0 and not self.lane_closed
        res = ce.decide(m, ident, veh, None, limits=self.cfg.limits, identity_min_confidence=self.cfg.identity_min_confidence, audit_rate=self.cfg.audit_rate,
                        audit_seed=int(self.rng.integers(0, 2**31 - 1)), token=token, node_kind="road_mainline", lane_available=lane_available)
        rec.decision = res.decision
        rec.route = res.route
        rec.rules_fired = tuple(r["rule"] for r in res.rules_fired)
        return res

    def _decide_in_lane(self, rec: TruckRecord) -> ce.ClearanceResult:
        """Rolling verification lane: the same truck measured on 1 % per-wheel scales with the dimension portal."""
        m, ident, veh = self._last_inputs
        axles = [ce.AxleInput(a.index, a.load_kg, self.cfg.lane_rel_uncertainty * a.load_kg, a.group_no) for a in m.axles]
        gvm_u = float(math.sqrt(sum(a.u_kg**2 for a in axles)))
        lane_m = ce.MeasurementInput(gvm_kg=m.gvm_kg, gvm_u_kg=gvm_u, axles=axles, detected_axle_config=m.detected_axle_config, quality_flags=[], sensor_health={}, speed_mps=2.8, source="simulated")
        res = ce.decide(lane_m, ident, veh, None, limits=self.cfg.limits, identity_min_confidence=self.cfg.identity_min_confidence, audit_rate=0.0,
                        audit_seed=int(self.rng.integers(0, 2**31 - 1)), node_kind="verification_lane", lane_available=False)
        rec.decision = res.decision
        rec.route = res.route
        rec.rules_fired = rec.rules_fired + tuple("LANE:" + r["rule"] for r in res.rules_fired)
        return res

    def _truck(self, rec: TruckRecord):
        cfg, env = self.cfg, self.env
        inspect = bool(self.rng.random() < cfg.inspection_rate)
        if cfg.policy in ("rolling", "rcs_v2") and self._routed_to_failed_lane():
            rec.stop_reason = "lane_down"
            self._decide(rec)
            needs_static = True
            inspect = inspect or rec.decision == "RED"
        elif cfg.policy == "rolling":
            t0 = env.now
            with self.wim.request() as req:
                yield req
                rec.wait_wim_s = env.now - t0
                svc = _lognormal(self.rng, cfg.wim_service_median_s, cfg.wim_service_sigma)
                self.wim_busy += svc
                yield env.timeout(svc)
            self._decide(rec)
            needs_static = rec.decision in ("AMBER", "RED") or inspect
            if needs_static:
                rec.stop_reason = rec.decision.lower() if rec.decision != "GREEN" else "inspection_sample"
        elif cfg.policy == "rcs_v2":
            t0 = env.now
            with self.wim.request() as req:
                yield req
                rec.wait_wim_s = env.now - t0
                svc = _lognormal(self.rng, cfg.wim_service_median_s, cfg.wim_service_sigma)
                self.wim_busy += svc
                yield env.timeout(svc)
            self._decide(rec)
            needs_static = rec.decision == "RED" or inspect
            if rec.route == "verification_lane" and not self.lane_closed:
                # roll through the verification lane at ~10 km/h: not a stop, but it takes lane time
                rec.lane_pass = True
                t1 = env.now
                with self.lane.request() as lreq:
                    yield lreq
                    rec.wait_lane_s = env.now - t1
                    svc = _lognormal(self.rng, cfg.lane_service_median_s, cfg.lane_service_sigma)
                    self.lane_busy += svc
                    yield env.timeout(svc)
                self._decide_in_lane(rec)
                needs_static = needs_static or rec.decision in ("AMBER", "RED")
                if needs_static:
                    rec.stop_reason = "lane_" + rec.decision.lower() if rec.decision != "GREEN" else "inspection_sample"
            elif rec.decision == "AMBER":
                needs_static = True  # no lane (closed or not built): v1 behaviour
                rec.stop_reason = "amber_no_lane"
            elif needs_static:
                rec.stop_reason = rec.decision.lower() if rec.decision != "GREEN" else "inspection_sample"
        else:  # all_stop baseline: no pre-screen, shadow decision only
            rec.stop_reason = "all_stop_policy"
            self._decide(rec)
            needs_static = True
            inspect = inspect or rec.decision == "RED"
        if rec.decision == "RED":
            inspect = True

        if needs_static:
            rec.stopped = True
            t0 = env.now
            prio = 0 if rec.priority else 1
            req = self.static.request(priority=prio) if cfg.priority_queue else self.static.request()
            with req:
                yield req
                rec.wait_static_s = env.now - t0
                svc = _lognormal(self.rng, cfg.static_service_median_s, cfg.static_service_sigma)
                self.static_busy += svc
                yield env.timeout(svc)
        if inspect:
            rec.stopped = True
            t0 = env.now
            with self.inspection.request() as req:
                yield req
                rec.wait_inspection_s = env.now - t0
                svc = _lognormal(self.rng, cfg.inspection_median_s, cfg.inspection_sigma)
                self.insp_busy += svc
                yield env.timeout(svc)
        if cfg.release_hold_prob > 0 and self.rng.random() < cfg.release_hold_prob:
            rec.stopped = True
            rec.stop_reason = rec.stop_reason or "hold"
            hold = _lognormal(self.rng, cfg.release_hold_median_s, cfg.release_hold_sigma)
            rec.hold_s = hold
            yield env.timeout(hold)
        rec.exit_s = float(env.now)
        self.in_system -= 1

    # --- run ----------------------------------------------------------------------------------------------
    def run(self) -> SimResult:
        self.env.process(self._source())
        self.env.process(self._monitor())
        for start, dur, n in self.cfg.lane_failures:
            self.env.process(self._lane_failure(start, dur, n))
        for start, dur in self.cfg.lane_closures:
            self.env.process(self._lane_closure(start, dur))
        self.env.run()
        return SimResult(
            config=self.cfg,
            trucks=self.trucks,
            series_t_s=np.array(self.series_t),
            queue_wim=np.array(self.q_wim),
            queue_static=np.array(self.q_static),
            queue_inspection=np.array(self.q_insp),
            static_busy_s=self.static_busy,
            wim_busy_s=self.wim_busy,
            inspection_busy_s=self.insp_busy,
            end_s=float(self.env.now),
            queue_lane=np.array(self.q_lane),
            lane_busy_s=self.lane_busy,
        )


def run_model(cfg: SimConfig, arrivals: np.ndarray | None = None) -> SimResult:
    """Run one replication. Deterministic for a fixed ``cfg.seed`` (and fixed arrivals, if given)."""
    return StationModel(cfg, arrivals=arrivals).run()
