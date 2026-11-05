"""Port visit lifecycle (SmartPort contract §1-2): create at stage 1, advance stage by stage with required-field
validation, keep the cargo passport in step, derive the per-visit KPIs, and compute the port KPIs with published
benchmarks from the data register."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import data_register
from ..models import (
    DATETIME_FIELDS,
    PORT_STAGE_META,
    PORT_STAGES,
    PORT_TO_SHIPMENT_STAGE,
    SHIPMENT_STAGES,
    CargoProcessingEvent,
    DeliveryRecord,
    PortVisit,
    Shipment,
    utcnow,
)
from . import ledger

STAGE_INDEX = {s: i for i, s in enumerate(PORT_STAGES)}
BENCHMARK_KEYS = ("kpa.truck_turnaround_h_2023", "kpa.import_dwell_h_q3_2026", "kenha.mariakani_daily_weighed_q3_2026", "ncttca.weighbridge_crossing_min_2025", "ncttca.mombasa_nairobi_transit_h_2025")
# columns a stage's data may write (required fields plus the optional ones from the contract table)
STAGE_FIELDS: dict[str, list[str]] = {
    "pre_registered": ["truck_type", "container_number", "cargo_type", "declared_mass_kg", "destination", "appointment_at", "expected_arrival_at"],
    "customs_cleared": ["customs_declaration_ref", "bill_of_lading", "trade_direction", "duty_status", "customs_status", "inspection_status", "permit_status", "hold_reason"],
    "arrived": ["anpr_plate", "rfid_epc", "appointment_valid", "queue_position", "queue_length", "queue_wait_s", "arrival_lat", "arrival_lon"],
    "gate_in": ["gate_in_id", "access_authorised", "vehicle_inspection", "driver_verified", "gate_in_processing_s", "rejection_reason"],
    "yard_allocated": ["terminal_id", "yard_block", "container_position", "loading_instruction", "yard_wait_s"],
    "loaded": ["loading_start_at", "loading_end_at", "equipment_id", "seal_number", "cargo_verification", "cargo_condition", "loading_exceptions"],
    "weighed": ["weighing_event_id", "weighing_arrival_at", "weighing_start_at", "weighing_end_at", "tare_kg", "gross_kg", "net_kg", "weight_discrepancy_kg", "calibration_valid", "token_ref"],
    "final_cleared": ["cargo_release_status", "delivery_order_ref", "gate_pass_no", "payment_status", "clearance_exceptions"],
    "gate_out": ["gate_out_id", "exit_cargo_verified", "exit_authorised"],
    "in_transit": ["route", "distance_km", "eta_at", "stoppage_s", "delay_reason"],
    "delivered": ["arrived_destination_at", "pod_ref"],
}


class StageError(ValueError):
    def __init__(self, message: str, missing: list[str] | None = None):
        super().__init__(message)
        self.missing = missing or []


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _parse_dt(v) -> datetime | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return _aware(v)
    return _aware(datetime.fromisoformat(str(v).replace("Z", "+00:00")))


def missing_fields(stage: str, data: dict) -> list[str]:
    return [f for f in PORT_STAGE_META[stage]["required_fields"] if data.get(f) in (None, "", [])]


def next_stage(v: PortVisit) -> str | None:
    i = STAGE_INDEX[v.stage]
    return PORT_STAGES[i + 1] if i + 1 < len(PORT_STAGES) else None


def apply_stage_data(v: PortVisit, stage: str, data: dict) -> None:
    for f in STAGE_FIELDS[stage]:
        if f not in data:
            continue
        val = data[f]
        if f in DATETIME_FIELDS:
            val = _parse_dt(val)
        elif f in ("loading_exceptions", "clearance_exceptions"):
            val = list(val or [])
        setattr(v, f, val)


def derive(v: PortVisit) -> None:
    """Fill derived fields: net weight and discrepancy, dwell and transit times, queue and clearance durations."""
    if v.gross_kg is not None and v.tare_kg is not None:
        v.net_kg = v.gross_kg - v.tare_kg
        if v.declared_mass_kg is not None:
            v.weight_discrepancy_kg = v.net_kg - v.declared_mass_kg
    if v.queue_wait_s is None and v.arrived_at and v.gate_in_at:
        v.queue_wait_s = max(0, int((_aware(v.gate_in_at) - _aware(v.arrived_at)).total_seconds()))
    if v.gate_in_at and v.gate_out_at:
        v.dwell_time_s = max(0, int((_aware(v.gate_out_at) - _aware(v.gate_in_at)).total_seconds()))
    if v.gate_out_at and v.delivered_at:
        v.transit_time_s = max(0, int((_aware(v.delivered_at) - _aware(v.gate_out_at)).total_seconds()))


def kpis_for(v: PortVisit) -> dict:
    def dur(a, b):
        a, b = _aware(a), _aware(b)
        return max(0, int((b - a).total_seconds())) if a and b else None

    return {
        "queue_wait_s": v.queue_wait_s,
        "gate_in_processing_s": v.gate_in_processing_s,
        "yard_wait_s": v.yard_wait_s,
        "loading_duration_s": dur(v.loading_start_at, v.loading_end_at),
        "weighing_service_s": dur(v.weighing_start_at, v.weighing_end_at),
        "clearance_duration_s": dur(v.weighing_end_at, v.final_cleared_at),
        "dwell_time_s": v.dwell_time_s,
        "transit_time_s": v.transit_time_s,
    }


def outstanding_for(v: PortVisit) -> list[str]:
    nxt = next_stage(v)
    if v.status != "active" or nxt is None:
        return []
    return [f for f in PORT_STAGE_META[nxt]["required_fields"] if getattr(v, f, None) in (None, "", [])]


def new_reference() -> str:
    return "PV-" + secrets.token_hex(4).upper()


def create(db: Session, *, shipment: Shipment | None, vehicle_id: str | None, driver_id: str | None, transporter_org_id: str | None, owner_org_id: str | None,
           appointment_id: str | None, data: dict, source: str = "simulated", at: datetime | None = None, actor_user_id: str | None = None) -> PortVisit:
    miss = missing_fields("pre_registered", data)
    if miss:
        raise StageError("missing required fields for pre_registered", miss)
    at = _aware(at) or utcnow()
    v = PortVisit(reference=new_reference(), shipment_id=shipment.id if shipment else None, vehicle_id=vehicle_id, driver_id=driver_id, transporter_org_id=transporter_org_id,
                  owner_org_id=owner_org_id or (shipment.owner_org_id if shipment else None), appointment_id=appointment_id, stage="pre_registered", status="active", source=source, timeline=[])
    if shipment and not data.get("container_number") and shipment.containers:
        data = {**data, "container_number": shipment.containers[0].number}
    apply_stage_data(v, "pre_registered", data)
    v.pre_registered_at = at
    v.timeline = [{"stage": "pre_registered", "at": at.isoformat(), "data": _json_safe(data)}]
    db.add(v)
    db.flush()
    _sync_shipment(db, v, "pre_registered", at, actor_user_id)
    ledger.append(db, "port.visit_created", {"visit_id": v.id, "reference": v.reference, "shipment_id": v.shipment_id, "vehicle_id": v.vehicle_id, "source": source}, producer="port-process", occurred_at=at)
    return v


def advance(db: Session, v: PortVisit, stage: str, data: dict, *, at: datetime | None = None, actor_user_id: str | None = None, source: str | None = None) -> PortVisit:
    if v.status != "active":
        raise StageError(f"visit is {v.status}")
    if stage not in STAGE_INDEX:
        raise StageError(f"unknown stage {stage}")
    expected = next_stage(v)
    if stage != expected:
        raise StageError(f"visit is at {v.stage}; the next stage is {expected}, not {stage}")
    miss = missing_fields(stage, data)
    if miss:
        raise StageError(f"missing required fields for {stage}", miss)
    at = _aware(at) or utcnow()
    apply_stage_data(v, stage, data)
    ts_col = PORT_STAGE_META[stage]["ts"]
    if getattr(v, ts_col, None) is None:
        setattr(v, ts_col, at)
    v.stage = stage
    if stage == "delivered":
        v.status = "closed"
    derive(v)
    v.timeline = list(v.timeline or []) + [{"stage": stage, "at": at.isoformat(), "data": _json_safe(data)}]
    if source:
        v.source = source
    _sync_shipment(db, v, stage, at, actor_user_id)
    ledger.append(db, "port.stage_advanced", {"visit_id": v.id, "reference": v.reference, "stage": stage, "dwell_time_s": v.dwell_time_s, "transit_time_s": v.transit_time_s},
                  producer="port-process", occurred_at=at)
    return v


def cancel(db: Session, v: PortVisit, reason: str, actor_user_id: str | None = None) -> PortVisit:
    v.status, v.cancel_reason = "cancelled", reason
    ledger.append(db, "port.visit_cancelled", {"visit_id": v.id, "reference": v.reference, "reason": reason, "by": actor_user_id}, producer="port-process")
    return v


def _sync_shipment(db: Session, v: PortVisit, stage: str, at: datetime, actor_user_id: str | None) -> None:
    if not v.shipment_id:
        return
    s = db.get(Shipment, v.shipment_id)
    if s is None:
        return
    db.add(CargoProcessingEvent(shipment_id=s.id, stage=f"PORT:{stage}", status="completed", occurred_at=at, source="port-process", notes=f"port visit {v.reference}", actor_user_id=actor_user_id))
    target = PORT_TO_SHIPMENT_STAGE[stage]
    if SHIPMENT_STAGES.index(target) > SHIPMENT_STAGES.index(s.stage if s.stage in SHIPMENT_STAGES else "registered"):
        s.stage = target
    if stage == "delivered":
        db.add(DeliveryRecord(shipment_id=s.id, delivered_at=at, notes=f"port visit {v.reference}, POD {v.pod_ref}"))


def _json_safe(data: dict) -> dict:
    out = {}
    for k, val in data.items():
        out[k] = val.isoformat() if isinstance(val, datetime) else val
    return out


def attach_port_weighing(db: Session, vehicle_id: str, ev, token_ref: str | None, calibration_valid: bool, tare_kg: int | None, occurred_at: datetime) -> PortVisit | None:
    """Stage 7 automation: a pass over the port gate-out weigh node advances the vehicle's active visit from `loaded` to `weighed`."""
    v = db.execute(select(PortVisit).where(PortVisit.vehicle_id == vehicle_id, PortVisit.status == "active", PortVisit.stage == "loaded").order_by(PortVisit.created_at.desc())).scalars().first()
    if v is None:
        return None
    start = _aware(occurred_at)
    data = {"weighing_event_id": ev.id, "weighing_arrival_at": start - timedelta(seconds=30), "weighing_start_at": start, "weighing_end_at": start + timedelta(seconds=20),
            "gross_kg": int(ev.gvm_kg), "tare_kg": int(tare_kg or 0), "calibration_valid": calibration_valid, "token_ref": token_ref}
    return advance(db, v, "weighed", data, at=start + timedelta(seconds=20), source=ev.source)


