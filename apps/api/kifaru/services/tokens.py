"""Load Compliance Tokens (RCS v2 §6.2): issue at the first verified weighing point, look up and honour downstream.

A token is a signed record (Ed25519 over its canonical payload). It is issued only from a GREEN decision at a token-issuing
node (port gate-out, approved origin scale, road mainline node, rolling verification lane). Later stations compare their
reading with the token weight instead of judging the absolute weight against the limit (clearance_engine.TokenInput).

Legal basis: Reg 10(2) (vehicles previously confirmed compliant by screening devices need not produce the paper certificate),
Reg 10(4) and 18(2) (certificates from earlier weighbridges are accepted as proof). A token never replaces the static scale as
proof of overload (Reg 4(6), 18(3)).
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ClearanceDecision, LoadComplianceToken, Shipment, Vehicle, WeighingEvent, WeighingStation, utcnow
from ..security import public_key_b64, sign_payload, verify_signature
from . import clearance_engine as ce

TRUST_TIERS: list[dict] = [
    {"tier": 1, "source": "port", "label": "Port gate-out node", "description": "Low-speed weighing at the KPA exit lane, container and seal captured, releases verified. Cargo rarely changes after the port."},
    {"tier": 2, "source": "origin", "label": "Approved origin scale", "description": "Weights-and-measures approved scale at a mine, quarry, factory or depot, linked to the registry. Audit rate falls with a clean record."},
    {"tier": 3, "source": "road", "label": "Road node or verification lane", "description": "First road station or the rolling verification lane for untokened trucks."},
    {"tier": 4, "source": "onboard", "label": "On-board signed record only", "description": "Air-suspension pressure or load-cell telematics; informs the risk score but never issues a token. Always verified in the lane at first."},
]


def tolerance_by_source() -> dict[str, float]:
    s = get_settings()
    return {"port": s.token_tolerance_port, "origin": s.token_tolerance_origin, "lane": s.token_tolerance_lane, "road": s.token_tolerance_road}


def validity_hours_by_source() -> dict[str, int]:
    s = get_settings()
    return {"port": s.token_validity_hours_port, "origin": s.token_validity_hours_origin, "lane": s.token_validity_hours_lane, "road": s.token_validity_hours_road}


def audit_rate_by_tier() -> dict[int, float]:
    s = get_settings()
    return {1: s.audit_rate_tier1, 2: s.audit_rate_tier2, 3: s.audit_rate_tier3, 4: s.audit_rate_tier4}


def trust_tiers() -> list[dict]:
    rates = audit_rate_by_tier()
    return [{**t, "audit_rate": rates[t["tier"]]} for t in TRUST_TIERS]


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _canonical(t: LoadComplianceToken) -> dict:
    return {
        "token_ref": t.token_ref, "vehicle_id": t.vehicle_id, "plate": t.plate, "trailer_plate": t.trailer_plate, "rfid_epc": t.rfid_epc,
        "container_number": t.container_number, "seal_id": t.seal_id, "shipment_id": t.shipment_id, "driver_id": t.driver_id,
        "source": t.source, "trust_tier": t.trust_tier, "gvm_kg": t.gvm_kg, "expected_gvm_kg": t.expected_gvm_kg, "variance_kg": t.variance_kg,
        "axle_group_loads_kg": list(t.axle_group_loads_kg or []), "axle_config": t.axle_config, "dimensions": t.dimensions, "permit_ref": t.permit_ref,
        "release_status": t.release_status, "route": t.route, "destination": t.destination,
        "issued_at": _aware(t.issued_at).isoformat(), "expires_at": _aware(t.expires_at).isoformat(),
        "issuing_station_id": t.issuing_station_id, "issuing_event_id": t.issuing_event_id, "source_label": t.source_label,
    }


def issue(
    db: Session,
    ev: WeighingEvent,
    dec: ClearanceDecision,
    vehicle: Vehicle | None,
    shipment: Shipment | None,
    source: str,
    *,
    plate: str | None,
    rfid_epc: str | None,
    seal_id: str | None,
    expected_gvm_kg: int | None,
    dimensions: dict | None,
    permit_ref: str | None,
    release_status: dict | None = None,
    trust_tier: int | None = None,
) -> LoadComplianceToken:
    """Create and sign a token from a GREEN decision. `source` is port | origin | road | lane."""
    s = get_settings()
    hours = validity_hours_by_source().get(source, 24)
    now = ev.occurred_at if ev.occurred_at else utcnow()
    now = _aware(now)
    groups: dict[int, int] = {}
    for a in ev.axles:
        groups[a.group_no] = groups.get(a.group_no, 0) + a.load_kg
    tier = trust_tier if trust_tier is not None else ce.TRUST_TIER_BY_SOURCE.get(source, 3)
    container = shipment.containers[0].number if shipment and shipment.containers else None
    t = LoadComplianceToken(
        token_ref="LCT-" + secrets.token_urlsafe(9).replace("-", "x").replace("_", "y").upper()[:12],
        vehicle_id=vehicle.id if vehicle else None,
        trailer_id=shipment.trailer_id if shipment else None,
        plate=vehicle.plate if vehicle else plate,
        trailer_plate=None,
        rfid_epc=rfid_epc,
        container_number=container,
        seal_id=seal_id,
        shipment_id=shipment.id if shipment else None,
        driver_id=shipment.driver_id if shipment else None,
        source=source,
        trust_tier=tier,
        gvm_kg=ev.gvm_kg,
        expected_gvm_kg=expected_gvm_kg,
        variance_kg=(ev.gvm_kg - expected_gvm_kg) if expected_gvm_kg else None,
        axle_group_loads_kg=[groups[g] for g in sorted(groups)],
        axle_config=ev.detected_axle_config,
        dimensions=dimensions,
        permit_ref=permit_ref,
        release_status=release_status or {},
        route=f"{shipment.origin} → {shipment.destination}" if shipment else None,
        destination=shipment.destination if shipment else None,
        issued_at=now,
        expires_at=now + timedelta(hours=hours),
        issuing_station_id=ev.station_id,
        issuing_event_id=ev.id,
        status="active",
        source_label=ev.source,
        signer_key_id=s.signing_key_id,
        signature="",
    )
    t.payload = _canonical(t)
    t.signature = sign_payload(t.payload)
    db.add(t)
    db.flush()
    # a new token from a higher-trust source supersedes older active tokens for the same vehicle
    if vehicle:
        for old in db.execute(select(LoadComplianceToken).where(LoadComplianceToken.vehicle_id == vehicle.id, LoadComplianceToken.status == "active", LoadComplianceToken.id != t.id)).scalars():
            old.status = "revoked"
            old.suspended_reason = f"superseded by {t.token_ref}"
    return t


def active_for_vehicle(db: Session, vehicle_id: str | None, plate: str | None, at: datetime | None = None) -> LoadComplianceToken | None:
    """Most recent active token for the vehicle (by id, falling back to the plate). Expired tokens are marked on the way out."""
    at = _aware(at or utcnow())
    q = select(LoadComplianceToken).where(LoadComplianceToken.status == "active").order_by(LoadComplianceToken.issued_at.desc())
    if vehicle_id:
        q = q.where(LoadComplianceToken.vehicle_id == vehicle_id)
    elif plate:
        q = q.where(LoadComplianceToken.plate == plate)
    else:
        return None
    for t in db.execute(q).scalars():
        if _aware(t.expires_at) < at:
            t.status = "expired"
            continue
        return t
    return None


def to_input(t: LoadComplianceToken, *, plate: str | None, rfid_epc: str | None, seal_status: str | None, at: datetime | None = None) -> ce.TokenInput:
    at = _aware(at or utcnow())
    valid = _aware(t.issued_at) <= at <= _aware(t.expires_at)
    identity_match = True
    if t.plate and plate and t.plate.replace(" ", "").upper() != plate.replace(" ", "").upper():
        identity_match = False
    if t.rfid_epc and rfid_epc and t.rfid_epc != rfid_epc:
        identity_match = False
    if t.seal_id and seal_status in ("breached", "removed"):
        identity_match = False
    return ce.TokenInput(token_id=t.id, token_ref=t.token_ref, source=t.source, trust_tier=t.trust_tier, gvm_kg=float(t.gvm_kg), valid=valid,
                         status=t.status, identity_match=identity_match, issued_at=_aware(t.issued_at).isoformat(), expires_at=_aware(t.expires_at).isoformat())


def honour(t: LoadComplianceToken, at: datetime | None = None) -> None:
    t.honoured_count = (t.honoured_count or 0) + 1
    t.last_honoured_at = _aware(at or utcnow())


def suspend(t: LoadComplianceToken, reason: str, revoke: bool = False) -> None:
    t.status = "revoked" if revoke else "suspended"
    t.suspended_reason = reason


def verify(t: LoadComplianceToken) -> bool:
    known = {get_settings().signing_key_id: public_key_b64()}
    key = known.get(t.signer_key_id)
    if key is None:
        return False
    return verify_signature(t.payload, t.signature, key)


def station_code(db: Session, station_id: str) -> str:
    st = db.get(WeighingStation, station_id)
    return st.code if st else station_id
