# KIFARU PORTOS — scenario comparison (modelled)

Generated 2026-11-05T07:20:05.584494+00:00 · horizon 12 h · 3 replications per scenario · base seed 1000 · 95 % confidence intervals (Student t) · runtime 32.5 s

> **MODELLED RESULTS — synthetic arrivals and assumed service-time distributions; not measured field data.** Fuel and CO2 are modelled estimates from the Environmental agent factors (idle 2.5 L/h, 0.35 L per stop-start cycle, 2.68 kg CO2/L) and must not be reported as measured savings. Baseline data is to be collected in Phase 7 before any claim is made.

## Comparison table

| Scenario | Trucks | Mean time in system (min) | P90 time in system (min) | Mean static queue | Max static queue | % trucks stopped | % via verification lane | Static-scale utilisation (%) | Stops avoided vs baseline | Fuel, modelled (L) | CO2, modelled (kg) | GREEN / AMBER / RED (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `baseline_all_stop` | 918 ± 96 | 44.3 ± 41.3 | 70.7 ± 69.8 | 44.4 ± 48.9 | 94 ± 89 | 100.0 ± 0.0 | 0.0 ± 0.0 | 99 ± 1 | 0 ± 0 | 1822 ± 1781 | 4882 ± 4772 | 80 / 18 / 2 |
| `rolling_clearance` | 918 ± 96 | 2.4 ± 1.1 | 4.7 ± 0.8 | 0.0 ± 0.0 | 1 ± 0 | 22.8 ± 5.9 | 0.0 ± 0.0 | 23 ± 6 | 709 ± 86 | 73 ± 22 | 196 ± 58 | 78 / 19 / 3 |
| `rcs_v2_untokened` | 918 ± 96 | 1.7 ± 1.1 | 2.8 ± 1.1 | 0.0 ± 0.0 | 0 ± 0 | 6.7 ± 1.4 | 18.6 ± 5.1 | 7 ± 1 | 857 ± 81 | 22 ± 6 | 58 ± 17 | 94 / 4 / 2 |
| `rcs_v2_tokens_50` | 918 ± 96 | 2.0 ± 0.6 | 3.0 ± 0.2 | 0.0 ± 0.0 | 0 ± 0 | 7.1 ± 0.7 | 19.8 ± 1.4 | 8 ± 2 | 853 ± 86 | 23 ± 4 | 62 ± 11 | 94 / 4 / 3 |
| `rcs_v2_tokens_90` | 918 ± 96 | 2.3 ± 1.5 | 3.1 ± 1.3 | 0.0 ± 0.0 | 0 ± 0 | 7.3 ± 1.7 | 19.9 ± 2.1 | 8 ± 2 | 851 ± 96 | 23 ± 5 | 63 ± 14 | 93 / 4 / 3 |
| `rcs_v2_allowance_5pct` | 918 ± 96 | 1.9 ± 1.4 | 2.6 ± 1.2 | 0.0 ± 0.0 | 0 ± 0 | 6.1 ± 2.9 | 20.0 ± 4.9 | 6 ± 2 | 863 ± 111 | 19 ± 8 | 52 ± 21 | 95 / 3 / 1 |
| `rcs_v2_lane_closure` | 918 ± 96 | 2.3 ± 1.4 | 3.1 ± 1.3 | 0.0 ± 0.0 | 0 ± 0 | 8.6 ± 2.4 | 15.9 ± 4.8 | 9 ± 2 | 840 ± 108 | 28 ± 5 | 74 ± 14 | 92 / 5 / 3 |
| `arrivals_+50` | 1400 ± 98 | 3.3 ± 2.9 | 4.8 ± 0.4 | 0.0 ± 0.1 | 3 ± 3 | 21.6 ± 3.8 | 0.0 ± 0.0 | 33 ± 6 | 616 ± 85 | 107 ± 19 | 286 ± 52 | 79 / 18 / 3 |

Values are mean ± half-width of the 95 % CI across replications. P90 of a heavy-tailed distribution can be below the mean when a few inspected trucks dominate the mean.

## Secondary metrics

| Scenario | Mean WIM queue | Max WIM queue | Mean static wait of stopped trucks (s) | Inspection-bay utilisation (%) | P90 time in system, priority cargo (min) | Fuel saved vs baseline, modelled (L) | CO2 saved vs baseline, modelled (kg) | Drain after last arrival (min) |
|---|---|---|---|---|---|---|---|---|
| `baseline_all_stop` | 0.00 ± 0.00 | 0 ± 0 | 2324 ± 2540 | 52 | 65.5 ± 68.3 | 0 ± 0 | 0 ± 0 | 81 ± 75 |
| `rolling_clearance` | 0.00 ± 0.00 | 1 ± 1 | 1 ± 1 | 62 | 4.0 ± 0.9 | 1748 ± 1772 | 4686 ± 4748 | 40 ± 46 |
| `rcs_v2_untokened` | 0.00 ± 0.00 | 0 ± 1 | 0 ± 0 | 51 | 3.1 ± 2.2 | 1800 ± 1775 | 4824 ± 4758 | 31 ± 58 |
| `rcs_v2_tokens_50` | 0.00 ± 0.00 | 1 ± 0 | 0 ± 0 | 57 | 2.6 ± 1.3 | 1799 ± 1777 | 4821 ± 4763 | 26 ± 66 |
| `rcs_v2_tokens_90` | 0.00 ± 0.00 | 1 ± 0 | 0 ± 0 | 63 | 2.8 ± 1.4 | 1798 ± 1780 | 4819 ± 4770 | 38 ± 104 |
| `rcs_v2_allowance_5pct` | 0.00 ± 0.00 | 1 ± 0 | 0 ± 0 | 50 | 2.5 ± 2.0 | 1802 ± 1786 | 4830 ± 4786 | 31 ± 58 |
| `rcs_v2_lane_closure` | 0.00 ± 0.00 | 1 ± 0 | 0 ± 0 | 65 | 2.7 ± 0.6 | 1794 ± 1785 | 4808 ± 4783 | 29 ± 85 |
| `arrivals_+50` | 0.00 ± 0.00 | 1 ± 0 | 4 ± 11 | 87 | 4.7 ± 2.4 | 1715 ± 1771 | 4596 ± 4747 | 72 ± 12 |

## Scenario definitions

- `baseline_all_stop` — Pre-platform situation: every truck queues for the static scale; no WIM pre-screen (engine decision is shadow only). (policy=all_stop, arrivals/h=60.0×1.0, WIM lanes=2, static bays=5, inspection bays=2, inspection rate=0.01, audit rate=0.02, slot cap/15 min=None, priority queue=False, hold prob=0.0, lane failures=())
- `rolling_clearance` — Platform: WIM pre-screen, GREEN continues, AMBER to static scale, RED to static + inspection. (policy=rolling, arrivals/h=60.0×1.0, WIM lanes=2, static bays=5, inspection bays=2, inspection rate=0.01, audit rate=0.02, slot cap/15 min=None, priority queue=False, hold prob=0.0, lane failures=())
- `rcs_v2_untokened` — RCS v2 lane only: no tokens (first-time traffic), every AMBER rolls through the verification lane. (policy=rcs_v2, arrivals/h=60.0×1.0, WIM lanes=2, static bays=5, inspection bays=2, inspection rate=0.01, audit rate=0.02, slot cap/15 min=None, priority queue=False, hold prob=0.0, lane failures=())
- `rcs_v2_tokens_50` — RCS v2: 50 % of trucks carry a port/origin token; AMBER rolls through the verification lane (1 lane, ~1.5 min) instead of stopping. (policy=rcs_v2, arrivals/h=60.0×1.0, WIM lanes=2, static bays=5, inspection bays=2, inspection rate=0.01, audit rate=0.02, slot cap/15 min=None, priority queue=False, hold prob=0.0, lane failures=())
- `rcs_v2_tokens_90` — RCS v2: 90 % token coverage, verification lane for the rest. (policy=rcs_v2, arrivals/h=60.0×1.0, WIM lanes=2, static bays=5, inspection bays=2, inspection rate=0.01, audit rate=0.02, slot cap/15 min=None, priority queue=False, hold prob=0.0, lane failures=())
- `rcs_v2_allowance_5pct` — RCS v2 at 90 % coverage with the 5 % Second Schedule discretion allowance applied (policy decision for KeNHA). (policy=rcs_v2, arrivals/h=60.0×1.0, WIM lanes=2, static bays=5, inspection bays=2, inspection rate=0.01, audit rate=0.02, slot cap/15 min=None, priority queue=False, hold prob=0.0, lane failures=())
- `rcs_v2_lane_closure` — RCS v2 at 90 % coverage with the verification lane closed for 2 h mid-run (AMBER falls back to the static scale). (policy=rcs_v2, arrivals/h=60.0×1.0, WIM lanes=2, static bays=5, inspection bays=2, inspection rate=0.01, audit rate=0.02, slot cap/15 min=None, priority queue=False, hold prob=0.0, lane failures=())
- `arrivals_+50` — Rolling clearance with +50 % demand. (policy=rolling, arrivals/h=60.0×1.5, WIM lanes=2, static bays=5, inspection bays=2, inspection rate=0.01, audit rate=0.02, slot cap/15 min=None, priority queue=False, hold prob=0.0, lane failures=())

## Method and limitations

- Discrete-event model (SimPy): non-homogeneous Poisson arrivals with a synthetic hour-of-day profile; lognormal service times (WIM median 6 s, static scale median 4 min, inspection median 25 min); truck masses from `kifaru_wim_dsp.signal_gen.random_truck`; decisions from the deterministic clearance engine `kifaru.services.clearance_engine.decide` (same code as the platform).
- The baseline scenario is a modelled all-stop station, not an observed one. No field baseline data exists yet (Phase 7).
- Identity confidence, sensor-fault rates and the overload share are assumptions (see config of each scenario).
- Replications differ only by random seed; CIs describe simulation variance, not model-structure uncertainty.
