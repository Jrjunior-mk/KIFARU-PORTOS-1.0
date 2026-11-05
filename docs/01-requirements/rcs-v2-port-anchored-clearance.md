# RCS v2: port-anchored clearance — implementation and simulation plan

Status: design accepted into the repository on 2026-11-05. The software elements listed under "Implemented in this
repository" exist in code and are exercised with simulated data only. Every quantitative result in this document is a
Monte Carlo estimate under the stated assumptions and must be replaced with measured data (Section 9, Section 12).
Nothing here claims that hardware has been built or that any regulator has agreed to the design.

Companion documents: [`legal-hooks-eac-vlc-2018.md`](legal-hooks-eac-vlc-2018.md),
[`../02-architecture/rcs-v2-api-contract.md`](../02-architecture/rcs-v2-api-contract.md),
[`../06-operations/rcs-v2-simulation-plan.md`](../06-operations/rcs-v2-simulation-plan.md),
[`../03-hardware/rolling-verification-lane.md`](../03-hardware/rolling-verification-lane.md),
[`../03-hardware/port-gateout-weigh-node.md`](../03-hardware/port-gateout-weigh-node.md).

Weighing every heavy truck at its first trusted point, and letting later stations honour that result, is what removes
repeat stops. For port cargo that point is the port exit. For mines, quarries, factories and other loaders it is the
loading site or the first road station. This plan covers all three truck streams, adds the sensors KeNHA needs beyond
weight, and shows how to implement and simulate the system.

## 1. Summary

- **The gap.** The port chain verifies containers, trucks and releases repeatedly, yet weight is first measured on the
  highway, where an overload is hardest to fix. Trucks from mines, quarries and factories have no port step at all.
- **Three truck streams.** Port trucks, industrial origin trucks and untokened trucks each receive a signed Load
  Compliance Token at their first verified weighing point. Later stations honour it, so a truck does not stop at every
  weighbridge (Section 4).
- **Weight is not enough.** High-speed WIM does not measure dimensions, lifted axles, per-wheel balance, permits or
  certificates, which KeNHA checks at static bridges. RCS adds a LiDAR dimension portal, cameras, per-wheel scales and
  registry checks (Section 5).
- **Own lanes.** A Rolling Verification Lane beside each station lets doubtful trucks roll through at about 10 km/h
  while every parameter is captured. One lane handles about 370 trucks an hour, roughly 25 times a static lane.
- **The legal opening.** Reg 10(2) excuses vehicles previously confirmed compliant by screening devices from producing
  a paper certificate. Reg 3(4) still reserves weighbridge tickets and release orders for overloaded vehicles to
  authorised officers, so an officer stays in the loop for red cases.
- **Modelled effect.** At 85 % average loading, static-scale visits at the first station fall from about 21 % of
  trucks (road-only screening) to 10 %, 7 %, 4 % and 1.5 % as token coverage rises from 30 % to 90 %. Later stations
  send almost nothing to static scales (Section 9). Trucks loaded within the measurement margin of the limit still
  need a legal-grade reading or the discretion allowance.
- **Viability changes.** Reuse KeNHA's existing high-speed WIM feed, put new hardware at the port, origin sites and one
  verification lane per station, calibrate quarterly, and obtain weights-and-measures approval.
- **Simulation.** Four linked levels over about 16 weeks, with a go/no-go gate before any hardware spend (Section 10).

### Implemented in this repository (software, simulated data)

| Plan element | Component |
|---|---|
| Three truck streams, node kinds, routes | `WeighingEvent.stream`, `WeighingEvent.node_kind`, `ClearanceDecision.route` (`apps/api/kifaru/models/weighing.py`) |
| Load Compliance Token | `LoadComplianceToken` model, `services/tokens.py`, `/api/v1/rcs/tokens*` |
| Token consistency and downstream honouring | engine `clr-2.0.0` rules `TOKEN_*`, `TOKEN_COVERS_MARGIN` (`services/clearance_engine.py`) |
| Trust tiers and audit rates | `Vehicle.trust_tier`, `LoadComplianceToken.trust_tier`, `GET /rcs/trust-tiers`, `audit_rate_by_tier` |
| Dimensions, lifted axle, per-wheel loads | `WeighingEvent.length_m/width_m/height_m/lifted_axle`, `AxleMeasurement.left_kg/right_kg`, rules `DIMENSION_OVER`, `LIFTED_AXLE` |
| Special-load permits | `SpecialLoadPermit`, `/rcs/permits`, rule `DIMENSION_PERMITTED` |
| Release orders (Reg 14), fees, officer e-sign | `ReleaseOrder`, `services/release_orders.py`, `/rcs/release-orders` |
| Discretion allowance, fee table, dimension limits | `services/limits.py` (`KE-EAC-VLC-REG-2018-schedule-v2`) |
| Legal-grade flag, lane types, station kinds | `Lane.legal_grade`, `Lane.type`, `WeighingStation.kind` |
| Registry statistics | `GET /rcs/stats`; web page `/registry` |
| Chain model (Section 9 tables) | `kifaru_sim.rcs_v2`, `kifaru_sim.experiments`, `POST /rcs/model`, web page `/model` |
| Station-level discrete-event model with lane and tokens | SimPy policy `rcs_v2` in `packages/simulation` |

