"""WIM + identification simulator (Phase 2 deliverable). Everything it produces is tagged source=simulated.

It picks a registered vehicle (or an unregistered plate), builds a physically-plausible truck profile for the
vehicle's axle configuration, synthesises 8 kHz lane signals, runs the SAME DSP pipeline the firmware mirrors, and
simulates ANPR/RFID reads with realistic failure modes (misread, missing tag, cloned tag).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from kifaru_wim_dsp import (
    ChannelCalibration,
    LaneGeometry,
    SensorModel,
    TruckProfile,
    generate_pass,
    process_pass,
)
from kifaru_wim_dsp.signal_gen import PROFILES

from ..models import Lane, Vehicle, WeighingEvent
from . import weighing_service

CONFIG_TO_PROFILE = {
    "1+1": "2A_rigid",
    "1+2": "3A_rigid",
    "1+1+2": "4A_semi_1+1+2",
    "1+2+2": "5A_semi_1+2+2",
    "1+2+3": "6A_semi_1+2+3",
    "1+3+3": "7A_semi_1+3+3",
}


@dataclass
class SimOptions:
    overload_prob: float = 0.15
    anpr_misread_prob: float = 0.05
    rfid_missing_prob: float = 0.10
    clone_prob: float = 0.01
    sensor_fault_prob: float = 0.03
    unregistered_prob: float = 0.05
    pavement_temp_c: float = 32.0
    speed_mps: float | None = None
    force_gvm_kg: int | None = None
    vehicle_id: str | None = None
    seed: int | None = None
    oversize_prob: float = 0.02  # RCS v2: share of trucks over a dimension limit (height / width / length)
    lifted_axle_prob: float = 0.02  # share with a lifted axle (axle count below registration)


LOW_SPEED_LANE_TYPES = ("port_gateout", "origin_scale", "rolling_verification")
# Expanded (k=2) relative uncertainty of the low-speed per-wheel scales by node (RCS v2 plan: lane and port error target 1 %)
LOW_SPEED_REL_U = {"port_gateout": 0.01, "origin_scale": 0.01, "rolling_verification": 0.01}


def _low_speed_measurement(truck: TruckProfile, lane_type: str, rng: np.random.Generator, pavement_temp_c: float) -> dict:
    """Synthetic per-wheel scale measurement for the port gate-out node, an origin scale or the rolling verification lane.
    These nodes weigh at walking pace to about 10 km/h on wheel load cells / bending plates, not on the high-speed piezo
    array, so the measurement is built directly (same dict shape as ``WimMeasurement.to_dict()``). SIMULATED."""
    rel_u = LOW_SPEED_REL_U.get(lane_type, 0.01)
    axles = []
    offsets = truck.axle_offsets_m
    groups: list[int] = []
    g = 1
    for i, load in enumerate(truck.axle_loads_kg):
        meas = load * (1 + rng.normal(0, rel_u / 2))  # 1 sigma = half the expanded uncertainty
        split = rng.uniform(0.46, 0.54)
        spacing = truck.axle_spacings_m[i] if i < len(truck.axle_spacings_m) else None
        groups.append(g)
        axles.append({"index": i, "load_kg": float(round(meas)), "u_kg": float(round(rel_u * meas)), "spacing_to_next_m": spacing, "group_no": g,
                      "left_kg": float(round(meas * split)), "right_kg": float(round(meas * (1 - split)))})
        if spacing is not None and spacing >= 2.0:
            g += 1
    sizes: dict[int, int] = {}
    for a in axles:
        sizes[a["group_no"]] = sizes.get(a["group_no"], 0) + 1
    cfg = "+".join(str(sizes[k]) for k in sorted(sizes))
    gvm = float(sum(a["load_kg"] for a in axles))
    gvm_u = float(np.sqrt(sum(a["u_kg"] ** 2 for a in axles)))
    health = {k: {"status": "ok", "reason": None} for k in ("WL1", "WL2", "WL3", "WL4")}
    return {
        "gvm_kg": gvm, "gvm_u_kg": gvm_u, "axles": axles, "axle_config": cfg, "class_code": f"HGV{len(axles)}",
        "speed_mps": truck.speed_mps, "speed_u_mps": 0.1, "quality_flags": [], "sensor_health": health,
        "pavement_temp_c": pavement_temp_c, "length_m": offsets[-1] + 3.0,
    }


def _scramble_plate(plate: str, rng: np.random.Generator) -> str:
    chars = list(plate)
    swaps = {"0": "O", "O": "0", "1": "I", "I": "1", "8": "B", "B": "8", "5": "S", "S": "5"}
    idx = [i for i, c in enumerate(chars) if c in swaps]
    if idx:
        i = int(rng.choice(idx))
        chars[i] = swaps[chars[i]]
    return "".join(chars)


def simulate_pass(db: Session, lane: Lane, opts: SimOptions | None = None) -> WeighingEvent:
    opts = opts or SimOptions()
    rng = np.random.default_rng(opts.seed)

    vehicles = db.execute(select(Vehicle).where(Vehicle.status == "active")).scalars().all()
    vehicle: Vehicle | None = None
    if opts.vehicle_id:
        vehicle = db.get(Vehicle, opts.vehicle_id)
    elif vehicles and rng.random() >= opts.unregistered_prob:
        vehicle = vehicles[int(rng.integers(len(vehicles)))]

    cfg = vehicle.axle_config if vehicle else str(rng.choice(list(CONFIG_TO_PROFILE)))
    prof = PROFILES[CONFIG_TO_PROFILE.get(cfg, "4A_semi_1+1+2")]
    loads = np.array(prof["typical_loads"], dtype=float) * rng.uniform(0.55, 1.0)
    if rng.random() < opts.overload_prob:
        loads *= rng.uniform(1.08, 1.30)
    loads *= rng.uniform(0.95, 1.05, size=len(loads))
    if opts.force_gvm_kg:
        loads *= opts.force_gvm_kg / loads.sum()
    # Node speed: port gate-out and origin scales at walking pace, the verification lane at about 10 km/h, mainline WIM at highway speed
    speed_by_type = {"port_gateout": (1.5, 3.0), "origin_scale": (1.0, 2.5), "rolling_verification": (2.0, 3.5)}
    lo, hi = speed_by_type.get(lane.type, (8.0, 25.0))
    spacings = list(prof["spacings"])
    lifted = bool(rng.random() < opts.lifted_axle_prob) and len(loads) > 3
    if lifted:
        # a lifted axle leaves the pavement: its load moves to the neighbours in the same group and the strips see one axle fewer
        i = len(loads) - 1
        loads[i - 1] += loads[i]
        loads = loads[:-1]
        spacings = spacings[:-1]
    truck = TruckProfile(
        axle_loads_kg=[float(round(x)) for x in loads],
        axle_spacings_m=spacings,
        speed_mps=opts.speed_mps or float(rng.uniform(lo, hi)),
        bounce_hz=float(rng.uniform(1.5, 3.5)),
        bounce_frac=float(rng.uniform(0.01, 0.06)),
        bounce_phase=float(rng.uniform(0, 2 * np.pi)),
    )
    if lane.type in LOW_SPEED_LANE_TYPES:
        measurement = _low_speed_measurement(truck, lane.type, rng, opts.pavement_temp_c)
        if rng.random() < opts.sensor_fault_prob:
            measurement["sensor_health"]["WL2"] = {"status": "fault", "reason": "simulated wheel-scale fault"}
            measurement["quality_flags"].append("sensor_fault")
    else:
        sensors = {k: SensorModel(pavement_temp_c=opts.pavement_temp_c, temp_coeff_per_c=-0.002) for k in ("P1", "P2", "P3", "BP")}
        if rng.random() < opts.sensor_fault_prob:
            k = str(rng.choice(["P1", "P2", "P3", "BP"]))
            sensors[k] = SensorModel(pavement_temp_c=opts.pavement_temp_c, fault=str(rng.choice(["dead", "noisy"])))
        geometry = LaneGeometry()
        p = generate_pass(truck, geometry=geometry, sensors=sensors, rng=rng)
        cal = {k: ChannelCalibration(temp_coeff_per_c=-0.002, type_b_rel_u=0.02) for k in sensors}
        m = process_pass(p.channels, p.fs_hz, geometry=geometry, calibration=cal, pavement_temp_c=opts.pavement_temp_c)
        measurement = m.to_dict()
    if lane.type in ("rolling_verification", "port_gateout"):
        # dimension portal (LiDAR / light curtain) readings; oversize draws exceed one of the limits
        length = float(sum(spacings) + rng.uniform(2.5, 4.5))
        width, height = float(rng.uniform(2.45, 2.60)), float(rng.uniform(3.6, 4.25))
        if rng.random() < opts.oversize_prob:
            which = int(rng.integers(3))
            if which == 0:
                height = float(rng.uniform(4.35, 4.9))
            elif which == 1:
                width = float(rng.uniform(2.7, 3.2))
            else:
                length = float(rng.uniform(22.5, 26.0))
        measurement["dimensions"] = {"length_m": round(length, 2), "width_m": round(width, 2), "height_m": round(height, 2)}
        measurement["lifted_axle"] = lifted
    elif lifted:
        measurement["lifted_axle"] = lifted

    # --- identity simulation
    anpr_plate, anpr_conf, rfid_epc, rfid_conf = None, None, None, None
    if vehicle:
        anpr_plate = vehicle.plate
        anpr_conf = float(rng.uniform(0.85, 0.99))
        if rng.random() < opts.anpr_misread_prob:
            anpr_plate = _scramble_plate(vehicle.plate, rng)
            anpr_conf = float(rng.uniform(0.5, 0.8))
        if vehicle.tags and rng.random() >= opts.rfid_missing_prob:
            rfid_epc = vehicle.tags[0].epc
            rfid_conf = float(rng.uniform(0.95, 0.999))
        if rng.random() < opts.clone_prob and len(vehicles) > 1:
            other = vehicles[int(rng.integers(len(vehicles)))]
            if other.id != vehicle.id and other.tags:
                rfid_epc, rfid_conf = other.tags[0].epc, 0.98  # cloned tag from another truck
    else:
        anpr_plate = f"K{rng.choice(list('CDE'))}{rng.choice(list('ABCDEFGHJKLMNPQRSTUVWXYZ'))} {rng.integers(100, 999)}{rng.choice(list('ABCDEFGHJKLMNPQRSTUVWXYZ'))}"
        anpr_conf = float(rng.uniform(0.7, 0.95))

    return weighing_service.process_lane_pass(
        db,
        lane,
        measurement,
        anpr_plate,
        anpr_conf,
        rfid_epc,
        rfid_conf,
        source="simulated",
        ambient_temp_c=float(opts.pavement_temp_c - 4.0),
    )
