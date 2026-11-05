"""Deterministic, evidence-based rolling clearance engine (Module 2, RCS v2).

Decision outputs: GREEN (continue), AMBER (verification), RED (inspection), plus a *route* that says where the truck
goes next in the RCS v2 chain: continue | verification_lane | static_scale | port_reweigh | hold.

RCS v2 additions (docs/02-architecture/rcs-v2-api-contract.md §2):
  * Load Compliance Token consistency: a valid token from an earlier verified weighing point means the road reading only
    has to confirm the weight is unchanged (tolerance by token source); the near-limit AMBER rules are then informational.
  * Dimension portal and lifted-axle checks, special-load permits.
  * Discretion allowance (Second Schedule, < 5 % of allowed load) as a configured policy value in LimitSet.
  * Audit rate by trust tier.

Design rules (non-negotiable, see RTM RCS-04..RCS-10, AGT-02):
  * The engine is a pure function of its inputs; no randomness except the audit sampler, which is seeded and logged.
  * AI outputs (identity confidence, anomaly score) are *inputs*; thresholds are configuration, not learned.
  * Any measurement-quality deficiency blocks GREEN. Nothing here can issue a legal certificate: the static scale does.
  * Every decision returns the full list of rules evaluated, the margins used, and an evidence hash.

Severity resolution: if any RED rule fires -> RED; else if any AMBER rule fires -> AMBER; else GREEN.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from typing import Literal

from .limits import DEFAULT_LIMITS, LimitSet, parse_axle_config

ENGINE_VERSION = "clr-2.0.0"
Decision = Literal["GREEN", "AMBER", "RED"]
Route = Literal["continue", "verification_lane", "static_scale", "port_reweigh", "hold"]
NodeKind = Literal["port_gateout", "origin", "road_mainline", "verification_lane", "static"]

# Consistency tolerance between a token weight and a later reading, by token source (RCS v2 plan §6.4):
# about 8 % for port / origin / lane tokens (3 combined standard deviations at 1 % + 2.5 % errors), about 11 % for road tokens.
TOKEN_TOLERANCE: dict[str, float] = {"port": 0.08, "origin": 0.08, "lane": 0.08, "road": 0.11}
# Nodes that may issue a token on GREEN
TOKEN_ISSUING_NODES = {"port_gateout", "origin", "road_mainline", "verification_lane"}
NODE_TO_TOKEN_SOURCE = {"port_gateout": "port", "origin": "origin", "road_mainline": "road", "verification_lane": "lane"}
TRUST_TIER_BY_SOURCE = {"port": 1, "origin": 2, "road": 3, "lane": 3, "onboard": 4}
DEFAULT_AUDIT_RATE_BY_TIER: dict[int, float] = {1: 0.02, 2: 0.04, 3: 0.03, 4: 1.0}
INSTRUCTIONS_BY_ROUTE: dict[str, str] = {
    "continue": "Continue — no stop required",
    "verification_lane": "Divert to the rolling verification lane (about 10 km/h, no stop)",
    "static_scale": "Proceed to the static scale for legal weighing",
    "port_reweigh": "Return to the port re-weigh lane",
    "hold": "Hold for corrective action",
}

# quality flags that make a measurement unusable for an automatic GREEN
BLOCKING_QUALITY_FLAGS = {
    "sensor_fault",
    "no_axles_detected",
    "speed_unavailable",
    "speed_out_of_range",
    "insufficient_rows",
    "axle_load_missing",
    "calibration_expired",
    "calibration_missing",
}
DEGRADING_QUALITY_FLAGS = {"sensor_degraded", "high_uncertainty", "lane_degraded"}


@dataclass
class AxleInput:
    index: int
    load_kg: float
    u_kg: float  # expanded uncertainty (k=2)
    group_no: int


@dataclass
class MeasurementInput:
    gvm_kg: float
    gvm_u_kg: float
    axles: list[AxleInput]
    detected_axle_config: str
    quality_flags: list[str] = field(default_factory=list)
    sensor_health: dict[str, str] = field(default_factory=dict)  # name -> ok|degraded|fault
    speed_mps: float | None = None
    source: str = "simulated"


@dataclass
class IdentityInput:
    confidence: float
    vehicle_id: str | None
    method: str = "none"  # rfid+anpr | rfid | anpr | none | conflict
    anpr_plate: str | None = None
    rfid_epc: str | None = None


@dataclass
class VehicleInput:
    vehicle_id: str
    plate: str
    axle_config: str
    tare_kg: int
    max_gvm_kg: int
    watchlist_reason: str | None = None
    trailer_axle_config: str | None = None


@dataclass
class CargoInput:
    shipment_ref: str | None = None
    declared_mass_kg: int | None = None
    vgm_kg: int | None = None
    seal_status: str | None = None  # armed | breached | removed | unknown | None
    declaration_status: str | None = None
    anomaly_score: float | None = None  # advisory AI input in [0,1]


@dataclass
class TokenInput:
    """An active Load Compliance Token found for the vehicle at this node (RCS v2 §6.2)."""

    token_id: str
    token_ref: str
    source: str  # port | origin | road | lane
    trust_tier: int
    gvm_kg: float
    valid: bool = True  # inside its validity window
    status: str = "active"  # active | expired | suspended | revoked
    identity_match: bool = True  # plate / tag / seal at this node agree with the token
    issued_at: str | None = None
    expires_at: str | None = None


@dataclass
class PermitInput:
    reference: str
    max_length_m: float
    max_width_m: float
    max_height_m: float
    max_gvm_kg: int | None = None
    valid: bool = True


@dataclass
class DimensionsInput:
    """Dimension portal (LiDAR / light curtain) and side-LiDAR readings; None when the node has no portal."""

    length_m: float | None = None
    width_m: float | None = None
    height_m: float | None = None
    lifted_axle: bool = False
    permit: PermitInput | None = None


@dataclass
class RuleResult:
    rule: str
    severity: Literal["RED", "AMBER", "INFO"]
    fired: bool
    detail: str


@dataclass
class ClearanceResult:
    decision: Decision
    rules: list[RuleResult]
    margins: dict
    explanation: str
    evidence_hash: str
    audit_selected: bool
    audit_seed: int | None
    limits_version: str
    engine_version: str = ENGINE_VERSION
    route: Route = "continue"
    node_kind: str = "road_mainline"
    token_eligible: bool = False  # GREEN at a token-issuing node: the caller may issue a Load Compliance Token
    token_consistent: bool | None = None  # None when no token was presented
    instruction: str = INSTRUCTIONS_BY_ROUTE["continue"]

    @property
    def rules_fired(self) -> list[dict]:
        return [asdict(r) for r in self.rules if r.fired]

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "rules": [asdict(r) for r in self.rules],
            "rules_fired": self.rules_fired,
            "margins": self.margins,
            "explanation": self.explanation,
            "evidence_hash": self.evidence_hash,
            "audit_selected": self.audit_selected,
            "audit_seed": self.audit_seed,
            "limits_version": self.limits_version,
            "engine_version": self.engine_version,
            "route": self.route,
            "node_kind": self.node_kind,
            "token_eligible": self.token_eligible,
            "token_consistent": self.token_consistent,
            "instruction": self.instruction,
        }


def _group_loads(axles: list[AxleInput]) -> list[tuple[int, float, float]]:
    """Returns [(group_no, load_kg, u_kg)] with uncertainties combined in quadrature."""
    groups: dict[int, list[AxleInput]] = {}
    for a in axles:
        groups.setdefault(a.group_no, []).append(a)
    out = []
    for g in sorted(groups):
        load = sum(a.load_kg for a in groups[g])
        u = (sum((a.u_kg) ** 2 for a in groups[g])) ** 0.5
        out.append((g, load, u))
    return out


def decide(
    m: MeasurementInput,
    identity: IdentityInput,
    vehicle: VehicleInput | None,
    cargo: CargoInput | None = None,
    limits: LimitSet = DEFAULT_LIMITS,
    identity_min_confidence: float = 0.90,
    audit_rate: float = 0.02,
    audit_seed: int | None = None,
    lane_calibration_valid: bool = True,
    require_two_sources: bool = False,
    token: TokenInput | None = None,
    dimensions: DimensionsInput | None = None,
    node_kind: str = "road_mainline",
    lane_available: bool = False,
    audit_rate_by_tier: dict[int, float] | None = None,
) -> ClearanceResult:
    rules: list[RuleResult] = []
    cargo = cargo or CargoInput()
    flags = set(m.quality_flags)
    if not lane_calibration_valid:
        flags.add("calibration_expired")

    # ---------------------------------------------------------------- token status (RCS v2)
    token_ok = False
    token_consistent: bool | None = None
    if token is not None:
        token_ok = token.valid and token.status == "active" and token.identity_match
        tol = TOKEN_TOLERANCE.get(token.source, 0.08)
        diff = m.gvm_kg - token.gvm_kg
        token_consistent = abs(diff) <= tol * token.gvm_kg if token.gvm_kg else False

    # ---------------------------------------------------------------- limits for this vehicle
    group_sizes = [len([a for a in m.axles if a.group_no == g]) for g in sorted({a.group_no for a in m.axles})]
    gvm_limit = limits.gvm_limit_for_config(group_sizes) if group_sizes else limits.gvm_max_kg
    if vehicle is not None:
        gvm_limit = min(gvm_limit, vehicle.max_gvm_kg) if vehicle.max_gvm_kg else gvm_limit
    allowance_kg = limits.allowance_kg(gvm_limit)
    gvm_tol = gvm_limit * (1 + limits.gvm_tolerance_pct / 100.0) + allowance_kg

    margins: dict = {
        "gvm": {
            "measured_kg": round(m.gvm_kg),
            "u_kg": round(m.gvm_u_kg),
            "limit_kg": gvm_limit,
            "allowance_kg": round(allowance_kg),
            "limit_with_tolerance_kg": round(gvm_tol),
            "margin_kg": round(gvm_tol - (m.gvm_kg + m.gvm_u_kg + limits.green_safety_margin_kg)),
            "overload_kg": round(max(0.0, m.gvm_kg - gvm_tol)),
        },
        "groups": [],
        "identity": {"confidence": round(identity.confidence, 3), "threshold": identity_min_confidence, "method": identity.method},
        "quality_flags": sorted(flags),
        "node_kind": node_kind,
    }
    if token is not None:
        tol = TOKEN_TOLERANCE.get(token.source, 0.08)
        margins["token"] = {
            "token_ref": token.token_ref, "source": token.source, "trust_tier": token.trust_tier, "token_gvm_kg": round(token.gvm_kg),
            "diff_kg": round(m.gvm_kg - token.gvm_kg), "tolerance_kg": round(tol * token.gvm_kg), "tolerance_pct": round(tol * 100, 1),
            "status": token.status, "valid": token.valid, "identity_match": token.identity_match, "consistent": token_consistent,
        }
    rules.append(RuleResult("DISCRETION_ALLOWANCE", "INFO", allowance_kg > 0, f"discretion allowance {allowance_kg:.0f} kg ({limits.discretion_allowance_pct} %) applied to the limit" if allowance_kg > 0 else "no discretion allowance applied"))

    # ---------------------------------------------------------------- quality rules (block GREEN)
    blocking = sorted(flags & BLOCKING_QUALITY_FLAGS)
    rules.append(
        RuleResult(
            "QUALITY_BLOCKING",
            "AMBER",
            bool(blocking),
            f"measurement quality insufficient for automatic clearance: {blocking}" if blocking else "measurement quality acceptable",
        )
    )
    degrading = sorted(flags & DEGRADING_QUALITY_FLAGS)
    rules.append(
        RuleResult("QUALITY_DEGRADED", "AMBER", bool(degrading), f"degraded measurement: {degrading}" if degrading else "no degradation flags")
    )
    faults = sorted(k for k, v in m.sensor_health.items() if v == "fault")
    rules.append(RuleResult("SENSOR_FAULT", "AMBER", bool(faults), f"sensor fault on {faults}" if faults else "all sensors healthy or degraded only"))

    # ---------------------------------------------------------------- weight rules
    certain_over = (m.gvm_kg - m.gvm_u_kg) > gvm_tol
    possible_over = (m.gvm_kg + m.gvm_u_kg + limits.green_safety_margin_kg) > gvm_tol
    # A valid, consistent token means the earlier verified weighing already settled the near-limit question for this load:
    # the road reading only has to confirm the weight is unchanged (RCS v2 §6.4). Certain overloads still go RED.
    token_covers = token_ok and bool(token_consistent)
    near_limit_severity = "INFO" if token_covers else "AMBER"
    rules.append(
        RuleResult(
            "GVM_OVER_CERTAIN",
            "RED",
            certain_over,
            f"GVM {m.gvm_kg:.0f} kg minus U {m.gvm_u_kg:.0f} kg exceeds {gvm_tol:.0f} kg" if certain_over else "GVM not certainly over limit",
        )
    )
    rules.append(
        RuleResult(
            "GVM_OVER_POSSIBLE",
            near_limit_severity,
            possible_over and not certain_over,
            (f"GVM {m.gvm_kg:.0f} kg plus U {m.gvm_u_kg:.0f} kg plus margin exceeds {gvm_tol:.0f} kg; " + ("covered by token consistency" if token_covers else "verification required"))
            if (possible_over and not certain_over)
            else "GVM clear of limit with margin",
        )
    )

    any_group_certain = False
    any_group_possible = False
    for idx, (g, load, u) in enumerate(_group_loads(m.axles)):
        size = len([a for a in m.axles if a.group_no == g])
        lim = limits.group_limit_kg(idx, size)
        lim_tol = lim * (1 + limits.axle_tolerance_pct / 100.0) + limits.allowance_kg(lim)
        certain = (load - u) > lim_tol
        possible = (load + u + limits.green_safety_margin_kg) > lim_tol
        any_group_certain |= certain
        any_group_possible |= possible and not certain
        margins["groups"].append(
            {
                "group_no": g,
                "axles": size,
                "measured_kg": round(load),
                "u_kg": round(u),
                "limit_kg": lim,
                "limit_with_tolerance_kg": round(lim_tol),
                "status": "over" if certain else ("marginal" if possible else "ok"),
            }
        )
    rules.append(RuleResult("AXLE_GROUP_OVER_CERTAIN", "RED", any_group_certain, "an axle group exceeds its limit beyond uncertainty" if any_group_certain else "no axle group certainly over"))
    rules.append(RuleResult("AXLE_GROUP_OVER_POSSIBLE", near_limit_severity, any_group_possible, ("an axle group is within uncertainty of its limit" + ("; covered by token consistency" if token_covers else "")) if any_group_possible else "axle groups clear with margin"))
    rules.append(RuleResult("TOKEN_COVERS_MARGIN", "INFO", token_covers and (possible_over or any_group_possible) and not certain_over and not any_group_certain,
                            "near-limit checks covered by a valid consistent token: only weight consistency is tested on the road" if token_covers else "no token coverage"))

    # ---------------------------------------------------------------- token rules (RCS v2)
    if token is not None:
        rules.append(RuleResult("TOKEN_PRESENT", "INFO", True, f"token {token.token_ref} ({token.source}, tier {token.trust_tier}) presented"))
        expired = not token.valid or token.status == "expired"
        rules.append(RuleResult("TOKEN_EXPIRED", "AMBER", expired, f"token {token.token_ref} outside its validity window" if expired else "token within validity window"))
        suspended = token.status in ("suspended", "revoked")
        rules.append(RuleResult("TOKEN_SUSPENDED", "AMBER", suspended, f"token {token.token_ref} {token.status}" if suspended else "token not suspended"))
        mismatch = not token.identity_match
        rules.append(RuleResult("TOKEN_IDENTITY_MISMATCH", "RED", mismatch, "token plate / tag / seal do not match this node's identity read (possible token fraud)" if mismatch else "token identity matches"))
        inconsistent = token_ok and not token_consistent
        rules.append(RuleResult("TOKEN_WEIGHT_INCONSISTENT", "AMBER", inconsistent,
                                f"GVM {m.gvm_kg:.0f} kg differs from token {token.gvm_kg:.0f} kg by more than {TOKEN_TOLERANCE.get(token.source, 0.08):.0%}; cargo may have changed since issue" if inconsistent
                                else ("weight consistent with token" if token_ok else "token not usable for consistency")))

    # ---------------------------------------------------------------- dimensions, lifted axle, permits (RCS v2 §5)
    if dimensions is not None:
        breaches = limits.dimension_breaches(dimensions.length_m, dimensions.width_m, dimensions.height_m)
        permit = dimensions.permit
        permitted = False
        if breaches and permit is not None and permit.valid:
            permitted = (
                (dimensions.length_m is None or dimensions.length_m <= permit.max_length_m)
                and (dimensions.width_m is None or dimensions.width_m <= permit.max_width_m)
                and (dimensions.height_m is None or dimensions.height_m <= permit.max_height_m)
                and (permit.max_gvm_kg is None or m.gvm_kg <= permit.max_gvm_kg)
            )
        margins["dimensions"] = {
            "length_m": dimensions.length_m, "width_m": dimensions.width_m, "height_m": dimensions.height_m,
            "max_length_m": limits.max_length_m, "max_width_m": limits.max_width_m, "max_height_m": limits.max_height_m,
            "breaches": breaches, "lifted_axle": dimensions.lifted_axle, "permit_ref": permit.reference if permit else None, "permitted": permitted,
        }
        over = bool(breaches) and not permitted
        rules.append(RuleResult("DIMENSION_OVER", "RED", over, "dimension limit exceeded without a valid permit: " + "; ".join(breaches) if over else ("dimensions within limits" if not breaches else "oversize covered by permit")))
        rules.append(RuleResult("DIMENSION_PERMITTED", "INFO", permitted, f"oversize within special-load permit {permit.reference}" if permitted else "no permit needed or none valid"))
        rules.append(RuleResult("LIFTED_AXLE", "AMBER", dimensions.lifted_axle, "lifted axle detected: axle configuration differs from registration; axle loads must be verified" if dimensions.lifted_axle else "no lifted axle"))

    # ---------------------------------------------------------------- identity rules
    conflict = identity.method == "conflict"
    rules.append(RuleResult("IDENTITY_CONFLICT", "RED", conflict, "ANPR plate and RFID tag resolve to different vehicles (possible cloning)" if conflict else "no identity conflict"))
    unknown = vehicle is None
    rules.append(RuleResult("VEHICLE_UNKNOWN", "AMBER", unknown, "vehicle not registered on the platform" if unknown else f"vehicle {vehicle.plate} registered"))
    low_conf = (not unknown) and identity.confidence < identity_min_confidence
    rules.append(RuleResult("IDENTITY_LOW_CONFIDENCE", "AMBER", low_conf, f"identity confidence {identity.confidence:.2f} < {identity_min_confidence}" if low_conf else "identity confidence sufficient"))

    single = require_two_sources and identity.method in ("rfid", "anpr")
    rules.append(RuleResult("IDENTITY_SINGLE_SOURCE", "AMBER", single, f"only one identity source ({identity.method}); two required for GREEN" if single else "two-source identity rule satisfied or not enabled"))

    if vehicle is not None:
        expected = vehicle.axle_config if not vehicle.trailer_axle_config else f"{vehicle.axle_config}+{vehicle.trailer_axle_config}"
        mismatch = parse_axle_config(expected) != parse_axle_config(m.detected_axle_config) if m.detected_axle_config else False
        rules.append(RuleResult("AXLE_CONFIG_MISMATCH", "AMBER", mismatch, f"detected {m.detected_axle_config} vs registered {expected}" if mismatch else "axle configuration matches registration"))
        wl = bool(vehicle.watchlist_reason)
        rules.append(RuleResult("WATCHLIST", "RED", wl, f"vehicle on watch-list: {vehicle.watchlist_reason}" if wl else "not on watch-list"))

    # ---------------------------------------------------------------- cargo rules
    breached = cargo.seal_status in ("breached", "removed")
    rules.append(RuleResult("SEAL_BREACH", "RED", breached, f"electronic seal status {cargo.seal_status}" if breached else "seal intact or not applicable"))
    if vehicle is not None and cargo.declared_mass_kg:
        expected_gvm = vehicle.tare_kg + cargo.declared_mass_kg
        diff = m.gvm_kg - expected_gvm
        tol = max(0.15 * expected_gvm, m.gvm_u_kg)
        big = abs(diff) > 2 * tol
        mid = abs(diff) > tol and not big
        margins["declaration"] = {"expected_gvm_kg": expected_gvm, "diff_kg": round(diff), "tolerance_kg": round(tol)}
        rules.append(RuleResult("DECLARATION_MISMATCH_LARGE", "RED", big, f"measured GVM differs from declaration by {diff:+.0f} kg (> {2*tol:.0f})" if big else "no large declaration mismatch"))
        rules.append(RuleResult("DECLARATION_MISMATCH", "AMBER", mid, f"measured GVM differs from declaration by {diff:+.0f} kg" if mid else "declaration consistent"))
    if cargo.vgm_kg and vehicle is not None:
        diff = m.gvm_kg - (vehicle.tare_kg + cargo.vgm_kg)
        over = diff > max(0.05 * cargo.vgm_kg, m.gvm_u_kg)
        rules.append(RuleResult("VGM_MISMATCH", "AMBER", over, f"GVM exceeds tare+VGM by {diff:.0f} kg" if over else "consistent with VGM"))
    if cargo.anomaly_score is not None:
        hi = cargo.anomaly_score >= 0.8
        rules.append(RuleResult("CARGO_ANOMALY_ADVISORY", "AMBER", hi, f"cargo anomaly score {cargo.anomaly_score:.2f} (advisory AI)" if hi else "no cargo anomaly"))

    # ---------------------------------------------------------------- random audit (seeded, logged)
    seed = audit_seed if audit_seed is not None else random.SystemRandom().randrange(2**31)
    effective_rate = audit_rate
    if audit_rate_by_tier and token is not None and token.trust_tier in audit_rate_by_tier:
        effective_rate = audit_rate_by_tier[token.trust_tier]
    audit = random.Random(seed).random() < effective_rate
    rules.append(RuleResult("RANDOM_AUDIT", "AMBER", audit, f"selected for random audit (rate {effective_rate:.1%}, seed {seed})" if audit else "not selected for audit"))

    # ---------------------------------------------------------------- resolve
    fired = [r for r in rules if r.fired]
    if any(r.severity == "RED" for r in fired):
        decision: Decision = "RED"
    elif any(r.severity == "AMBER" for r in fired):
        decision = "AMBER"
    else:
        decision = "GREEN"

    route = route_for(decision, node_kind, lane_available)
    token_eligible = decision == "GREEN" and node_kind in TOKEN_ISSUING_NODES

    if decision == "GREEN":
        explanation = (
            f"GREEN: GVM {m.gvm_kg:.0f} kg ± {m.gvm_u_kg:.0f} kg is within {gvm_tol:.0f} kg"
            + (" (token consistency covers the near-limit margin)" if token_covers and (possible_over or any_group_possible) else " with margin")
            + f"; all axle groups within limits; identity {identity.method} at {identity.confidence:.2f}; measurement quality acceptable. Source: {m.source}."
        )
    else:
        explanation = f"{decision}: " + "; ".join(r.detail for r in fired if r.severity != "INFO") + f". Route: {route}. Source: {m.source}."

    evidence = {
        "engine": ENGINE_VERSION,
        "limits": limits.version,
        "measurement": asdict(m),
        "identity": asdict(identity),
        "vehicle": asdict(vehicle) if vehicle else None,
        "cargo": asdict(cargo),
        "rules": [asdict(r) for r in rules],
        "decision": decision,
        "audit_seed": seed,
        "token": asdict(token) if token else None,
        "dimensions": asdict(dimensions) if dimensions else None,
        "node_kind": node_kind,
        "route": route,
    }
    evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()
    return ClearanceResult(decision, rules, margins, explanation, evidence_hash, audit, seed, limits.version,
                           route=route, node_kind=node_kind, token_eligible=token_eligible, token_consistent=token_consistent,
                           instruction=INSTRUCTIONS_BY_ROUTE[route])


def route_for(decision: str, node_kind: str, lane_available: bool) -> Route:
    """Where the truck goes next (RCS v2 §6.4). The static scale remains the legal proof for RED cases (Reg 4(6), 18(3))."""
    if decision == "GREEN":
        return "continue"
    if decision == "RED":
        return "hold" if node_kind == "port_gateout" else "static_scale"
    # AMBER
    if node_kind == "port_gateout":
        return "port_reweigh"
    if node_kind == "road_mainline" and lane_available:
        return "verification_lane"
    return "static_scale"