## 2. Where the chain duplicates checks and leaves gaps

| Stage | Checked today | Duplication or gap | RCS v2 response | Implemented in |
|---|---|---|---|---|
| Before arrival | Manifest and ACD hold declared cargo weight | Declared weight is never compared with measured truck weight | Compute expected gross weight from declarations, container tare and truck tare, then compare with measurement | `CargoInput.declared_mass_kg`, rules `DECLARATION_MISMATCH*`; `LoadComplianceToken.expected_gvm_kg`, `variance_kg` |
| Port entry | Driver ID, licence, truck and trailer registration, access credentials, loading barcode | Same identity data re-checked at loading and exit | Enrol once; recognise by plate plus RFID tag | `Vehicle`, `RfidTag`, `services/identity.py` |
| Loading | Container number matched to loading instruction; condition check; twist locks | Container number checked again after loading and at exit | Capture once at the gate-out portal with OCR and attach it to the token | sensor kind `container_ocr`; `LoadComplianceToken.container_number` |
| Exit inspection | Container number, registrations, loading slip, seal, scanner, customs, shipping-line and KPA release, i-Gate validation, exit slip, KRA and KPA security verification | Releases are electronic, yet two agencies re-verify physically and by document | Show one release-status record to both agencies; physical checks only on exceptions | `LoadComplianceToken.release_status` (snapshot); adapters KPA/KRA remain `mock` until authorised |
| Port exit to road | No weight is measured | The first weighing happens far from cranes, customs and yard space | Weigh at the exit lane | lane type `port_gateout`, station kind `port_gate` (seed `MBS-GATE18`) |
| Weighbridges | WIM, then static; paper certificate signed and stamped; presented again at later stations | Repeated at each station (Dongo Kundu, Mariakani, Mtwapa, later Athi River) | Digital certificate and token lookup | `DigitalTicket`, `GET /rcs/tokens/lookup`, public `GET /rcs/tokens/verify/{token_ref}` |
| Transit cargo | E-seal (ECTS), certificate at every station | An overloaded transit vehicle waits for a customs officer to break the seal | Registry alerts customs the moment an overload is confirmed | `ReleaseOrder.transit`, `customs_notified` |
| Overload handling | Fees, detention, paper release order carried through the journey | Later stations rely on the paper | Digital release order visible to every station | `ReleaseOrder`, `GET /rcs/release-orders` |

## 3. Legal hooks in the EAC regulations

The EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018, set the rules. Summary in plain words; the
full mapping to platform configuration is in [`legal-hooks-eac-vlc-2018.md`](legal-hooks-eac-vlc-2018.md).

| Regulation | What it says | Design consequence |
|---|---|---|
| Reg 3(3) | The roads authority may outsource weighbridge operation, management and maintenance to private operators | A legal route for a private partner role |
| Reg 4(5)–(6) | Mobile weighbridges and surveillance technology may be used. A vehicle found in breach is escorted to the nearest static weighbridge for accurate weighing | RCS readings decide who needs a static weighing. They never replace it as proof of overload |
| Reg 5 | Any weighbridge, including mobile, needs approval and a certificate from the national weights-and-measures body | Our scales need approval. Confirm whether screening devices need it too |
| Reg 6 and 8 | Calibration at least every three months by an accredited calibrator, and an audit every twelve months | Quarterly calibration is a legal requirement, not an option. Budget for it |
| Reg 9(1) | The duty to submit for weighing arises on direction by an authorised officer or a weighbridge road sign | Our driver signals must be approved signs. No direction means no duty to stop |
| Reg 10(2) | Except for a vehicle previously confirmed within limits by surveillance or screening devices, a transporter must produce the certificate on request | The legal hook for a digital green status replacing the paper certificate |
| Reg 10(4) | A certificate from any weighbridge is accepted as proof, unless there is apparent forgery, tampering or manifest error | Digital certificates must be tamper-evident and signed |
| Reg 14 | A release order must be kept for the journey and shown at later weighbridges. If the vehicle is found overloaded again in the same journey, the fees are tripled | A digital release-order registry. Fleets will want it to avoid the tripled fee |
| Reg 18 | Transit cargo certificates are shown at every later weighbridge. A surveillance-detected overload is verified on a static scale. An overloaded transit vehicle is detained until a customs officer breaks the seal with the transporter present | Integrate with KRA's tracking seals and customs officers |
| Reg 20, Fifth Schedule | Demerit points go against the vehicle, transporter and driver declared in the trip plan, with bans from the regional network | The registry should hold trip-plan and demerit data |
| Second Schedule | The certificate records measured load, allowed load, a discretion allowance of less than 5 % of the allowed load, adjusted load, overload and fee | Agree thresholds with KeNHA. Whether the allowance applies changes the stop share a lot (Section 9) |
| Third Schedule and Reg 13 | Legal weights: steering axle 8 t, single drive axle 10 t, tandem 18 t, tridem 24 t. In the 2021–2030 fee table, 5,000 kg over the gross limit costs about 2,990 USD. Detention is free for three days, then 50 USD a day | Strong incentive for transporters to join a clearance programme |

