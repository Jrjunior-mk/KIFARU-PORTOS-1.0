# SmartPort port-process layer — platform contract

Status: design contract (2026-11-05) for the SmartPort additions: the eleven-stage truck and cargo workflow from
pre-arrival registration to delivery, the per-stage data dictionary, agency roles (adding KEBS and KenTrade), a data
register with provenance (actual / published / estimated / simulated), and an "existing port versus SmartPort"
discrete-event simulation. Backend, web, simulation and documentation are built against this file. It extends, and
never replaces, the RCS v2 contract (`rcs-v2-api-contract.md`): the port gate-out weigh node is stage 7 of this
workflow and the token it issues is what later stations honour.

## 1. The port visit

One `PortVisit` per truck collection trip. It links a shipment, a vehicle, a driver and (optionally) a weighbridge
appointment, and records the timestamp and data of each stage.

```
PORT_STAGES = [
  "pre_registered",   # 1  pre-arrival registration and scheduling
  "customs_cleared",  # 2  customs clearance and document verification
  "arrived",          # 3  truck arrival and identification (approach / queue)
  "gate_in",          # 4  gate-in and security inspection
  "yard_allocated",   # 5  yard allocation and cargo location
  "loaded",           # 6  cargo verification and loading
  "weighed",          # 7  automated weighing and weight verification (port gate-out weigh node, RCS v2)
  "final_cleared",    # 8  final cargo and document verification (gate pass)
  "gate_out",         # 9  gate-out and port departure (dwell time closed)
  "in_transit",       # 10 inland transportation and cargo tracking
  "delivered",        # 11 cargo delivery and trip closure
]
```

### `PortVisit` columns (schema `core`, table `port_visits`)

| Group | Columns |
|---|---|
| Identity | `id`, `reference` (PV-…), `shipment_id`, `vehicle_id`, `driver_id`, `transporter_org_id`, `appointment_id`, `stage`, `status` (active / closed / cancelled), `source` (live / simulated / replay) |
| 1 Pre-arrival | `truck_type`, `container_number`, `cargo_type`, `declared_mass_kg`, `destination`, `appointment_at`, `expected_arrival_at`, `pre_registered_at` |
| 2 Customs | `customs_declaration_ref`, `bill_of_lading`, `trade_direction` (import / export / transit), `duty_status` (paid / unpaid / pending), `customs_status` (cleared / pending / held), `inspection_status` (required / completed / not_required), `permit_status` (approved / rejected / pending), `hold_reason`, `customs_cleared_at` |
| 3 Arrival | `arrived_at`, `anpr_plate`, `rfid_epc`, `appointment_valid`, `queue_position`, `queue_length`, `queue_wait_s`, `arrival_lat`, `arrival_lon` |
| 4 Gate-in | `gate_in_at`, `gate_in_id`, `access_authorised`, `vehicle_inspection` (passed / failed), `driver_verified`, `gate_in_processing_s`, `rejection_reason` |
| 5 Yard | `yard_allocated_at`, `terminal_id`, `yard_block`, `container_position`, `loading_instruction`, `yard_wait_s` |
| 6 Loading | `loading_start_at`, `loading_end_at`, `equipment_id`, `seal_number`, `cargo_verification` (matched / mismatched), `cargo_condition` (good / damaged), `loading_exceptions` |
| 7 Weighing | `weighing_event_id` (the port gate-out pass), `weighing_arrival_at`, `weighing_start_at`, `weighing_end_at`, `tare_kg`, `gross_kg`, `net_kg`, `weight_discrepancy_kg`, `calibration_valid`, `token_ref` |
| 8 Final clearance | `final_cleared_at`, `cargo_release_status`, `delivery_order_ref`, `gate_pass_no`, `payment_status`, `clearance_exceptions` |
| 9 Gate-out | `gate_out_at`, `gate_out_id`, `exit_cargo_verified`, `exit_authorised`, `dwell_time_s` (gate_out − gate_in) |
| 10 Transit | `departed_at`, `route`, `distance_km`, `eta_at`, `stoppage_s`, `delay_reason` |
| 11 Delivery | `arrived_destination_at`, `delivered_at`, `pod_ref`, `transit_time_s` (delivered − gate_out) |

Every stage change writes a `CargoProcessingEvent` (existing table) with `stage = PORT:<stage>` so the passport
timeline shows the port visit, and the shipment's own stage is kept in step (at_port → gate_processing → released →
in_transit → delivered).

## 2. API (`/api/v1/port`)

```
GET  /port/stages                          -> [{stage, order, label, required_fields[], agency}]
POST /port/visits                          PortVisitIn (stage 1 data) -> PortVisitOut        (transporter_admin, dispatcher, cargo_owner, port_controller, admin)
GET  /port/visits?stage&vehicle_id&shipment_id&status&limit -> PortVisitOut[]           (tenant-scoped)
GET  /port/visits/{id}                     -> PortVisitOut
POST /port/visits/{id}/advance             StageAdvanceIn {stage, data{...}} -> PortVisitOut (validates required fields for that stage; port_controller / admin for stages 4-9, transporter roles for 10-11, auditor read-only)
POST /port/visits/{id}/cancel              {reason}
GET  /port/kpis?hours=24                   -> PortKpisOut
GET  /port/board                           -> {stages: [{stage, label, count, visits: PortVisitOut[] (latest 20)}]}
POST /port/simulate                        PortSimIn -> PortSimOut          (runs kifaru_sim.port_process, modelled)
GET  /data/register?classification&agency -> DataParameterOut[]
GET  /data/register/{key}                  -> DataParameterOut
```

