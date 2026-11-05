# SmartPort — truck and cargo workflow, data required at each stage, and platform mapping

Status: requirements document, 2026-11-05. Source: the SmartPort document supplied by the project owner (introduction
and purpose, eleven-stage workflow, per-stage data tables, agencies, data sharing, simulation data format). Platform
contract: `docs/02-architecture/smartport-port-process-contract.md`. The SmartPort layer extends RCS v2
(`rcs-v2-port-anchored-clearance.md`): stage 7 of this workflow is the port gate-out weigh node, and the Load
Compliance Token it issues is what later weighbridges honour. Nothing in this document is a measured result; the
figures referenced come from `docs/06-operations/data-register.md` with their classification.

## 1. Purpose

SmartPort streamlines truck and cargo movement within and beyond the Port of Mombasa by:

1. Reducing delays and congestion through automated truck identification, scheduling and queue monitoring.
2. Improving weighing efficiency through automated weighing and accurate cargo weight recording.
3. Enhancing data sharing and coordination among KPA, KRA, KenTrade and other agencies.
4. Improving cargo tracking from port entry to inland destinations.
5. Supporting decisions through real-time operational data, monitoring and simulation.

The platform implements these as one record per truck collection trip (`PortVisit`), advanced stage by stage with the
data each stage requires, a data register that classifies every number as actual, published, estimated or simulated,
and an "existing port versus SmartPort" simulation.

## 2. The eleven-stage workflow

Each stage below lists what happens, the data the SmartPort document requires (verbatim), the owning agency, and the
platform mapping (`PortVisit` columns and API from the contract).

### Stage 1 — Pre-arrival registration and scheduling

What happens: transporters and clearing agents submit truck, driver, cargo and container details; truck collection
appointments are scheduled; cargo documentation is prepared before the truck arrives.

| Data required | Specific information |
|---|---|
| Truck ID | Unique truck identification number |
| Registration number | Vehicle number plate |
| Truck type | Trailer, tanker, flatbed, container truck |
| Transport company | Name of transporter |
| Driver ID | Unique driver reference |
| Container number | Unique container identification |
| Cargo type | General cargo, containerised, bulk, etc. |
| Cargo weight | Declared cargo weight (kg/tonnes) |
| Destination | Nairobi, Kisumu, Nakuru, etc. |
| Appointment time | Scheduled port arrival |
| Expected arrival | Estimated truck arrival time |

Owner: transporter / clearing agent (data), KPA (appointment capacity). Platform: `POST /port/visits` creates the visit
at stage `pre_registered` with `vehicle_id`, `driver_id`, `transporter_org_id`, `truck_type`, `container_number`,
`cargo_type`, `declared_mass_kg`, `destination`, `appointment_at`, `expected_arrival_at`, `pre_registered_at`; optional
`appointment_id` links a weighbridge slot (`core.appointments`). The container number is validated as ISO 6346.

### Stage 2 — Customs clearance and document verification

What happens: KRA verifies declarations, duties and requirements; other agencies verify permits and certificates; cargo
is marked cleared, pending or held.

| Data required | Specific information |
|---|---|
| Customs declaration number | Unique customs entry reference |
| Bill of lading number | Shipping document reference |
| Import/export status | Import, export or transit |
| Duty payment status | Paid, unpaid or pending |
| Customs clearance status | Cleared, pending or held |
| Inspection status | Required, completed or not required |
| Permit status | Approved, rejected or pending |
| Clearance timestamp | Date and time of approval |
| Hold reason | Reason cargo cannot proceed |

Owner: KRA (customs), KenTrade (permits through TradeNet), KEBS (standards). Platform: `advance` to `customs_cleared`
with `customs_declaration_ref`, `bill_of_lading`, `trade_direction`, `duty_status`, `customs_status`,
`inspection_status`, `permit_status`, `hold_reason`, `customs_cleared_at`; adapters `kra`, `kentrade`, `kebs` (mock
until authorised). The declaration reference also feeds the expected-weight comparison in stage 7.

### Stage 3 — Truck arrival and identification

What happens: the truck approaches the port entrance; RFID and ANPR identify it; appointment and cargo details are
verified; the truck joins the queue if processing is not immediate.

| Data required | Specific information |
|---|---|
| Actual arrival time | Time truck reaches the port approach |
| Truck registration | Number plate captured by ANPR |
| RFID number | Electronic truck identification |
| Appointment verification | Valid or invalid |
| Queue position | Truck's position in the queue |
| Queue length | Number of waiting trucks |
| Waiting time | Time spent waiting |
| GPS location | Truck's recorded coordinates |