def kpis(db: Session, hours: int = 24) -> dict:
    since = utcnow() - timedelta(hours=hours)
    rows = db.execute(select(PortVisit).where(PortVisit.updated_at >= since)).scalars().all()
    by_stage = {s: 0 for s in PORT_STAGES}
    for v in rows:
        by_stage[v.stage] = by_stage.get(v.stage, 0) + 1

    def avg(vals):
        vals = [x for x in vals if x is not None]
        return (sum(vals) / len(vals)) if vals else None

    def p90(vals):
        vals = sorted(x for x in vals if x is not None)
        return vals[min(len(vals) - 1, int(0.9 * len(vals)))] if vals else None

    k = [kpis_for(v) for v in rows]
    gate_outs = sum(1 for v in rows if v.gate_out_at and _aware(v.gate_out_at) >= since)
    exceptions = sum(len(v.loading_exceptions or []) + len(v.clearance_exceptions or []) + (1 if v.customs_status == "held" else 0) for v in rows)
    benchmarks = []
    for key in BENCHMARK_KEYS:
        r = data_register.get(key)
        if r:
            benchmarks.append({"key": key, "label": r["label"], "value": r["value"], "unit": r["unit"], "classification": r["classification"], "source_url": r["source_url"], "period": r["period"]})
    total = db.execute(select(func.count()).select_from(PortVisit)).scalar() or 0
    return {
        "period_hours": hours, "visits_total": total, "visits_in_period": len(rows), "visits_by_stage": by_stage,
        "avg_queue_wait_s": avg(x["queue_wait_s"] for x in k), "avg_gate_in_processing_s": avg(x["gate_in_processing_s"] for x in k), "avg_yard_wait_s": avg(x["yard_wait_s"] for x in k),
        "avg_loading_duration_s": avg(x["loading_duration_s"] for x in k), "avg_weighing_service_s": avg(x["weighing_service_s"] for x in k), "avg_clearance_duration_s": avg(x["clearance_duration_s"] for x in k),
        "avg_dwell_time_s": avg(x["dwell_time_s"] for x in k), "p90_dwell_time_s": p90(x["dwell_time_s"] for x in k), "avg_transit_time_s": avg(x["transit_time_s"] for x in k),
        "throughput_per_hour": gate_outs / hours if hours else 0.0, "gate_outs_total": gate_outs, "exceptions_total": exceptions,
        "benchmarks": benchmarks, "label": "measured from platform records (live / simulated as tagged)",
    }
