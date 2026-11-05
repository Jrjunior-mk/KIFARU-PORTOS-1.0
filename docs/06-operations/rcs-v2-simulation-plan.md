# RCS v2 simulation plan

Status: plan, 2026-11-05. The L2 implementation exists in `packages/simulation` (`kifaru_sim.rcs_v2`,
`kifaru_sim.experiments`, SimPy policy `rcs_v2`); every number it produces is **modelled** and must be replaced by
measured data from the baseline study before any saving is claimed. See also
[`simulation-guide.md`](simulation-guide.md) for the station model and
[`../01-requirements/rcs-v2-port-anchored-clearance.md`](../01-requirements/rcs-v2-port-anchored-clearance.md) for
the design being simulated.

## 1. Questions to answer

1. How many stops and how much delay does each design remove?
2. How accurate must the port and road scales be?
3. How robust is the system to low token coverage, outages and traffic peaks?
4. Can the port re-weigh stage cope with the volume?
5. Do queues at the port exit and the weighbridge stay stable?

## 2. Four linked levels

| Level | Simulates | Tools | Output | Repository implementation |
|---|---|---|---|---|
| L1 Sensor and algorithm | Truck dynamics on a rough road, tyre contact, sensor response, temperature drift and noise, then the weight estimator | Python (NumPy, SciPy), a quarter-car model; MATLAB or Simulink optional | Error curves by speed, load and temperature. These set the port and road errors used in L2 | `packages/wim_dsp` (synthetic signal generator, DSP pipeline, uncertainty); quarter-car model to be added |
| L2 Process | The whole chain for three truck streams, as-is and to-be, as a discrete-event model | SimPy (Python); AnyLogic is an alternative | Stops, delays, queues, truck-hours, false-clear rate | `kifaru_sim.rcs_v2` (chain Monte Carlo), SimPy policy `rcs_v2` in `kifaru_sim.model`, `kifaru_sim.experiments`; CLI `kifaru-sim v2`, `v2-sweep`, `v2-gate` |
| L3 Road traffic | Approach lanes, diverge lanes, the rolling verification lane and queue spillback onto the mainline | SUMO with TraCI | Queue lengths, spillback risk, diverge lane length | `kifaru_sim.sumo_adapter` (export, replay; SUMO optional) |
| L4 System and hardware-in-the-loop | Token service, APIs and edge pipeline under load and failure | FastAPI mock agencies, Locust, Mosquitto MQTT, recorded signals replayed into the bench rig | Latency, failover behaviour, data integrity | `apps/api` (`/api/v1/rcs`), `apps/api/tests/load`, `edge/gateway` outbox and clearance mirror |

## 3. Model specification for L2

**Entities.** Trucks with truck stream (port, origin or untokened), tractor and trailer tare, container tare,
declared and actual cargo, axle distribution, dimensions, lifted-axle status, tag status, route and driver.

**Resources.** Port entry and exit lanes, i-Gate validation, port scale and re-weigh lane, road screening lane, rolling
verification lane, static scale lanes, customs officers for sealed-load corrections.

**Arrivals.** 8,000 trucks a day at Mariakani (public figure), a time-of-day profile with a peak factor (1.5 assumed),
and bursts after vessel discharge at the port.

| Parameter | Initial assumption | How to measure |
|---|---|---|
| Static scale lanes and service time | 8 lanes, 4 minutes | Observe at Mariakani, request logs |
| Extra time to stop and rejoin traffic | 2 minutes | Stopwatch and cameras |
| Port exit validation time | Unknown | Time-and-motion at the i-Gate |
| Duplicate container and registration checks | Unknown | Count and time each |
| Port scale approach speed | 10 km/h | Design choice |
| Token coverage | 90 % | Enrolment plan |
| Audit share | 3 % | Policy |
| Share of loads near the limit | Mean 75–90 % of limit, spread 12 % | Weighbridge logs |
| Lane speed | 10 km/h | Design choice |
| Lane pass cost | 1.5 minutes (assumed) | Stopwatch in the shadow pilot |
| Lane scale error | 1 % | Bench rig, then paired static readings |
| Truck headway in the lane | 27 m | Cameras |
| Stream mix (port, origin, untokened) | To be measured | Classification counts at the station |
| Origin scale error | 1 % | Comparison of origin tickets with road and lane readings |
| Road-token validity window | 24 h (36 h for port and origin tokens) | Policy; journey times from telematics |
| Dimension and lifted-axle violation rates | To be measured | Static-bridge records, LiDAR portal in shadow mode |

These map onto `RcsModelIn` (`POST /api/v1/rcs/model`) and `SimConfig` (`kifaru-sim run --set key=value`).

**Policies compared.**

