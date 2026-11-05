# RCS v2 chain model — Section 9 tables (modelled)

`kifaru-sim v2` · 600,000 trucks per row · seed 1 · **MODELLED under stated assumptions, not measured.**

## Port trucks by average loading (shares of all trucks at the road station)

| Average load (% of limit) | Road-only screening | Road-only with allowance | RCS v2 road stops | RCS v2 port re-weigh | Road truck-hours saved per day (v1 to v2) |
|---|---|---|---|---|---|
| 75 % | 9.0 % | 5.7 % | 3.8 % | 4.2 % | about 41 |
| 80 % | 14.4 % | 7.5 % | 4.4 % | 7.9 % | about 80 |
| 85 % | 23.2 % | 10.8 % | 5.3 % | 14.8 % | about 143 |
| 90 % | 35.6 % | 16.1 % | 6.5 % | 25.6 % | about 232 |

The 'with allowance' column applies a 5 % discretion allowance to the road-only rule; the other columns use the configured allowance (`--set allowance_pct=5` applies it everywhere, including the port node).

## Mixed traffic at the first station with a rolling verification lane (85 % loading)

| Trucks with a port or origin token | Sent to the lane | Sent to a static scale | Road-only baseline (static) | Later station: lane | Later station: static | Truck-hours saved per day at the first station |
|---|---|---|---|---|---|---|
| 30 % | 17.2 % | 10.0 % | 20.8 % | 3.3 % | 0.0 % | about 52 |
| 50 % | 13.2 % | 7.1 % | 20.8 % | 3.3 % | 0.0 % | about 83 |
| 70 % | 9.2 % | 4.3 % | 20.8 % | 3.3 % | 0.0 % | about 114 |
| 90 % | 5.3 % | 1.5 % | 20.8 % | 3.3 % | 0.0 % | about 144 |

Untokened trucks alone (85 % loading): lane 23.3 %, static 14.2 % of untokened trucks. Lane peak 116 trucks/h against a capacity of 370/h (one lane per station is enough). False-clear rate 0.00 %.

## Assumptions

- Loads ~ Normal(85 % of limit, spread 12 % of limit), capped just below the limit; 1.5 % of trucks are overloaded by 0–15 %.
- Scale errors (relative SD): port 1 %, origin 1 %, road WIM 2.5 %, lane 1 %.
- Screening rule: reading × (1 + 2 × error) > limit. Token consistency: |road − token| ≤ 3 combined SD (8.1 % port/origin tokens, 10.6 % road tokens).
- Lane margin 2 % (lane not legal-grade); port scale not legal-grade; discretion allowance 0 %.
- Random audits 3 % of mainline greens. Stream mix: port 54 %, origin 36 %, untokened 10 %.
- Truck-hours: 8000 trucks/day, 6 min per static stop, 1.5 min per lane pass. Lane peak assumes a 500 trucks/h peak of untokened trucks; lane capacity 370/h at 10 km/h and 27 m headway.
- 'untokened_lane' and 'untokened_static' are shares of untokened trucks only; every other share is a share of all trucks.
- Fraud (plate swaps, cargo added after the first weighing) and legitimate weight changes are not modelled; they are covered by audits in the design.
- All figures are modelled under these assumptions and must be replaced with measured data (RCS v2 plan, Section 10).
