# KIFARU PORTOS

**Kenya Intelligent Freight, Access, Routing & Unified Logistics Platform** — an AI-assisted smart-port and freight
logistics ecosystem for the Port of Mombasa, Mariakani and the Northern Corridor, built around **RCS v2, port-anchored
clearance**: every heavy truck is weighed at its first trusted point (the port exit for port cargo, an approved
loading-site scale for mines, quarries and factories, or the first road station for everyone else), receives a signed
**Load Compliance Token**, and later weighbridges honour that token instead of weighing again. Doubtful trucks roll
through a **Rolling Verification Lane** at about 10 km/h where weight, dimensions, lifted axles and per-wheel loads are
captured without a stop; red cases still go to the static scale and an authorised officer. A clearance **registry**
holds tokens, certificates, permits, release orders and demerit data for every station. Design, legal basis and
modelled effect: `docs/01-requirements/rcs-v2-port-anchored-clearance.md`.

**SmartPort port-process layer.** Around the weighing sits the full port workflow: one port-visit record per truck
collection trip, advanced through eleven stages (pre-arrival registration, customs clearance, arrival, gate-in, yard
allocation, loading, weighing at the port gate-out node, final clearance and gate pass, gate-out with dwell time,
inland transit, delivery) with the data each stage requires, agency roles (KPA, KRA, KenTrade, KeNHA, NTSA, KEBS),
KPIs shown beside published benchmarks, a data register that classifies every figure as actual, published,
estimated or simulated with its source, and an "existing port versus SmartPort" simulation. See
`docs/01-requirements/smartport-workflow-and-data.md` and `docs/06-operations/data-register.md`.

| | |
|---|---|
| Live site | **https://kifaru-portos-1-0.vercel.app** — Vercel project `kifaru-portos-1-0`, deployed automatically from `main` of this repository, backed by the Supabase PostgreSQL project KIFARU-PORTOS (durable, shared data; polling instead of WebSockets on serverless). See `docs/06-operations/vercel-demo-hosting.md` and `docs/06-operations/supabase-postgres.md`. |
| Status (2026-11-05) | Phases 1–5 implemented and tested locally; Phase 6 hardware designed (not built); Phase 7 pilot procedure written. **RCS v2 implemented in software (tokens, registry, release orders, verification lane, chain model); field items pending** — agency access, legal opinion, scale approval, lane and port-node hardware, baseline data (RTM section L, `docs/02-architecture/roadmap.md`). **Deployed on Vercel + Supabase (2026-11-05)** at the live-site link above; the production AWS design (ECS, RDS, IoT Core) in `docs/06-operations/deployment-guide.md` remains unapplied and requires the owner's AWS account. |
| Honesty rules | Every weighing record carries `source` = `live` / `simulated` / `replay`; simulated data is never shown as live. Government and commercial adapters are `mock` until authorised credentials are configured. Environmental figures and every RCS v2 chain-model result are labelled *modelled*. Accuracy/latency targets remain targets until measured in Phase 7. No regulator has reviewed or agreed the RCS v2 design. |
| Legal note | Axle/GVM limits, the discretion allowance, dimension limits and the overload fee table in `apps/api/kifaru/services/limits.py` are configuration flagged for verification against the EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018 (`docs/01-requirements/legal-hooks-eac-vlc-2018.md`). The static scale remains the legal reference; WIM, port and lane readings only pre-screen, and fees and release orders are issued by an authorised officer. |

## Repository layout

