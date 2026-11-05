# KIFARU PORTOS — Requirements Traceability Matrix (RTM)

Legend — **Disp.**: P = Preserve (from original RCS), E = Enhance, R = Replace, N = New.
**Phase**: implementation phase per `docs/02-architecture/roadmap.md`. **Status**: Planned / In progress / Done / Blocked (reason).
Source "MP §n" = Master Prompt section n. "RCS" = original Rolling Clearance System concept (reconstructed, see `00-source-review.md`).

## A. Core rolling clearance (original concept)

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance criteria | Status |
|---|---|---|---|---|---|---|---|
| RCS-01 | Identify approaching trucks automatically (ANPR + RFID) | RCS; MP §2 | P | 2 (sim), 6 (hw) | `kifaru/identity`, `ai_agents/vehicle_identity` | Identity event with plate, RFID, confidence produced for every lane pass | Done (simulated identity; hardware Phase 6) |
| RCS-02 | Measure axle loads and GVM while moving | RCS; MP §2, M1 | E | 2 (sim), 6 (hw) | `packages/wim_dsp`, firmware | Axle loads, spacing, speed, GVM, uncertainty produced per pass | Done (simulated signals through DSP; hardware Phase 6) |
| RCS-03 | Evaluate measurement confidence and compliance | MP §2, M2 | E | 2 | `kifaru/clearance` | Every decision carries expanded uncertainty U (k=2) and quality flags | Done |
| RCS-04 | Clear eligible trucks without stops (GREEN) | RCS; MP §2 | P | 2 | `kifaru/clearance` | GREEN only when GVM+U and each axle-group+U are within legal limit, identity above threshold, sensors healthy, not watch-listed, not audit-sampled | Done |
| RCS-05 | Direct uncertain trucks to static verification (AMBER) | RCS; MP §2 | P | 2 | `kifaru/clearance` | AMBER when limits within margin, identity low, or quality degraded | Done |
| RCS-06 | Flag suspected non-compliance (RED) | RCS; MP §2 | P | 2 | `kifaru/clearance` | RED when measured minus U still exceeds limit, or watch-list / seal / declaration mismatch | Done |
| RCS-07 | Static weighing remains legal authority | RCS; MP §3 M2 | P | all | policy + `clearance` | No API path issues a legally binding certificate from WIM alone; ticket type `prescreen` vs `static_certified` | Done |
| RCS-08 | Complete evidence record per decision | MP §3 M2 | E | 2 | `kifaru/clearance`, `kifaru/ledger` | Decision row links weighing event, identity, rules fired, thresholds, sensor health, signed hash | Done |
| RCS-09 | Never auto-clear when quality insufficient | MP §3 M2 | E | 2 | `kifaru/clearance` | Unit test: any quality flag means not GREEN | Done (tested) |
| RCS-10 | Random audit selection | MP §3 M2 | N | 2 | `kifaru/clearance` | Configurable audit rate; selection logged with seed | Done |
| RCS-11 | Digital weighing ticket | RCS; MP §3 M5 | E | 2 | `kifaru/tickets` | Signed JSON + QR; verifiable via public endpoint | Done |
## B. Module 1 — WIM infrastructure

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance criteria | Status |
|---|---|---|---|---|---|---|---|
| WIM-01 | Multi-sensor lane: piezo, bending plate/strain gauge, loops, radar, IR, ANPR, RFID, pavement temp, ambient T/RH, axle/wheel detectors | MP M1 | R | 6 | `docs/03-hardware`, firmware | Sensor architecture doc + BOM; firmware channel map | Designed (docs/03-hardware/sensor-architecture.md, bom.md); hardware not built |
| WIM-02 | 5–10 kHz/channel acquisition, anti-alias, 24-bit ADC | MP M1 | R | 6 | firmware `stm32-wim-daq` | ADS131M08 at 8 kSPS/ch verified on bench | Designed (ADS131M08 at 8 kSPS; firmware acq task written, not compiled — no toolchain) |
| WIM-03 | No HX711 on highway lane | MP M1 | R | 6 | hardware doc | BOM excludes HX711 for lane; allowed only on lab aux | Done (HX711 excluded in BOM; lab rig only) |
| WIM-04 | Charge amplifier for piezo-quartz | MP M1 | N | 6 | `docs/03-hardware/analog-front-end.md` | LTspice sim + bench noise floor | Designed (charge amplifier derivation, LTspice netlist; not simulated here) |
| WIM-05 | DSP: axle detection, spacing, speed, GVM, classification, temperature and dynamic compensation, uncertainty, sensor health | MP M1 | E | 2 (python), 6 (fw) | `packages/wim_dsp` | Unit tests on synthetic + recorded signals; error vs reference reported | Done (Python reference, 24 tests) |
| WIM-06 | STM32 primary, ESP32 auxiliary | MP M1 | N | 6 | firmware | Build passes; HIL test | Written (STM32H743 FreeRTOS firmware + ESP32 aux; not compiled — no toolchain) |
| WIM-07 | Sensor health monitoring | MP M1 | N | 2/6 | `wim_dsp.health`, `kifaru/stations` | Health states OK/DEGRADED/FAULT with reasons | Done (health flags + sensor status API) |
## C. Module 3 — Traffic and queue intelligence

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| TRQ-01 | Forecast arrivals, queue length, utilisation, processing time at 15/30/60/120 min | MP M3 | N | 4 | `ai_agents/traffic_forecast` | Forecast endpoint returns 4 horizons with intervals; backtest MAE reported | Done (HGB/Holt/persistence by data volume; backtest on real data pending) |
| TRQ-02 | Dynamic weighing-slot allocation | MP M3 | N | 3 | `kifaru/queue` | Slot assigned to appointment; conflicts rejected | Done |
| TRQ-03 | Recommend authorised alternative stations | MP M3 | N | 4 | `ai_agents/queue_optimizer` | Only stations flagged `alt_allowed` recommended | Done (agent; alt_allowed enforced) |
| TRQ-04 | Notify transporters/dispatchers of slot and wait | MP M3 | N | 3 | `kifaru/notifications` | Notification record + WS push + SMS adapter | Done (WS + inbox; SMS adapter mock) |
## D. Module 4 — Backhaul

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| BKH-01 | Identify empty trucks / completing deliveries / return cargo | MP M4 | N | 4 | `kifaru/backhaul` | Query returns candidate trucks with capacity and location | Done |
| BKH-02 | Matching optimisation (payload, dims, type, compatibility, destination, extra km, deadline, fuel, driver hours, revenue) | MP M4 | N | 4 | `ai_agents/backhaul_matcher` | Deterministic score with explanation; unit tests | Done (tested) |
| BKH-03 | Offer, match, accept/reject, assign, track | MP M4 | N | 4 | `kifaru/backhaul` | State machine enforced in API | Done |
| BKH-04 | No automatic commercial assignment without user approval | MP M4 | N | 4 | `kifaru/backhaul` | Assignment requires acceptance by both parties | Done (tested) |
| BKH-05 | Report extra km, fuel cost, revenue, emissions avoided | MP M4 | N | 4 | `kifaru/backhaul`, `environment` | Fields present with formula reference | Done |
## E. Module 5 — Digital cargo passport

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| DCP-01 | Unique shipment identity linking truck, trailer, container, RFID, declaration, seal, VGM, weighings, tickets, status, history | MP M5 | N | 2 | `kifaru/shipments` | Passport endpoint aggregates all links | Done |
| DCP-02 | QR verification | MP M5 | N | 2 | `kifaru/tickets` | Public verify endpoint validates signature | Done (public verify + QR) |
| DCP-03 | Signed, tamper-evident event ledger (no blockchain) | MP M5 | N | 2 | `kifaru/ledger` | Hash-chained events; chain verification endpoint | Done (chain verify endpoint, tested) |
## F. Module 6 — Predictive release

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| PRL-01 | Predict processing/release time with confidence range and reasons | MP M6 | N | 4 | `ai_agents/release_predictor` | Prediction with P10/P50/P90 and stage reasons | Done (priors; learns from platform history) |
| PRL-02 | No claim of government data without authorised integration | MP M6 | N | all | adapters | All government adapters default to `mode=mock` and label output | Done (adapters mock by default) |
## G. Module 7 — Small cargo owner

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| SCO-01 | Mobile-first register/track/notify | MP M7 | N | 3 | `apps/web` (PWA), `apps/mobile` | Lighthouse mobile pass; PWA installable | Done (PWA web app mobile-first owner view; Flutter app written, not compiled) |
| SCO-02 | Low-bandwidth, SMS/USSD-compatible notifications | MP M7 | N | 3 | `kifaru/notifications` SMS adapter | 160-char templates; USSD menu spec | Designed (SMS templates ≤160 chars, USSD menu spec; SMS adapter mock) |
## H. Module 8 — Environmental

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| ENV-01 | Estimate idling fuel, empty km, detours, queue emissions, savings, CO2 | MP M8 | N | 4 | `kifaru/environment` | Formulas and factors in `docs/.../emissions-model.md`; outputs labelled *modelled* | Done (labelled modelled) |
## I. Module 9 — Multi-agent AI

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| AGT-01 | Ten agents + orchestrator with responsibilities, I/O, API, confidence, errors, logging, tests, explainability | MP M9 | N | 4 | `packages/ai_agents` | Each agent implements the `Agent` protocol; orchestrator runs pipeline; tests | Done (10 agents + orchestrator, tests) |
| AGT-02 | AI never overrides deterministic legal/safety rules | MP M9 | N | 2 | `kifaru/clearance` | Agent outputs are advisory inputs; rule engine is final | Done (engine is rule-based) |
## J. Cloud, real-time, integrations

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| CLD-01 | Provider evaluation and selection documented | MP §4 | N | 1 | `docs/02-architecture/cloud-architecture.md` | Done in this phase | Done |
| CLD-02 | Terraform for dev/staging/prod; ECS Fargate, RDS, Redis, IoT Core, S3, CloudFront, Route53, ACM, CloudWatch, Secrets, WAF, SQS | MP §4 | N | 2 | `infra/terraform` | `terraform validate` passes; plan documented | Done (12 Terraform modules, 3 env roots + bootstrap; fmt and validate pass; no apply without owner AWS account) |
| CLD-03 | Actual deployment verified | MP §4 | N | 2 | — | **Blocked: requires owner's AWS account credentials** | Blocked: requires owner's AWS account; deployment guide ready |
| CLD-04 | Edge store-and-forward during outage | MP §4 | N | 3/6 | `edge/gateway` | Outage test: no event loss | Done in software (edge/gateway SQLite outbox: 22 tests incl. outage replay, no duplicates); field test Phase 6 |
| CLD-05 | Docker + CI/CD (GitHub Actions) | MP §4 | N | 2 | `infra/docker`, `.github` | CI green on push | Done (Dockerfiles, Compose, GitHub Actions ci.yml + deploy.yml with OIDC; images not built locally — no Docker) |
| RTC-01 | MQTT (devices), WebSocket (dashboards), REST, queue, webhooks, Redis | MP §5 | N | 2/3 | `kifaru/realtime` | Dashboards update without refresh | Done (REST, WS, Redis fan-in/out, MQTT and SQS ingest workers) |
| RTC-02 | 13 event categories | MP §5 | N | 2 | `kifaru/events` | Enum + schema per event | Done |
| INT-01 | Adapters: KeNHA, KPA, KRA, NTSA, customs, fleet mgmt, WMS, payments, SMS/email, maps, telematics — mock by default | MP §5 | N | 5 | `kifaru/integrations` | Adapter interface; health endpoint; no fabricated endpoints | Done (12 adapters registered, mock by default, mode switch + health endpoint; no real endpoints fabricated) |
## K. Applications, database, twin, hardware, security, testing, docs

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance | Status |
|---|---|---|---|---|---|---|---|
| APP-01..07 | Port control, weighbridge operator, transporter, driver, cargo owner, warehouse, admin dashboards — all wired to real APIs | MP §7 | N | 2–5 | `apps/web` | No decorative controls; every action hits an API | Done (React app, 7 role routes wired to API, build passes, smoke-tested); no browser screenshot verification |
| APP-08 | Driver app: no phone interaction while driving (voice/large-tile, auto-advance) | MP §7 | N | 3 | `apps/mobile` | UX review checklist | Done (web driver view + Flutter driver mode: no controls while driving, TTS, auto-update) |
| DB-01 | Normalised schema for all 30 listed entities, PII separated, indexes, migrations, retention | MP §8 | N | 2 | `apps/api/alembic`, `docs/.../database-erd.md` | Alembic upgrade head clean; PII in `pii` schema | Done (Alembic 0001 verified up/down on SQLite; PostgreSQL run pending) |
| DT-01 | Three.js port twin bound to live events; simulation-mode banner | MP §9 | N | 5 | `apps/web/twin` | Banner when source is not live | Done (Three.js twin bound to live events; SIMULATION MODE banner unless source=live) |
| DT-02 | SimPy/SUMO scenarios (+20/30/50 %, failure, inspection rate, capacity, release delay, slot policies) with comparative reports | MP §9 | N | 5 | `packages/simulation` | CLI produces comparison table | Done (SimPy, 11 scenarios, comparison report with CIs; SUMO adapter degrades gracefully) |
| HW-01..15 | 15 hardware deliverables with real calculations; lab rig distinguished from certified equipment | MP §10 | N | 1 (arch), 6 (detail) | `docs/03-hardware` | Calculations reproducible | Designed (15 deliverables in docs/03-hardware with calculations; lab rig guide; not fabricated) |
| SEC-01 | RBAC, MFA (privileged), Argon2, TLS, encryption at rest, device certs, audit, rate limit, validation, sessions, backup encryption, retention, privacy-by-design, DPA 2019 | MP §11 | N | 2+ | `kifaru/auth`, docs | Threat model doc; tests | Done for Phase 2 (threat model, controls catalogue, DPIA, IR plan; PII encryption, key pinning, MFA enrolment, deployment guard); TLS/KMS/device certs in Terraform |
| TST-01 | Unit/integration/API/E2E/DB/load/security/fault/outage/sync/AI validation | MP §12 | N | 2+ | `apps/api/tests`, CI | CI matrix | Done for Phase 2–5 (61 API/security/worker, 24 DSP, 8 agent, 15 simulation, 22 gateway tests; migrations SQLite+PostgreSQL; web build; load harness); HIL/E2E-browser pending |
| TST-02 | Targets: latency 2 s, WIM ±5 % at 95 %, false-clear 1 %, identity 97 %, availability 99.9 %, stops −50 % — remain targets until measured | MP §12 | N | 7 | benchmarks | Reported with evidence only | Planned |
| DOC-01 | 42-section engineering report | MP §13 | N | 7 (draft from 1) | `docs/05-report` | All sections present | Done (draft: 42-section engineering report, docs/05-report) |