1. As-is (`baseline_all_stop`).
2. Road-only screening with absolute rule (`rolling_clearance`; `road_only_static` in the chain model).
3. RCS v2 for port trucks (chain model, port-truck table).
4. RCS with all three streams, tokens and the verification lane, at stream mixes from 30 % to 90 % tokened
   (`kifaru-sim v2-sweep --factor token_coverage`; SimPy scenarios `rcs_v2_tokens_*`).
5. The same with the 5 % allowance policy and an approved lane (`allowance_pct=5`, `lane_legal_grade=true`).
6. The same with outages, degraded token coverage and a lane closure (SimPy `rcs_v2_lane_closure`, `station_lane_failure`).

## 4. Experiment design

- Factors: average loading (75–90 %), port error (0.5–2 %), road error (1.5–4 %), token coverage (50–100 %), peak
  factor (1.0–2.0), outage frequency and duration, audit share (1–5 %).
- 30 replications per scenario, 30 simulated days each, 2-day warm-up, different random seeds.
- Common random numbers so scenario differences are paired and cleaner (`kifaru_sim.experiments` reuses the seed
  stream across scenarios).
- Report means with 95 % confidence intervals (Student t).
- KPIs: stops per 1,000 trucks, mean and 95th-percentile delay, truck-hours a day, maximum queue, false-clear rate,
  port re-weigh load, port yard dwell effect.

## 5. Verification and validation

- **Verification.** Unit tests, conservation checks (every truck exits once), trace single trucks by hand, and compare
  a single-server version with the Erlang C formula (`packages/simulation/tests`).
- **Validation.** Compare simulated as-is delays and queues with measured baselines. Accept if the mean delay is within
  about 15 % and peak queues align. Review the model with KPA and KeNHA staff.
- **Sensitivity.** Tornado chart of every factor, so the committee sees which assumptions matter most
  (`kifaru_sim.experiments.tornado`).
- **If data access is delayed.** Run a two-week time-and-motion and counting study with cameras and stopwatches, and
  flag results as provisional.

## 6. Data requests

| Dataset | Owner | Use |
|---|---|---|
| Gate-out and i-Gate timestamps, exit slips | KPA | Port exit delay and duplicate checks |
| Weighbridge logs: time, gross and axle loads, outcome | KeNHA | Loading distribution, baseline stops and delays |
| Release timestamps, declared weights sample, tracking-seal events | KRA | Expected weight, misdeclaration rate, transit flows |
| Tare weights and axle configurations | NTSA | Expected-weight calculation |
| Fleet and trip-plan information | Kenya Transporters Association | Enrolment and coverage estimates |

Anonymise plates and driver details before analysis, in line with the Data Protection Act, 2019 (see
`docs/04-security/dpia.md`). Request status is tracked in the RCS v2 roadmap, Phase 0–1.

## 7. Software stack

Python with NumPy, SciPy and pandas for L1 and analysis. SimPy for L2. SUMO with TraCI for L3. FastAPI, Mosquitto,
PostgreSQL and Locust for L4. Grafana for result dashboards, Jupyter for reports, Git with pytest for reproducible runs.

## 8. Timeline

| Weeks | Work |
|---|---|
| 1–2 | Baseline study plan and data requests |
| 3–4 | L1 sensor and algorithm model |
| 5–8 | L2 process model, verification and first scenarios |
| 9–10 | L3 road traffic model |
| 11–14 | L4 token service, mock APIs and hardware-in-the-loop |
| 15–16 | Validation, sensitivity, committee report |

## 9. Go/no-go gate

Proceed to the shadow pilot if the validated model shows that v2 cuts the road stop share by at least 10 points against
the measured baseline, or removes recurring peak saturation, with a false-clear rate at or below 1 %, and the port
re-weigh volume is practical for KPA. If not, narrow the project to a vehicle-side or registry-only offering.

`kifaru-sim v2-gate` evaluates the three conditions against the model and prints PASS / FAIL per condition; the
result counts only once the model has been validated against measured baseline data (Section 5).

## 10. Running the L2 implementation

```bash
kifaru-sim v2 --set avg_loading_pct=85 --set token_coverage=0.9          # one chain run, Section 9 shares
kifaru-sim v2-sweep --factor avg_loading_pct --values 75,80,85,90        # port-truck table
kifaru-sim v2-sweep --factor token_coverage --values 0.3,0.5,0.7,0.9     # mixed-traffic table
kifaru-sim v2-gate                                                        # go/no-go evaluation (modelled)
kifaru-sim run --scenarios rcs_v2_tokens_90,rcs_v2_lane_closure          # SimPy station model with lane and tokens
```

Outputs are labelled MODELLED in every report and on the web page `/model`.
