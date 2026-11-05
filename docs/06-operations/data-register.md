# Data register — published, estimated and simulated figures used by the platform

Status: 2026-11-05. The register is the single list of numbers the platform, the simulations and the proposal rely on,
each with its classification, period and source. It is exposed by `GET /api/v1/data/register` and shown on the web page
`/data`. Classifications follow the SmartPort document: **actual** (operational records obtained from an agency),
**published** (figures in official reports or press reports of agency statements), **estimated** (engineering
assumptions), **simulated** (model outputs). No entry is currently `actual`: no agency record has been obtained yet.

## 1. How to read this register

- Definitions differ and the figures are not interchangeable. *Container dwell time* (KPA, SCEA) is the time a
  container spends in the port from discharge to gate-out. *Truck turnaround time* (KPA) is the time a truck spends in
  the port from gate-in to gate-out. *Port dwell time* in the Northern Corridor Observatory is containerised cargo dwell
  against a 72-hour target. *Transit time* is gate-out to a destination or border. The SmartPort "total port dwell time"
  (gate-in to gate-out) corresponds to KPA's truck turnaround, not to container dwell.
- Several entries are press reports of agency statements (The Star, Kenya News Agency, KBC, Business Daily) rather
  than audited tables; they are marked as such in the notes.
- Several entries are from 2016–2022 (Northern Corridor Observatory issue 10, 18th edition, 2019 and 2021 dashboards,
  KenTrade 2017). They are kept as history; the current values are in section 2b (NCTTCA 21st edition and the
  July–September 2026 quarterly report). Still to obtain: the KPA Annual Review and Bulletin of Statistics 2024 and 2025
  (truck turnaround and container dwell for 2024 and 2025 by KPA's own definitions).
- The Observatory's *containerized import cargo dwell* is discharge to exit, excluding containers held more than
  21 days; it is not truck turnaround (gate-in to gate-out). The two must not be compared with each other.
- The platform's weighbridge stop-cost assumption (6 minutes per static stop, `sim.stop_minutes`) sits between the
  corridor's normal weighbridge crossing time of 5–10 minutes (corridor average about 4 minutes in 2025) and
  Mariakani's 29 minutes under road works in 2025 (NCTTCA 21st edition).
- The newest primary figures come from the NCTTCA 21st edition Observatory report (April 2026, data year 2025) and
  the NCTTCA quarterly performance report for July–September 2026; the older 2016–2022 entries are kept as history.
- `used_by` names the simulation parameters or pages that take a default or a benchmark from the entry.

## 2. Register

| Key | Value | Unit | Classification | Period | Agency / source | Used by |
|---|---|---|---|---|---|---|
| `kpa.throughput_tonnes_2024` | 41.1 million | tonnes | published | 2024 | KPA, reported by Kenya News Agency and Business Daily | About page, proposal |
| `kpa.container_teu_2024` | 2,005,076 | TEU | published | 2024 | KPA annual figures, Business Daily | About page, proposal |
| `kpa.transshipment_teu_2024` | 491,666 | TEU | published | 2024 | KPA annual figures, Business Daily | proposal |
| `kpa.throughput_tonnes_2023` | 35.98 million | tonnes | published | 2023 | KPA Annual Review and Bulletin of Statistics 2024, via The Star | proposal |
| `kpa.truck_turnaround_h_2023` | 6.7 | hours | published | 2023 (7.1 h in 2022) | KPA annual bulletin, via Kenya News Agency | `port_process` calibration target, `/port` KPI benchmark |
| `kpa.container_dwell_days_2023` | 3.6 | days | published | 2023 (3.9 d 2022; 4.1 d 2019) | KPA bulletin; SCEA | `/port` KPI benchmark |
| `kpa.container_ship_turnaround_days_2024` | 2.9 | days | published | 2024 (2.3 d 2023) | KPA bulletin 2024, via The Star | About page |
| `kpa.ship_waiting_days_2024` | 1.53 | days | published | 2024 (0.78 d 2023) | KPA bulletin 2024, via The Star | About page |
| `scea.icdn_truck_turnaround_h_2023` | 3.7 | hours | published | 2023 (7 h in 2020) | Shippers Council of Eastern Africa | `/port` KPI benchmark (inland depot) |
| `scea.mombasa_dwell_h_2024` | 79 | hours | published | Nov 2024 | SCEA (Agayo Ogambi), via KBC | `/port` KPI benchmark |
| `kpa.gate_scanning_delay_h_2025` | 3 | hours (target 15 min) | estimated | Aug 2025 | Transporters' association complaint, via The Standard | `port_process` existing-policy hold assumption |
| `kenha.compliance_pct_fy2425` | 98.43 | % | published | FY 2024/25 | KeNHA Annual Report 2025 | `rcs_v2` overload_prob (1 − compliance), About page |
| `kenha.network_km_fy2425` | 10,776 | km | published | FY 2024/25 | KeNHA Annual Report 2025 | About page |
| `kenha.weighbridge_stations` | 13 | stations | published | FY 2024/25 | KeNHA Annual Report 2025 | About page |
| `kenha.mariakani_compliance_pct` | 98.5 | % | published | 2026 (KeNHA statement) | The Star; Streamline Feed | `rcs_v2` overload_prob |
| `kenha.mariakani_trucks_per_day` | 8,000 (more than) | trucks/day | published | 2026 (KeNHA statement) | The Star | `rcs_v2` trucks_per_day, `port_process` trucks_per_day, station model arrivals |
| `kenha.dongo_kundu_compliance_pct` | 98.5 | % | published | 2024 | KeNHA, via KBC | — |
| `ncttca.mariakani_daily_weighed_2016_17` | 2,162 – 5,312 | trucks/day | published | Oct 2016 – Mar 2017 | NC Transport Observatory report issue 10, figure 19 | historical comparator |
| `ncttca.mariakani_compliance_2016_17` | 96 – 99 | % | published | Oct 2016 – Mar 2017 | NC Transport Observatory issue 10, figure 20 | historical comparator |
| `ncttca.weighbridge_share_of_stoppages_2017` | 13.4 | % of stoppages | published | 2017 | NC Transport Observatory issue 10 | proposal (benefit framing) |
| `ncttca.port_dwell_h_mar2017` | 70 | hours (target 72) | published | Mar 2017 | NC Transport Observatory issue 10 | historical comparator |
| `ncttca.mombasa_malaba_transit_h_2019` | 53 – 72 | hours | published | 2019 (quarterly) | NC quarterly dashboard Oct–Dec 2019 | `port_process` inland transit sanity check |
| `ncttca.mombasa_malaba_transit_h_2022` | 77 | hours (target 40) | published | 2022 | NC Transport Observatory 18th edition; NC Strategic Plan 2022–2026 | `port_process` inland transit sanity check |
| `ncttca.mombasa_nairobi_transit_h_2017` | 110 – 163 | hours | published | Feb–Mar 2017 (RECTS) | NC Transport Observatory issue 10, figure 27 | historical comparator |
| `ncttca.corridor_compliance_pct_2021` | 94 | % | published | Jul–Sep 2021 | NC quarterly dashboard Jul–Sep 2021 | historical comparator |
| `kentrade.agencies_connected` | 22 – 30 | agencies | published | 2015–2017 | KenTrade / WTO TFA brief; TradeMark Africa | About page (agency table) |
| `kentrade.document_reduction_pct` | 30 – 50 | % | published | 2017 | KenTrade | About page |
| `scea.permit_agencies` | 26 | agencies | published | 2024 | SCEA | About page |
| `eac.overload_fee_5000kg_usd` | 2,990 | USD | published | 2021–2030 fee table | EAC VLC (Enforcement Measures) Regulations 2018, as reported in the RCS v2 plan | `limits.py` fee anchor |
| `platform.lane_capacity_per_hour` | 370 | trucks/h | estimated | — | RCS v2 plan arithmetic (10 km/h, 27 m headway) | `rcs_v2` lane capacity |
| `platform.port_node_error_pct` | 1.0 | % | estimated | — | RCS v2 plan | `rcs_v2` port_error_pct |
| `sim.static_service_min` | 4 | min | estimated | — | SimPy station model assumption | station model `static_service_median_s` |
| `sim.port_gate_service_existing_s` | 240 | s | estimated | — | SmartPort simulation assumption | `port_process` existing policy |
| `sim.port_gate_service_smart_s` | 60 | s | estimated | — | SmartPort simulation assumption | `port_process` smartport policy |

## 2b. Current primary figures — NCTTCA Observatory 21st edition (data year 2025) and quarterly report July–September 2026

All entries below are **published** (primary source: Northern Corridor Transit and Transport Coordination Authority).
Source (A) = 21st Edition Northern Corridor Transport Observatory Report, April 2026, data year 2025. Source (B) =
Quarterly Performance Report July–September 2026, October 2026.

### Port of Mombasa

| Key | Value | Unit | Period | Source | Used by |
|---|---|---|---|---|---|
| `ncttca.mombasa_throughput_mt_2025` | 45.45 (+10.9 %) | million tonnes | 2025 | A | About page, proposal |
| `ncttca.mombasa_imports_mt_2025` | 36.03 | million tonnes | 2025 | A | proposal |
| `ncttca.mombasa_exports_mt_2025` | 5.03 | million tonnes | 2025 | A | proposal |
| `ncttca.mombasa_transit_mt_2025` | 15.88 | million tonnes | 2025 | A | proposal (transit share) |
| `ncttca.mombasa_teu_2025` | 2.11 million (over 35 % empty) | TEU | 2025 | A | About page |
| `ncttca.sgr_cargo_mt_2025` | 7.43 | million tonnes | 2025 | A | proposal (rail share) |
| `ncttca.import_container_dwell_h_2025` | 106.7 (target 48) | hours | 2025 | A | `/port` KPI benchmark (container dwell, not truck turnaround) |
| `ncttca.customs_release_h_2025` | 57 | hours | 2025 | A | `/port` stage 2 benchmark |
| `ncttca.after_release_h_2025` | 79 | hours | 2025 | A | `/port` stages 3–9 benchmark |
| `ncttca.vessel_turnaround_h_2025` | 192 | hours | 2025 | A | About page |
| `ncttca.vessel_waiting_days_2025` | 4.7 (target 0.3) | days | 2025 | A | About page |
| `ncttca.icdn_teu_2025` | 311,647 | TEU | 2025 | A | proposal |
| `ncttca.icdn_dwell_days_2025` | 3.4 (target 4.4) | days | 2025 | A | `/port` KPI benchmark (inland depot) |
| `ncttca.import_container_dwell_h_q3_2026` | 87 (83 in Q3 2025; target 60) | hours | Jul–Sep 2026 | B | `/port` KPI benchmark |
| `ncttca.vessel_turnaround_h_q3_2026` | 107 (83 in H1 2026; target 76) | hours | Jul–Sep 2026 | B | About page |
| `ncttca.vessel_waiting_h_q3_2026` | about 54 (46 in H1 2026; target 12) | hours | Jul–Sep 2026 | B | About page |

KPA initiatives reported for 2026 (B): smart gates at Gates 23 and 24, terminal operating system upgrade, an empty
container yard, the Maritime Single Window and a new vessel traffic management information system. These are the
systems a port gate-out weigh node would sit beside.

### Weighbridges

| Key | Value | Unit | Period | Source | Used by |
|---|---|---|---|---|---|
| `ncttca.weighbridge_crossing_min_2025` | about 4 (normal 5–10) | minutes | 2025 | A | `sim.stop_minutes` context; station model service time |
| `ncttca.mariakani_crossing_min_2025` | 29 (road works) | minutes | 2025 | A | `sim.stop_minutes` upper context |
| `ncttca.webuye_crossing_min_2025` | 11 | minutes | 2025 | A | — |
| `ncttca.mariakani_daily_weighed_h2_2025` | 2,695 / 2,501 / 2,720 / 2,965 / 3,864 / 3,512 (Jul–Dec, peak Nov) | trucks/day | Jul–Dec 2025 | A | station model arrivals (2025 level) |
| `ncttca.athi_river_daily_weighed_2025` | 2,055 – 2,946 (high 3,665 in Feb) | trucks/day | 2025 | A | station model arrivals |
| `ncttca.gilgil_daily_weighed_2025` | 760 – 1,392 | trucks/day | 2025 | A | station model arrivals |
| `ncttca.webuye_daily_weighed_2025` | 988 – 2,794 | trucks/day | 2025 | A | — |
| `ncttca.mariakani_compliance_jan_jul_2025` | 98.49 / 98.64 / 97.32 / 98.03 / 96.43 / 97.73 / 95.76 | % by month | Jan–Jul 2025 | A | `rcs_v2` overload_prob (1 − compliance) |
| `ncttca.corridor_compliance_2025` | above 95 | % | 2025 | A | `rcs_v2` overload_prob |
| `ncttca.mariakani_daily_weighed_q3_2026` | 9,066 / 9,184 / 7,954 (Jul / Aug / Sep) | trucks/day | Jul–Sep 2026 | B | `rcs_v2` trucks_per_day and `port_process` trucks_per_day (8,000/day) |
| `ncttca.gilgil_daily_weighed_q3_2026` | 2,435 / 2,661 / 1,706 | trucks/day | Jul–Sep 2026 | B | station model arrivals |
| `ncttca.busia_daily_weighed_q3_2026` | 2,703 / 2,439 / 2,598 | trucks/day | Jul–Sep 2026 | B | — |
| `ncttca.webuye_daily_weighed_q3_2026` | 2,241 / 2,207 / 2,005 | trucks/day | Jul–Sep 2026 | B | — |
| `ncttca.mariakani_compliance_q3_2026` | 99.87 / 99.23 / 99.08 | % by month | Jul–Sep 2026 | B | `rcs_v2` overload_prob |
| `ncttca.gilgil_compliance_q3_2026` | 98.56 / 99.01 / 98.67 | % by month | Jul–Sep 2026 | B | — |
| `ncttca.busia_compliance_q3_2026` | 97.78 / 97.84 / 98.34 | % by month | Jul–Sep 2026 | B | — |
| `ncttca.webuye_compliance_q3_2026` | 98.56 / 99.47 / 98.01 | % by month | Jul–Sep 2026 | B | — |

Reading the Mariakani traffic: the 2025 Observatory months run near 2,500–3,900 trucks a day, while the July–September
2026 quarterly report shows 7,954–9,184 a day. The platform's 8,000 trucks a day assumption therefore matches the 2026
level; a simulation of 2025 conditions should use about 3,000 a day. The 2026 compliance of 99.1–99.9 % at Mariakani
implies a lower overloaded share (0.1–0.9 %) than the 1.5 % used in the chain model, which is conservative.

### Transit times and transport rates

| Key | Value | Unit | Period | Source | Used by |
|---|---|---|---|---|---|
| `ncttca.mombasa_nairobi_transit_h_2025` | 66 over 482 km (target 29; variance 37) | hours | 2025 (RECTS) | A | `port_process` inland transit sanity check; `/port` stage 10 benchmark |
| `ncttca.mombasa_malaba_transit_h_2025` | 67 by GPS / 89 by RECTS (target 55) | hours | 2025 | A | `/port` stage 10 benchmark |
| `ncttca.mombasa_busia_transit_h_2025` | 49 by GPS / 76 by RECTS | hours | 2025 | A | — |
| `ncttca.nairobi_malaba_transit_h_2025` | 73 | hours | 2025 | A | — |
| `ncttca.malaba_border_crossing_min_2025` | 48 | minutes | 2025 | A | — |
| `ncttca.busia_border_crossing_h_2025` | 2.55 | hours | 2025 | A | — |
| `ncttca.mombasa_malaba_transit_h_q3_2026` | 94 (target 55; about 4 h delay per 100 km) | hours | Jul–Sep 2026 | B | `/port` stage 10 benchmark |
| `ncttca.mombasa_busia_transit_h_q3_2026` | 79 | hours | Jul–Sep 2026 | B | — |
| `ncttca.mombasa_kampala_transit_h_q3_2026` | 116 over 1,169 km | hours | Jul–Sep 2026 | B | — |
| `ncttca.road_rate_mombasa_nairobi_usd_2025` | 860 per truck (1.79 USD/km) | USD | 2025 | A | proposal (cost of delay framing) |
| `ncttca.road_rate_nairobi_mombasa_backhaul_usd_2025` | 600 per truck (1.25 USD/km) | USD | 2025 | A | backhaul marketplace pricing context |
| `ncttca.corridor_road_rate_usd_per_km_2025` | 1.8 – 2.4 | USD/km | 2025 | A | backhaul marketplace pricing context |

## 3. Sources

| Source | URL |
|---|---|
| (A) NCTTCA — 21st Edition Northern Corridor Transport Observatory Report, April 2026 (data year 2025) | https://top.ttcanc.org/uploads/attachments/cmownhhl201qpfmqhl5ikzprd-en-21-top-report.pdf |
| (B) NCTTCA — Quarterly Performance Report, July–September 2026 (October 2026) | https://top.ttcanc.org/uploads/attachments/cmvo7m7gv00qfwznu9zlgz9zh-quarterly-report-july-to-september-2026.pdf |
| NCTTCA — 20th Edition Observatory Report, April 2025 (data year 2024) | https://top.ttcanc.org/uploads/attachments/cmc8ygxa41ro3m9oad2oqch1w-en-20th-edition-northern-corridor-transport-observatory-report.pdf |
| NCTTCA — 19th Edition Observatory Report, June 2024 (data year 2023) | https://top.ttcanc.org/uploads/attachments/clzax0v8l054e0ipnu3qrjw35-19th-top-design-english-final.pdf |
| NCTTCA — Biannual Report January–June 2026 | https://top.ttcanc.org/uploads/attachments/cmspuxn6h0de8hfnu9smo4ulg-biannual-report-jan-to-jun-2026.pdf |
| NCTTCA — document library (all editions and dashboards) | https://top.ttcanc.org/documents |
| Business Daily — Mombasa port container traffic hits a record in 2024 | https://www.businessdailyafrica.com/bd/corporate/companies/mombasa-port-container-traffic-hits-a-record-in-2024-4884082 |
| Kenya News Agency — Mombasa Port records 14 percent surge in cargo throughput | https://www.kenyanews.go.ke/mombasa-port-records-14-percent-surge-in-cargo-throughput/ |
| The Star — Transshipment volumes at Mombasa port more than double (KPA bulletin 2024 ship figures) | https://www.the-star.co.ke/business/2025-05-30-transshipment-volumes-at-mombasa-port-more-than-double |
| Kenya News Agency — Port of Mombasa buoyant in the face of global maritime upheaval (2023 truck turnaround, dwell) | https://www.kenyanews.go.ke/port-of-mombasa-buoyant-in-the-face-of-global-maritime-upheaval/ |
| SCEA — Achievements and challenges | https://shipperscouncilea.org/about-scea/achievements-challenges/ |
| SCEA — Permit delays, high turn-around time costs shippers Sh1.2bn | https://shipperscouncilea.org/2024/07/04/permit-delays-high-turn-around-time-costs-shippers-sh1-2bn/ |
| The Standard — Transporters decry delays at Mombasa port (gate scanning, Aug 2025) | https://www.standardmedia.co.ke/business/2001527935/transporters-decry-over-delays-at-mombasa-port |
| KeNHA Annual Report 2025 (FY 2024/25) | https://kenha.co.ke/wp-content/uploads/2026/06/KeNHA-ANNUAL-REPORT-2025-WEB-VERSION.pdf |
| The Star — KeNHA, Judiciary unite to boost axle-load compliance (Mariakani 98.5 %, 8,000 trucks/day) | https://www.the-star.co.ke/news/2026-06-30-kenha-judiciary-unite-to-boost-axle-load-compliance |
| Streamline Feed — High-speed sensors push Mariakani weighbridge to 98.5 percent compliance | https://streamlinefeed.co.ke/news/high-speed-sensors-push-mariakani-weighbridge-to-98-5-percent-axle-load-compliance-rate |
| KBC — KeNHA intensifies crackdown on overloaded trucks (Dongo Kundu) | https://www.kbc.co.ke/kenha-intensifies-crackdown-on-overloaded-trucks/ |
| Northern Corridor Transport Observatory report, issue 10 (Oct 2016 – Mar 2017) | https://top.ttcanc.org/uploads/attachments/clf9hbzdu5c880iqxm7ddfc1g-top-report-issue10-english.pdf |
| Northern Corridor Transport Observatory annual report 2022, 18th edition | https://top.ttcanc.org/uploads/attachments/clkawgz074em10irl1z7owszt-18-top-report-2022-en.pdf |
| Northern Corridor quarterly performance dashboard, Oct–Dec 2019 | https://top.ttcanc.org/uploads/attachments/cl1utgsgc01gr0jqxzv5nr8ip-quarterly-northern-corridor-performance-report-for-october-december-2019.pdf |
| Northern Corridor quarterly performance dashboard, Jul–Sep 2021 | https://top.ttcanc.org/uploads/attachments/cl1uuindc01y00jqxxdgzcs1c-quarterly-northern-corridor-performance-report-for-july-sept-2021.pdf |
| Northern Corridor Strategic Plan 2022–2026 | https://www.ttcanc.org/sites/default/files/2023-12/StrategicPlan_20220617_EN.pdf |
| KenTrade — Kenya National Electronic Single Window brief (WTO TFA facility, 2017) | https://www.tfafacility.org/sites/default/files/2022-01/2017_-_kenya_knesw_wto.pdf |
| TradeMark Africa — Implementation of single window in Kenya (TradeNet) | https://trademarkafrica.com/news/implementation-of-single-window-in-kenya-kenya-tradenet |
| KenTrade — Single Window System | https://kentrade.go.ke/single-window-system |

Refresh schedule: the 20th and 19th editions and the biannual January–June 2026 report are listed above for the
2023–2024 series and the first half of 2026; the quarterly reports should be checked each quarter at the document
library. Still to obtain: KPA Annual Review and Bulletin of Statistics 2024 and 2025 (truck turnaround and container
dwell for 2024 and 2025 by KPA's own definitions); Mombasa Port and Northern Corridor Community Charter dashboard
indicators (mpnccc.go.ke, not reachable at the time of writing).

## 4. Data required for simulation (SmartPort document)

| Data category | Information required | Purpose in simulation | Platform source |
|---|---|---|---|
| Truck and arrival data | Truck ID, vehicle type, cargo ID, arrival time, trucks arriving per hour | Arrival patterns and traffic flow | `PortVisit` stages 1 and 3; `kenha.mariakani_trucks_per_day` |
| Queue and waiting-time data | Queue length, number waiting, waiting duration | Congestion and delays at processing points | `PortVisit.queue_length` / `queue_wait_s`; `core.queue_records` |
| Weighbridge data | Weighbridge ID, weighing start and end times, gross, tare and net weight | Weighing duration and capacity | `WeighingEvent`, `PortVisit` stage 7 |
| Cargo handling data | Cargo type, container ID, loading start and end times, equipment used | Cargo handling efficiency | `PortVisit` stage 6 |
| Clearance and documentation data | Customs, inspection and approval status, clearance duration | Delays from documentation and regulation | `PortVisit` stages 2 and 8 |
| Gate operations data | Gate-in time, gate-out time, gate ID, verification status | Processing time and port dwell time | `PortVisit` stages 4 and 9 |
| Inland transportation data | Destination, departure and arrival times, route, travel duration | Movement from the port to mainland destinations | `PortVisit` stages 10 and 11; telematics |

### Data collection format (illustrative examples from the SmartPort document, not operational records)

| Truck ID | Arrival time | Queue waiting time (min) |
|---|---|---|
| T001 | 08:00 | 15 |
| T002 | 08:05 | 20 |
| T003 | 08:10 | 25 |

| Truck ID | Weighing start | Weighing end | Duration (min) |
|---|---|---|---|
| T001 | 08:20 | 08:25 | 5 |
| T002 | 08:26 | 08:32 | 6 |
| T003 | 08:33 | 08:38 | 5 |

| Truck ID | Cargo type | Loading duration (min) |
|---|---|---|
| T001 | Container | 20 |
| T002 | Container | 25 |
| T003 | Bulk cargo | 30 |

The platform's `GET /port/visits` returns these columns per visit so the same tables can be exported from recorded
(live, replay or simulated) visits.

### Key simulation parameters

| Parameter | Unit | Purpose | `port_process` field | Default and provenance |
|---|---|---|---|---|
| Truck arrival rate | trucks/hour | Rate at which trucks enter the system | `trucks_per_day` / 24 with peak factor | 8,000/day (`kenha.mariakani_trucks_per_day`, published), peak 1.5 (estimated) |
| Average waiting time | minutes | Delays experienced by trucks | output `avg_wait_min` | simulated |
| Number of processing gates | number | Gate processing capacity | `gates_in`, `gates_out` | 4 (estimated) |
| Number of weighbridges | number | Weighing capacity | `weighbridges` | 2 (estimated) |
| Average weighing time | minutes/truck | Weighing service duration | `weigh_service_existing_s` 300, `weigh_service_smart_s` 90 | estimated (SmartPort illustrative table: 5–6 min) |
| Average cargo loading time | minutes/truck | Cargo handling duration | `loading_minutes_container` 20, `_bulk` 30, `_general` 25 | estimated (SmartPort illustrative table) |
| Average clearance time | minutes/truck | Documentation and approval duration | `clearance_minutes` 15, `hold_prob_existing` 0.15, `hold_minutes` 45 | estimated |
| Total port dwell time | hours | Time a truck spends within the port | output `avg_dwell_h` | simulated; calibration target `kpa.truck_turnaround_h_2023` = 6.7 h (published) |

### Proposed simulation scenarios

| Scenario | Description | Expected result | `port_process` policy |
|---|---|---|---|
| Existing port operations | Current truck processing, weighing, cargo handling and clearance | Baseline efficiency and delays | `existing` (manual gate checks, static weighing, 15 % document holds, no appointment smoothing) |
| Proposed SmartPort system | Automated identification, automated weighing, digital information sharing, queue monitoring | Reductions in waiting time, congestion and processing delays | `smartport` (RFID/ANPR gate, port gate-out node with token, pre-cleared documents, appointment smoothing) |

### Key performance indicators

| Indicator | Measurement | Platform |
|---|---|---|
| Average truck waiting time | Average time spent in queues | `PortKpisOut.avg_queue_wait_s`; `port_process` `avg_wait_min` |
| Average queue length | Trucks waiting at a processing point | `port_process` `avg_queue_len` / `max_queue_len`; `core.queue_records` |
| Truck processing time | Total time to complete port processing | `port_process` `avg_processing_min` |
| Weighbridge service time | Time to weigh one truck | `PortKpisOut.avg_weighing_service_s`; `port_process` `weigh_service_min` |
| Truck throughput | Trucks processed per period | `PortKpisOut.throughput_per_hour`; `port_process` `throughput_per_hour` |
| Port dwell time | Time a truck spends inside the port | `PortKpisOut.avg_dwell_time_s` / `p90_dwell_time_s`; `port_process` `avg_dwell_h` / `p90_dwell_h` |

All `port_process` outputs are modelled and labelled `MODELLED`; the published benchmarks shown beside them are not
measurements of the platform.

## 5. Data sources and classification

| Data type | Possible source | Classification today |
|---|---|---|
| Port arrival, gate and cargo handling records | Kenya Ports Authority (KPA) | not obtained (would be `actual`); KPA bulletin figures `published` |
| Customs clearance records | Kenya Revenue Authority (KRA) | not obtained |
| Electronic trade documentation and approvals | KenTrade | `published` (2017 single-window figures) |
| Road and axle-load information | KeNHA | `published` (Annual Report 2025, station statements) |
| Truck movement and GPS records | Transport companies and fleet operators | not obtained; `simulated` positions in the demo |
| Published port performance statistics | Official port and transport reports | `published` (NCTTCA Observatory 21st edition and Q3 2026 report as primary; KPA bulletins, SCEA) |

Where actual operational records are unavailable, clearly labelled estimates are used for preliminary modelling and
validated where possible. The data requests to obtain `actual` records are in `rcs-v2-port-anchored-clearance.md`
(appendix: data requests) and follow the Data Protection Act, 2019 (plates and driver details anonymised).