The guide supplied with the plan also lists reported gross limits by axle count (2 axles 18 t, 3 axles 26 t,
4 axles 30 t, 6 axles 50 t). Treat these as reported figures and check the legal schedules for each vehicle
configuration (`REPORTED_GVM_BY_AXLES in services/limits.py`, flagged for verification).

## 4. Who is on the road: three truck streams

The corridor carries more than port cargo. Mines, quarries, cement and sugar works, fuel depots, farms and factories
load trucks that never see a port gate. They use the same highways and weighbridges, so the system needs a first
trusted weighing point for them too.

| Stream | Examples | Where the first trusted weight comes from | Main risk |
|---|---|---|---|
| A. Port trucks | Containers from Mombasa | Port gate-out weigh node | Cargo changes after the port (low) |
| B. Industrial origin trucks | Mine, quarry, cement, sugar, fuel depot, farm and factory loads | An approved scale at the loading site, linked to the registry | Under-reported weights at private scales; bulk loads that shift or settle |
| C. Untokened trucks | Spot loads, traders, small fleets, first-time users | The first RCS road station or Rolling Verification Lane | No earlier weight to compare, so more uncertainty |

**One rule for all streams.** A signed Load Compliance Token is issued at a truck's first verified weighing point, and
every later station honours it until it expires or a consistency check fails. This is how a truck avoids stopping at
every weighbridge. Reg 10(2) already excuses vehicles previously confirmed within limits by screening devices, and
Reg 10(4) and Reg 18(2) already treat certificates from earlier stations as proof.

Implemented in: `WeighingEvent.stream` (`port` / `origin` / `untokened`), `services/tokens.py` (issue, lookup,
honour, suspend), engine rules `TOKEN_PRESENT`, `TOKEN_EXPIRED`, `TOKEN_SUSPENDED`, `TOKEN_IDENTITY_MISMATCH`,
`TOKEN_WEIGHT_INCONSISTENT`, `TOKEN_COVERS_MARGIN`.

### Origin weigh nodes

- **At large loaders:** an approved scale (Reg 5 approval) with plate and tag readers, sending a signed digital
  ticket to the registry. The loader saves its trucks road stops and overload fees. Implemented as lane type
  `origin_scale` at a station of kind `origin_site` with `Lane.legal_grade = true` once approved (seed: `BMB-QRY`).
- **Where no approved scale exists:** on-board weighing (air-suspension pressure or load cells) with signed
  telematics. Accuracy is lower, so it informs the risk score but does not issue a token. The truck uses the Rolling
  Verification Lane. (Trust tier 4; no token source in the registry, only a risk input.)
- **Trust is earned.** Origin readings are compared with road and lane readings. Drift or under-reporting raises that
  origin's audit rate and can suspend its tokens (`POST /rcs/tokens/{id}/suspend`, `suspended_reason`).

### Trust tiers and audit rates (proposed)

| Tier | Token source | Initial audit rate | Registry value |
|---|---|---|---|
| 1 | Port gate-out node | 1–3 % | `audit_rate_by_tier[1] = 0.02` |
| 2 | Approved origin scale | 3–5 %, falling with a clean record | `audit_rate_by_tier[2] = 0.04` |
| 3 | Road node or lane (untokened trucks) | 3 % | `audit_rate_by_tier[3] = 0.03` |
| 4 | On-board signed record only | Always verified in the lane at first | `audit_rate_by_tier[4] = 1.00` |

Audit rates also rise with demerit points (Reg 20, `Vehicle.demerit_points`) and fall for fleets with a clean
record, so enforcement effort follows risk. Exposed by `GET /rcs/trust-tiers` and `GET /rcs/policy`.

## 5. Parameter coverage: what KeNHA checks and what must be sensed

High-speed WIM estimates axle loads, axle spacing and speed. A static weighbridge check covers more: dimensions,
axle configuration, permits and certificates. RCS adds sensors, registry checks and its own lane so KeNHA receives
every parameter it needs.

