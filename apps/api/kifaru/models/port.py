"""SmartPort port-process layer: one PortVisit per truck collection trip through the eleven-stage workflow
(docs/02-architecture/smartport-port-process-contract.md §1). Stage 7 is the RCS v2 port gate-out weigh node."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, Timestamped, ULIDPk

PORT_STAGES = [
    "pre_registered",
    "customs_cleared",
    "arrived",
    "gate_in",
    "yard_allocated",
    "loaded",
    "weighed",
    "final_cleared",
    "gate_out",
    "in_transit",
    "delivered",
]

# order, label, required data fields when advancing INTO the stage, owning agency, timestamp column set from `at`
PORT_STAGE_META: dict[str, dict] = {
    "pre_registered": {"order": 1, "label": "Pre-arrival registration and scheduling", "agency": "Transporter / clearing agent",
                       "required_fields": ["truck_type", "cargo_type", "declared_mass_kg", "destination", "appointment_at"], "ts": "pre_registered_at"},
    "customs_cleared": {"order": 2, "label": "Customs clearance and document verification", "agency": "KRA, KenTrade, KEBS",
                        "required_fields": ["customs_declaration_ref", "trade_direction", "duty_status", "customs_status", "inspection_status", "permit_status"], "ts": "customs_cleared_at"},
    "arrived": {"order": 3, "label": "Truck arrival and identification", "agency": "KPA",
                "required_fields": ["appointment_valid", "queue_length", "queue_wait_s"], "ts": "arrived_at"},
    "gate_in": {"order": 4, "label": "Gate-in and security inspection", "agency": "KPA",
                "required_fields": ["gate_in_id", "access_authorised", "vehicle_inspection", "driver_verified", "gate_in_processing_s"], "ts": "gate_in_at"},
    "yard_allocated": {"order": 5, "label": "Yard allocation and cargo location", "agency": "KPA",
                       "required_fields": ["terminal_id", "yard_block", "container_position", "loading_instruction", "yard_wait_s"], "ts": "yard_allocated_at"},
    "loaded": {"order": 6, "label": "Cargo verification and loading", "agency": "KPA",
               "required_fields": ["loading_start_at", "loading_end_at", "equipment_id", "seal_number", "cargo_verification", "cargo_condition"], "ts": "loading_end_at"},
    "weighed": {"order": 7, "label": "Automated weighing and weight verification", "agency": "KPA + KeNHA",
                "required_fields": ["gross_kg", "tare_kg", "weighing_start_at", "weighing_end_at", "calibration_valid"], "ts": "weighing_end_at"},
    "final_cleared": {"order": 8, "label": "Final cargo and document verification", "agency": "KPA, KRA",
                      "required_fields": ["cargo_release_status", "delivery_order_ref", "gate_pass_no", "payment_status"], "ts": "final_cleared_at"},
    "gate_out": {"order": 9, "label": "Gate-out and port departure", "agency": "KPA",
                 "required_fields": ["gate_out_id", "exit_cargo_verified", "exit_authorised"], "ts": "gate_out_at"},
    "in_transit": {"order": 10, "label": "Inland transportation and cargo tracking", "agency": "Transporter, telematics, KeNHA weighbridges",
                   "required_fields": ["route", "distance_km", "eta_at"], "ts": "departed_at"},
    "delivered": {"order": 11, "label": "Cargo delivery and trip closure", "agency": "Cargo owner / warehouse",
                  "required_fields": ["pod_ref", "arrived_destination_at"], "ts": "delivered_at"},
}

# port stage -> shipment (cargo passport) stage; the shipment only ever moves forward
PORT_TO_SHIPMENT_STAGE = {
    "pre_registered": "registered", "customs_cleared": "customs_processing", "arrived": "at_port", "gate_in": "at_port", "yard_allocated": "at_port",
    "loaded": "at_port", "weighed": "weighing_verification", "final_cleared": "gate_processing", "gate_out": "released", "in_transit": "in_transit", "delivered": "delivered",
}

# columns that hold ISO timestamps when supplied through stage data
DATETIME_FIELDS = {"appointment_at", "expected_arrival_at", "loading_start_at", "loading_end_at", "weighing_arrival_at", "weighing_start_at", "weighing_end_at", "eta_at", "arrived_destination_at"}


class PortVisit(ULIDPk, Timestamped, Base):
    __tablename__ = "port_visits"
    __table_args__ = {"schema": "core"}
    reference: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    shipment_id: Mapped[str | None] = mapped_column(CHAR(26), ForeignKey("core.shipments.id"), index=True)
    vehicle_id: Mapped[str | None] = mapped_column(CHAR(26), ForeignKey("core.vehicles.id"), index=True)
    driver_id: Mapped[str | None] = mapped_column(CHAR(26), ForeignKey("core.drivers.id"))
    transporter_org_id: Mapped[str | None] = mapped_column(CHAR(26), ForeignKey("core.organizations.id"), index=True)
    owner_org_id: Mapped[str | None] = mapped_column(CHAR(26), ForeignKey("core.organizations.id"), index=True)
    appointment_id: Mapped[str | None] = mapped_column(CHAR(26), ForeignKey("core.appointments.id"))
    stage: Mapped[str] = mapped_column(String(20), default="pre_registered", index=True)
    status: Mapped[str] = mapped_column(String(12), default="active", index=True)  # active | closed | cancelled
    source: Mapped[str] = mapped_column(String(12), default="simulated")  # live | simulated | replay
    timeline: Mapped[list] = mapped_column(JSON, default=list)  # [{stage, at, data}]
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    # 1 pre-arrival
    truck_type: Mapped[str | None] = mapped_column(String(24))
    container_number: Mapped[str | None] = mapped_column(String(11))
    cargo_type: Mapped[str | None] = mapped_column(String(24))
    declared_mass_kg: Mapped[int | None] = mapped_column(Integer)
    destination: Mapped[str | None] = mapped_column(String(120))
    appointment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pre_registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 2 customs
    customs_declaration_ref: Mapped[str | None] = mapped_column(String(40))
    bill_of_lading: Mapped[str | None] = mapped_column(String(40))
    trade_direction: Mapped[str | None] = mapped_column(String(10))  # import | export | transit
    duty_status: Mapped[str | None] = mapped_column(String(10))  # paid | unpaid | pending
    customs_status: Mapped[str | None] = mapped_column(String(10))  # cleared | pending | held
    inspection_status: Mapped[str | None] = mapped_column(String(14))  # required | completed | not_required
    permit_status: Mapped[str | None] = mapped_column(String(10))  # approved | rejected | pending
    hold_reason: Mapped[str | None] = mapped_column(String(200))
    customs_cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 3 arrival
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anpr_plate: Mapped[str | None] = mapped_column(String(16))
    rfid_epc: Mapped[str | None] = mapped_column(String(64))
    appointment_valid: Mapped[bool | None] = mapped_column(Boolean)
    queue_position: Mapped[int | None] = mapped_column(Integer)
    queue_length: Mapped[int | None] = mapped_column(Integer)
    queue_wait_s: Mapped[int | None] = mapped_column(Integer)
    arrival_lat: Mapped[float | None] = mapped_column(Float)
    arrival_lon: Mapped[float | None] = mapped_column(Float)
    # 4 gate-in
    gate_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gate_in_id: Mapped[str | None] = mapped_column(String(24))
    access_authorised: Mapped[bool | None] = mapped_column(Boolean)
    vehicle_inspection: Mapped[str | None] = mapped_column(String(8))  # passed | failed
    driver_verified: Mapped[bool | None] = mapped_column(Boolean)
    gate_in_processing_s: Mapped[int | None] = mapped_column(Integer)
    rejection_reason: Mapped[str | None] = mapped_column(String(200))
    # 5 yard
    yard_allocated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_id: Mapped[str | None] = mapped_column(String(24))
    yard_block: Mapped[str | None] = mapped_column(String(24))
    container_position: Mapped[str | None] = mapped_column(String(40))
    loading_instruction: Mapped[str | None] = mapped_column(String(80))
    yard_wait_s: Mapped[int | None] = mapped_column(Integer)
    # 6 loading
    loading_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    loading_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    equipment_id: Mapped[str | None] = mapped_column(String(24))
    seal_number: Mapped[str | None] = mapped_column(String(40))
    cargo_verification: Mapped[str | None] = mapped_column(String(12))  # matched | mismatched
    cargo_condition: Mapped[str | None] = mapped_column(String(8))  # good | damaged
    loading_exceptions: Mapped[list] = mapped_column(JSON, default=list)
    # 7 weighing
    weighing_event_id: Mapped[str | None] = mapped_column(CHAR(26), ForeignKey("core.weighing_events.id"))
    weighing_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weighing_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weighing_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tare_kg: Mapped[int | None] = mapped_column(Integer)
    gross_kg: Mapped[int | None] = mapped_column(Integer)
    net_kg: Mapped[int | None] = mapped_column(Integer)
    weight_discrepancy_kg: Mapped[int | None] = mapped_column(Integer)
    calibration_valid: Mapped[bool | None] = mapped_column(Boolean)
    token_ref: Mapped[str | None] = mapped_column(String(32))
    # 8 final clearance
    final_cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cargo_release_status: Mapped[str | None] = mapped_column(String(10))  # approved | pending
    delivery_order_ref: Mapped[str | None] = mapped_column(String(40))
    gate_pass_no: Mapped[str | None] = mapped_column(String(40))
    payment_status: Mapped[str | None] = mapped_column(String(10))  # paid | unpaid
    clearance_exceptions: Mapped[list] = mapped_column(JSON, default=list)
    # 9 gate-out
    gate_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gate_out_id: Mapped[str | None] = mapped_column(String(24))
    exit_cargo_verified: Mapped[bool | None] = mapped_column(Boolean)
    exit_authorised: Mapped[bool | None] = mapped_column(Boolean)
    dwell_time_s: Mapped[int | None] = mapped_column(Integer)
    # 10 transit
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    route: Mapped[str | None] = mapped_column(String(120))
    distance_km: Mapped[float | None] = mapped_column(Float)
    eta_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stoppage_s: Mapped[int | None] = mapped_column(Integer)
    delay_reason: Mapped[str | None] = mapped_column(String(120))
    # 11 delivery
    arrived_destination_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pod_ref: Mapped[str | None] = mapped_column(String(40))
    transit_time_s: Mapped[int | None] = mapped_column(Integer)
