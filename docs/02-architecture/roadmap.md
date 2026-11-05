# KIFARU PORTOS — Implementation Roadmap

| Phase | Scope | Depends on | Milestone / acceptance criteria | Target |
|---|---|---|---|---|
| **1 Architecture & design** | Source review, RTM, system/cloud/DB/hardware architecture, stack, roadmap | — | All docs in `docs/01-requirements`, `docs/02-architecture` reviewed by owner; open questions in `00-source-review.md` answered | 2026-11 |
| **2 Core working platform** | Auth+RBAC, orgs/fleets/vehicles, stations/lanes/sensors, WIM simulator, identity simulator, **clearance engine**, tickets+QR, shipments/passport, ledger, Postgres+Alembic, Docker Compose, Terraform (validated), CI | 1 | `pytest` green incl. clearance rule tests; `docker compose up` gives working API+web; `terraform validate` passes; live deploy **only** when AWS access granted | 2026-11/12 |
| **3 Logistics intelligence** | Queue records, appointments/slots, truck & cargo tracking (telematics adapter), notifications (WS/SMS/email), transporter + cargo-owner + driver UIs, PWA | 2 | Slot booking rejects over-capacity; dashboards update over WS without refresh; SMS adapter sends via Africa's Talking sandbox | 2027-01 |
| **4 Advanced AI** | Queue forecasting (15/30/60/120), backhaul matching + marketplace flow, cargo anomaly detection, release prediction, environmental model, agent orchestrator | 3 | Backtest report for forecaster; matcher unit tests; no automatic commercial assignment; emissions formulas documented | 2027-02 |
| **5 Digital twin & integrations** | Three.js port, SimPy/SUMO scenarios + comparison reports, adapters (mock → real where authorised) | 3, 4 | Twin shows live events with simulation banner when not live; scenario CLI produces comparison table; adapter health page | 2027-03 |
| **6 Industrial prototype** | STM32 DAQ firmware, AFE boards, lab rig, calibration, edge gateway, hardware→cloud | 2 | Bench: axle pulses captured at 8 kSPS; lab-rig load error vs reference reported with uncertainty; outage store-and-forward test passes | 2027-04/05 |
| **7 Pilot readiness** | Shadow mode at a weighbridge (WIM decisions logged, not enforced), fault injection, security review, accuracy benchmark vs static scale, docs, runbooks | 5, 6 | KPIs reported against MP §12 targets with real data; regulator pack | 2027-06+ |

Critical path: 1 → 2 → 3 → 4 → 5 → 7, with 6 in parallel from Phase 2 onward.
Blocking external dependencies: AWS account (Phase 2 deploy), SMS account (3), weighbridge site access and regulator engagement (6–7).

## RCS v2 roadmap (port-anchored clearance)

Source: `docs/01-requirements/rcs-v2-port-anchored-clearance.md` §8. Months are counted from approval of the v2
redesign. The software items of Phases 2 and 3 (token service, registry APIs, mock agency APIs, chain and station
simulation, web registry and model pages) are implemented in this repository with simulated data; every other item is
open.

| Phase | When | What happens | Exit gate |
|---|---|---|---|
| **v2-0/1 Access and legal** | Months 0–3 | Meet KPA, KRA, KeNHA, NTSA, KenTrade, the weights-and-measures body, the Kenya Transporters Association and two or three candidate loaders (a quarry, a mine or factory). Request data (simulation plan §6). Legal opinion on Reg 10(2), Reg 5, Reg 3(4) and digital certificates | MoUs or written interest, data access agreed, legal route clear |
| **v2-2 Baseline and design** | Months 3–7 | Time-and-motion study at the port exit and Mariakani. Classification count for the real share of port and non-port trucks. Study of dimension and lifted-axle violations. Run the four-level simulation (16 weeks). Specify token, APIs and security | Validated model meets the go/no-go gate (simulation plan §9) |
| **v2-3 Bench prototype** | Months 6–11 | Scale-model rig, token service, OCR on recorded video, LiDAR dimension portal test, per-wheel scale test, mock agency APIs, replay of recorded signals | Latency and repeatability targets met on the rig |
| **v2-4 Shadow pilot** | Months 10–16 | One port exit lane, one origin site and a verification lane at Mariakani. Tokens issued and compared, nobody acts on them (`docs/06-operations/pilot-shadow-mode.md` §7) | Accuracy and false-clear targets met over a sustained period |
| **v2-5 Live pilot** | Months 16–24 | Volunteer fleets and loaders use the green lane. Approved signs (Reg 9). Static scale audits continue. Seek approval of lane scales as legal-grade (Reg 5) | Agency approval to operate live, then scale to other stations |

Critical path: v2-0/1 → v2-2 → v2-4 → v2-5, with v2-3 in parallel from month 6. No hardware spend before the v2-2 gate.

### Integration map

| System | Data exchanged | Dependency risk | Platform adapter |
|---|---|---|---|
| KPA gate systems (i-Gate, KWATOS) | Gate events, release status, exit slip | KPA must allow a weigh node in the exit lane | `kpa` (mock) |
| KRA (iCMS, ACD, tracking seals) | Release status, declared weight, seal ID, overload alerts | Data-sharing agreement | `kra` (mock) |
| KeNHA control centre and WIM feed | Road weights, static results, certificates, release orders, officer e-signature | Access to the feed or permission to add readers and a lane | `kenha` (mock) |
| Loading-site scales (private) | Signed tickets, calibration certificates | Approval and audit of each scale | `origin_scale` lanes, `Lane.legal_grade` |
| NTSA vehicle and permit records | Registration, tare, axle configuration, special-load permits | Data quality | `ntsa` (mock), `SpecialLoadPermit` |
| KenTrade and clearing agents | Document status | Optional first, deeper later | `customs` (mock) |
| Insurers (later) | Insurance validity | Optional | not registered |