### Schemas

```ts
PortVisitOut { id, reference, shipment_id, shipment_reference, vehicle_id, plate, driver_id, transporter_org_id, appointment_id, stage, stage_order, status, source,
  // every column of section 1 by its name, nullable
  timeline: { stage, at, data: Record<string, unknown> }[],   // one entry per completed stage
  kpis: { queue_wait_s, gate_in_processing_s, yard_wait_s, loading_duration_s, weighing_service_s, clearance_duration_s, dwell_time_s, transit_time_s },  // nulls until known
  outstanding: string[],   // required fields of the next stage that are still missing
  created_at, updated_at }
StageAdvanceIn { stage: PortStage; data: Record<string, unknown>; at?: string }   // `at` defaults to now
PortKpisOut {
  period_hours, visits_total, visits_by_stage: Record<PortStage, number>,
  avg_queue_wait_s, avg_gate_in_processing_s, avg_yard_wait_s, avg_loading_duration_s, avg_weighing_service_s, avg_clearance_duration_s,
  avg_dwell_time_s, p90_dwell_time_s, avg_transit_time_s, throughput_per_hour, gate_outs_total, exceptions_total,
  benchmarks: { key, label, value, unit, classification, source_url }[],   // published comparators from the data register (e.g. KPA truck turnaround 6.7 h, 2023)
  label: "measured from platform records (live / simulated as tagged)"
}
PortSimIn {
  trucks_per_day: 8000, hours: 24, gates_in: 4, gates_out: 4, gate_service_existing_s: 240, gate_service_smart_s: 60,
  loading_equipment: 30, loading_minutes_container: 20, loading_minutes_bulk: 30, loading_minutes_general: 25,
  weighbridges: 2, weigh_service_existing_s: 300, weigh_service_smart_s: 90,
  clearance_desks: 6, clearance_minutes: 15, hold_prob_existing: 0.15, hold_prob_smart: 0.05, hold_minutes: 45,
  appointment_smoothing: true, peak_factor: 1.5, inland_distance_km: 480, inland_speed_kmh: 45, stop_prob: 0.3, stop_minutes: 40, seed: 1, reps: 3
}
PortSimOut { label: "MODELLED", scenarios: { existing: PortSimKpis, smartport: PortSimKpis }, deltas: Record<string, number>, assumptions: string[], benchmarks: [...] }
PortSimKpis { avg_wait_min, avg_queue_len, max_queue_len, avg_processing_min, weigh_service_min, throughput_per_hour, avg_dwell_h, p90_dwell_h, avg_transit_h, gate_in_utilisation, weigh_utilisation }
DataParameterOut { key, label, value, unit, classification: "actual"|"published"|"estimated"|"simulated", agency, source_title, source_url, period, notes, used_by: string[] }
```

## 3. Data register (seed; `published` unless stated)