```
kifaru-portos/
├── apps/
│   ├── api/            FastAPI backend: auth/RBAC/MFA, fleet, stations, WIM ingest + simulator, deterministic
│   │                   clearance engine, signed tickets + QR, hash-chained ledger, cargo passport, queue/slots,
│   │                   backhaul marketplace, environment, integrations, admin, WebSocket, workers (MQTT/SQS/jobs)
│   ├── web/            React 18 + TypeScript + Vite + Tailwind: 7 role dashboards, clearance registry, RCS v2 model
│   │                   explorer, public ticket/token verify and About page, Three.js twin
│   └── mobile/         Flutter driver (hands-free) + cargo-owner app (not compiled here: no Flutter SDK)
├── packages/
│   ├── wim_dsp/        Reference WIM signal generation + processing (axle detection, speed, loads, uncertainty, health)
│   ├── ai_agents/      10 cooperating advisory agents + orchestrator (forecast, backhaul, release, environment, …)
│   └── simulation/     SimPy station model (16 scenarios incl. RCS v2 tokens + verification lane), RCS v2 Monte Carlo
│                       chain model + experiments/gate, comparison reports, SUMO adapter
├── edge/gateway/       Roadside gateway (Python): DAQ client, identity adapters, local clearance mirror,
│                       SQLite store-and-forward outbox, MQTT/HTTP uplink, VMS driver
├── firmware/
│   ├── stm32-wim-daq/  STM32H743 + ADS131M08 acquisition/DSP firmware (CMake, FreeRTOS; not compiled here)
│   └── esp32-aux/      ESP-IDF environmental/cabinet node
├── infra/
│   ├── terraform/      AWS af-south-1: 12 modules, dev/staging/prod roots, bootstrap (validated, not applied)
│   └── docker/         docker-compose (PostgreSQL, Redis, EMQX, api, web, workers)
├── .github/workflows/  CI (lint, tests, web build, terraform validate, security scans) and OIDC deploy pipeline
└── docs/
    ├── 01-requirements/  RCS v2 plan (rcs-v2-port-anchored-clearance.md), legal hooks (legal-hooks-eac-vlc-2018.md),
    │                     SmartPort workflow and per-stage data (smartport-workflow-and-data.md), source review
    │                     (original v1 document missing — see 00-source-review.md), RTM (L = RCS v2, M = SmartPort)
    ├── 02-architecture/  system, cloud, database ERD, hardware, tech stack, roadmap (incl. RCS v2 phases),
    │                     RCS v2 API contract (rcs-v2-api-contract.md), SmartPort port-process contract
    │                     (smartport-port-process-contract.md)
    ├── 03-hardware/      sensor architecture, analog front-end calculations, power/protection, enclosure,
    │                     communications, calibration, lab rig build guide, BOM, rolling verification lane,
    │                     port gate-out weigh node
    ├── 04-security/      threat model, controls catalogue, DPIA (Kenya DPA 2019), incident response plan
    ├── 05-report/        engineering report (42 sections + addenda 43 RCS v2, 44 SmartPort)
    └── 06-operations/    deployment guide, DR runbook, backups, local development, API documentation
                          (+ openapi.json), simulation guide, RCS v2 simulation plan, data register with sources
                          (data-register.md), emissions model, maintenance,
                          user manuals, USSD/SMS spec, pilot shadow-mode plan (incl. v2 additions), verified test results
```

## Quick start (local, no Docker)

Prerequisites: Python 3.12, Node 20+ (26 used here), git.

```bash
# 1. Python environment and packages
python -m venv .venv
.venv/Scripts/python -m pip install -e packages/wim_dsp -e packages/ai_agents -e packages/simulation
.venv/Scripts/python -m pip install -e "apps/api[dev]" email-validator

# 2. Backend (SQLite by default; see apps/api/.env.example for PostgreSQL/Redis/MQTT)
cd apps/api
../../.venv/Scripts/python -m alembic upgrade head
../../.venv/Scripts/python -m kifaru.seed          # demo data; prints the demo accounts and a generated password once
../../.venv/Scripts/python -m uvicorn kifaru.main:app --reload --port 8000   # http://localhost:8000/docs

# 3. Frontend (second terminal)
cd apps/web && npm install && npm run dev           # http://localhost:5173 (proxies /api and /ws to :8000)

# 4. Optional workers (third terminal)
cd apps/api && ../../.venv/Scripts/python -m kifaru.worker --every 5     # forecasts, predictions, incidents, security scan
cd apps/api && ../../.venv/Scripts/python -m kifaru.ingest               # MQTT/SQS device ingest (needs a broker)

# 5. Edge gateway simulator (feeds the API like a real lane would)
cd edge/gateway && ../../.venv/Scripts/python -m kifaru_gateway.main --simulate --rate 2
```

