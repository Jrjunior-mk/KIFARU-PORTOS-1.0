"""SmartPort port-process API (contract §2): stages, port visits, KPIs with published benchmarks, the stage board and
the existing-versus-SmartPort simulation."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DbDep, Principal, audit, org_scope, require_roles
from ..events import EventType, publish
from ..models import PORT_STAGE_META, PORT_STAGES, PortVisit, Shipment, Vehicle
from ..services import port_visits as svc

router = APIRouter(prefix="/port", tags=["port-process"])
CREATE_ROLES = require_roles("platform_admin", "port_controller", "transporter_admin", "dispatcher", "cargo_owner")
PORT_ROLES = ("platform_admin", "port_controller", "weighbridge_operator")
TRANSPORT_ROLES = ("platform_admin", "port_controller", "transporter_admin", "dispatcher", "cargo_owner", "warehouse_manager")
STAGE_ROLES: dict[str, tuple[str, ...]] = {
    "customs_cleared": TRANSPORT_ROLES, "arrived": TRANSPORT_ROLES + ("weighbridge_operator",),
    "gate_in": PORT_ROLES, "yard_allocated": PORT_ROLES, "loaded": PORT_ROLES, "weighed": PORT_ROLES, "final_cleared": PORT_ROLES, "gate_out": PORT_ROLES,
    "in_transit": TRANSPORT_ROLES, "delivered": TRANSPORT_ROLES,
}
STAGE_COLUMNS = [c for cols in svc.STAGE_FIELDS.values() for c in cols] + [
    "pre_registered_at", "customs_cleared_at", "arrived_at", "gate_in_at", "yard_allocated_at", "final_cleared_at", "gate_out_at", "departed_at", "delivered_at", "dwell_time_s", "transit_time_s", "cancel_reason",
]


class PortVisitIn(BaseModel):
    shipment_id: str | None = None
    vehicle_id: str | None = None
    driver_id: str | None = None
    appointment_id: str | None = None
    data: dict = Field(default_factory=dict, description="stage 1 fields: truck_type, cargo_type, declared_mass_kg, destination, appointment_at (+ container_number, expected_arrival_at)")
    at: datetime | None = None


class StageAdvanceIn(BaseModel):
    stage: str
    data: dict = Field(default_factory=dict)
    at: datetime | None = None


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


def _out(db, v: PortVisit, plates: dict[str, str] | None = None, refs: dict[str, str] | None = None) -> dict:
    plate = (plates or {}).get(v.vehicle_id) if v.vehicle_id else None
    if v.vehicle_id and plate is None:
        veh = db.get(Vehicle, v.vehicle_id)
        plate = veh.plate if veh else None
    sref = (refs or {}).get(v.shipment_id) if v.shipment_id else None
    if v.shipment_id and sref is None:
        sh = db.get(Shipment, v.shipment_id)
        sref = sh.reference if sh else None
    d = {
        "id": v.id, "reference": v.reference, "shipment_id": v.shipment_id, "shipment_reference": sref, "vehicle_id": v.vehicle_id, "plate": plate, "driver_id": v.driver_id,
        "transporter_org_id": v.transporter_org_id, "owner_org_id": v.owner_org_id, "appointment_id": v.appointment_id, "stage": v.stage, "stage_order": PORT_STAGE_META[v.stage]["order"],
        "stage_label": PORT_STAGE_META[v.stage]["label"], "status": v.status, "source": v.source,
        "timeline": list(v.timeline or []), "kpis": svc.kpis_for(v), "outstanding": svc.outstanding_for(v), "next_stage": svc.next_stage(v) if v.status == "active" else None,
        "created_at": v.created_at, "updated_at": v.updated_at,
    }
    for c in STAGE_COLUMNS:
        d[c] = getattr(v, c, None)
    return d


def _visible(p: Principal, v: PortVisit) -> bool:
    scope = org_scope(p)
    return scope is None or v.transporter_org_id == scope or v.owner_org_id == scope


@router.get("/stages")
def stages(p: CurrentUser):
    return [{"stage": s, **PORT_STAGE_META[s]} for s in PORT_STAGES]


@router.post("/visits", status_code=201)
def create_visit(body: PortVisitIn, db: DbDep, p: Principal = Depends(CREATE_ROLES)):
    shipment = db.get(Shipment, body.shipment_id) if body.shipment_id else None
    if body.shipment_id and shipment is None:
        raise HTTPException(404, "Shipment not found")
    vehicle = db.get(Vehicle, body.vehicle_id) if body.vehicle_id else None
    if body.vehicle_id and vehicle is None:
        raise HTTPException(404, "Vehicle not found")
    scope = org_scope(p)
    if scope and vehicle and vehicle.org_id != scope and not (shipment and shipment.owner_org_id == scope):
        raise HTTPException(403, "Vehicle belongs to another organisation")
    data = dict(body.data)
    if shipment:
        data.setdefault("cargo_type", shipment.cargo_type)
        data.setdefault("declared_mass_kg", shipment.declared_mass_kg)
        data.setdefault("destination", shipment.destination)
    if vehicle:
        data.setdefault("truck_type", vehicle.body_type)
    try:
        v = svc.create(db, shipment=shipment, vehicle_id=vehicle.id if vehicle else None, driver_id=body.driver_id,
                       transporter_org_id=vehicle.org_id if vehicle else (shipment.transporter_org_id if shipment else p.org_id),
                       owner_org_id=shipment.owner_org_id if shipment else (p.org_id if p.has_role("cargo_owner") else None),
                       appointment_id=body.appointment_id, data=data, source="simulated", at=body.at, actor_user_id=p.user.id)
    except svc.StageError as e:
        raise HTTPException(422, {"message": str(e), "missing": e.missing})
    audit(db, p, "create", "port_visit", v.id, after={"reference": v.reference, "stage": v.stage})
    db.commit()
    publish(EventType.CARGO_STATUS_CHANGED, {"port_visit": v.reference, "stage": v.stage, "shipment_id": v.shipment_id}, org_id=v.owner_org_id)
    return _out(db, v)


@router.get("/visits")
def list_visits(p: CurrentUser, db: DbDep, stage: str | None = None, vehicle_id: str | None = None, shipment_id: str | None = None, status: str | None = None, limit: int = Query(100, le=500)):
    q = select(PortVisit).order_by(PortVisit.updated_at.desc()).limit(limit)
    if stage:
        q = q.where(PortVisit.stage == stage)
    if vehicle_id:
        q = q.where(PortVisit.vehicle_id == vehicle_id)
    if shipment_id:
        q = q.where(PortVisit.shipment_id == shipment_id)
    if status:
        q = q.where(PortVisit.status == status)
    scope = org_scope(p)
    if scope:
        q = q.where((PortVisit.transporter_org_id == scope) | (PortVisit.owner_org_id == scope))
    rows = db.execute(q).scalars().all()
    plates = {v.id: v.plate for v in db.execute(select(Vehicle.id, Vehicle.plate).where(Vehicle.id.in_({r.vehicle_id for r in rows if r.vehicle_id}))).all()} if rows else {}
    refs = {s.id: s.reference for s in db.execute(select(Shipment.id, Shipment.reference).where(Shipment.id.in_({r.shipment_id for r in rows if r.shipment_id}))).all()} if rows else {}
    return [_out(db, v, plates, refs) for v in rows]


@router.get("/kpis")
def port_kpis(p: CurrentUser, db: DbDep, hours: int = Query(24, ge=1, le=24 * 90)):
    return svc.kpis(db, hours)


@router.get("/board")
def board(p: CurrentUser, db: DbDep):
    q = select(PortVisit).where(PortVisit.status == "active").order_by(PortVisit.updated_at.desc())
    scope = org_scope(p)
    if scope:
        q = q.where((PortVisit.transporter_org_id == scope) | (PortVisit.owner_org_id == scope))
    rows = db.execute(q).scalars().all()
    plates = {v.id: v.plate for v in db.execute(select(Vehicle.id, Vehicle.plate).where(Vehicle.id.in_({r.vehicle_id for r in rows if r.vehicle_id}))).all()} if rows else {}
    refs = {s.id: s.reference for s in db.execute(select(Shipment.id, Shipment.reference).where(Shipment.id.in_({r.shipment_id for r in rows if r.shipment_id}))).all()} if rows else {}
    cols = []
    for s in PORT_STAGES:
        here = [v for v in rows if v.stage == s]
        cols.append({"stage": s, "label": PORT_STAGE_META[s]["label"], "order": PORT_STAGE_META[s]["order"], "agency": PORT_STAGE_META[s]["agency"], "count": len(here), "visits": [_out(db, v, plates, refs) for v in here[:20]]})
    return {"stages": cols, "active_total": len(rows)}


class PortSimIn(BaseModel):
    trucks_per_day: int = Field(default=2400, ge=100, le=20000)
    hours: float = Field(default=24.0, ge=2, le=72)
    gates_in: int = Field(default=12, ge=1, le=60)
    gates_out: int = Field(default=12, ge=1, le=60)
    gate_service_existing_s: float = Field(default=240.0, ge=10, le=3600)
    gate_service_smart_s: float = Field(default=60.0, ge=5, le=3600)
    loading_equipment: int = Field(default=70, ge=1, le=500)
    loading_minutes_container: float = Field(default=20.0, ge=1, le=240)
    loading_minutes_bulk: float = Field(default=30.0, ge=1, le=240)
    loading_minutes_general: float = Field(default=25.0, ge=1, le=240)
    weighbridges: int = Field(default=14, ge=1, le=60)
    weigh_service_existing_s: float = Field(default=300.0, ge=10, le=3600)
    weigh_service_smart_s: float = Field(default=90.0, ge=5, le=3600)
    clearance_desks: int = Field(default=16, ge=1, le=100)
    clearance_minutes: float = Field(default=6.0, ge=1, le=240)
    hold_prob_existing: float = Field(default=0.15, ge=0, le=1)
    hold_prob_smart: float = Field(default=0.05, ge=0, le=1)
    hold_minutes: float = Field(default=45.0, ge=1, le=600)
    appointment_smoothing: bool = True
    peak_factor: float = Field(default=1.5, ge=1, le=3)
    inland_distance_km: float = Field(default=482.0, ge=10, le=2000)
    inland_speed_kmh: float = Field(default=45.0, ge=10, le=120)
    stop_prob: float = Field(default=0.3, ge=0, le=1)
    stop_minutes: float = Field(default=40.0, ge=1, le=600)
    seed: int = 1
    reps: int = Field(default=3, ge=1, le=10)


@router.post("/simulate")
def simulate(body: PortSimIn, p: CurrentUser):
    """Existing port operations versus the SmartPort policy (SimPy, modelled). Never a measurement."""
    try:
        from kifaru_sim.port_process import PortSimConfig, compare
    except ImportError as e:  # pragma: no cover
        raise HTTPException(503, f"simulation package not installed: {e}")
    return compare(PortSimConfig(**body.model_dump()))


@router.get("/visits/{visit_id}")
def get_visit(visit_id: str, p: CurrentUser, db: DbDep):
    v = db.get(PortVisit, visit_id)
    if v is None and len(visit_id) < 26:
        v = db.execute(select(PortVisit).where(PortVisit.reference == visit_id.upper())).scalar_one_or_none()
    if v is None or not _visible(p, v):
        raise HTTPException(404, "Port visit not found")
    return _out(db, v)


@router.post("/visits/{visit_id}/advance")
def advance_visit(visit_id: str, body: StageAdvanceIn, p: CurrentUser, db: DbDep):
    v = db.get(PortVisit, visit_id)
    if v is None or not _visible(p, v):
        raise HTTPException(404, "Port visit not found")
    if body.stage not in PORT_STAGE_META:
        raise HTTPException(422, {"message": f"unknown stage {body.stage}", "missing": []})
    allowed = STAGE_ROLES.get(body.stage, ("platform_admin",))
    if not p.has_role(*allowed):
        raise HTTPException(403, f"Stage {body.stage} may only be advanced by: {', '.join(allowed)}")
    before = v.stage
    try:
        svc.advance(db, v, body.stage, body.data, at=body.at, actor_user_id=p.user.id)
    except svc.StageError as e:
        raise HTTPException(422, {"message": str(e), "missing": e.missing})
    audit(db, p, "advance", "port_visit", v.id, before={"stage": before}, after={"stage": v.stage})
    db.commit()
    db.refresh(v)
    publish(EventType.CARGO_STATUS_CHANGED, {"port_visit": v.reference, "stage": v.stage, "shipment_id": v.shipment_id, "dwell_time_s": v.dwell_time_s}, org_id=v.owner_org_id)
    return _out(db, v)


@router.post("/visits/{visit_id}/cancel")
def cancel_visit(visit_id: str, body: CancelIn, db: DbDep, p: Principal = Depends(CREATE_ROLES)):
    v = db.get(PortVisit, visit_id)
    if v is None or not _visible(p, v):
        raise HTTPException(404, "Port visit not found")
    if v.status != "active":
        raise HTTPException(409, f"visit is {v.status}")
    svc.cancel(db, v, body.reason, p.user.id)
    audit(db, p, "cancel", "port_visit", v.id, after=body.model_dump())
    db.commit()
    return _out(db, v)
