"""Orchestrates one lane pass: persist measurement -> resolve identity -> deterministic decision -> ticket -> ledger -> events.

Used by both the edge ingest endpoint (`source=live`, measurement computed on the gateway) and the simulator
(`source=simulated`). The source is never dropped.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..events import EventType, publish
from ..models import (
    NODE_KIND_BY_LANE_TYPE,
    AxleMeasurement,
    ClearanceDecision,
    ElectronicSeal,
    IdentityEvent,
    Lane,
    Shipment,
    Vehicle,
    WeighingEvent,
    utcnow,
)
from ..security import sign_payload
from . import clearance_engine as ce
from . import identity as identity_svc
from . import ledger, tickets
from . import tokens as token_svc
from .limits import DEFAULT_LIMITS
from .release_orders import fee_preview

# Decision-level instructions (kept for callers that only know the colour); route-level text is in clearance_engine.INSTRUCTIONS_BY_ROUTE
INSTRUCTIONS = {
    "GREEN": "Continue — no stop required",
    "AMBER": "Proceed to verification",
    "RED": "Stop for inspection",
}


def node_kind_for_lane(lane: Lane) -> str:
    return NODE_KIND_BY_LANE_TYPE.get(lane.type, "road_mainline")


def _lane_available(lane: Lane) -> bool:
    """True when the station has an operational rolling verification lane (AMBER on the mainline diverts there)."""
    st = lane.station
    return bool(st) and any(ln.type == "rolling_verification" and ln.status != "offline" for ln in st.lanes)


def _permit_input(vehicle: Vehicle | None, at: datetime) -> ce.PermitInput | None:
    if not vehicle or not vehicle.permits:
        return None
    best = None
    for pm in vehicle.permits:
        vf = pm.valid_from if pm.valid_from.tzinfo else pm.valid_from.replace(tzinfo=UTC)
        vt = pm.valid_to if pm.valid_to.tzinfo else pm.valid_to.replace(tzinfo=UTC)
        valid = vf <= at <= vt
        cand = ce.PermitInput(pm.reference, pm.max_length_m, pm.max_width_m, pm.max_height_m, pm.max_gvm_kg, valid)
        if valid:
            return cand
        best = best or cand
    return best


def _lane_calibration_valid(lane: Lane, at: datetime) -> bool:
    if lane.calibration_valid_to is None:
        return False
    v = lane.calibration_valid_to
    if v.tzinfo is None:
        v = v.replace(tzinfo=UTC)
    return v >= at


def process_lane_pass(
    db: Session,
    lane: Lane,
    measurement: dict,
    anpr_plate: str | None,
    anpr_conf: float | None,
    rfid_epc: str | None,
    rfid_conf: float | None,
    occurred_at: datetime | None = None,
    source: str = "simulated",
    edge_event_id: str | None = None,
    raw_ref: str | None = None,
    ambient_temp_c: float | None = None,
) -> WeighingEvent:
    """`measurement` is the dict form of `kifaru_wim_dsp.WimMeasurement.to_dict()`."""
    t_start = time.perf_counter()
    s = get_settings()
    occurred_at = occurred_at or utcnow()

    if edge_event_id:
        existing = db.execute(select(WeighingEvent).where(WeighingEvent.edge_event_id == edge_event_id)).scalar_one_or_none()
        if existing:
            return existing  # idempotent replay from store-and-forward

    publish(EventType.TRUCK_DETECTED, {"lane_id": lane.id, "anpr_plate": anpr_plate, "rfid_epc": rfid_epc}, station_id=lane.station_id, source=source)
    publish(EventType.WEIGHING_STARTED, {"lane_id": lane.id}, station_id=lane.station_id, source=source)

    ident = identity_svc.resolve(db, anpr_plate, anpr_conf, rfid_epc, rfid_conf)
    vehicle: Vehicle | None = ident.vehicle

    # cargo context: the active shipment assigned to this vehicle, if any
    shipment: Shipment | None = None
    if vehicle:
        shipment = db.execute(
            select(Shipment).where(Shipment.vehicle_id == vehicle.id, Shipment.status == "active").order_by(Shipment.created_at.desc())
        ).scalars().first()
    seal_status = None
    seal_id = None
    if shipment:
        seal = db.execute(select(ElectronicSeal).where(ElectronicSeal.shipment_id == shipment.id).order_by(ElectronicSeal.created_at.desc())).scalars().first()
        seal_status = seal.status if seal else None
        seal_id = seal.seal_id if seal else None

    node_kind = node_kind_for_lane(lane)
    dims = measurement.get("dimensions") or {}
    lifted = bool(measurement.get("lifted_axle", False))
    # RCS v2: the token the truck carries from its first verified weighing point (if any)
    token_row = token_svc.active_for_vehicle(db, vehicle.id if vehicle else None, anpr_plate if not vehicle else None, at=occurred_at)
    stream = "untokened"
    if token_row and token_row.source in ("port", "origin"):
        stream = token_row.source
    elif node_kind == "port_gateout":
        stream = "port"
    elif node_kind == "origin":
        stream = "origin"

    ev = WeighingEvent(
        lane_id=lane.id,
        station_id=lane.station_id,
        vehicle_id=vehicle.id if vehicle else None,
        shipment_id=shipment.id if shipment else None,
        occurred_at=occurred_at,
        speed_mps=float(measurement.get("speed_mps", 0.0)),
        gvm_kg=int(measurement["gvm_kg"]),
        gvm_uncertainty_kg=int(measurement["gvm_u_kg"]),
        axle_count=len(measurement["axles"]),
        detected_axle_config=measurement.get("axle_config"),
        class_code=measurement.get("class_code"),
        quality_flags=list(measurement.get("quality_flags", [])),
        sensor_health={k: v["status"] if isinstance(v, dict) else v for k, v in measurement.get("sensor_health", {}).items()},
        pavement_temp_c=measurement.get("pavement_temp_c"),
        ambient_temp_c=ambient_temp_c,
        raw_ref=raw_ref,
        source=source,
        kind="wim" if node_kind != "static" else "static",
        edge_event_id=edge_event_id,
        node_kind=node_kind,
        stream=stream,
        length_m=dims.get("length_m"),
        width_m=dims.get("width_m"),
        height_m=dims.get("height_m"),
        lifted_axle=lifted,
        token_id=token_row.id if token_row else None,
    )
    db.add(ev)
    db.flush()
    for a in measurement["axles"]:
        db.add(
            AxleMeasurement(
                weighing_event_id=ev.id,
                axle_index=a["index"],
                load_kg=int(a["load_kg"]),
                uncertainty_kg=int(a["u_kg"]),
                spacing_to_next_m=a.get("spacing_to_next_m"),
                group_no=a.get("group_no", 1),
                left_kg=int(a["left_kg"]) if a.get("left_kg") is not None else None,
                right_kg=int(a["right_kg"]) if a.get("right_kg") is not None else None,
            )
        )
    db.add(
        IdentityEvent(
            weighing_event_id=ev.id,
            anpr_plate=anpr_plate,
            anpr_confidence=anpr_conf,
            rfid_epc=rfid_epc,
            rfid_confidence=rfid_conf,
            fused_vehicle_id=vehicle.id if vehicle else None,
            confidence=ident.confidence,
            method=ident.method,
            explanation=ident.explanation,
        )
    )
    publish(
        EventType.TRUCK_IDENTIFIED,
        {"weighing_event_id": ev.id, "plate": vehicle.plate if vehicle else anpr_plate, "confidence": ident.confidence, "method": ident.method},
        station_id=lane.station_id,
        org_id=vehicle.org_id if vehicle else "platform",
        source=source,
    )

    # ------------------------------------------------------------ decision
    m_in = ce.MeasurementInput(
        gvm_kg=ev.gvm_kg,
        gvm_u_kg=ev.gvm_uncertainty_kg,
        axles=[ce.AxleInput(a["index"], a["load_kg"], a["u_kg"], a.get("group_no", 1)) for a in measurement["axles"]],
        detected_axle_config=ev.detected_axle_config or "",
        quality_flags=ev.quality_flags,
        sensor_health=ev.sensor_health,
        speed_mps=ev.speed_mps,
        source=source,
    )
    id_in = ce.IdentityInput(ident.confidence, vehicle.id if vehicle else None, ident.method, anpr_plate, rfid_epc)
    v_in = (
        ce.VehicleInput(vehicle.id, vehicle.plate, vehicle.axle_config, vehicle.tare_kg, vehicle.max_gvm_kg, vehicle.watchlist_reason)
        if vehicle
        else None
    )
    c_in = ce.CargoInput(
        shipment_ref=shipment.reference if shipment else None,
        declared_mass_kg=shipment.declared_mass_kg if shipment else None,
        vgm_kg=shipment.vgm_kg if shipment else None,
        seal_status=seal_status,
    )
    token_in = token_svc.to_input(token_row, plate=vehicle.plate if vehicle else anpr_plate, rfid_epc=rfid_epc, seal_status=seal_status, at=occurred_at) if token_row else None
    dims_in = None
    if dims or lifted or node_kind in ("verification_lane", "port_gateout"):
        dims_in = ce.DimensionsInput(dims.get("length_m"), dims.get("width_m"), dims.get("height_m"), lifted, _permit_input(vehicle, occurred_at))
    result = ce.decide(
        m_in,
        id_in,
        v_in,
        c_in,
        limits=DEFAULT_LIMITS,
        identity_min_confidence=s.identity_min_confidence,
        audit_rate=s.audit_sample_rate,
        lane_calibration_valid=_lane_calibration_valid(lane, occurred_at),
        require_two_sources=s.identity_require_two_sources,
        token=token_in,
        dimensions=dims_in,
        node_kind=node_kind,
        lane_available=_lane_available(lane),
        audit_rate_by_tier=token_svc.audit_rate_by_tier() if s.audit_sample_rate > 0 else None,
    )
    latency_ms = int((time.perf_counter() - t_start) * 1000)
    fee_prev = None
    if result.decision == "RED":
        fee_prev = fee_preview(ev.gvm_kg, int(result.margins["gvm"]["limit_kg"]))["fee_usd"]
    dec = ClearanceDecision(
        weighing_event_id=ev.id,
        decision=result.decision,
        rules_fired=result.rules_fired,
        margins=result.margins,
        limits_version=result.limits_version,
        engine_version=result.engine_version,
        audit_selected=result.audit_selected,
        evidence_hash=result.evidence_hash,
        signature=sign_payload({"evidence_hash": result.evidence_hash, "decision": result.decision}),
        decided_at=utcnow(),
        latency_ms=latency_ms,
        explanation=result.explanation,
        route=result.route,
        token_checked_id=token_row.id if token_row else None,
        fee_preview_usd=fee_prev,
    )
    db.add(dec)
    db.flush()

    station_code = lane.station.code if lane.station else "UNKNOWN"

    # ------------------------------------------------------------ RCS v2 token lifecycle
    issued_token = None
    if token_row:
        if result.token_consistent and token_in and token_in.valid and token_in.identity_match and result.decision != "RED":
            token_svc.honour(token_row, occurred_at)
            ledger.append(db, "token.honoured", {"token_id": token_row.id, "token_ref": token_row.token_ref, "weighing_event_id": ev.id, "diff_kg": ev.gvm_kg - token_row.gvm_kg, "station": station_code},
                          station_id=lane.station_id, producer="clearance-registry", occurred_at=occurred_at)
        elif result.decision == "RED" or not token_in.identity_match:
            token_svc.suspend(token_row, f"{result.decision} at {station_code}: " + "; ".join(r["rule"] for r in result.rules_fired)[:200])
            ledger.append(db, "token.suspended", {"token_id": token_row.id, "token_ref": token_row.token_ref, "weighing_event_id": ev.id, "reason": token_row.suspended_reason},
                          station_id=lane.station_id, producer="clearance-registry", occurred_at=occurred_at)
    # Issue a token on GREEN at an issuing node. Port and origin nodes always issue (they are the first trusted point) and a
    # verification-lane pass renews whatever the truck carried (1 % lane scales beat a 2.5 % road reading); a road node
    # only issues when the truck carries no active token.
    if result.token_eligible and vehicle is not None:
        src = ce.NODE_TO_TOKEN_SOURCE[node_kind]
        should_issue = src != "road" or token_row is None or token_row.status != "active"
        if should_issue:
            expected = (vehicle.tare_kg + shipment.declared_mass_kg) if (shipment and shipment.declared_mass_kg) else None
            issued_token = token_svc.issue(
                db, ev, dec, vehicle, shipment, src,
                plate=vehicle.plate, rfid_epc=rfid_epc, seal_id=seal_id, expected_gvm_kg=expected,
                dimensions=dims or None, permit_ref=(dims_in.permit.reference if dims_in and dims_in.permit else None),
                release_status={"customs": shipment.declaration.status if shipment and shipment.declaration else "n/a", "stage": shipment.stage if shipment else "n/a"},
                trust_tier=min(vehicle.trust_tier or 3, ce.TRUST_TIER_BY_SOURCE[src]) if src in ("port", "origin") else ce.TRUST_TIER_BY_SOURCE[src],
            )
            dec.token_issued_id = issued_token.id
            ledger.append(db, "token.issued", {"token_id": issued_token.id, "token_ref": issued_token.token_ref, "source": src, "trust_tier": issued_token.trust_tier,
                                               "gvm_kg": issued_token.gvm_kg, "expires_at": issued_token.expires_at.isoformat(), "weighing_event_id": ev.id},
                          station_id=lane.station_id, producer="clearance-registry", occurred_at=occurred_at)

    ticket = tickets.issue(db, ev, dec, "prescreen", vehicle.plate if vehicle else anpr_plate, station_code)

    ledger.append(
        db,
        "weighing.completed",
        {"weighing_event_id": ev.id, "gvm_kg": ev.gvm_kg, "u_kg": ev.gvm_uncertainty_kg, "axles": ev.axle_count, "source": source},
        station_id=lane.station_id,
        producer=f"lane:{lane.id}",
        occurred_at=occurred_at,
    )
    ledger.append(
        db,
        "clearance.decided",
        {"decision_id": dec.id, "weighing_event_id": ev.id, "decision": dec.decision, "evidence_hash": dec.evidence_hash, "ticket_id": ticket.id},
        station_id=lane.station_id,
        producer="clearance-engine",
    )

    # Tenant scoping: vehicle-level events are tagged with the owning organisation so WebSocket clients of other
    # transporters never receive them. Unregistered vehicles are tagged "platform" (visible to platform-wide roles only).
    org_id = vehicle.org_id if vehicle else "platform"
    payload = {
        "weighing_event_id": ev.id,
        "decision_id": dec.id,
        "decision": dec.decision,
        "instruction": result.instruction,
        "route": dec.route,
        "node_kind": node_kind,
        "stream": stream,
        "token_ref": (issued_token.token_ref if issued_token else (token_row.token_ref if token_row else None)),
        "token_issued": issued_token.token_ref if issued_token else None,
        "token_checked": token_row.token_ref if token_row else None,
        "plate": vehicle.plate if vehicle else anpr_plate,
        "vehicle_id": vehicle.id if vehicle else None,
        "shipment_id": shipment.id if shipment else None,
        "gvm_kg": ev.gvm_kg,
        "u_kg": ev.gvm_uncertainty_kg,
        "axle_config": ev.detected_axle_config,
        "lane_id": lane.id,
        "station_code": station_code,
        "ticket_id": ticket.id,
        "ticket_qr_token": ticket.qr_token,
        "latency_ms": latency_ms,
        "source": source,
        "rules_fired": [r["rule"] for r in dec.rules_fired],
    }
    publish(EventType.WEIGHING_COMPLETED, payload, station_id=lane.station_id, org_id=org_id, source=source)
    publish(EventType.CLEARANCE_DECIDED, payload, station_id=lane.station_id, org_id=org_id, source=source)
    if dec.decision in ("AMBER", "RED"):
        publish(EventType.TRUCK_DIVERTED, payload, station_id=lane.station_id, org_id=org_id, source=source)
    else:
        publish(EventType.TRUCK_RELEASED, payload, station_id=lane.station_id, org_id=org_id, source=source)
    if vehicle:
        from ..routers.notifications import notify

        notify(db, user_id=None, org_id=vehicle.org_id, template="clearance", title=f"{vehicle.plate}: {dec.decision} at {station_code}",
               body=f"{vehicle.plate} {dec.decision} at {station_code}. {result.instruction}" + (f" Token {issued_token.token_ref} issued." if issued_token else ""),
               payload={"weighing_event_id": ev.id, "decision": dec.decision, "vehicle_id": vehicle.id, "source": source})
    if shipment:
        shipment.stage = "weighing_verification" if dec.decision != "GREEN" else shipment.stage
    return ev
