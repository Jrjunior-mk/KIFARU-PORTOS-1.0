# Simulation guide — `packages/simulation` (RTM DT-02)

**Status: modelled results only.** Every number produced by `kifaru-sim` comes from a discrete-event model with
synthetic arrivals and assumed service-time distributions. Nothing in it is a measurement of Mariakani, Athi River or
the Port of Mombasa. The platform must collect baseline data in Phase 7 (observed arrivals, static-scale service times,
queue lengths, GREEN/AMBER/RED mix from live passes) before any saving is claimed. Until then the reports answer
"what does the model predict if these assumptions hold", not "what will happen".

## 1. What is modelled

```
arrivals ──► [WIM pre-screen, N lanes] ──GREEN──► exit
                        │── AMBER ──► [static scale, M bays] ──► exit
                        │── RED   ──► [static scale] ──► [inspection bay] ──► exit
                        (optional gate hold for a share of trucks = delayed cargo release)
```

| Element | Model | Default |
|---|---|---|
| Arrivals | Non-homogeneous Poisson (thinning) with a 24-value hour-of-day profile (`model.DEFAULT_TOD_PROFILE`, synthetic) | 60 trucks/h mean, one direction; peak ×1.45 at 08:00 and 16:00 |
| WIM pre-screen | `N` lanes, lognormal service, median 6 s | 2 lanes |
| Static scale | `M` bays, lognormal, median 4 min (σ 0.4) ≈ 13.8 trucks/h/bay | 5 bays (≈ 69/h) |
| Inspection | lognormal, median 25 min; RED trucks + a random sample (`inspection_rate`) | 2 bays, 1 % sample |
| Trucks | `kifaru_wim_dsp.signal_gen.random_truck` (EAC configurations, overload probability) | 15 % overload draw |
| Measurement | k=2 relative uncertainty per axle, sensor fault → `sensor_fault` quality flag, degraded → `sensor_degraded` | 2.5 %, 3 %, 2 % |
| Identity | RFID+ANPR / RFID / ANPR / low confidence; unregistered share | 80/10/8/2 %, 5 % unregistered |
| Decision | `kifaru.services.clearance_engine.decide` — the same deterministic engine the API uses, seeded audit sampler | audit 2 %, identity threshold 0.90 |
| Baseline | `policy="all_stop"`: no pre-screen, every truck queues for the static scale; engine decision computed as a shadow | — |

Collected per truck: arrival, wait at WIM, wait at static, wait at inspection, hold, exit, decision, `stopped`,
`stop_reason`, priority flag, GVM, axle config, rules fired. Per station: queue length of each resource every minute.

## 2. Running scenarios

```bash
# from the repo root, with the venv active (packages/simulation is installed editable)
kifaru-sim list
kifaru-sim run --scenarios all --hours 12 --reps 5 --out packages/simulation/reports/
kifaru-sim run --scenarios rolling_clearance,arrivals_+50 --hours 24 --reps 10 --seed 7 --out /tmp/sim
kifaru-sim run --scenarios all --set arrivals_per_hour=75 --set static_bays=4 --set overload_prob=0.25 --out /tmp/sim
kifaru-sim sumo-export --out /tmp/sumo --hours 12
```

`--set key=value` overrides any `SimConfig` field for every scenario (use `python -c "from kifaru_sim.model import
SimConfig; help(SimConfig)"` for the list). The run always includes `baseline_all_stop` so "stops avoided" can be computed.
Replication `k` uses seed `--seed + k`; the same seed gives byte-identical results (tested).

Programmatic use:

```python
from kifaru_sim import build, run_model
from kifaru_sim.report import compare, to_markdown
res = run_model(build("arrivals_+30", hours=12, seed=1))
print(res.metrics())
print(to_markdown(compare(["rolling_clearance", "static_capacity_-1"], hours=12, reps=5)))
```

### Scenarios