| Parameter checked at a static bridge | High-speed WIM alone | Added in RCS | Implemented in |
|---|---|---|---|
| Gross vehicle weight | Estimate only | Rolling Verification Lane at about 10 km/h (error target 1 %). Static scale remains legal proof for red cases | lane type `rolling_verification`; `Lane.legal_grade` |
| Single axle load | Estimate only | Same lane, per-wheel load cells or bending plates | sensor kind `wheel_load_cell`; `AxleMeasurement.left_kg/right_kg` |
| Axle group (tandem, tridem) | Depends on axle spacing accuracy | Axle spacing from WIM rows and LiDAR, group loads from the lane | `AxleMeasurement.group_no`, rules `AXLE_GROUP_OVER_*` |
| Axle count, configuration, lifted axles | Counts axles in contact, so a lifted axle looks like a missing one | Side LiDAR and camera classification matched to the registered configuration. A lifted axle shows as a mismatch | sensor kind `side_lidar`; `WeighingEvent.lifted_axle`; rules `LIFTED_AXLE`, `AXLE_CONFIG_MISMATCH` |
| Left-right imbalance | Only with per-wheel strips | Per-wheel scales in the lane, wheel-track position from the WIM rows | `AxleMeasurement.left_kg/right_kg` |
| Height, width, length | Not measured | Overhead LiDAR or laser scanner portal, light curtain for over-height | sensor kinds `lidar_portal`, `light_curtain`; `WeighingEvent.length_m/width_m/height_m`; rule `DIMENSION_OVER` |
| Special-load permit | Not checked | Plate links to a digital permit registry; scanner checks dimensions against the permit terms | `SpecialLoadPermit`, `/rcs/permits`, rule `DIMENSION_PERMITTED` |
| Vehicle and trailer identity | Plate if a camera is present | ANPR, RFID and trailer pairing, matched to the registry | `IdentityEvent`, `Trailer`, `TOKEN_IDENTITY_MISMATCH` |
| Licence, insurance, roadworthiness | Not checked | Registry links to NTSA and insurers in a later phase. Flagged, not blocking | integration adapters (`mock` until authorised) |
| Earlier certificate and release order | Not checked | Held digitally in the registry and shown to every station (Reg 10, Reg 14) | `DigitalTicket`, `ReleaseOrder` |
| Transit cargo seal | Not checked | E-seal status from KRA; customs alerted on confirmed overload (Reg 18) | `ElectronicSeal`, sensor kind `eseal_reader`, `ReleaseOrder.customs_notified` |
| Hazardous or perishable flag | Not checked | From trip plan or manifest; changes how a red truck is handled (Reg 13) | `ReleaseOrderIn.hazardous/perishable`; `Shipment.cargo_type` |
| Overload fee, certificate, signature | Not done | Registry computes the fee from the Third Schedule and the allowance policy. An authorised officer e-signs (Reg 3(4), Reg 11(3)). Electronic payment is allowed (Reg 12(3)) | `LimitSet.overload_fee`, `ReleaseOrder.officer_signature`, status `paid` |
| Calibration status of the scales | Not shown | Calibration register with quarterly certificates (Reg 6) | `CalibrationRecord`, `Lane.calibration_valid_to`, rule `QUALITY_BLOCKING` (`calibration_expired`) |

Two limits follow from the regulations. A reading from screening devices cannot replace static weighing as proof of
overload (Reg 4(6), Reg 18(3)), and fees and release orders for overloaded trucks must come from an authorised officer.
The system prepares everything; the officer approves the red cases (`POST /rcs/release-orders` requires an
officer role with MFA).

### 5.1 The Rolling Verification Lane

This is RCS's own lane, built beside each road station and reached by a diverge from the mainline screening node.
Engineering detail: [`../03-hardware/rolling-verification-lane.md`](../03-hardware/rolling-verification-lane.md).

- **What it does.** Doubtful trucks and random audits roll through at about 10 km/h (target 15 km/h or less) over
  low-speed per-wheel scales, under a LiDAR dimension portal and cameras. The full parameter set is captured in
  roughly 20–30 seconds with no stop.
- **Throughput.** At 10 km/h (2.8 m/s) and about 27 m per truck (17 m truck plus a 10 m gap), one truck passes every
  9.7 seconds, about 370 an hour. A static lane at 4 minutes per truck handles about 15 an hour, so one rolling lane
  equals roughly 25 static lanes.
- **Layout (design assumption).** About 100–150 m approach with speed signs, a flat concrete measuring zone of at
  least 15 m, and a 50 m exit that rejoins the road. Check land and civil works early.
- **Who gets what.** KeNHA officers see the same data as a static check (axle loads, dimensions, images, computed fee)
  plus dimensions and lifted-axle checks, on one screen with an e-sign button (web: Weighbridge console, lane tab;
  `/registry`).
- **Legal grade.** If the lane's scales gain weights-and-measures approval, only red trucks need a static scale. Until
  then, trucks measured within the margin of the limit still go to a static scale (`Lane.legal_grade`).
- **Reuse.** The same lane design serves the port exit.

## 6. RCS v2 design

### 6.1 Five checkpoints and one registry

| Element | Where | Job | Implemented in |
|---|---|---|---|
| A. Port gate-out weigh node | KPA exit lane, beside the i-Gate | Low-speed weighing of every loaded truck. Reads plate, RFID tag, container number and e-seal. Compares measured with expected weight. Issues the token | lane type `port_gateout`, node kind `port_gateout`, token source `port` (tier 1) |
| B. Origin weigh nodes | Mines, quarries, factories, depots | Approved scale at the loading site linked to the registry, with plate, tag and a signed digital ticket. Issues an origin token | lane type `origin_scale`, node kind `origin`, token source `origin` (tier 2) |
| C. Road screening nodes | Dongo Kundu, Mariakani, Mtwapa and other stations | Existing high-speed WIM feed plus plate, tag and LiDAR readers. Checks tokens and issues road tokens | lane types `wim_highspeed` / `wim_lowspeed`, node kind `road_mainline`, token source `road` (tier 3) |
| D. Rolling Verification Lane | Beside each road station | Low-speed scales, dimension portal and cameras. Captures every static-bridge parameter without stopping | lane type `rolling_verification`, node kind `verification_lane`, token source `lane` (tier 3) |
| E. Static scales | Existing weighbridges and a port re-weigh lane | Legal proof for red cases and audits. Results feed calibration | lane type `static`, `POST /weighing/events/{id}/static-verify`, ticket `static_certified` |
| Clearance registry | Cloud, with edge caches at each site | One record per truck-journey: tokens, weights, dimensions, certificates, permits, release orders, demerit points, release status | `/api/v1/rcs/*`, edge `clearance_mirror` (cache) |

