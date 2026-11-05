"""RCS v2 clearance registry: Load Compliance Tokens, Reg 14 release orders, special-load permits, trust-tier policy,
stream / route statistics and the Monte Carlo chain model (docs/02-architecture/rcs-v2-api-contract.md §4)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..config import get_settings
from ..deps import CurrentUser, DbDep, Principal, audit, org_scope, require_roles
from ..events import EventType, publish
from ..models import (
    ClearanceDecision,
    LoadComplianceToken,
    ReleaseOrder,
    SpecialLoadPermit,
    User,
    Vehicle,
    WeighingEvent,
    WeighingStation,
    utcnow,
)
from ..services import clearance_engine as ce
from ..services import ledger
from ..services import release_orders as ro_svc
from ..services import tokens as token_svc
from ..services.limits import DEFAULT_LIMITS

router = APIRouter(prefix="/rcs", tags=["rcs-v2"])
OPS = require_roles("platform_admin", "weighbridge_operator", "port_controller")
OFFICER = require_roles("platform_admin", "weighbridge_operator", mfa=True)
FLEET = require_roles("platform_admin", "transporter_admin")

LEGAL_HOOKS = [
    {"reg": "Reg 3(3)", "says": "The roads authority may outsource weighbridge operation, management and maintenance to private operators.", "consequence": "A legal route for a private partner role."},
    {"reg": "Reg 3(4) / 11(3)", "says": "Weighbridge tickets and release orders for overloaded vehicles are reserved to authorised officers.", "consequence": "The platform prepares everything; an officer e-signs the red cases (release orders require MFA)."},
    {"reg": "Reg 4(5)–(6)", "says": "Mobile weighbridges and surveillance technology may be used; a vehicle found in breach is escorted to the nearest static weighbridge.", "consequence": "RCS readings decide who needs a static weighing; they never replace it as proof of overload."},
    {"reg": "Reg 5", "says": "Any weighbridge needs approval and a certificate from the national weights-and-measures body.", "consequence": "Lane.legal_grade is false until approval; only then can a lane reading settle a near-limit case."},
    {"reg": "Reg 6 / 8", "says": "Calibration at least every three months by an accredited calibrator; audit every twelve months.", "consequence": "Calibration register with quarterly records; expired calibration blocks GREEN."},
    {"reg": "Reg 9(1)", "says": "The duty to submit for weighing arises on direction by an authorised officer or a weighbridge road sign.", "consequence": "Driver signals must be approved signs; no direction means no duty to stop."},
    {"reg": "Reg 10(2)", "says": "Except for a vehicle previously confirmed within limits by surveillance or screening devices, a transporter must produce the certificate on request.", "consequence": "The legal hook for the Load Compliance Token replacing the paper certificate."},
    {"reg": "Reg 10(4)", "says": "A certificate from any weighbridge is accepted as proof unless there is apparent forgery, tampering or manifest error.", "consequence": "Tokens and certificates are Ed25519-signed and tamper-evident."},
    {"reg": "Reg 12(3)", "says": "Electronic payment is allowed.", "consequence": "Release orders carry a computed fee and can be marked paid electronically."},
    {"reg": "Reg 14", "says": "A release order must be kept for the journey and shown at later weighbridges; a second overload in the same journey triples the fees.", "consequence": "Digital release-order registry with repeat-offence detection inside the journey window."},
    {"reg": "Reg 18", "says": "Transit cargo certificates are shown at every later weighbridge; an overloaded transit vehicle is detained until a customs officer breaks the seal.", "consequence": "A transit release order flags customs_notified the moment the overload is confirmed."},
    {"reg": "Reg 20 / Fifth Schedule", "says": "Demerit points go against the vehicle, transporter and driver declared in the trip plan.", "consequence": "Vehicle.demerit_points feeds the audit rate."},
    {"reg": "Second Schedule", "says": "The certificate records measured load, allowed load, a discretion allowance of less than 5 %, adjusted load, overload and fee.", "consequence": "LimitSet.discretion_allowance_pct is a policy value; the release order records the full arithmetic."},
    {"reg": "Third Schedule / Reg 13", "says": "Legal weights: steering 8 t, single drive 10 t, tandem 18 t, tridem 24 t; 5 000 kg over gross ≈ 2 990 USD; detention free for three days then 50 USD a day.", "consequence": "Values in services/limits.py, flagged for verification."},
]


# ============================================================================ policy
class TrustTierOut(BaseModel):
    tier: int
    source: str
    label: str
    audit_rate: float
    description: str


@router.get("/trust-tiers", response_model=list[TrustTierOut])
def trust_tiers(p: CurrentUser):
    return [TrustTierOut(**t) for t in token_svc.trust_tiers()]


@router.get("/policy")
def policy(p: CurrentUser):
    lim = DEFAULT_LIMITS
    return {
        "limits_version": lim.version,
        "engine_version": ce.ENGINE_VERSION,
        "discretion_allowance_pct": lim.discretion_allowance_pct,
        "token_tolerance": token_svc.tolerance_by_source(),
        "token_validity_hours": token_svc.validity_hours_by_source(),
        "trust_tiers": token_svc.trust_tiers(),
        "fee_schedule": lim.fee_schedule(),
        "dimension_limits": {"max_length_m": lim.max_length_m, "max_width_m": lim.max_width_m, "max_height_m": lim.max_height_m},
        "reported_gvm_by_axles": {str(k): v for k, v in __import__("kifaru.services.limits", fromlist=["REPORTED_GVM_BY_AXLES"]).REPORTED_GVM_BY_AXLES.items()},
        "legal_hooks": LEGAL_HOOKS,
        "notes": lim.notes,
    }


# ============================================================================ tokens
class TokenOut(BaseModel):
    id: str
    token_ref: str
    vehicle_id: str | None
    plate: str | None
    trailer_plate: str | None
    rfid_epc: str | None
    container_number: str | None
    seal_id: str | None
    shipment_id: str | None
    source: str
    trust_tier: int
    gvm_kg: int
    expected_gvm_kg: int | None
    variance_kg: int | None
    axle_group_loads_kg: list
    axle_config: str | None
    dimensions: dict | None
    permit_ref: str | None
    release_status: dict
    route: str | None
    destination: str | None
    driver_id: str | None
    issued_at: datetime
    expires_at: datetime
    issuing_station_id: str
    issuing_station_code: str
    issuing_event_id: str
    status: str
    honoured_count: int
    last_honoured_at: datetime | None
    suspended_reason: str | None
    signature: str
    signer_key_id: str
    signature_valid: bool
    source_label: str


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _token_out(db, t: LoadComplianceToken, codes: dict[str, str] | None = None) -> TokenOut:
    code = (codes or {}).get(t.issuing_station_id) or token_svc.station_code(db, t.issuing_station_id)
    # lazily mark expiry on read so the registry never shows a stale "active"
    if t.status == "active" and _aware(t.expires_at) < utcnow():
        t.status = "expired"
    return TokenOut(
        id=t.id, token_ref=t.token_ref, vehicle_id=t.vehicle_id, plate=t.plate, trailer_plate=t.trailer_plate, rfid_epc=t.rfid_epc,
        container_number=t.container_number, seal_id=t.seal_id, shipment_id=t.shipment_id, source=t.source, trust_tier=t.trust_tier, gvm_kg=t.gvm_kg,
        expected_gvm_kg=t.expected_gvm_kg, variance_kg=t.variance_kg, axle_group_loads_kg=list(t.axle_group_loads_kg or []), axle_config=t.axle_config,
        dimensions=t.dimensions, permit_ref=t.permit_ref, release_status=t.release_status or {}, route=t.route, destination=t.destination, driver_id=t.driver_id,
        issued_at=t.issued_at, expires_at=t.expires_at, issuing_station_id=t.issuing_station_id, issuing_station_code=code, issuing_event_id=t.issuing_event_id,
        status=t.status, honoured_count=t.honoured_count or 0, last_honoured_at=t.last_honoured_at, suspended_reason=t.suspended_reason,
        signature=t.signature, signer_key_id=t.signer_key_id, signature_valid=token_svc.verify(t), source_label=t.source_label,
    )


def _station_codes(db) -> dict[str, str]:
    return {s.id: s.code for s in db.execute(select(WeighingStation)).scalars()}


@router.get("/tokens", response_model=list[TokenOut])
def list_tokens(p: CurrentUser, db: DbDep, status: str | None = None, source: str | None = None, vehicle_id: str | None = None,
                station_id: str | None = None, limit: int = Query(100, le=500)):
    q = select(LoadComplianceToken).order_by(LoadComplianceToken.issued_at.desc()).limit(limit)
    if status:
        q = q.where(LoadComplianceToken.status == status)
    if source:
        q = q.where(LoadComplianceToken.source == source)
    if vehicle_id:
        q = q.where(LoadComplianceToken.vehicle_id == vehicle_id)
    if station_id:
        q = q.where(LoadComplianceToken.issuing_station_id == station_id)
    scope = org_scope(p)
    if scope:
        q = q.join(Vehicle, Vehicle.id == LoadComplianceToken.vehicle_id).where(Vehicle.org_id == scope)
    codes = _station_codes(db)
    out = [_token_out(db, t, codes) for t in db.execute(q).scalars().all()]
    db.commit()
    return out


@router.get("/tokens/lookup", response_model=TokenOut)
def lookup_token(p: CurrentUser, db: DbDep, plate: str = Query(min_length=3)):
    norm = plate.replace(" ", "").upper()
    v = db.execute(select(Vehicle).where(Vehicle.plate_norm == norm)).scalar_one_or_none()
    scope = org_scope(p)
    if v is not None and scope and v.org_id != scope:
        raise HTTPException(404, "No active token for this plate")
    t = token_svc.active_for_vehicle(db, v.id if v else None, plate if not v else None)
    if t is None:
        raise HTTPException(404, "No active token for this plate")
    out = _token_out(db, t)
    db.commit()
    return out


class TokenVerifyOut(BaseModel):
    valid: bool
    status: str | None = None
    plate: str | None = None
    source: str | None = None
    trust_tier: int | None = None
    gvm_kg: int | None = None
    issued_at: str | None = None
    expires_at: str | None = None
    issuing_station: str | None = None
    honoured_count: int | None = None
    signature_valid: bool = False
    source_label: str | None = None
    note: str | None = None


@router.get("/tokens/verify/{token_ref}", response_model=TokenVerifyOut, tags=["public"])
def verify_token_public(token_ref: str, db: DbDep):
    """Public, unauthenticated check of a Load Compliance Token by its reference (QR). Non-sensitive fields only."""
    t = db.execute(select(LoadComplianceToken).where(LoadComplianceToken.token_ref == token_ref.upper())).scalar_one_or_none()
    if t is None:
        return TokenVerifyOut(valid=False, note="no token matches this reference")
    sig_ok = token_svc.verify(t)
    if t.status == "active" and _aware(t.expires_at) < utcnow():
        t.status = "expired"
        db.commit()
    usable = sig_ok and t.status == "active"
    note = None if usable else ("signature does not verify — treat as tampered" if not sig_ok else f"token is {t.status}" + (f": {t.suspended_reason}" if t.suspended_reason else ""))
    return TokenVerifyOut(valid=usable, status=t.status, plate=t.plate, source=t.source, trust_tier=t.trust_tier, gvm_kg=t.gvm_kg,
                          issued_at=_aware(t.issued_at).isoformat(), expires_at=_aware(t.expires_at).isoformat(), issuing_station=token_svc.station_code(db, t.issuing_station_id),
                          honoured_count=t.honoured_count or 0, signature_valid=sig_ok, source_label=t.source_label, note=note)


@router.get("/tokens/{token_id}", response_model=TokenOut)
def get_token(token_id: str, p: CurrentUser, db: DbDep):
    t = db.get(LoadComplianceToken, token_id)
    if t is None:
        raise HTTPException(404, "Token not found")
    scope = org_scope(p)
    if scope:
        v = db.get(Vehicle, t.vehicle_id) if t.vehicle_id else None
        if v is None or v.org_id != scope:
            raise HTTPException(404, "Token not found")
    out = _token_out(db, t)
    db.commit()
    return out


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


def _change_token(db, p: Principal, token_id: str, body: ReasonIn, revoke: bool) -> TokenOut:
    t = db.get(LoadComplianceToken, token_id)
    if t is None:
        raise HTTPException(404, "Token not found")
    before = t.status
    token_svc.suspend(t, body.reason, revoke=revoke)
    ledger.append(db, "token.revoked" if revoke else "token.suspended", {"token_id": t.id, "token_ref": t.token_ref, "reason": body.reason, "by": p.user.id}, station_id=t.issuing_station_id, producer="operator")
    audit(db, p, "revoke" if revoke else "suspend", "load_compliance_token", t.id, before={"status": before}, after={"status": t.status, "reason": body.reason})
    db.commit()
    return _token_out(db, t)


@router.post("/tokens/{token_id}/suspend", response_model=TokenOut)
def suspend_token(token_id: str, body: ReasonIn, db: DbDep, p: Principal = Depends(OPS)):
    return _change_token(db, p, token_id, body, revoke=False)


@router.post("/tokens/{token_id}/revoke", response_model=TokenOut)
def revoke_token(token_id: str, body: ReasonIn, db: DbDep, p: Principal = Depends(OPS)):
    return _change_token(db, p, token_id, body, revoke=True)


# ============================================================================ release orders
class ReleaseOrderIn(BaseModel):
    weighing_event_id: str
    static_gvm_kg: int | None = Field(default=None, ge=500, le=90000)
    transit: bool = False
    hazardous: bool = False
    perishable: bool = False
    detention_days: int = Field(default=0, ge=0, le=60)
    journey_ref: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=1000)


class ReleaseOrderOut(BaseModel):
    id: str
    order_ref: str
    vehicle_id: str | None
    plate: str | None
    weighing_event_id: str
    decision_id: str
    station_code: str
    measured_gvm_kg: int
    allowed_gvm_kg: int
    allowance_kg: int
    adjusted_gvm_kg: int
    overload_kg: int
    fee_usd: float
    fee_multiplier: float
    repeat_offence: bool
    detention_days: int
    detention_usd: float
    total_usd: float
    transit: bool
    customs_notified: bool
    hazardous: bool
    perishable: bool
    officer_user_id: str
    officer_name: str | None
    officer_signature: str
    status: str
    issued_at: datetime
    valid_until: datetime
    journey_ref: str | None
    notes: str | None
    source_label: str


def _ro_out(db, o: ReleaseOrder, codes: dict[str, str] | None = None) -> ReleaseOrderOut:
    code = (codes or {}).get(o.station_id) or token_svc.station_code(db, o.station_id)
    u = db.get(User, o.officer_user_id)
    name = u.pii.full_name if u and u.pii else None
    return ReleaseOrderOut(
        id=o.id, order_ref=o.order_ref, vehicle_id=o.vehicle_id, plate=o.plate, weighing_event_id=o.weighing_event_id, decision_id=o.decision_id, station_code=code,
        measured_gvm_kg=o.measured_gvm_kg, allowed_gvm_kg=o.allowed_gvm_kg, allowance_kg=o.allowance_kg, adjusted_gvm_kg=o.adjusted_gvm_kg, overload_kg=o.overload_kg,
        fee_usd=o.fee_usd, fee_multiplier=o.fee_multiplier, repeat_offence=o.repeat_offence, detention_days=o.detention_days, detention_usd=o.detention_usd, total_usd=o.total_usd,
        transit=o.transit, customs_notified=o.customs_notified, hazardous=o.hazardous, perishable=o.perishable, officer_user_id=o.officer_user_id, officer_name=name,
        officer_signature=o.officer_signature, status=o.status, issued_at=o.issued_at, valid_until=o.valid_until, journey_ref=o.journey_ref, notes=o.notes, source_label=o.source_label,
    )


@router.get("/release-orders", response_model=list[ReleaseOrderOut])
def list_release_orders(p: CurrentUser, db: DbDep, status: str | None = None, vehicle_id: str | None = None, limit: int = Query(100, le=500)):
    q = select(ReleaseOrder).order_by(ReleaseOrder.issued_at.desc()).limit(limit)
    if status:
        q = q.where(ReleaseOrder.status == status)
    if vehicle_id:
        q = q.where(ReleaseOrder.vehicle_id == vehicle_id)
    scope = org_scope(p)
    if scope:
        q = q.join(Vehicle, Vehicle.id == ReleaseOrder.vehicle_id).where(Vehicle.org_id == scope)
    codes = _station_codes(db)
    return [_ro_out(db, o, codes) for o in db.execute(q).scalars().all()]


@router.post("/release-orders", response_model=ReleaseOrderOut, status_code=201)
def issue_release_order(body: ReleaseOrderIn, db: DbDep, p: Principal = Depends(OFFICER)):
    """Officer-signed Reg 14 release order for a RED pass (or a pass whose static verification shows an overload)."""
    ev = db.get(WeighingEvent, body.weighing_event_id)
    if ev is None or ev.decision is None:
        raise HTTPException(404, "Weighing event not found")
    d: ClearanceDecision = ev.decision
    measured = body.static_gvm_kg or d.static_verified_gvm_kg
    if d.decision != "RED" and measured is None:
        raise HTTPException(409, "A release order requires a RED decision or a static-verified overload")
    if db.execute(select(ReleaseOrder).where(ReleaseOrder.weighing_event_id == ev.id)).scalar_one_or_none():
        raise HTTPException(409, "A release order already exists for this pass")
    allowed = int((d.margins or {}).get("gvm", {}).get("limit_kg") or DEFAULT_LIMITS.gvm_max_kg)
    if measured is not None and ro_svc.fee_preview(measured, allowed)["overload_kg"] <= 0 and d.decision != "RED":
        raise HTTPException(409, "No overload after the discretion allowance; a release order is not required")
    if body.static_gvm_kg and d.static_verified_gvm_kg is None:
        d.static_verified_gvm_kg = body.static_gvm_kg
    order = ro_svc.issue(db, ev, d, p.user.id, static_gvm_kg=body.static_gvm_kg, transit=body.transit, hazardous=body.hazardous,
                         perishable=body.perishable, journey_ref=body.journey_ref, notes=body.notes, detention_days=body.detention_days)
    ledger.append(db, "release_order.issued", {"order_ref": order.order_ref, "weighing_event_id": ev.id, "overload_kg": order.overload_kg, "fee_usd": order.fee_usd,
                                                "multiplier": order.fee_multiplier, "repeat_offence": order.repeat_offence, "officer": p.user.id, "transit": order.transit},
                  station_id=ev.station_id, producer="officer")
    audit(db, p, "issue", "release_order", order.id, after=body.model_dump())
    publish(EventType.CARGO_STATUS_CHANGED, {"release_order": order.order_ref, "plate": order.plate, "overload_kg": order.overload_kg, "customs_notified": order.customs_notified},
            station_id=ev.station_id)
    db.commit()
    return _ro_out(db, order)


@router.get("/release-orders/{order_id}", response_model=ReleaseOrderOut)
def get_release_order(order_id: str, p: CurrentUser, db: DbDep):
    o = db.get(ReleaseOrder, order_id)
    if o is None:
        raise HTTPException(404, "Release order not found")
    scope = org_scope(p)
    if scope:
        v = db.get(Vehicle, o.vehicle_id) if o.vehicle_id else None
        if v is None or v.org_id != scope:
            raise HTTPException(404, "Release order not found")
    return _ro_out(db, o)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(paid|closed)$")


@router.post("/release-orders/{order_id}/status", response_model=ReleaseOrderOut)
def set_release_order_status(order_id: str, body: StatusIn, db: DbDep, p: Principal = Depends(OPS)):
    o = db.get(ReleaseOrder, order_id)
    if o is None:
        raise HTTPException(404, "Release order not found")
    audit(db, p, "status", "release_order", o.id, before={"status": o.status}, after=body.model_dump())
    o.status = body.status
    ledger.append(db, f"release_order.{body.status}", {"order_ref": o.order_ref, "by": p.user.id}, station_id=o.station_id, producer="operator")
    db.commit()
    return _ro_out(db, o)


# ============================================================================ permits
class PermitIn(BaseModel):
    vehicle_id: str
    reference: str = Field(min_length=3, max_length=40)
    max_length_m: float = Field(gt=0, le=60)
    max_width_m: float = Field(gt=0, le=10)
    max_height_m: float = Field(gt=0, le=8)
    max_gvm_kg: int | None = Field(default=None, ge=1000, le=200000)
    valid_from: datetime
    valid_to: datetime
    route: str | None = Field(default=None, max_length=200)


class PermitOut(PermitIn):
    id: str
    plate: str
    status: str


def _permit_out(pm: SpecialLoadPermit, plate: str) -> PermitOut:
    now = utcnow()
    vf, vt = _aware(pm.valid_from), _aware(pm.valid_to)
    status = "future" if vf > now else ("expired" if vt < now else "valid")
    return PermitOut(id=pm.id, plate=plate, status=status, vehicle_id=pm.vehicle_id, reference=pm.reference, max_length_m=pm.max_length_m, max_width_m=pm.max_width_m,
                     max_height_m=pm.max_height_m, max_gvm_kg=pm.max_gvm_kg, valid_from=pm.valid_from, valid_to=pm.valid_to, route=pm.route)


@router.get("/permits", response_model=list[PermitOut])
def list_permits(p: CurrentUser, db: DbDep, vehicle_id: str | None = None):
    q = select(SpecialLoadPermit, Vehicle.plate).join(Vehicle, Vehicle.id == SpecialLoadPermit.vehicle_id).order_by(SpecialLoadPermit.valid_to.desc())
    if vehicle_id:
        q = q.where(SpecialLoadPermit.vehicle_id == vehicle_id)
    scope = org_scope(p)
    if scope:
        q = q.where(Vehicle.org_id == scope)
    return [_permit_out(pm, plate) for pm, plate in db.execute(q).all()]


@router.post("/permits", response_model=PermitOut, status_code=201)
def create_permit(body: PermitIn, db: DbDep, p: Principal = Depends(FLEET)):
    v = db.get(Vehicle, body.vehicle_id)
    if v is None:
        raise HTTPException(404, "Vehicle not found")
    scope = org_scope(p)
    if scope and v.org_id != scope:
        raise HTTPException(403, "Vehicle belongs to another organisation")
    if body.valid_to <= body.valid_from:
        raise HTTPException(422, "valid_to must be after valid_from")
    pm = SpecialLoadPermit(**body.model_dump())
    db.add(pm)
    db.flush()
    audit(db, p, "create", "special_load_permit", pm.id, after=body.model_dump(mode="json"))
    db.commit()
    return _permit_out(pm, v.plate)


# ============================================================================ stats
ROUTES = ("continue", "verification_lane", "static_scale", "port_reweigh", "hold")


@router.get("/stats")
def stats(p: CurrentUser, db: DbDep, station_id: str | None = None):
    q = select(WeighingEvent.station_id, WeighingEvent.stream, ClearanceDecision.route, func.count()).join(ClearanceDecision, ClearanceDecision.weighing_event_id == WeighingEvent.id)
    if station_id:
        q = q.where(WeighingEvent.station_id == station_id)
    rows = db.execute(q.group_by(WeighingEvent.station_id, WeighingEvent.stream, ClearanceDecision.route)).all()
    by_stream = {"port": 0, "origin": 0, "untokened": 0}
    by_route = {r: 0 for r in ROUTES}
    per: dict[str, dict] = {}
    stations = {s.id: s for s in db.execute(select(WeighingStation)).scalars()}
    total = 0
    for sid, stream, route, c in rows:
        total += c
        by_stream[stream or "untokened"] = by_stream.get(stream or "untokened", 0) + c
        by_route[route or "continue"] = by_route.get(route or "continue", 0) + c
        st = per.setdefault(sid, {"station_id": sid, "code": stations[sid].code if sid in stations else sid, "kind": stations[sid].kind if sid in stations else "road_station", "total": 0, "routes": {r: 0 for r in ROUTES}})
        st["total"] += c
        st["routes"][route or "continue"] = st["routes"].get(route or "continue", 0) + c
    for st in per.values():
        n = st["total"] or 1
        st["lane_share"] = st["routes"]["verification_lane"] / n
        st["static_share"] = (st["routes"]["static_scale"] + st["routes"]["hold"]) / n
    tokened = by_stream["port"] + by_stream["origin"]
    # one grouped query for the token registry (active count, issued by source, honoured total) and one for open orders
    active, by_src, honoured = 0, {}, 0
    for src, status_, c, hon in db.execute(select(LoadComplianceToken.source, LoadComplianceToken.status, func.count(), func.coalesce(func.sum(LoadComplianceToken.honoured_count), 0))
                                           .group_by(LoadComplianceToken.source, LoadComplianceToken.status)).all():
        by_src[src] = by_src.get(src, 0) + c
        honoured += int(hon or 0)
        if status_ == "active":
            active += c
    open_ro = db.execute(select(func.count()).select_from(ReleaseOrder).where(ReleaseOrder.status == "issued")).scalar() or 0
    return {
        "total": total, "by_stream": by_stream, "by_route": by_route, "token_coverage": (tokened / total) if total else 0.0,
        "tokens_active": active, "tokens_issued_by_source": by_src, "honoured_total": int(honoured), "release_orders_open": open_ro,
        "per_station": sorted(per.values(), key=lambda x: x["code"]),
    }


# ============================================================================ chain model (Monte Carlo, modelled)
class RcsModelIn(BaseModel):
    avg_loading_pct: float = Field(default=85.0, ge=50, le=100)
    load_spread_pct: float = Field(default=12.0, ge=1, le=30)
    overload_prob: float = Field(default=0.015, ge=0, le=0.5)
    token_coverage: float = Field(default=0.9, ge=0, le=1)
    stream_mix: dict[str, float] | None = None
    port_error_pct: float = Field(default=1.0, ge=0.1, le=10)
    origin_error_pct: float = Field(default=1.0, ge=0.1, le=10)
    road_error_pct: float = Field(default=2.5, ge=0.1, le=10)
    lane_error_pct: float = Field(default=1.0, ge=0.1, le=10)
    lane_margin_pct: float = Field(default=2.0, ge=0, le=10)
    allowance_pct: float = Field(default=0.0, ge=0, le=5)
    audit_rate: float = Field(default=0.03, ge=0, le=0.2)
    port_legal_grade: bool = False
    lane_legal_grade: bool = False
    trucks_per_day: int = Field(default=8000, ge=100, le=50000)
    stop_minutes: float = Field(default=6.0, ge=0.5, le=60)
    lane_minutes: float = Field(default=1.5, ge=0.1, le=30)
    peak_per_hour: int = Field(default=500, ge=10, le=5000)
    n: int = Field(default=200_000, ge=1000, le=600_000)
    seed: int = 1


class RcsSweepIn(BaseModel):
    factor: str
    values: list[float] = Field(min_length=1, max_length=12)
    base: RcsModelIn = Field(default_factory=RcsModelIn)


def _chain():
    try:
        from kifaru_sim import rcs_v2
    except ImportError as e:  # pragma: no cover
        raise HTTPException(503, f"simulation package not installed: {e}")
    return rcs_v2


@router.post("/model")
def run_model(body: RcsModelIn, p: CurrentUser):
    """Monte Carlo of the RCS v2 clearance chain (plan §9). Output is MODELLED and must never be reported as measured."""
    rcs_v2 = _chain()
    params = rcs_v2.ChainParams(**body.model_dump())
    return rcs_v2.run_chain(params).to_dict()


@router.post("/model/sweep")
def run_sweep(body: RcsSweepIn, p: CurrentUser):
    _chain()
    if body.factor not in RcsModelIn.model_fields:
        raise HTTPException(422, f"unknown factor {body.factor}")
    try:
        from kifaru_sim.experiments import sweep
    except ImportError as e:  # pragma: no cover
        raise HTTPException(503, f"simulation package not installed: {e}")
    return sweep(body.factor, body.values, body.base.model_dump())


@router.get("/instructions")
def instructions(p: CurrentUser):
    return {"by_route": ce.INSTRUCTIONS_BY_ROUTE, "settings": {"audit_sample_rate": get_settings().audit_sample_rate}}
