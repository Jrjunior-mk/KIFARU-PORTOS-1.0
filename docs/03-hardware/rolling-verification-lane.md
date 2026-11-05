# Rolling Verification Lane — engineering note

Status: design, 2026-11-05. Not built. Layout dimensions are design assumptions to be checked against land and civil
works at each station. Accuracy figures are targets until measured against a static reference (Phase 4 shadow pilot).

The Rolling Verification Lane is RCS's own lane beside each road station, reached by a diverge from the mainline
screening node. Doubtful trucks and random audits roll through at about 10 km/h while every parameter a static bridge
checks is captured without stopping. Platform representation: `Lane.type = "rolling_verification"`, node kind
`verification_lane`, token source `lane` (trust tier 3).

## 1. Layout (design assumption)

| Segment | Length | Purpose |
|---|---|---|
| Diverge and approach | 100–150 m | Approved speed signs (Reg 9), speed reduction to ≤ 15 km/h, lane discipline markings, ANPR and RFID read before the measuring zone |
| Measuring zone | ≥ 15 m, flat concrete, level to pavement-standard tolerances | Per-wheel scales, dimension portal, cameras; must accommodate the longest combination (about 22 m) with all axles on instrumented plates in sequence |
| Exit and merge | 50 m | VMS with the result (continue / static scale), rejoin the carriageway |
| Total | about 250 m | Land take to be confirmed early at each station |

Speed discipline: the lane speed target is 10 km/h (15 km/h or less). Radar speed and loop timing flag passes above
the band as `speed_out_of_range`, which blocks an automatic GREEN; the truck repeats the pass or goes to the static
scale.

## 2. Sensors

| Sensor | Purpose | Platform sensor kind |
|---|---|---|
| Per-wheel low-speed scales (load cells) or bending plates, left and right | Axle and axle-group loads, left-right imbalance | `wheel_load_cell`, `bending_plate` |
| Inductive loops | Presence, axle count cross-check, speed | `inductive_loop` |
| Radar speed | Speed band enforcement | `radar_speed` |
| Overhead LiDAR or laser scanner portal | Height, width, length | `lidar_portal` |
| Light curtain | Over-height alarm, redundancy for the portal | `light_curtain` |
| Side LiDAR | Axle count including lifted axles, axle spacing, configuration classification | `side_lidar` |
| Cameras (overview, side, rear) | Evidence images for the officer screen, load type | `anpr_camera` (overview channel) |
| ANPR camera | Plate | `anpr_camera` |
| RFID reader | Tag, trailer pairing | `rfid_reader` |
| Pavement and ambient temperature | Compensation | `pavement_temp`, `ambient_temp_rh` |

The full parameter set (loads, dimensions, axle configuration, lifted axle, identity) is captured in roughly 20–30
seconds per truck. Readings are written as a `WeighingEvent` with `node_kind = "verification_lane"`, `length_m`,
`width_m`, `height_m`, `lifted_axle` and per-wheel loads on `AxleMeasurement.left_kg / right_kg`.

## 3. Throughput

- 10 km/h = 2.8 m/s.
- Headway about 27 m per truck (17 m truck plus a 10 m gap).
- 27 m / 2.8 m/s = 9.7 s per truck, about 370 trucks an hour per lane.
- A static lane at 4 minutes per truck handles about 15 an hour, so one rolling lane equals roughly 25 static lanes.
- Modelled demand: at 500 trucks an hour on the mainline, the lane peak is about 117 trucks an hour (85 % loading,
  30 % token coverage), so one lane per station is enough (modelled; `kifaru-sim v2` reports `lane_peak_per_hour`
  against `lane_capacity_per_hour`).

## 4. Accuracy target and legal grade

| Item | Value |
|---|---|
| Gross and axle-group error target | 1 % (expanded uncertainty, k = 2) at ≤ 15 km/h |
| Lane margin used in the decision | 2 % of the limit (`lane_margin_pct`) |
| Legal grade | `Lane.legal_grade = false` until the scales hold a weights-and-measures approval certificate (Reg 5). Until then a lane reading within the margin of the limit still sends the truck to the static scale; only RED cases need the static scale once approved |
| Calibration | At least every three months by an accredited calibrator (Reg 6), recorded as `CalibrationRecord`; an expired record blocks GREEN (`calibration_expired`) |
| Audit | Every twelve months (Reg 8) |

Approval path: bench rig characterisation (Phase 3), paired static readings in shadow mode (Phase 4, minimum 5,000
paired passes), application to the national weights-and-measures body for approval of low-speed in-motion weighing
as legal-grade (open question in the legal opinion).

## 5. Officer screen and e-sign

KeNHA officers see the same data as a static check on one screen: axle and group loads with limits and margins,
dimensions against limits and permit terms, lifted-axle check, images, identity, token status, computed fee
(indicative until the Third Schedule table is confirmed) and an e-sign button. The e-sign issues a `ReleaseOrder`
under Reg 3(4) and Reg 11(3) (`POST /api/v1/rcs/release-orders`, officer role, MFA). GREEN passes issue a lane token;
RED passes route to the static scale, which remains the legal proof of overload (Reg 4(6)).

## 6. Reuse at the port

The same measuring-zone design (per-wheel scales, dimension portal, cameras, readers) serves the port gate-out weigh
node, with the i-Gate as the exit; see [`port-gateout-weigh-node.md`](port-gateout-weigh-node.md).

## 7. Open items

- Land and civil works at each station (about 250 m); drainage and pavement flatness in the measuring zone.
- Lane closure handling: when the lane is down, AMBER trucks fall back to the static scale (SimPy scenario
  `rcs_v2_lane_closure`).
- Enforcement of speed discipline and what happens on a repeated over-speed pass.
- Whether side LiDAR classification is accepted by KeNHA as evidence of a lifted axle.