Owner: KPA. Platform: stage `arrived` with `arrived_at`, `anpr_plate`, `rfid_epc`, `appointment_valid`,
`queue_position`, `queue_length`, `queue_wait_s`, `arrival_lat`, `arrival_lon`; identity resolution reuses the
`identity` service (ANPR + RFID fusion) and queue length reuses `core.queue_records`.

### Stage 4 — Gate-in and security inspection

What happens: port security verifies access authorisation, vehicle and driver details; the gate records entry time.

| Data required | Specific information |
|---|---|
| Gate ID | Entrance gate used |
| Gate-in time | Actual entry timestamp |
| Access authorisation | Approved or rejected |
| Vehicle inspection status | Passed or failed |
| Driver verification | Verified or unverified |
| Entry processing time | Time taken to complete entry |
| Rejection reason | Reason for denied entry |

Owner: KPA. Platform: stage `gate_in` with `gate_in_at`, `gate_in_id`, `access_authorised`, `vehicle_inspection`,
`driver_verified`, `gate_in_processing_s`, `rejection_reason`. Dwell time starts here.

### Stage 5 — Yard allocation and cargo location

What happens: the truck is directed to the terminal or yard; container location is identified; loading instructions
are issued.

| Data required | Specific information |
|---|---|
| Terminal ID | Terminal assigned |
| Yard/block number | Cargo storage location |
| Container location | Specific container position |
| Truck assignment | Truck allocated to cargo |
| Loading instruction | Assigned collection instruction |
| Assignment time | Time truck receives allocation |
| Yard waiting time | Time spent waiting for cargo handling |

Owner: KPA (terminal operations). Platform: stage `yard_allocated` with `yard_allocated_at`, `terminal_id`,
`yard_block`, `container_position`, `loading_instruction`, `yard_wait_s`.

### Stage 6 — Cargo verification and loading

What happens: the container number is matched against collection documents; terminal equipment loads the cargo;
loading time and details are recorded.

| Data required | Specific information |
|---|---|
| Container ID | Container being collected |
| Cargo description | Type of goods |
| Seal number | Container security seal |
| Cargo verification status | Matched or mismatched |
| Loading start time | When loading begins |
| Loading completion time | When loading ends |
| Equipment ID | Crane, reach stacker, etc. |
| Loading duration | Total loading time |
| Cargo condition | Good or damaged |
| Loading exceptions | Any handling problems |

Owner: KPA. Platform: stage `loaded` with `loading_start_at`, `loading_end_at`, `equipment_id`, `seal_number`,
`cargo_verification`, `cargo_condition`, `loading_exceptions`; the seal is also recorded as an `ElectronicSeal` on the
shipment so the clearance engine can check it on the road.

### Stage 7 — Automated weighing and weight verification

What happens: the loaded truck proceeds to the weighbridge; gross and axle weights are recorded; the system compares
measured weight against declared weight and legal limits; discrepancies and overloads are flagged.

| Data required | Specific information |
|---|---|
| Weighbridge ID | Identification of weighing station |
| Truck ID | Truck being weighed |
| Weighing arrival time | Time truck joins weighing queue |
| Weighing start time | Time weighing begins |
| Weighing completion time | Time weighing ends |
| Tare weight | Weight of empty truck |
| Gross weight | Total weight of loaded truck |
| Net cargo weight | Gross weight minus tare weight |
| Axle weight | Weight carried by individual axles |
| Declared weight | Weight stated in cargo documents |
| Weight discrepancy | Difference between declared and measured weight |
| Calibration status | Whether weighing equipment is calibrated |

Owner: KPA (port gate-out weigh node) with KeNHA (axle-load limits). Platform: this stage is the RCS v2 port gate-out
node (`Lane.type = port_gateout`). A pass on that lane attaches automatically to the vehicle's active visit and
advances it to `weighed`, filling `weighing_event_id`, `weighing_arrival_at`, `weighing_start_at`, `weighing_end_at`,
`tare_kg` (vehicle registry), `gross_kg`, `net_kg`, `weight_discrepancy_kg` (measured minus declared), `calibration_valid`
and `token_ref` (the Load Compliance Token issued on GREEN). Axle loads, uncertainties and the decision stay on the
weighing event; the static scale remains the legal reference for RED cases.

### Stage 8 — Final cargo and document verification

What happens: documents, cargo release status and gate-pass details are confirmed; outstanding holds or payments are
addressed; the truck is authorised to exit.

| Data required | Specific information |
|---|---|
| Cargo release status | Approved or pending |
| Delivery order | Reference number |
| Gate pass number | Unique exit authorisation |
| Outstanding payment status | Paid or unpaid |
| Final verification time | Time documents are checked |
| Clearance exceptions | Any outstanding issues |

Owner: KPA with KRA release. Platform: stage `final_cleared` with `final_cleared_at`, `cargo_release_status`,
`delivery_order_ref`, `gate_pass_no`, `payment_status`, `clearance_exceptions`.