### 6.2 The Load Compliance Token

A signed digital record created at the first verified weighing point: the port gate-out, an approved origin scale, or
the first road station or verification lane. Later stations honour it until it expires or a consistency check fails.
Fields (`LoadComplianceToken`, serialised as `TokenOut`):

- Tractor plate, trailer plate and RFID tag ID (`plate`, `trailer_plate`, `rfid_epc`).
- Container number (with check-digit result) and e-seal ID (`container_number`, `seal_id`).
- Axle and axle-group loads, gross weight, expected weight and the variance between them (`axle_group_loads_kg`,
  `gvm_kg`, `expected_gvm_kg`, `variance_kg`).
- Gate, time stamp and validity window (to the destination or an agreed time limit) (`issuing_station_code`,
  `issued_at`, `expires_at`; defaults 36 h for port and origin tokens, 24 h for road and lane tokens).
- Snapshot of customs, shipping-line and KPA release status (`release_status`).
- Route, destination, and the driver declared in the trip plan (`route`, `destination`, `driver_id`).
- Digital signature, so it cannot be altered (`signature`, `signer_key_id`; Ed25519 over the canonical payload).
- Token source (port, origin or road) and trust tier, which sets the audit rate (`source`, `trust_tier`).
- Dimensions, axle configuration and permit reference captured at issue (`dimensions`, `axle_config`, `permit_ref`).

Road nodes cache active tokens, which is small: roughly 8,000 a day.

### 6.3 Flow of one port truck

1. The truck enrols once; its tag is bound to plate, trailer and fleet.
2. At the port exit lane the system reads plate, tag, container number and seal, and checks release status.
3. The truck rolls over the low-speed scale at walking pace on its way to the i-Gate.
4. The system computes expected weight (truck and trailer tare plus container tare plus declared cargo) and compares
   it with the measurement.
5. If compliant, it issues the token and the exit slip shows the result. Otherwise the truck is sent to the port
   re-weigh lane for corrective action (route `port_reweigh`).
6. On the road the node reads plate and tag, matches the token and compares the road reading with the token weight.
7. Consistent readings give a green with no stop. Anything else becomes amber or red, and the legal process runs on
   static scales.
8. Each outcome updates the registry, so later stations do not repeat the work (`honoured_count`,
   ledger events `token.issued`, `token.honoured`).

### Flow for non-port trucks

1. The truck is enrolled and tagged. Its registration, axle configuration, tare and permits are in the registry.
2. At a mine, quarry or factory, the approved loading-site scale weighs it and sends a signed ticket. The registry
   issues an origin token. Without an approved scale there is no token.
3. At the first road station the mainline node reads plate and tag and takes the high-speed WIM reading and the
   dimension scan.
4. With a valid token, consistent weight and dimensions inside limits give a green. Without a token, a weight below
   the limit by the full margin and the same other checks also give a green, and the node issues a road token.
5. Anything else diverts into the Rolling Verification Lane, which measures every parameter at about 10 km/h
   (route `verification_lane`).
6. Passing the lane issues a token. Failing sends the truck to the static scale and an officer (route `static_scale`).
7. Later stations honour the token and check only consistency, so the truck keeps moving.

### 6.4 Decision rules

| Where | Result | Conditions | Engine (clr-2.0.0) |
|---|---|---|---|
| Port | Green | Identity and releases valid, gross and axle-group loads below the limit after the margin, measured and expected weight within tolerance. Token issued | node `port_gateout`, no RED/AMBER rule, token source `port` issued |
| Port | Amber | Near the limit or weight variance too large. Re-weigh in the port, correct if needed (customs present for sealed loads) | `GVM_OVER_POSSIBLE`, `DECLARATION_MISMATCH` → route `port_reweigh` |
| Port | Red | Over the limit beyond the margin. Held for corrective action. Blocking gate-out is a policy decision for KPA, KRA and KeNHA | `GVM_OVER_CERTAIN` etc. → route `hold` |
| Origin | Green | Approved scale reading below the limit after the margin, identity match, signed ticket. Origin token issued at an initial trust tier | node `origin`, token source `origin`, tier 2 |
| Road mainline | Green | Valid token and identity match, weight within tolerance of the token weight (about 8 % for port or origin tokens, about 11 % for road tokens), dimensions inside limits, axle count matches registration. Or no token but weight below the limit by the full margin and the same other checks, which also issues a road token | `TOKEN_PRESENT` + `TOKEN_COVERS_MARGIN`; or no token and no AMBER rule → token source `road` |
| Road mainline | Divert to lane | No token and weight inside the margin band, inconsistent weight, dimension or axle-count mismatch, unreadable identity, or random audit | `GVM_OVER_POSSIBLE` (untokened), `TOKEN_WEIGHT_INCONSISTENT`, `DIMENSION_OVER` without permit, `AXLE_CONFIG_MISMATCH`, `IDENTITY_LOW_CONFIDENCE`, `RANDOM_AUDIT` → route `verification_lane` |
| Rolling Verification Lane | Green | Full parameter set within limits after the margin. Token issued, valid downstream | node `verification_lane`, token source `lane` |
| Rolling Verification Lane | Red | Over the limit beyond the margin, dimension or permit breach, or inconclusive. Static scale and officer. Hazardous and perishable flags change the handling | RED rules or AMBER at the lane → route `static_scale` |
| Audit | Random | 3 % of mainline greens go through the lane at first, falling toward 1–2 % as trust builds, and higher for new origins and high-demerit fleets | `RANDOM_AUDIT` with `audit_rate_by_tier` |

