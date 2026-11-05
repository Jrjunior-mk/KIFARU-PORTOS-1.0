# Port gate-out weigh node — engineering note

Status: design, 2026-11-05. Not built. KPA has not been approached; whether a weigh node may be placed in the exit
lane, and whether weight may be a gate-out condition, are Phase 0–1 questions.

The port gate-out weigh node is the first trusted weighing point for port trucks. It sits in the KPA exit lane beside
the i-Gate, weighs every loaded truck at walking pace, reads plate, RFID tag, container number and e-seal, compares
the measurement with the expected weight and issues the Load Compliance Token. Platform representation:
`WeighingStation.kind = "port_gate"`, `Lane.type = "port_gateout"`, node kind `port_gateout`, token source `port`
(trust tier 1). Seed station: `MBS-GATE18`.

## 1. Position and flow

1. Truck leaves the yard with the loaded container and approaches the exit lane.
2. ANPR and RFID identify tractor and trailer; the container OCR camera reads the container number (ISO 6346 check
   digit validated); the e-seal reader reads the seal ID and status.
3. The truck rolls over the low-speed scale (about 10 km/h) on its way to the i-Gate.
4. The registry computes the expected gross weight: tractor tare + trailer tare + container tare + declared cargo
   mass (from the declaration / manifest snapshot).
5. The decision is made (plan Section 6.4, port rows). GREEN: token issued and the exit slip shows the result.
   AMBER: route `port_reweigh` (port re-weigh lane; customs present for sealed loads). RED: route `hold`, corrective
   action; whether gate-out is blocked is a policy decision for KPA, KRA and KeNHA.

## 2. Sensors and readers

| Device | Purpose | Platform sensor kind |
|---|---|---|
| Low-speed scale (per-wheel load cells or bending plates) | Gross and axle-group loads at walking pace, error target 1 % | `wheel_load_cell`, `bending_plate` |
| Inductive loops | Presence, axle count | `inductive_loop` |
| ANPR camera | Tractor and trailer plates | `anpr_camera` |
| RFID reader | Tag bound to plate, trailer and fleet at enrolment | `rfid_reader` |
| Container OCR camera | Container number, captured once and attached to the token | `container_ocr` |
| E-seal reader | Seal ID and status (ECTS) | `eseal_reader` |
| Overhead LiDAR portal (optional at the port) | Height, width, length for permit checks before the road | `lidar_portal` |
| Pavement temperature | Compensation | `pavement_temp` |

## 3. Expected-weight computation

```
expected_gvm_kg = vehicle.tare_kg + trailer.tare_kg + container_tare_kg + declaration.declared_mass_kg
variance_kg     = measured_gvm_kg - expected_gvm_kg
```

The engine compares the variance with a tolerance (`DECLARATION_MISMATCH`, `DECLARATION_MISMATCH_LARGE`); the token
records `expected_gvm_kg` and `variance_kg` so KRA receives a weight risk signal for misdeclaration. Container tare
comes from the container record (size and type) until a shipping-line feed exists.

## 4. Port re-weigh lane

A static scale inside the port (`Lane.type = "static"`, lane 9 at `MBS-GATE18` in the seed) handles AMBER and RED
cases from the gate-out node: near-limit loads, large declaration variance, and overloads. The static reading is the
legal proof (Reg 4(6)); corrections happen where cranes, yard space and customs are at hand instead of on the highway.
Modelled port re-weigh shares are in the plan, Section 9 (about 14.9 % of port trucks at 85 % loading with a 1 %
scale and no allowance; about 1.3 % with a 5 % allowance). Two levers reduce the share: weights-and-measures approval
of the port scale (`Lane.legal_grade`) and the discretion allowance policy.

## 5. KPA and KRA interface

| Exchange | Direction | Platform |
|---|---|---|
| Gate events, release status, exit slip | KPA (i-Gate, KWATOS) ↔ registry | KPA adapter (`mode=mock` until authorised); `LoadComplianceToken.release_status` snapshot |
| Declared weight, release status, seal ID | KRA (iCMS, ACD, tracking seals) → registry | KRA adapter (`mock`); `CargoDeclaration`, `ElectronicSeal` |
| Overload alerts on transit cargo | registry → KRA customs | `ReleaseOrder.customs_notified` (Reg 18) |
| Token and exit result | registry → exit slip / driver | `TokenOut`, public verify `GET /rcs/tokens/verify/{token_ref}` |

## 6. Throughput and dwell

The node adds no stop for GREEN trucks: the scale is crossed on the way to the i-Gate at walking pace. The port
re-weigh lane is the capacity question (plan question 4); the chain model reports the re-weigh share and the Phase 2
time-and-motion study must measure i-Gate validation time and yard dwell to size the lane.

## 7. Open items

- KPA permission for a weigh node in the exit lane and acceptance of weight as a gate-out condition.
- Weights-and-measures approval of the port scale (Reg 5) so that only RED trucks need the re-weigh lane.
- Whether the port already weighs imports at the gate.
- Container tare source (container record vs shipping-line feed) and the 34-tonne container limit.