## L. RCS v2 — port-anchored clearance

Source "RCS v2 plan §n" = `docs/01-requirements/rcs-v2-port-anchored-clearance.md`. Contract: `docs/02-architecture/rcs-v2-api-contract.md`.
Phase "v2-n" refers to the RCS v2 roadmap in `docs/02-architecture/roadmap.md`. "Done (software, simulated)" means the behaviour exists in code and tests with simulated data only; nothing has been measured in the field.

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance criteria | Status |
|---|---|---|---|---|---|---|---|
| RCS2-01 | Three truck streams (port, industrial origin, untokened) carried on every weighing record | RCS v2 plan §4 | N | v2-2 | `WeighingEvent.stream`, `WeighingEvent.node_kind` | Every event carries a stream and node kind; `/rcs/stats` reports the mix | Done (software, simulated) |
| RCS2-02 | Load Compliance Token issued at the first verified weighing point (port gate-out, approved origin scale, first road station or verification lane) | RCS v2 plan §4, §6.2 | N | v2-2 | `LoadComplianceToken`, `services/tokens.py` | GREEN at an issuing node creates a signed token with the §6.2 fields; token source and tier recorded | Done (software, simulated) |
| RCS2-03 | Later stations honour a valid token and check only consistency (tolerance 8 % port/origin/lane, 11 % road); expired, suspended or mismatched tokens divert | RCS v2 plan §4, §6.4 | E | v2-2 | engine `clr-2.0.0` rules `TOKEN_*`, `TOKEN_COVERS_MARGIN` | Unit tests: consistent token downgrades possible-over rules; inconsistent token → AMBER; identity mismatch → RED; `honoured_count` increments | Done (software, simulated) |
| RCS2-04 | Trust tiers 1–4 with audit rates that follow risk (demerit points, origin record) | RCS v2 plan §4 | N | v2-2 | `Vehicle.trust_tier`, `Vehicle.demerit_points`, `audit_rate_by_tier`, `GET /rcs/trust-tiers` | Audit rate applied per tier in the engine; policy exposed by `/rcs/policy` | Done (software, simulated) |
| RCS2-05 | Origin weigh nodes: approved loading-site scale linked to the registry issues an origin token; on-board records never issue a token | RCS v2 plan §4 | N | v2-2 (software), v2-4 (field) | station kind `origin_site`, lane type `origin_scale`, `Lane.legal_grade` | Origin lane pass issues a tier-2 token; drift raises audit rate and can suspend tokens (`POST /rcs/tokens/{id}/suspend`) | Done (software, simulated); scale approval and audit Planned (Phase 0–2 of v2) |
| RCS2-06 | Port gate-out weigh node: low-speed weighing, plate/RFID/container OCR/e-seal, expected-weight comparison, token issue, port re-weigh route | RCS v2 plan §6.1 A, §6.3 | N | v2-2 (software), v2-4 (field) | station kind `port_gate`, lane type `port_gateout`, routes `port_reweigh`/`hold`, `docs/03-hardware/port-gateout-weigh-node.md` | Port lane pass computes expected GVM and variance, issues a tier-1 token on GREEN, routes AMBER to re-weigh | Done (software, simulated); KPA access Planned (Phase 0–2 of v2) |
| RCS2-07 | Rolling Verification Lane: doubtful trucks and audits measured at about 10 km/h without a stop; AMBER on the mainline routes to the lane, lane failure routes to the static scale | RCS v2 plan §5.1, §6.4 | N | v2-2 (software), v2-3/4 (hardware) | lane type `rolling_verification`, route `verification_lane`, `docs/03-hardware/rolling-verification-lane.md` | Route logic tested; lane pass issues a lane token on GREEN; SimPy lane resource with closure scenario | Done (software, simulated); lane not built |
| RCS2-08 | Dimensions (height, width, length), lifted axles and per-wheel balance captured and judged | RCS v2 plan §5 | N | v2-2 | `WeighingEvent.length_m/width_m/height_m/lifted_axle`, `AxleMeasurement.left_kg/right_kg`, rules `DIMENSION_OVER`, `LIFTED_AXLE`, sensor kinds `lidar_portal`, `light_curtain`, `side_lidar`, `wheel_load_cell` | Over-dimension without permit → RED; lifted axle → AMBER; simulator produces oversize and lifted-axle cases | Done (software, simulated) |
| RCS2-09 | Special-load permits linked to the vehicle and checked against measured dimensions | RCS v2 plan §5 | N | v2-2 | `SpecialLoadPermit`, `/rcs/permits`, rule `DIMENSION_PERMITTED` | Oversize within a valid permit → INFO, not RED; expired permit → RED | Done (software, simulated) |
| RCS2-10 | Digital release orders (Reg 14) kept for the journey, visible to every station, fee tripled on a repeat overload in the same journey | RCS v2 plan §3, §5 | N | v2-2 | `ReleaseOrder`, `services/release_orders.py`, `/rcs/release-orders` | Second order for the same vehicle within the journey window carries `repeat_offence=true`, `fee_multiplier=3` | Done (software, simulated) |
| RCS2-11 | Discretion allowance (< 5 % of allowed load) as a configurable policy applied to limits and shown on the record | RCS v2 plan §3 (Second Schedule), §9 | E | v2-2 | `LimitSet.discretion_allowance_pct`, rule `DISCRETION_ALLOWANCE`, `ReleaseOrder.allowance_kg` | Allowance changes `limit_with_tolerance_kg`; default 0 until KeNHA confirms | Done (software); policy value Planned (Phase 0–2 of v2) |
| RCS2-12 | Overload fee, detention and repeat multiplier computed from the Third Schedule configuration (indicative until the table is loaded) | RCS v2 plan §3 | N | v2-2 | `LimitSet.overload_fee`, `detention_free_days`, `detention_usd_per_day`, `repeat_offence_multiplier` | 5,000 kg over → about 2,990 USD; detention free 3 days then 50 USD/day; labelled indicative | Done (software, indicative table) |
| RCS2-13 | Officer e-signature for tickets and release orders of overloaded vehicles (Reg 3(4), 11(3)); the platform never issues a fee or legal certificate on its own | RCS v2 plan §5 | E | v2-2 | `POST /rcs/release-orders` (officer role, MFA), `ReleaseOrder.officer_signature`, `static_certified` tickets | Endpoint rejects non-officer and non-MFA sessions; signature bound to officer id | Done (software); remote e-sign legality Planned (Phase 0–2 of v2) |
| RCS2-14 | Transit cargo: confirmed overload alerts customs; detention until the seal is broken with the transporter present (Reg 18) | RCS v2 plan §2, §3 | N | v2-2 (software), v2-4 (integration) | `ReleaseOrder.transit`, `customs_notified`, `ElectronicSeal`, KRA adapter | Transit release order sets `customs_notified`; alert path to KRA remains mock | Done (software, simulated); KRA integration Planned (Phase 0–2 of v2) |
| RCS2-15 | Legal-grade flag per lane (Reg 5 approval) controlling whether near-limit lane readings still need the static scale | RCS v2 plan §5.1, §11 | N | v2-2 | `Lane.legal_grade`, chain model inputs `port_legal_grade`, `lane_legal_grade` | Flag false by default; model shows the effect on re-weigh share | Done (software); approval Planned (Phase 0–2 of v2) |
| RCS2-16 | Calibration register with quarterly accredited calibration (Reg 6) and annual audit (Reg 8); expired calibration blocks GREEN | RCS v2 plan §3, §7 | E | v2-2 | `CalibrationRecord`, `Lane.calibration_valid_to`, `QUALITY_BLOCKING` | Expired record → no GREEN (tested); 90-day validity to replace seeded 150-day demo values | Done (software); accredited calibrator Planned (Phase 0–2 of v2) |
| RCS2-17 | Registry statistics: stream mix, token coverage, routes (continue, lane, static, port re-weigh, hold) per station; web registry and model pages | RCS v2 plan §6.1, §9 | N | v2-2 | `GET /rcs/stats`, web `/registry`, `/model` | Stats endpoint returns per-station route shares; pages render tokens, release orders, permits, policy and the chain model | Done (software, simulated) |
| RCS2-18 | Whole-chain simulation for three truck streams: Monte Carlo chain model reproducing the §9 tables, SimPy `rcs_v2` policy with lane and tokens, experiments (30 reps, CRN, 95 % CIs, tornado) and go/no-go gate | RCS v2 plan §9, §10 | E | v2-2 | `kifaru_sim.rcs_v2`, `kifaru_sim.experiments`, SimPy policy `rcs_v2`, CLI `kifaru-sim v2`/`v2-sweep`/`v2-gate`, `POST /rcs/model` | Port-truck and mixed-traffic tables reproduced within Monte Carlo noise; gate evaluation prints PASS/FAIL; all outputs labelled modelled | Done (software, modelled); validation against measured baseline Planned (Phase 0–2 of v2) |
| RCS2-19 | Baseline data requests (KPA, KeNHA, KRA, NTSA, KTA), time-and-motion study, classification counts; legal opinion on Reg 10(2), Reg 5, Reg 3(4) and digital certificates | RCS v2 plan §8, §10.6, §11 | N | v2-0/1/2 | roadmap, `docs/06-operations/rcs-v2-simulation-plan.md` §6 | Data access agreed and legal route clear (exit gate of Phase 0–1) | Planned (Phase 0–2 of v2) |

