"""Reg 14 digital release orders (RCS v2 §3, §5): fee from the Third Schedule policy, officer e-signature, tripled fee on a
repeat overload in the same journey, customs alert for sealed transit cargo (Reg 18).

The platform *prepares* everything; an authorised officer approves and e-signs the red case (Reg 3(4), 11(3)). Fees are
indicative until the full schedule is loaded (services/limits.py).
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ClearanceDecision, ReleaseOrder, Vehicle, WeighingEvent, utcnow
from ..security import sign_payload
from .limits import DEFAULT_LIMITS, LimitSet


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def fee_preview(measured_gvm_kg: int, allowed_gvm_kg: int, limits: LimitSet = DEFAULT_LIMITS) -> dict:
    """Second Schedule arithmetic: allowed load, discretion allowance, adjusted load, overload and fee."""
    allowance = int(round(limits.allowance_kg(allowed_gvm_kg)))
    adjusted = measured_gvm_kg - allowance
    overload = max(0, adjusted - allowed_gvm_kg)
    return {"allowed_gvm_kg": allowed_gvm_kg, "allowance_kg": allowance, "adjusted_gvm_kg": adjusted, "overload_kg": overload, "fee_usd": limits.overload_fee(overload)}


def repeat_offence_in_journey(db: Session, vehicle_id: str | None, at: datetime, hours: int | None = None) -> ReleaseOrder | None:
    """A release order for the same vehicle inside the journey window means this overload is a repeat (fee tripled)."""
    if not vehicle_id:
        return None
    hours = hours if hours is not None else get_settings().release_order_journey_hours
    since = _aware(at) - timedelta(hours=hours)
    q = select(ReleaseOrder).where(ReleaseOrder.vehicle_id == vehicle_id, ReleaseOrder.issued_at >= since).order_by(ReleaseOrder.issued_at.desc())
    return db.execute(q).scalars().first()


def issue(
    db: Session,
    ev: WeighingEvent,
    dec: ClearanceDecision,
    officer_user_id: str,
    *,
    static_gvm_kg: int | None,
    transit: bool,
    hazardous: bool,
    perishable: bool,
    journey_ref: str | None,
    notes: str | None,
    detention_days: int = 0,
    limits: LimitSet = DEFAULT_LIMITS,
) -> ReleaseOrder:
    s = get_settings()
    vehicle = db.get(Vehicle, ev.vehicle_id) if ev.vehicle_id else None
    measured = static_gvm_kg or dec.static_verified_gvm_kg or ev.gvm_kg
    allowed = int((dec.margins or {}).get("gvm", {}).get("limit_kg") or limits.gvm_max_kg)
    fp = fee_preview(measured, allowed, limits)
    now = utcnow()
    prior = repeat_offence_in_journey(db, ev.vehicle_id, _aware(ev.occurred_at))
    multiplier = limits.repeat_offence_multiplier if prior else 1.0
    fee = round(fp["fee_usd"] * multiplier, 2)
    detention = limits.detention_fee(detention_days)
    order = ReleaseOrder(
        order_ref="RO-" + secrets.token_hex(5).upper(),
        vehicle_id=ev.vehicle_id,
        plate=vehicle.plate if vehicle else (ev.identity.anpr_plate if ev.identity else None),
        weighing_event_id=ev.id,
        decision_id=dec.id,
        station_id=ev.station_id,
        measured_gvm_kg=measured,
        allowed_gvm_kg=allowed,
        allowance_kg=fp["allowance_kg"],
        adjusted_gvm_kg=fp["adjusted_gvm_kg"],
        overload_kg=fp["overload_kg"],
        fee_usd=fee,
        fee_multiplier=multiplier,
        repeat_offence=prior is not None,
        detention_days=detention_days,
        detention_usd=detention,
        total_usd=round(fee + detention, 2),
        transit=transit,
        customs_notified=transit,  # Reg 18: the registry alerts customs the moment a transit overload is confirmed
        hazardous=hazardous,
        perishable=perishable,
        officer_user_id=officer_user_id,
        signer_key_id=s.signing_key_id,
        officer_signature="",
        status="issued",
        issued_at=now,
        valid_until=now + timedelta(hours=s.release_order_journey_hours),
        journey_ref=journey_ref or (prior.journey_ref if prior else None),
        notes=notes,
        source_label=ev.source,
    )
    order.officer_signature = sign_payload({
        "order_ref": order.order_ref, "weighing_event_id": ev.id, "decision_id": dec.id, "officer_user_id": officer_user_id,
        "measured_gvm_kg": measured, "allowed_gvm_kg": allowed, "overload_kg": order.overload_kg, "fee_usd": fee, "total_usd": order.total_usd,
        "issued_at": now.isoformat(), "repeat_offence": order.repeat_offence,
    })
    db.add(order)
    db.flush()
    if vehicle:
        vehicle.demerit_points = (vehicle.demerit_points or 0) + (2 if prior else 1)  # Fifth Schedule demerits: placeholder scale
    return order
