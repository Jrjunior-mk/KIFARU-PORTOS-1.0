"""SmartPort port-process model (SimPy): existing port operations versus SmartPort, stages 3-11 of the port visit.

    arrivals -> [gate-in, G lanes] -> yard wait -> [loading, E equipment] -> [weighing, W bridges]
             -> [final clearance, C desks; document hold with probability h] -> [gate-out, G lanes] -> inland transit

Everything produced here is MODELLED. Calibration: with the defaults the `existing` policy gives a mean port dwell
(gate-in to gate-out) close to KPA's published 2023 truck turnaround of 6.7 hours (KPA annual bulletin via Kenya News
Agency); the yard-wait median is the parameter tuned to reach it. SmartPort assumptions (faster RFID/ANPR gates, the port
gate-out weigh node, pre-cleared documents, appointments aligned with container readiness) are design assumptions to be
replaced by shadow-pilot measurements. Sources: docs/06-operations/data-register.md.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace

import numpy as np
import simpy

KPA_TRUCK_TURNAROUND_H_2023 = 6.7


@dataclass
class PortSimConfig:
    trucks_per_day: float = 2400.0  # trucks collecting cargo at the port gates (estimated; KPA gate logs to replace)
    hours: float = 24.0
    gates_in: int = 12
    gates_out: int = 12
    gate_service_existing_s: float = 240.0
    gate_service_smart_s: float = 60.0
    loading_equipment: int = 70
    loading_minutes_container: float = 20.0
    loading_minutes_bulk: float = 30.0
    loading_minutes_general: float = 25.0
    weighbridges: int = 14
    weigh_service_existing_s: float = 300.0
    weigh_service_smart_s: float = 90.0
    clearance_desks: int = 16
    clearance_minutes: float = 6.0
    hold_prob_existing: float = 0.15
    hold_prob_smart: float = 0.05
    hold_minutes: float = 45.0
    appointment_smoothing: bool = True
    peak_factor: float = 1.5
    inland_distance_km: float = 482.0  # Mombasa-Nairobi (NCTTCA 21st edition)
    inland_speed_kmh: float = 45.0
    stop_prob: float = 0.3
    stop_minutes: float = 40.0
    seed: int = 1
    reps: int = 3
    # calibration parameters (not in the API form): container readiness wait in the yard
    yard_wait_existing_min: float = 315.0  # median; tuned so existing dwell is near 6.7 h
    yard_wait_smart_min: float = 180.0  # appointments booked against container readiness (design assumption)
    cargo_mix: tuple[float, float, float] = (0.7, 0.15, 0.15)  # container, bulk, general

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cargo_mix"] = list(self.cargo_mix)
        return d


def _ln(rng: np.random.Generator, median: float, sigma: float = 0.35) -> float:
    return float(rng.lognormal(math.log(max(median, 1e-6)), sigma))


def _arrivals(cfg: PortSimConfig, rng: np.random.Generator, smooth: bool) -> np.ndarray:
    """Non-homogeneous Poisson arrivals with a 07:00-17:00 peak (`peak_factor`), flattened when appointments smooth demand."""
    horizon = cfg.hours * 3600.0
    mean = cfg.trucks_per_day / 86400.0
    pf = 1.0 if smooth else cfg.peak_factor
    off = max(0.2, (24 - 10 * pf) / 14)  # keeps the daily mean near `mean`

    def rate(t: float) -> float:
        hour = (t / 3600.0) % 24
        return mean * (pf if 7 <= hour < 17 else off)

    lam_max = mean * max(pf, off, 1.0)
    t, out = 0.0, []
    while True:
        t += rng.exponential(1.0 / lam_max)
        if t >= horizon:
            return np.array(out)
        if rng.random() < rate(t) / lam_max:
            out.append(t)


def run_port(cfg: PortSimConfig, policy: str, seed: int | None = None) -> dict:
    smart = policy == "smartport"
    rng = np.random.default_rng(cfg.seed if seed is None else seed)
    env = simpy.Environment()
    gate_in = simpy.Resource(env, cfg.gates_in)
    gate_out = simpy.Resource(env, cfg.gates_out)
    loaders = simpy.Resource(env, cfg.loading_equipment)
    bridges = simpy.Resource(env, cfg.weighbridges)
    desks = simpy.Resource(env, cfg.clearance_desks)
    recs: list[dict] = []
    busy = {"gate_in": 0.0, "weigh": 0.0}
    qlen: list[int] = []
    arrivals = _arrivals(cfg, rng, smooth=smart and cfg.appointment_smoothing)
    end = cfg.hours * 3600.0

    def monitor():
        while env.now < end:
            qlen.append(len(gate_in.queue) + len(loaders.queue) + len(bridges.queue) + len(desks.queue) + len(gate_out.queue))
            yield env.timeout(60)

    def use(r: dict, res, service_s: float, key: str | None = None):
        t0 = env.now
        with res.request() as rq:
            yield rq
            r["wait"] += env.now - t0
            if key:
                busy[key] += service_s
            yield env.timeout(service_s)

    def truck(t_arr: float):
        r = {"arr": t_arr, "wait": 0.0}
        mix = int(rng.choice(3, p=list(cfg.cargo_mix)))
        load_min = (cfg.loading_minutes_container, cfg.loading_minutes_bulk, cfg.loading_minutes_general)[mix]
        gate_s = cfg.gate_service_smart_s if smart else cfg.gate_service_existing_s
        yield from use(r, gate_in, _ln(rng, gate_s), "gate_in")
        r["gate_in"] = env.now
        yield env.timeout(_ln(rng, (cfg.yard_wait_smart_min if smart else cfg.yard_wait_existing_min) * 60, 0.5))
        yield from use(r, loaders, _ln(rng, load_min * 60))
        ws = _ln(rng, cfg.weigh_service_smart_s if smart else cfg.weigh_service_existing_s, 0.25)
        yield from use(r, bridges, ws, "weigh")
        r["weigh_s"] = ws
        yield from use(r, desks, _ln(rng, cfg.clearance_minutes * 60 * (0.5 if smart else 1.0)))
        if rng.random() < (cfg.hold_prob_smart if smart else cfg.hold_prob_existing):
            yield env.timeout(_ln(rng, cfg.hold_minutes * 60, 0.6))
        yield from use(r, gate_out, _ln(rng, gate_s))
        r["gate_out"] = env.now
        transit = cfg.inland_distance_km / cfg.inland_speed_kmh * 3600
        if rng.random() < cfg.stop_prob:
            transit += _ln(rng, cfg.stop_minutes * 60, 0.6)
        r["transit_s"] = transit
        recs.append(r)

    def source():
        for t in arrivals:
            if t > env.now:
                yield env.timeout(t - env.now)
            env.process(truck(float(t)))

    env.process(source())
    env.process(monitor())
    env.run(until=end + 48 * 3600)  # drain window so every arrival exits
    done = recs
    dwell = np.array([r["gate_out"] - r["gate_in"] for r in done]) / 3600 if done else np.zeros(1)

    def mean(vals: list[float]) -> float:
        return float(np.mean(vals)) if vals else 0.0

    return {
        "trucks": float(len(done)),
        "avg_wait_min": mean([r["wait"] for r in done]) / 60,
        "avg_queue_len": mean(qlen),
        "max_queue_len": float(max(qlen or [0])),
        "avg_processing_min": mean([r["gate_out"] - r["arr"] for r in done]) / 60,
        "weigh_service_min": mean([r["weigh_s"] for r in done]) / 60,
        "throughput_per_hour": float(sum(1 for r in done if r["gate_out"] <= end) / cfg.hours),
        "avg_dwell_h": float(dwell.mean()),
        "p90_dwell_h": float(np.percentile(dwell, 90)),
        "avg_transit_h": mean([r["transit_s"] for r in done]) / 3600,
        "gate_in_utilisation": float(busy["gate_in"] / (cfg.gates_in * end)),
        "weigh_utilisation": float(busy["weigh"] / (cfg.weighbridges * end)),
    }


def compare(cfg: PortSimConfig) -> dict:
    """PortSimOut: both policies over `reps` replications with common seeds, deltas, assumptions and the calibration note."""
    out: dict[str, dict] = {}
    for pol in ("existing", "smartport"):
        runs = [run_port(cfg, pol, seed=cfg.seed + k) for k in range(max(1, cfg.reps))]
        out[pol] = {k: round(float(np.mean([r[k] for r in runs])), 3) for k in runs[0]}
    deltas: dict[str, float] = {}
    for k, v in out["existing"].items():
        s = out["smartport"][k]
        deltas[k] = round(s - v, 3)
        deltas[k + "_pct"] = round((s - v) / v * 100, 1) if v else 0.0
    ex = out["existing"]["avg_dwell_h"]
    return {
        "label": "MODELLED",
        "scenarios": out,
        "deltas": deltas,
        "calibration_note": (f"Existing-operations dwell {ex:.1f} h against KPA's published 2023 truck turnaround of "
                             f"{KPA_TRUCK_TURNAROUND_H_2023} h; the yard-wait median ({cfg.yard_wait_existing_min:.0f} min) is the tuned parameter."),
        "assumptions": [
            f"{cfg.trucks_per_day:.0f} trucks a day at the port gates (estimated; replace with KPA gate logs); day-time peak factor {cfg.peak_factor} unless appointments smooth arrivals.",
            f"Gate service {cfg.gate_service_existing_s:.0f} s manual vs {cfg.gate_service_smart_s:.0f} s RFID/ANPR; weighing {cfg.weigh_service_existing_s:.0f} s static vs {cfg.weigh_service_smart_s:.0f} s at the port gate-out node.",
            f"Document holds {cfg.hold_prob_existing:.0%} existing vs {cfg.hold_prob_smart:.0%} with pre-cleared data sharing; median hold {cfg.hold_minutes:.0f} min; SmartPort clearance desk time halved.",
            f"Yard wait median {cfg.yard_wait_existing_min:.0f} min existing vs {cfg.yard_wait_smart_min:.0f} min with readiness-based appointments (design assumption).",
            f"Inland transit at {cfg.inland_speed_kmh:.0f} km/h over {cfg.inland_distance_km:.0f} km is a free-flow estimate; NCTTCA measured Mombasa-Nairobi at 66 h (RECTS, 2025), so most observed transit time is stoppage and seal-handling delay outside this model.",
        ],
        "benchmarks": [],
        "inputs": cfg.to_dict(),
    }


def with_overrides(cfg: PortSimConfig, **kw) -> PortSimConfig:
    return replace(cfg, **kw)


def table_markdown(res: dict) -> str:
    rows = [("avg_dwell_h", "Port dwell, mean (h)"), ("p90_dwell_h", "Port dwell, P90 (h)"), ("avg_wait_min", "Queue waiting per truck (min)"),
            ("avg_queue_len", "Mean trucks queuing"), ("max_queue_len", "Max trucks queuing"), ("weigh_service_min", "Weighbridge service (min)"),
            ("throughput_per_hour", "Gate-out throughput (trucks/h)"), ("gate_in_utilisation", "Gate-in utilisation"), ("weigh_utilisation", "Weighbridge utilisation")]
    lines = ["| KPI | Existing | SmartPort | Change |", "|---|---|---|---|"]
    for k, lab in rows:
        e, s = res["scenarios"]["existing"][k], res["scenarios"]["smartport"][k]
        lines.append(f"| {lab} | {e:.2f} | {s:.2f} | {res['deltas'].get(k + '_pct', 0):+.1f} % |")
    return "\n".join(lines) + f"\n\n{res['calibration_note']} All figures MODELLED.\n"