## M. SmartPort port process and data

Source "SmartPort doc §n" = the SmartPort document supplied by the owner, documented in `docs/01-requirements/smartport-workflow-and-data.md`. Contract: `docs/02-architecture/smartport-port-process-contract.md`. Data register: `docs/06-operations/data-register.md`. "Done (software, simulated)" = the behaviour exists in code with simulated data; "Planned (field data)" = needs agency records or integration.

| ID | Requirement | Source | Disp. | Phase | Component | Acceptance criteria | Status |
|---|---|---|---|---|---|---|---|
| SPT-01 | One port visit record per truck collection trip carrying the eleven SmartPort stages in order (pre-registered … delivered) | SmartPort doc §3 workflow | N | v2-2 | `PortVisit`, `PORT_STAGES`, `GET/POST /port/visits` | Visit advances only in stage order; every stage change written as a `CargoProcessingEvent` and reflected in the shipment stage | Done (software, simulated) |
| SPT-02 | Per-stage data validation: each stage requires the fields of its SmartPort data table | SmartPort doc "Data required at each stage" | N | v2-2 | `POST /port/visits/{id}/advance`, `GET /port/stages` | Advance rejected (422) when a required field is missing; `outstanding` lists what is missing | Done (software, simulated) |
| SPT-03 | Pre-arrival registration and scheduling (truck, driver, cargo, container, destination, appointment, expected arrival) | SmartPort doc stage 1 | E | v2-2 | `POST /port/visits`, `core.appointments`, queue forecast | Visit created at stage 1 with an optional slot; ISO 6346 container check | Done (software, simulated) |
| SPT-04 | Gate-in and gate-out with gate IDs, authorisation, inspection and verification results; port dwell time computed as gate-out minus gate-in | SmartPort doc stages 4, 9 | N | v2-2 | `PortVisit.gate_in_*`, `gate_out_*`, `dwell_time_s` | `dwell_time_s` set on gate-out; KPIs expose mean and P90 | Done (software, simulated) |
| SPT-05 | Yard allocation and loading records (terminal, block, position, instruction, equipment, seal, condition, exceptions, durations) | SmartPort doc stages 5, 6 | N | v2-2 | `PortVisit.yard_*`, `loading_*`; seal copied to `ElectronicSeal` | Loading duration and yard wait derived from timestamps | Done (software, simulated) |
| SPT-06 | Stage 7 filled automatically from the port gate-out weigh node: gross, tare, net, declared, discrepancy, calibration status, token reference | SmartPort doc stage 7; RCS v2 §6.1 A | E | v2-2 | `weighing_service` → `PortVisit` (stage `weighed`), `Lane.type = port_gateout` | A pass on a port gate-out lane attaches to the vehicle's active visit and advances it; static scale remains legal proof | Done (software, simulated) |
| SPT-07 | Final clearance and gate pass (release status, delivery order, gate pass number, payment status, exceptions) | SmartPort doc stage 8 | N | v2-2 | `PortVisit.final_*`, `gate_pass_no` | Gate-out refused without a gate pass | Done (software, simulated) |
| SPT-08 | Inland tracking and delivery (departure, route, distance, ETA, stops, delay reason, proof of delivery, transit time) | SmartPort doc stages 10, 11 | E | v2-2 (software), v2-4 (telematics) | `PortVisit.departed_at … transit_time_s`, `telematics` adapter, `DeliveryRecord` | Transit time computed on delivery; positions from fleet API | Done (software, simulated); live GPS Planned (field data) |
| SPT-09 | Agency roles and adapters: KPA, KRA, KenTrade, KeNHA, NTSA, KEBS; mock until authorised | SmartPort doc "Agencies" | E | v2-2 (software), v2-1 (agreements) | integration registry (`kebs`, `kentrade` added) | Adapters registered, mode `mock`, health endpoint | Done (software); Planned (field data) for real credentials |
| SPT-10 | Data register with provenance: every figure classified actual / published / estimated / simulated with period, agency and source URL | SmartPort doc "Data sources and classification" | N | v2-2 | `GET /data/register`, `docs/06-operations/data-register.md`, web `/data` | Each register entry has classification, source and `used_by`; no `actual` entries until agency records are obtained | Done (software); `actual` records Planned (field data) |
| SPT-11 | Port-process simulation, existing operations versus SmartPort, with the SmartPort parameters and KPIs | SmartPort doc "Data format for simulation" | N | v2-2 | `kifaru_sim.port_process`, `kifaru-sim port`, `POST /port/simulate`, model explorer tab | Existing policy calibrated to the published 2023 truck turnaround (6.7 h); outputs labelled modelled | Done (software, modelled); validation Planned (field data) |
| SPT-12 | KPIs with published benchmarks: waiting time, queue length, processing time, weighbridge service time, throughput, dwell time shown beside KPA / SCEA / KeNHA figures | SmartPort doc KPIs | N | v2-2 | `GET /port/kpis`, web `/port` | Each KPI tile names the benchmark, its period and classification | Done (software, simulated) |