For loads in the margin band, the road reading no longer has to be accurate against the limit. It only has to confirm
that the weight is unchanged since the port, which is a much easier test (`TOKEN_COVERS_MARGIN` downgrades the
"possible over" rules to INFO when a valid, consistent token exists; "certainly over" remains RED).

## 7. What changes from the earlier proposals

| Earlier | Now | Why |
|---|---|---|
| Weigh only on the road | Weigh at each truck's first trusted point (port exit, origin site or first road station) and honour it downstream | Gives a reference and removes repeat stops |
| Port trucks only | All heavy trucks in three streams | Mines, quarries and factories are part of the traffic |
| Weight only | Weight, dimensions, axle configuration, lifted axles, per-wheel balance, permits, certificates | High-speed WIM misses most of what KeNHA checks at static bridges |
| Judge absolute weight against the limit | Compare with the token, absolute rule as fallback | Removes the near-limit accuracy problem for tokened trucks |
| Build our own road high-speed scales | Reuse KeNHA's high-speed WIM feed, add our own verification lane | Lower cost, and the lane supplies what the feed lacks |
| Static scale for every doubtful truck | Rolling Verification Lane for doubtful trucks, static scale for red cases | One rolling lane equals about 25 static lanes |
| Plate and RFID identity | Add container OCR, e-seal, release status, permits and fleet enrolment | Removes repeated manual checks |
| Periodic calibration | Quarterly by an accredited calibrator, plus the audit loop | Required by Reg 6 |
| Assumed pre-screening is acceptable | Use Reg 10(2), seek approval under Reg 5, approved signs under Reg 9 | A legal basis for green decisions |
| Compete with the weighbridge operator | Registry, port and origin nodes, and the lane, in partnership on road feeds | Fits Reg 3(3) and the contractor model |
| Simulate one road station | Simulate the whole chain for three truck streams | The gain comes from moving and merging work |

What each party gains: KPA shorter exit inspection and fewer re-checks; KRA a new weight risk signal for
misdeclaration; KeNHA fewer static-scale queues, full parameter data and a clean audit trail; loaders such as mines
and quarries a way to keep trucks moving and avoid fees; transporters fewer stops and a way to avoid fees and
detention.

## 8. Implementation roadmap

| Phase | When | What happens | Exit gate |
|---|---|---|---|
| 0–1. Access and legal | Months 0–3 | Meet KPA, KRA, KeNHA, NTSA, KenTrade, the weights-and-measures body, the Kenya Transporters Association and two or three candidate loaders (a quarry, a mine or factory). Request data (Section 10.6). Get a legal opinion on Reg 10(2), Reg 5, Reg 3(4) and digital certificates | MoUs or written interest, data access agreed, legal route clear |
| 2. Baseline and design | Months 3–7 | Time-and-motion study at the port exit and Mariakani. Classification count to find the real share of port and non-port trucks. Study of dimension and lifted-axle violations. Run the simulation. Specify token, APIs and security | Simulation shows the gate is met (Section 10.9) |
| 3. Bench prototype | Months 6–11 | Scale-model rig, token service, OCR on recorded video, LiDAR dimension portal test, per-wheel scale test, mock agency APIs, replay of recorded signals | Latency and repeatability targets met on the rig |
| 4. Shadow pilot | Months 10–16 | One port exit lane, one origin site and a verification lane at Mariakani. Tokens are issued and compared, but nobody acts on them | Accuracy and false-clear targets met over a sustained period |
| 5. Live pilot | Months 16–24 | Volunteer fleets and loaders use the green lane. Approved signs. Static scale audits continue. Seek approval of lane scales as legal-grade | Agency approval to operate live, then scale to other stations |

The software deliverables of Phases 2 and 3 (token service, registry APIs, mock agency APIs, simulation) are in this
repository now; the data, legal and hardware items remain open.

### Integration map