### Stage 9 — Gate-out and port departure

What happens: final exit verification; RFID or ANPR records departure; gate-out time and port dwell time are computed.

| Data required | Specific information |
|---|---|
| Gate-out time | Actual departure timestamp |
| Exit gate ID | Gate used |
| Truck ID | Departing truck |
| Cargo verification | Confirmation cargo matches records |
| Exit authorisation | Approved or rejected |
| Total port dwell time | Time between gate-in and gate-out |

Owner: KPA. Platform: stage `gate_out` with `gate_out_at`, `gate_out_id`, `exit_cargo_verified`, `exit_authorised`;
`dwell_time_s = gate_out_at − gate_in_at` is computed, and the shipment stage moves to `released`.

### Stage 10 — Inland transportation and cargo tracking

What happens: the truck proceeds to Nairobi, Nakuru, Kisumu or Eldoret; GPS tracks route, location and ETA; delays,
deviations and stops are recorded.

| Data required | Specific information |
|---|---|
| Departure time | Time truck leaves port |
| Destination | Final delivery location |
| GPS coordinates | Truck's location during transit |
| Route taken | Road/corridor used |
| Distance travelled | Kilometres covered |
| Estimated arrival time | Predicted delivery time |
| Actual arrival time | Recorded arrival |
| Stoppage duration | Time spent stationary |
| Delay reason | Traffic, breakdown, road closure, etc. |
| Delivery confirmation | Proof of delivery |
| Total transit time | Time from gate-out to destination |

Owner: transporters and telematics providers (positions), KeNHA weighbridges (token honoured on the road). Platform:
stage `in_transit` with `departed_at`, `route`, `distance_km`, `eta_at`, `stoppage_s`, `delay_reason`; positions come
from `POST /fleet/vehicles/{id}/position` and the `telematics` adapter; road weighbridge passes honour the token.

### Stage 11 — Cargo delivery and trip closure

What happens: cargo arrives; delivery is confirmed by proof of delivery; the trip is closed and transit time recorded.

Owner: cargo owner / warehouse. Platform: stage `delivered` with `arrived_destination_at`, `delivered_at`, `pod_ref`,
`transit_time_s = delivered_at − gate_out_at`; the visit closes and a `DeliveryRecord` is written.

## 3. SmartPort components mapped to the platform

| SmartPort component | Main function | Platform component |
|---|---|---|
| RFID and ANPR | Automated truck identification | `kifaru/services/identity.py` (ANPR + RFID fusion, confidence, conflict detection), lane readers, `PortVisit.anpr_plate` / `rfid_epc` |
| Digital scheduling | Manage truck arrival appointments | `core.appointments` (slot capacity per 15 min), `PortVisit.appointment_at` / `expected_arrival_at`, queue forecast |
| Queue monitoring | Monitor congestion and waiting times | `core.queue_records`, `GET /queue/{station}/forecast` (15/30/60/120 min), `PortVisit.queue_length` / `queue_wait_s` |
| Automated weighing | Record and verify truck/cargo weight | Port gate-out weigh node (RCS v2), clearance engine `clr-2.0.0`, declaration-mismatch rules, Load Compliance Token |
| Cargo tracking | Monitor cargo movement and status | Digital cargo passport (`/shipments/{ref}`), `PortVisit` timeline and transit fields, electronic seals |
| Agency integration | Facilitate authorised information sharing | Adapter registry (`kpa`, `kra`, `kenha`, `ntsa`, `customs`, `kentrade`, `kebs`), mock until authorised |
| GPS monitoring | Track trucks to mainland destinations | `telematics` adapter, `POST /fleet/vehicles/{id}/position`, station map |
| Central dashboard | Operational visibility and alerts | Control centre, `/port` stage board and KPIs, notifications, incidents |

Overall process flow (SmartPort): pre-arrival registration → customs and document clearance → truck identification and
gate-in → yard allocation → cargo verification and loading → weighing and weight verification → final clearance →
gate-out → inland transportation → cargo delivery. The platform's `PORT_STAGES` enumeration follows this order with
arrival (stage 3) kept separate from gate-in (stage 4) so that approach queue time and gate processing time are
measured independently.

## 4. Agencies and their responsibilities