| Name | Meaning |
|---|---|
| `baseline_all_stop` | Pre-platform: every truck stops at the static scale. |
| `rolling_clearance` | Platform policy with default assumptions. |
| `arrivals_+20` / `+30` / `+50` | Demand growth under rolling clearance. |
| `station_lane_failure` | One of two WIM lanes down for 2 h mid-run; trucks in that lane cannot be pre-screened and fall back to the static scale. |
| `inspection_rate_x2` | Physical-inspection sampling and random-audit rate doubled. |
| `static_capacity_-1` | One static bay fewer. |
| `delayed_cargo_release` | 15 % of trucks held at the gate (median 15 min) awaiting cargo release. |
| `dynamic_slot_allocation` | Booking cap of ~110 % of mean demand per 15-min window; excess arrivals are shifted to the next window (booking delay is **not** counted as time in system). |
| `queue_policy_priority` | Perishable / hazardous cargo (12 %) served first at the static scale (`simpy.PriorityResource`). |

Add a scenario by appending to `kifaru_sim/scenarios.py::SCENARIOS` (base config + overrides) and `DESCRIPTIONS`.

## 3. Reading the comparison table

The report (`<out>/<stem>.md` and `.json`; example: `packages/simulation/reports/example-report.md`) has one row per
scenario; cells are **mean ± half-width of the 95 % confidence interval across replications** (Student t).

| Column | Interpretation | Caveats |
|---|---|---|
| Trucks | arrivals over the horizon | depends only on arrival settings; identical across scenarios with the same demand |
| Mean / P90 time in system | arrival → exit, minutes | P90 can be *below* the mean when a few inspected trucks dominate the mean; under rolling clearance the P90 sits inside the stopped 20 %, so it is ≈ static-scale time, not GREEN pass time |
| Mean / max static queue | trucks waiting (not in service), sampled every minute | the main congestion indicator for the all-stop baseline |
| % trucks stopped | share with `stopped=True` (static, inspection, lane fallback or gate hold) | 100 % by definition in the baseline |
| Static-scale utilisation | busy time / (bays × run length) | run length includes the drain after the last arrival |
| Stops avoided vs baseline | paired difference (same seed) in stopped trucks | the primary modelled benefit; not a measured saving |
| Fuel / CO2 (modelled) | `EnvironmentalAgent` factors: 0.35 L per stop-start cycle, 2.5 L/h idling in queue, 2.68 kg CO2/L | **modelled, never report as measured** |
| GREEN / AMBER / RED | engine decision mix | in the baseline this is the shadow decision |