| System | Data exchanged | Dependency risk |
|---|---|---|
| KPA gate systems (i-Gate, KWATOS) | Gate events, release status, exit slip | KPA must allow a weigh node in the exit lane |
| KRA (iCMS, ACD, tracking seals) | Release status, declared weight, seal ID, overload alerts | Data-sharing agreement |
| KeNHA control centre and WIM feed | Road weights, static results, certificates, release orders, officer e-signature | Access to the feed or permission to add readers and a lane |
| Loading-site scales (private) | Signed tickets, calibration certificates | Approval and audit of each scale |
| NTSA vehicle and permit records | Registration, tare, axle configuration, special-load permits | Data quality |
| KenTrade and clearing agents | Document status | Optional first, deeper later |
| Insurers (later) | Insurance validity | Optional |

All of these are registered as adapters in `mode=mock` until authorised credentials exist (`/api/v1/integrations`).

## 9. Expected benefit (revised, modelled)

All figures in this section are **modelled** (Monte Carlo, author's estimates). They are reproduced by
`kifaru_sim.rcs_v2` (`kifaru-sim v2`, `POST /api/v1/rcs/model`, web page `/model`) and must be replaced with
measured data from the Phase 2 baseline study.

Simulation of 600,000 trucks per row. Assumptions: 1.5 % of trucks overloaded (from the reported 98.5 % compliance),
load spread of 12 % of the limit (loads that would exceed the limit are capped just below it, so heavily loaded fleets
bunch at the limit; at 85 % average loading about 10 % of trucks sit there), port scale error 1 %, road scale error
2.5 %, 90 % of trucks carry a token, mismatch tolerance of three combined standard deviations (about 8 %), and 3 %
audits. Stop shares are percentages of all trucks at the road station.

| Average load (% of limit) | Road-only screening | Road-only with 5 % allowance | RCS v2 road stops | RCS v2 port re-weigh | Road truck-hours saved per day (v1 to v2) |
|---|---|---|---|---|---|
| 75 % | 9.0 % | 5.7 % | 3.8 % | 4.2 % | about 42 |
| 80 % | 14.4 % | 7.5 % | 4.4 % | 7.9 % | about 80 |
| 85 % | 23.3 % | 10.9 % | 5.3 % | 14.9 % | about 144 |
| 90 % | 35.5 % | 16.0 % | 6.5 % | 25.5 % | about 232 |

Truck-hours use 8,000 trucks a day and 6 minutes per stop, so one percentage point is 8 truck-hours.

### Reading it honestly

- v2 does not delete the near-limit checks. It moves them from the public road to the port, where trucks are already
  in a controlled area with cranes and customs. In total there are still about as many re-weighs (at 85 % loading,
  5.3 % on the road plus 14.9 % at the port versus 23.3 % on the road).
- The saving comes from relieving road queues and from fixing overloads where it is cheap. The more heavily loaded
  the fleet, the larger the shift.
- Two levers cut the port re-weigh share sharply. One is approving the port scale as legal-grade, which needs
  weights-and-measures approval. The other is applying the legal discretion allowance. With a 5 % allowance at the
  port, re-weighs fall to about 1.3 %. That is a policy decision for KeNHA.
- Token coverage matters. At 85 % loading the road stop share is 3.3 % with full coverage, 5.3 % at 90 %, 8.3 % at
  75 % and 13.3 % at 50 %. Fleet enrolment is therefore a core workstream.
- Port scale accuracy mainly moves the port re-weigh share (13.0 % at 0.5 % error, 14.9 % at 1 %, 18.8 % at 2 %) and
  barely changes the road stop share.
- Not yet counted: time saved from removed duplicate checks at port entry, loading and exit, avoided fees and
  detention, and customs benefits from catching weight misdeclaration. The baseline study must time each duplicate
  check.

### Mixed traffic and the Rolling Verification Lane

The table above covers port trucks. For the full traffic mix, the model adds a verification lane (error 1 %, margin
2 %), origin and road tokens, and a stream mix. Average loading is 85 %. A lane pass is assumed to cost 1.5 minutes and
a static stop 6 minutes. Shares are percentages of all trucks at the first station. (Modelled.)

| Trucks with a port or origin token | Sent to the lane | Sent to a static scale | Road-only baseline (static) | Truck-hours saved per day at the first station |
|---|---|---|---|---|
| 30 % | 17.3 % | 10.0 % | 20.9 % | about 53 |
| 50 % | 13.3 % | 7.1 % | 20.9 % | about 84 |
| 70 % | 9.3 % | 4.3 % | 20.9 % | about 114 |
| 90 % | 5.2 % | 1.5 % | 20.9 % | about 145 |

- **Later stations.** Once every truck carries a token (port, origin or road), about 3.3 % go to the lane (audits and
  mismatches) and almost none to a static scale. This is where the repeat stops disappear.
- **Untokened trucks alone.** The lane trims static-scale visits only from about 21 % to 14 %. The rest are trucks
  loaded within the 2 % margin of the limit. They need either a legal-grade lane reading or the discretion allowance.
- **Capacity.** At 500 trucks an hour, the lane peak is about 117 trucks an hour against a capacity near 370, so one
  lane per station is enough.
- **False clears.** Tokens are only issued to trucks that passed an earlier check, and the model shows no false clears
  among tokened trucks. Real fraud (plate swaps, cargo added later) is not in the model and is covered by audits.

## 10. Simulation plan (summary)

The full plan is in [`../06-operations/rcs-v2-simulation-plan.md`](../06-operations/rcs-v2-simulation-plan.md).

| Level | Simulates | Tools | Output | Repository |
|---|---|---|---|---|
| L1 Sensor and algorithm | Truck dynamics on a rough road, tyre contact, sensor response, temperature drift and noise, then the weight estimator | Python (NumPy, SciPy), a quarter-car model; MATLAB or Simulink optional | Error curves by speed, load and temperature. These set the port and road errors used in L2 | `packages/wim_dsp` (signal generator and pipeline) |
| L2 Process | The whole chain for three truck streams, as-is and to-be, as a discrete-event model | SimPy (Python); AnyLogic is an alternative | Stops, delays, queues, truck-hours, false-clear rate | `kifaru_sim.rcs_v2` (chain Monte Carlo), SimPy policy `rcs_v2`, `kifaru_sim.experiments` |
| L3 Road traffic | Approach lanes, diverge lanes, the rolling verification lane and queue spillback onto the mainline | SUMO with TraCI | Queue lengths, spillback risk, diverge lane length | `kifaru_sim.sumo_adapter` |
| L4 System and hardware-in-the-loop | Token service, APIs and edge pipeline under load and failure | FastAPI mock agencies, Locust, Mosquitto MQTT, recorded signals replayed into the bench rig | Latency, failover behaviour, data integrity | `apps/api` (`/rcs`), `apps/api/tests/load`, `edge/gateway` |

Timeline: about 16 weeks (baseline plan and data requests, L1, L2, L3, L4, validation and committee report).
Go/no-go gate: proceed to the shadow pilot if the validated model shows that v2 cuts the road stop share by at least
10 points against the measured baseline, or removes recurring peak saturation, with a false-clear rate at or below
1 %, and the port re-weigh volume is practical for KPA. If not, narrow the project to a vehicle-side or registry-only
offering (`kifaru-sim v2-gate`).

## 11. Risks, open questions and decisions

### Main risks

- KPA may not allow a weigh node in the exit lane, or may not accept weight as a gate-out condition.
- A port or lane scale needs approval. Without legal-grade status, trucks measured within the margin of the limit
  still need static weighing (`Lane.legal_grade` defaults to false).
- Private origin scales may under-report. Mitigate with approval and audit of each scale, comparison of origin
  readings with road and lane readings, and token suspension for drift.
- Token fraud: swapped plates or cargo added after the first weighing. Bind token to plate, tag and seal, check
  weight consistency on the road and audit (`TOKEN_IDENTITY_MISMATCH`, `TOKEN_WEIGHT_INCONSISTENT`, `RANDOM_AUDIT`).
- Legitimate weight changes: partial offloads at inland depots and fuel use. Use a validity window and tolerance, and
  let a lane pass renew a token.
- Untokened and first-time trucks have more uncertainty, so they rely on the verification lane. Fleet and loader
  enrolment is a core workstream.
- The lane needs land and civil works at each station (about 250 m including approach and exit). Confirm
  availability early, and enforce speed discipline.
- Legal limits: officers must still sign tickets and release orders for overloaded vehicles (Reg 3(4), Reg 11(3)).
  Define an e-signature workflow and confirm that Reg 10(2) covers a digital status.
- Data-sharing delays and cybersecurity. Sign every record and keep audit logs (Ed25519 signatures, hash-chained
  ledger, audit events).

### Open questions to confirm

- What share of trucks at Mariakani and other stations come from the port, from industrial origins and from elsewhere?
- Does KeNHA already share road WIM results with KPA or KRA, and can we get the raw feed?
- Does the port already weigh imports at the gate?
- Which dimension limits, lifted-axle and permit checks does KeNHA enforce at static bridges today, and how often are
  they violated?
- Can the Reg 10(2) screening exemption apply to a digital token, who must approve the devices, and can an authorised
  officer e-sign remotely?
- Can low-speed in-motion weighing be approved as legal-grade?
- Is the 5 % discretion allowance applied routinely?
- Which route-specific limits apply, and does the 34-tonne container limit still hold?

### Decisions requested

1. Approve the redesign around the port gate-out weigh node and token.
2. Approve Phases 0–2, including the 16-week simulation, with a gate before any hardware spend.
3. Authorise approaches to KPA, KRA, KeNHA, NTSA and the weights-and-measures body.
4. Nominate an executive sponsor and a legal adviser.

## 12. Sources

- EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018, full text: bdears.busitema.ac.ug
- Process guide supplied by the project owner covering ship arrival, customs, port release, truck exit and
  weighbridges. It cites KRA, KPA, KeNHA, InfoTrade Kenya and the Kenya Transporters Association. Items such as the
  reported gross limits and 2026 events were not independently re-verified.
- Earlier RCS decision brief and hardware analysis: sensor, calibration and benefit assumptions.
- Simulation results in Section 9 are the author's Monte Carlo estimates under the stated assumptions and must be
  replaced with measured data.
- Sections 4, 5 and the mixed-traffic results in Section 9 are the author's design and Monte Carlo estimates (lane
  error 1 %, origin scale error 1 %, lane pass 1.5 minutes, static stop 6 minutes). They must be replaced with measured
  data.