| key | value | unit | agency / source | period |
|---|---|---|---|---|
| `kpa.throughput_tonnes_2024` | 41.1 million | tonnes | KPA via Kenya News Agency / Business Daily | 2024 |
| `kpa.container_teu_2024` | 2,005,076 | TEU | KPA via Business Daily | 2024 |
| `kpa.transshipment_teu_2024` | 491,666 | TEU | KPA via Business Daily | 2024 |
| `kpa.throughput_tonnes_2023` | 35.98 million | tonnes | KPA bulletin via The Star | 2023 |
| `kpa.truck_turnaround_h_2023` | 6.7 | hours | KPA annual bulletin via Kenya News Agency | 2023 (7.1 h in 2022) |
| `kpa.container_dwell_days_2023` | 3.6 | days | KPA bulletin; SCEA | 2023 (3.9 d 2022; 4.1 d 2019) |
| `kpa.container_ship_turnaround_days_2024` | 2.9 | days | KPA bulletin 2024 via The Star | 2024 (2.3 d 2023) |
| `kpa.ship_waiting_days_2024` | 1.53 | days | KPA bulletin 2024 via The Star | 2024 (0.78 d 2023) |
| `scea.icdn_truck_turnaround_h_2023` | 3.7 | hours | Shippers Council of Eastern Africa | 2023 (7 h in 2020) |
| `scea.mombasa_dwell_h_2024` | 79 | hours | SCEA (Agayo Ogambi) via KBC | Nov 2024 |
| `kpa.gate_scanning_delay_h_2025` | 3 | hours | transporters' association via The Standard (complaint; target 15 min) | Aug 2025, estimated |
| `kenha.compliance_pct_fy2425` | 98.43 | % | KeNHA Annual Report 2025 | FY 2024/25 |
| `kenha.network_km_fy2425` | 10,776 | km | KeNHA Annual Report 2025 | FY 2024/25 |
| `kenha.weighbridge_stations` | 13 | stations | KeNHA Annual Report 2025 | FY 2024/25 |
| `kenha.mariakani_compliance_pct` | 98.5 | % | The Star / Streamline (KeNHA statement) | 2026 |
| `kenha.mariakani_trucks_per_day` | 8,000 | trucks/day (more than) | The Star (KeNHA statement) | 2026 |
| `ncttca.mariakani_daily_weighed_2016_17` | 2,162 – 5,312 | trucks/day | NC Transport Observatory report issue 10, fig. 19 | Oct 2016 – Mar 2017 |
| `ncttca.mariakani_compliance_2016_17` | 96 – 99 | % | NC Transport Observatory issue 10, fig. 20 | Oct 2016 – Mar 2017 |
| `ncttca.weighbridge_share_of_stoppages_2017` | 13.4 | % of stoppages | NC Transport Observatory issue 10 | 2017 |
| `ncttca.port_dwell_h_mar2017` | 70 | hours | NC Transport Observatory issue 10 (target 72 h) | Mar 2017 |
| `ncttca.mombasa_malaba_transit_h_2019` | 53 – 72 | hours | NC quarterly dashboard Q4 2019 | 2019 |
| `ncttca.mombasa_malaba_transit_h_2022` | 77 | hours | NC Transport Observatory 18th edition | 2022 (target 40 h) |
| `ncttca.mombasa_nairobi_transit_h_2017` | 110 – 163 | hours | NC Transport Observatory issue 10, RECTS Feb–Mar 2017 | 2017 |
| `kentrade.agencies_connected` | 22 – 30 | agencies | KenTrade / TradeMark Africa | 2015–2017 |
| `kentrade.document_reduction_pct` | 30 – 50 | % | KenTrade | 2017 |
| `scea.permit_agencies` | 26 | agencies | SCEA | 2024 |
| `eac.overload_fee_5000kg_usd` | 2,990 | USD | EAC VLC Regulations 2018 (reported in the RCS v2 plan) | 2021–2030 table |
| `platform.lane_capacity_per_hour` | 370 | trucks/h | RCS v2 plan arithmetic | estimated |
| `platform.port_node_error_pct` | 1.0 | % | RCS v2 plan | estimated |
| `sim.static_service_min` | 4 | min | SimPy station model | estimated |

Source URLs are in `docs/06-operations/data-register.md`. Every register entry is exposed by `GET /data/register`
and shown in the web app with its classification badge; simulation parameters that take their default from a
register entry name it in `used_by`.

## 4. Simulation (`kifaru_sim/port_process.py`)

SimPy model of the port visit (stages 3 to 9) plus inland transit (10 to 11):

```
arrivals (appointments or free) -> approach queue -> [gate-in, G gates] -> yard wait -> [loading, E equipment]
   -> [weighing, W bridges] -> [final clearance, C desks; hold with prob h for H minutes] -> [gate-out, G gates]
   -> inland transit (distance / speed, random stops) -> delivery
```

Two policies: `existing` (manual gate checks 4 min, static weighing 5 min, 15 % document holds, no appointment
smoothing) and `smartport` (RFID/ANPR gate 1 min, port gate-out node 1.5 min, pre-cleared documents so 5 % holds,
appointment smoothing, token issued for the road). KPIs per the SmartPort document: average waiting time, average
queue length, truck processing time, weighbridge service time, throughput, port dwell time, transit time. Defaults
are calibrated so the `existing` policy reproduces KPA's published 2023 truck turnaround of about 6.7 hours; the
calibration note is printed with every result. CLI: `kifaru-sim port --reps 3 --hours 24`.

## 5. Agencies

Add `kebs` ("KEBS standards and PVoC / import standardisation mark", contract: GET /v1/consignments/{ref}/standards-status) and
`kentrade` ("KenTrade TradeNet single window", contract: GET /v1/declarations/{ucr}/permits -> [{agency, permit, status}]) to the
integration registry, mock by default like the others. Stage ownership: 1 transporter / clearing agent; 2 KRA, KenTrade,
KEBS; 3–6, 8, 9 KPA; 7 KPA + KeNHA (axle loads); 10 transporters, telematics, KeNHA weighbridges; 11 cargo owner / warehouse.

## 6. Web

- `/port` page (roles: port_controller, weighbridge_operator, transporter_admin, dispatcher, cargo_owner, auditor, admin): KPI tiles with published benchmarks beside them, a stage board (11 columns, counts, cards), visit drawer with the stage timeline and an "advance stage" form that renders the required fields of the next stage, "new visit" form (stage 1).
- `/data` page: the data register as a table with classification badges, agency filter, source links, and which parameters use each entry.
- Model explorer gains a "Port process (existing vs SmartPort)" tab calling `POST /port/simulate` with a comparison table and a bar chart of the KPIs.
- About page gains the eleven-stage workflow and the agency table (KPA, KRA, KenTrade, KeNHA, NTSA, KEBS).
- Passport view shows the port-visit timeline when a visit exists.