Docker Compose path (PostgreSQL + Redis + EMQX + api + web): `docs/06-operations/local-development.md`.
Hosted PostgreSQL on Supabase (project KIFARU-PORTOS): `apps/api/scripts/connect_supabase.py --url "<uri>"`, see `docs/06-operations/supabase-postgres.md`.

## Tests

```bash
cd apps/api            && ../../.venv/Scripts/python -m pytest -q    # 57 tests: API, clearance rules, security, workers
cd packages/wim_dsp    && ../../.venv/Scripts/python -m pytest -q    # 24 tests: signal pipeline
cd packages/ai_agents  && ../../.venv/Scripts/python -m pytest -q    # 8 tests: agents + orchestrator
cd packages/simulation && ../../.venv/Scripts/python -m pytest -q    # 15 tests: SimPy model + reports
cd edge/gateway        && ../../.venv/Scripts/python -m pytest -q    # outbox, clearance mirror, frame parser
cd apps/web            && npm run build                               # TypeScript + Vite production build
python -m ruff check apps/api packages                                # lint (config in ruff.toml)
```

Run the API suite against PostgreSQL: `KIFARU_TEST_DATABASE_URL=postgresql+psycopg://user:pass@host/db pytest -q`.
Verified results and their caveats: `docs/06-operations/test-results.md`.

## RCS v2 chain model (modelled, not measured)

```bash
kifaru-sim v2 --set avg_loading_pct=85 --set token_coverage=0.9        # one run: road stops, port re-weigh, lane and static shares
kifaru-sim v2-sweep --factor avg_loading_pct --values 75,80,85,90      # port-truck table (plan §9)
kifaru-sim v2-sweep --factor token_coverage --values 0.3,0.5,0.7,0.9   # mixed-traffic table (plan §9)
kifaru-sim v2-gate                                                      # go/no-go gate evaluation
kifaru-sim run --scenarios rcs_v2_tokens_90,rcs_v2_lane_closure        # SimPy station model with tokens and a verification lane
kifaru-sim port --reps 3 --hours 24                                     # SmartPort port process: existing vs SmartPort (gate-in, yard, loading, weighing, clearance, gate-out, transit)
```

The same models back `POST /api/v1/rcs/model`, `POST /api/v1/port/simulate` and the web pages `/model`, `/port` (visit board and KPIs) and `/data` (data register). Plan and assumptions:
`docs/06-operations/rcs-v2-simulation-plan.md`. Every figure is an estimate under stated assumptions until the Phase 2
baseline study replaces them with measured data.

## Demo accounts (local only)

The seed command creates one account per role and prints the e-mail addresses together with a password that is
generated for that run (or taken from `KIFARU_SEED_PASSWORD`). Credentials are deliberately not listed in this
repository. Production seeding never creates demo users.

## What the owner must provide to go live

1. AWS account (Organization recommended), Route 53 hosted zone and domain, GitHub repository for OIDC deploys.
2. SMS (Africa's Talking) and email (SES) accounts; telematics/fleet API credentials where available.
3. Decisions on data-protection registration with the ODPC and counsel review of `docs/04-security/dpia.md`.
4. Confirmation of the legal axle-load schedule and tolerance policy with KeNHA (`services/limits.py`).
5. Weighbridge site access and regulator agreement for the shadow-mode pilot (`docs/06-operations/pilot-shadow-mode.md`).
6. For RCS v2: approaches to KPA, KRA, KeNHA, NTSA and the weights-and-measures body; the data requests and legal
   opinion of v2 Phase 0–1; a volunteer loading site with an approved scale; the discretion-allowance policy value
   (`docs/01-requirements/rcs-v2-port-anchored-clearance.md` §11, `docs/02-architecture/roadmap.md`).

## Licence

Proprietary — KIFARU PORTOS project. All rights reserved unless otherwise agreed in writing.