Secondary table: WIM queue, inspection-bay utilisation (watch it under `arrivals_+50` and `inspection_rate_x2` — the
model's bottleneck moves from the static scale to inspection once rolling clearance is in place), priority-cargo P90,
fuel/CO2 saved vs baseline (paired, modelled), drain time after the last arrival.

JSON output contains every replication's metrics, the full scenario configuration, decision mix and the mean static
queue by minute (for plotting).

## 4. Attaching SUMO (optional)

SUMO adds the approach road (platooning, merging of two lanes into the weighbridge exit) that the queueing model abstracts
away. `kifaru_sim/sumo_adapter.py`:

1. `kifaru-sim sumo-export --out dir/` writes `mariakani_trucks.rou.xml` (truck departures from the arrival profile,
   shifted by free-flow travel time), `mariakani.nod.xml` + `mariakani.edg.xml` (netconvert inputs), a minimal
   hand-written `mariakani.net.xml` (2 km two-lane approach, 300 m weighbridge exit lane, through lanes) and `mariakani.sumocfg`.
   For a geometrically faithful network run `netconvert -n mariakani.nod.xml -e mariakani.edg.xml -o mariakani.net.xml`
   or import OSM for the A109 at Mariakani.
2. With SUMO installed (`sumo` on PATH, `SUMO_HOME` set, `pip install traci sumolib`): `run_sumo(sumocfg)` produces
   `tripinfo.xml`; `read_sumo_arrivals(tripinfo)` extracts arrival times on the `weigh_exit` edge; `replay_into_model(cfg, arrivals)`
   runs the SimPy station with those arrivals. `run_with_sumo(cfg, work_dir)` chains all three.
3. Without SUMO (the normal developer case) `sumo_status().message` explains what is missing, the export still works
   and `run_sumo` raises `SumoUnavailable` with the same message. Nothing else in the package depends on SUMO.

## 5. Limitations

- **Synthetic arrivals.** The hour-of-day profile and the 60 trucks/h default are engineering assumptions, not counts.
- **No measured baseline.** The all-stop baseline is itself a model. Phase 7 must record observed queue lengths, static
  service times and the live decision mix; those feed `SimConfig` (service medians/sigmas, overload share, identity mix,
  `tod_profile`) and replace the defaults.
- Service times are lognormal with assumed sigmas; inspection outcomes (offloading, fines) are not modelled beyond bay time.
- The WIM array is never a bottleneck at 6 s median service; lane failure matters through lost pre-screening, not capacity.
- Identity confidence and sensor-fault probabilities are independent draws; correlated failures (weather, power) are not modelled.
- `dynamic_slot_allocation` shifts arrivals; the booking delay borne by transporters is reported only indirectly (drain time).
- Fuel/CO2 use fixed emission factors; vehicle mix, gradient and ambient conditions are ignored. Labelled modelled everywhere.
- Confidence intervals reflect seed-to-seed variance only, not uncertainty in the model structure or its parameters.
- Runtime: ~2.5 ms per truck (dominated by the clearance engine's evidence hashing); 11 scenarios × 5 reps × 12 h ≈ 90 s.

## 6. Tests

```bash
cd packages/simulation && python -m pytest -q
```
Covers: conservation (every truck exits), baseline stops 100 % vs rolling < 50 %, +50 % arrivals raises P90 in the
saturated configuration, lane failure raises the static queue, capacity −1 raises utilisation, hold/priority scenarios
run, determinism with a fixed seed, time-of-day and slot-cap behaviour, report rendering (Markdown + JSON), CLI, and the
SUMO adapter's export/replay/graceful degradation.

## 7. RCS v2 chain model (`kifaru_sim.rcs_v2`, `kifaru_sim.experiments`)

**Status: modelled results only.** The chain model is the Monte Carlo behind Section 9 of the RCS v2 plan
(`docs/01-requirements/rcs-v2-port-anchored-clearance.md`). It is independent of the SimPy station model: it has no
queues or service times, only loads, scale errors and decision rules, which is why it can run 600 000 trucks in well
under a second and answer "what share of trucks stops where" for each policy. Queue behaviour stays with the SimPy
model and SUMO (levels L2 and L3 of the simulation plan).

### 7.1 What is modelled

```
true load (fraction of limit) --> port gate-out / origin scale --token--> first road station --> later stations
                                   (1 % error)                            | mainline WIM 2.5 %      (token honoured)
                                                                          |--> rolling verification lane 1 %
                                                                          +--> static scale (legal proof)
```

| Element | Model | Default (`ChainParams`) |
|---|---|---|
| Loads | Normal(`avg_loading_pct`, `load_spread_pct`) as a fraction of the legal limit, capped just below the limit (heavily loaded fleets bunch at the limit); `overload_prob` of trucks placed 0–15 % over | 85 %, 12 %, 1.5 % |
| Scale readings | true × (1 + Normal(0, error)) per node | port 1 %, origin 1 %, road 2.5 %, lane 1 % |
| Screening rule | reading × (1 + 2 × error) > limit sends the truck for a closer look (k = 2 expanded uncertainty, as in the clearance engine). This is the choice that reproduces the plan's 23 % road-only share at 85 % loading | — |
| Token consistency | a tokened truck on the road continues when abs(road − token) ≤ 3 combined standard deviations (8.1 % for port/origin tokens, 10.6 % for road tokens); the absolute near-limit test is not applied to tokened trucks | — |
| Streams | port / origin / untokened; derived from `token_coverage` (60 / 40 split of the tokened share) unless `stream_mix` is given | coverage 0.9 |
| Lane | untokened trucks inside the margin band or audited go to the lane; the lane sends to the static scale those with lane reading × (1 + `lane_margin_pct`) over the limit; a legal-grade lane has margin 0 | margin 2 % |
| Port node | green when port reading × (1 + 2 × port error) is within the limit (margin 0 if `port_legal_grade`); otherwise port re-weigh | not legal grade |
| Allowance | `allowance_pct` raises the limit everywhere it is applied; the "road-only with allowance" column always shows the 5 % policy bound when no allowance is configured | 0 % |
| Audits | `audit_rate` of mainline greens go to the lane (or to the static scale in the port-truck table, which has no lane) | 3 % |
| Later station | every truck carries a token (port, origin, road or lane); only audits, mismatches and certain overloads stop | — |
| Truck-hours | `trucks_per_day` × share × minutes / 60; one percentage point = 8 truck-hours at 8 000 trucks/day and 6 min per stop; a lane pass costs `lane_minutes` | 8 000, 6 min, 1.5 min |
| Lane capacity | 3600 / (27 m ÷ 2.78 m/s) ≈ 370 trucks/h; peak demand = `peak_per_hour` × untokened lane share (a peak hour of untokened trucks, the conservative case) | 500/h |

Common random numbers: all policies inside one run share the same loads, errors and audit draws, so the difference
between two columns is a paired comparison, not seed noise. Replications (`replicate`) change the seed.

### 7.2 Running it

```bash
kifaru-sim v2                                            # both Section 9 tables at the defaults (200 000 trucks per row)
kifaru-sim v2 --n 600000 --out packages/simulation/reports --stem rcs-v2-example
kifaru-sim v2 --set allowance_pct=5 --set port_legal_grade=true
kifaru-sim v2-sweep --factor token_coverage --values 0.3,0.5,0.7,0.9,1.0
kifaru-sim v2-sweep --factor port_error_pct --values 0.5,1,2 --json
kifaru-sim v2-gate --reps 30 --tornado                   # Section 10.9 gate, 95 % CIs, tornado sensitivity
kifaru-sim v2-gate --baseline 21.0                       # use a measured road-only stop share as the baseline
```

```python
from kifaru_sim import ChainParams, run_chain, sweep, replicate, tornado, evaluate_gate
r = run_chain(ChainParams(avg_loading_pct=85, token_coverage=0.9))
r.to_dict()                       # the RcsModelOut shape of docs/02-architecture/rcs-v2-api-contract.md
sweep("token_coverage", [0.3, 0.5, 0.7, 0.9], ChainParams())
replicate(ChainParams(), reps=30)["outputs"]["v2_road_static"]   # {"mean", "ci_low", "ci_high", "n"}
evaluate_gate(r)                  # {"proceed": bool, "checks": [...]}
```

`POST /api/v1/rcs/model` and `/rcs/model/sweep` call the same functions, so the web explorer and the CLI can never disagree.

### 7.3 Reading the two tables

Example output: `packages/simulation/reports/rcs-v2-example.md`.

*Port trucks by average loading.* Each row is one population of port trucks measured under four policies with the
same random numbers. "Road-only screening" is the v1 design (absolute rule at the road station); "with allowance" the
same rule with the Second Schedule discretion allowance; "RCS v2 road stops" the share still sent to a static scale on
the road when `token_coverage` of the trucks carry a port token; "RCS v2 port re-weigh" the share held at the port
gate-out node. Read it honestly: v2 moves the near-limit checks from the road to the port rather than deleting them
(the sum of the two v2 columns is close to the v1 column). The last column is the road truck-hours saved per day.

*Mixed traffic at the first station.* Rows are token coverage of the traffic (port and origin streams combined).
"Sent to the lane" and "sent to a static scale" are shares of all trucks at the first road station; the road-only
baseline is the static share of the same population under the v1 rule (audits excluded). "Later station" columns show
what remains once every truck carries a token: audits and mismatches go to the lane, almost nothing to a static scale.
`untokened_lane` and `untokened_static` in the API output are shares **of untokened trucks only** (the "untokened trucks
alone" sentence of the plan).

Expected figures at the defaults (seed 1, 600 000 trucks): 85 % loading → road-only 23.2 %, with allowance 10.8 %,
v2 road 5.3 %, port re-weigh 14.8 %, about 143 truck-hours a day; 90 % coverage → lane 5.3 %, static 1.5 %, about
144 truck-hours a day at the first station. These match the plan's Monte Carlo to within a few tenths of a point.

### 7.4 Experiments and the gate

`sweep` varies one factor (Section 10.4 factor list: loading, port and road error, coverage, audit share, allowance,
overload share, lane margin, legal-grade flags). `replicate` runs 30 seeds and reports Student-t 95 % confidence
intervals; at 200 000 trucks the half-widths are a few hundredths of a point, so seed noise is never the reason two
policies differ. `tornado` ranks the factors by how far they move the v2 road stop share: token coverage dominates,
then the audit rate, then average loading; port error and the allowance barely move the road share (they move the
port re-weigh share instead). `evaluate_gate` applies Section 10.9: proceed to the shadow pilot only when the model cuts
the road stop share by at least 10 points against the baseline (a measured baseline once Phase 2 data exists), the
false-clear rate is at or below 1 %, the port re-weigh share is practical for KPA (20 % placeholder threshold to agree)
and one verification lane covers the peak.

### 7.5 Limitations

- Loads are a capped normal with an assumed spread; the real distribution must come from KeNHA weighbridge logs.
- Scale errors are independent Gaussian relative errors; temperature drift, speed dependence and correlated faults are
  left to the L1 sensor model and the SimPy station model.
- The plan's numbers assume all port trucks pass the port node; trucks re-weighed at the port are assumed corrected and
  tokened, so their later road check is a consistency check only.
- Fraud (plate swaps, cargo added after the first weighing) and legitimate weight changes (partial offloads, fuel use)
  are not modelled; the design covers them with audits, validity windows and tolerances.
- No queues: the lane capacity check compares a peak-hour demand with a headway-based capacity, nothing more. Queue
  stability is the SimPy model's job.
- Every number is modelled under the stated assumptions and is to be replaced by measured data in the baseline study.

Tests: `packages/simulation/tests/test_rcs_v2.py` (contract shape, determinism, monotonic responses to loading,
coverage, allowance and legal-grade flags, false-clear target, lane capacity, truck-hour formula, sweep, replications,
tornado, gate, CLI).

## 8. RCS v2 in the SimPy station model (policy `rcs_v2`)

The station queue model gains a third policy beside `all_stop` and `rolling`:

```
arrivals ──► [WIM screening node] ──GREEN (token consistent, or clear with margin)──► exit
                       │── AMBER ──► [rolling verification lane, lane_bays, ~1.5 min, no stop] ──GREEN──► exit
                       │                                                │── AMBER / RED ──► [static scale] ──► …
                       │── RED   ──► [static scale] ──► [inspection bay] ──► exit
```

| Field | Meaning | Default |
|---|---|---|
| `token_coverage` | share of arriving trucks with a port or origin Load Compliance Token | 0.9 |
| `token_port_share` | of the tokened trucks, share from the port (rest: approved origin scales) | 0.6 |
| `token_error` | relative 1-sigma error of the scale behind the token | 0.01 |
| `cargo_change_prob` | tokened trucks whose load changed after the token; the consistency check sends them to the lane | 0.02 |
| `lane_bays`, `lane_service_median_s`, `lane_service_sigma` | rolling verification lane resource; a pass is lane time, not a stop | 1, 90 s, 0.3 |
| `lane_rel_uncertainty` | expanded (k = 2) relative uncertainty of the lane's per-wheel scales | 0.01 |
| `lane_closures` | `((start_s, duration_s), …)`: while closed, AMBER falls back to the static scale as in v1 | `()` |

The decision at the screening node is the production engine with a `TokenInput` (`clearance_engine.decide`, engine
`clr-2.0.0`): a valid, consistent token downgrades the near-limit AMBER rules, so the road only confirms that the weight
is unchanged. A truck routed to the lane is re-decided with the lane measurement (`node_kind="verification_lane"`); only
AMBER/RED out of the lane stops at the static scale. New per-truck fields: `stream`, `route`, `lane_pass`,
`wait_lane_s`; new metrics: `pct_lane`, `pct_tokened`, `mean_wait_lane_s`, `max_queue_lane`, `lane_utilisation`; the
comparison report has a "% via verification lane" column.

Scenarios: `rcs_v2_untokened`, `rcs_v2_tokens_50`, `rcs_v2_tokens_90`, `rcs_v2_allowance_5pct` (limits with the 5 %
Second Schedule allowance), `rcs_v2_lane_closure` (lane closed for 2 h mid-run).

```bash
kifaru-sim run --scenarios rolling_clearance,rcs_v2_untokened,rcs_v2_tokens_90,rcs_v2_lane_closure --hours 12 --reps 5
```

Caveat: the station model keeps the v1 truck population (`overload_prob` 0.15, synthetic arrivals), so its absolute
shares differ from the plan-calibrated chain model in section 7 (1.5 % overloaded, loads capped at the limit). Use the
chain model for the Section 9 figures and the station model for queues, lane capacity and closure behaviour. Both are
modelled; neither is a measurement.