| Agency | Responsibilities in SmartPort | Stages | Platform adapter |
|---|---|---|---|
| Kenya Ports Authority (KPA) | Port entry and exit, cargo handling, container storage, terminal operations, port infrastructure | 3–6, 8, 9 (and 7 as the port gate-out node host) | `kpa` (gate status, appointments) |
| Kenya Revenue Authority (KRA) | Customs declarations, duty collection, inspections, compliance, cargo release | 2, 8 | `kra` (iCMS declarations), `customs` (ECTS seals) |
| Kenya Trade Network Agency (KenTrade) | TradeNet national electronic single window: trade documentation, permits, approvals, inter-agency exchange | 1, 2 | `kentrade` (permits by UCR) |
| Kenya National Highways Authority (KeNHA) | National highways, axle-load compliance, weighbridge operations | 7, 10 | `kenha` (WIM events, watch-list) |
| National Transport and Safety Authority (NTSA) | Vehicle registration, roadworthiness, licensing, road safety | 1, 3 | `ntsa` (vehicle registry) |
| Kenya Bureau of Standards (KEBS) | Standards of goods (PVoC, import standardisation) | 2 | `kebs` (standards status) |

How agencies communicate today: KenTrade's TradeNet receives trade documents electronically; KRA, KEBS and other
regulators verify cargo and communicate clearance decisions through it; KRA handles customs clearance; KPA manages
port operations and truck entry and exit. SmartPort connects the relevant status from these systems into one shared
view (customs and agency clearance, entry and exit authorisation, loading and weighing records, truck location and
ETA, holds and delays) and complements the agency systems rather than replacing them. Published figures on the single
window (agencies connected, document reduction) are in the data register.

## 5. How the platform advances the SmartPort design

| SmartPort as drafted | Platform refinement | Why it performs better |
|---|---|---|
| Every truck verified at every stage | Exception-based verification: a valid token and a clean record pass on identity and consistency; only exceptions (mismatch, hold, audit) get a physical check | Cuts repeat checks without removing any legal check |
| Weight compared against declared and limits at the port | The port gate-out node issues a signed Load Compliance Token honoured at Mariakani, Athi River and later stations (RCS v2) | Removes repeat weighing stops on the road; modelled effect in `rcs-v2-port-anchored-clearance.md` §9 |
| Appointments scheduled | Appointment smoothing driven by the queue forecast (15/30/60/120 min) and a per-window cap; the port simulation shows the smoothing effect | Flattens the arrival peak instead of merely recording it |
| Dwell time computed per truck | Dwell, queue wait, gate processing, yard wait, loading, weighing service and clearance durations are KPIs with P90s, shown beside published benchmarks: KPA truck turnaround 6.7 h (2023); NCTTCA import container dwell 106.7 h in 2025 against a 48 h target and 87 h in July–September 2026 against 60 h, split into customs release 57 h and after-release 79 h (2025); Nairobi ICD dwell 3.4 days (2025); Mombasa–Nairobi transit 66 h over 482 km against a 29 h target (2025) | Managers see where the time goes and how it compares with the published record; the register separates container dwell from truck turnaround |
| Data "classified as actual, published, estimated or simulated" | A machine-readable data register (`GET /data/register`) with source URL and period on every entry; simulation parameters name the register entry they take their default from | Every number on the site and in the simulation is traceable |
| Existing vs proposed simulation | SimPy port-process model (`kifaru-sim port`) calibrated so the existing policy reproduces the published 2023 truck turnaround, plus the RCS v2 chain and station models; arrivals use Mariakani's 7,954–9,184 trucks a day (NCTTCA, July–September 2026), and the 6-minute stop cost sits between the corridor's normal 5–10 minute weighbridge crossing and Mariakani's 29 minutes under road works (NCTTCA 2025) | Baseline anchored on published figures, not assumed ones |

### Benchmarks from the newest primary sources

The NCTTCA 21st edition Observatory report (April 2026, data year 2025) and the July–September 2026 quarterly report
give the current corridor record against which the `/port` KPIs are shown: Mombasa throughput 45.45 million tonnes and
2.11 million TEU in 2025; import container dwell 106.7 hours in 2025 and 87 hours in Q3 2026; vessel turnaround 192
hours (2025) and 107 hours (Q3 2026); Mariakani weighing 7,954–9,184 trucks a day in Q3 2026 at 99.1–99.9 % compliance;
Mombasa–Malaba transit 94 hours in Q3 2026 against a 55-hour target; road rate Mombasa–Nairobi 860 USD a truck. KPA's
2026 initiatives (smart gates at Gates 23 and 24, terminal operating system upgrade, Maritime Single Window) are the
systems the port gate-out weigh node would sit beside. Keys, periods and URLs: `docs/06-operations/data-register.md`
section 2b.

## 6. Data for simulation

Simulation data represents the actual operations of the Port of Mombasa for modelling truck movement, cargo
handling, weighing, clearance and transportation to mainland destinations. The categories, collection formats,
parameters, scenarios and KPIs from the SmartPort document, and the classification of each source, are in
`docs/06-operations/data-register.md`. Where actual records are unavailable, clearly labelled estimates are used for
preliminary modelling and validated where possible.
