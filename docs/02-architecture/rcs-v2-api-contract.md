# RCS v2 — platform contract (port-anchored clearance)

Status: design contract for the RCS v2 implementation (2026-11-05). Backend, web, simulation and documentation work
are built against this file. Field names are the API snake_case names. Everything here is configuration-driven and
flagged where a legal value must be confirmed with KeNHA or the weights-and-measures body.

## 1. Concepts added to the platform

| Concept | Where | Notes |
|---|---|---|
| Truck stream | `WeighingEvent.stream` = `port` / `origin` / `untokened` | Set from the token source (port or origin) or, without a token, `untokened` |
| Node kind | `WeighingEvent.node_kind`, derived from `Lane.type` | `port_gateout`, `origin`, `road_mainline`, `verification_lane`, `static` |
| Lane types | `Lane.type` | existing `wim_highspeed`, `wim_lowspeed`, `static` plus `port_gateout`, `origin_scale`, `rolling_verification` |
| Station kinds | `WeighingStation.kind` | `road_station` (default), `port_gate`, `origin_site` |
| Legal grade | `Lane.legal_grade` (bool) | true only when the lane's scale holds weights-and-measures approval (Reg 5). Until then a lane reading never replaces the static scale as proof of overload |
| Load Compliance Token | `LoadComplianceToken` | signed record issued at the first verified weighing point; honoured downstream until it expires or a consistency check fails |
| Trust tier | `LoadComplianceToken.trust_tier`, `Vehicle.trust_tier` | 1 port gate-out, 2 approved origin scale, 3 road node or lane, 4 on-board record only |
| Route | `ClearanceDecision.route` | `continue`, `verification_lane`, `static_scale`, `port_reweigh`, `hold` |
| Release order | `ReleaseOrder` | Reg 14 digital release order, officer e-signed, repeat offence in the same journey triples the fee |
| Special-load permit | `SpecialLoadPermit` | dimension / mass permit linked to a vehicle, checked by the dimension portal |
| Dimensions | `WeighingEvent.length_m / width_m / height_m / lifted_axle` | from the LiDAR portal, light curtain and side LiDAR on verification and port lanes |

New sensor kinds: `lidar_portal`, `light_curtain`, `side_lidar`, `wheel_load_cell`, `container_ocr`, `eseal_reader`.

## 2. Decision rules (engine `clr-2.0.0`)

Inputs added to `clearance_engine.decide`: `token: TokenInput | None`, `dimensions: DimensionsInput | None`,
`node_kind: str`, `lane_available: bool`, `audit_rate_by_tier: dict[int, float] | None`.

| Rule | Severity | Fires when |
|---|---|---|
| `TOKEN_PRESENT` | INFO | a valid token was found for the vehicle |
| `TOKEN_EXPIRED` | AMBER | token found but past its validity window |
| `TOKEN_SUSPENDED` | AMBER | token suspended or revoked (origin drift, audit failure) |
| `TOKEN_IDENTITY_MISMATCH` | RED | token plate / tag / seal do not match the identity read at this node |
| `TOKEN_WEIGHT_INCONSISTENT` | AMBER | abs(measured GVM − token GVM) > tolerance × token GVM (8 % for port, origin and lane tokens, 11 % for road tokens) |
| `TOKEN_COVERS_MARGIN` | INFO | a valid, consistent token downgrades `GVM_OVER_POSSIBLE` and `AXLE_GROUP_OVER_POSSIBLE` to INFO: the road reading only has to confirm the weight is unchanged |
| `DIMENSION_OVER` | RED | height, width or length exceed the limit and no valid permit covers them |
| `DIMENSION_PERMITTED` | INFO | oversize but within a valid special-load permit |
| `LIFTED_AXLE` | AMBER | lifted axle detected (axle configuration mismatch with registration) |
| `DISCRETION_ALLOWANCE` | INFO | the allowance (< 5 % of allowed load, Second Schedule) was applied to the limit |

Route from decision and node: GREEN → `continue`; AMBER at `road_mainline` → `verification_lane` when a lane exists, else
`static_scale`; AMBER at `port_gateout` → `port_reweigh`; AMBER at `verification_lane` → `static_scale`; RED → `static_scale`
(`hold` at the port). Tokens are issued only on GREEN at `port_gateout`, `origin`, `road_mainline` and `verification_lane`.

Audit rates by tier (initial policy): tier 1 2 %, tier 2 4 %, tier 3 3 %, tier 4 100 % (always verified in the lane).

## 3. Legal configuration (`services/limits.py`)

`LimitSet` gains `discretion_allowance_pct` (default 0; policy value < 5 %), `max_length_m` 22.0, `max_width_m` 2.65,
`max_height_m` 4.3 (flagged for verification), an indicative overload fee table in USD with the point 5 000 kg → 2 990 USD,
`detention_free_days` 3, `detention_usd_per_day` 50, `repeat_offence_multiplier` 3, and `reported_gvm_by_axles`
(2: 18 t, 3: 26 t, 4: 30 t, 6: 50 t, reported figures to be checked against the schedules). Version string
`KE-EAC-VLC-REG-2018-schedule-v2`.

## 4. REST surface (`/api/v1/rcs`)

```
GET  /rcs/policy                       -> RcsPolicyOut
GET  /rcs/trust-tiers                  -> TrustTierOut[]
GET  /rcs/tokens?status&source&vehicle_id&station_id&limit -> TokenOut[]
GET  /rcs/tokens/lookup?plate=         -> TokenOut | 404
GET  /rcs/tokens/verify/{token_ref}    -> TokenVerifyOut   (public, no auth)
GET  /rcs/tokens/{token_id}            -> TokenOut
POST /rcs/tokens/{token_id}/suspend    {reason}            (ops)
POST /rcs/tokens/{token_id}/revoke     {reason}            (ops)
GET  /rcs/release-orders?status&vehicle_id -> ReleaseOrderOut[]
POST /rcs/release-orders               ReleaseOrderIn -> ReleaseOrderOut (officer: weighbridge_operator / platform_admin, MFA)
GET  /rcs/release-orders/{id}          -> ReleaseOrderOut
POST /rcs/release-orders/{id}/status   {status: paid|closed}
GET  /rcs/permits?vehicle_id           -> PermitOut[]
POST /rcs/permits                      PermitIn -> PermitOut (transporter_admin / platform_admin)
GET  /rcs/stats?station_id             -> RcsStatsOut
POST /rcs/model                        RcsModelIn -> RcsModelOut      (Monte Carlo, modelled)
POST /rcs/model/sweep                  RcsSweepIn -> RcsSweepOut
```

### Schemas

```ts
RcsPolicyOut {
  limits_version: string; engine_version: string;
  discretion_allowance_pct: number;
  token_tolerance: { port: number; origin: number; lane: number; road: number };   // fractions, e.g. 0.08
  token_validity_hours: { port: number; origin: number; lane: number; road: number };
  trust_tiers: TrustTierOut[];
  fee_schedule: { currency: 'USD'; points: [number, number][]; detention_free_days: number; detention_usd_per_day: number; repeat_offence_multiplier: number; note: string };
  dimension_limits: { max_length_m: number; max_width_m: number; max_height_m: number };
  reported_gvm_by_axles: Record<string, number>;
  legal_hooks: { reg: string; says: string; consequence: string }[];
  notes: string[];
}
TrustTierOut { tier: 1|2|3|4; source: 'port'|'origin'|'road'|'onboard'; label: string; audit_rate: number; description: string }
TokenOut {
  id: string; token_ref: string; vehicle_id: string | null; plate: string | null; trailer_plate: string | null; rfid_epc: string | null;
  container_number: string | null; seal_id: string | null; shipment_id: string | null;
  source: 'port'|'origin'|'road'|'lane'; trust_tier: number; gvm_kg: number; expected_gvm_kg: number | null; variance_kg: number | null;
  axle_group_loads_kg: number[]; axle_config: string | null; dimensions: { length_m: number|null; width_m: number|null; height_m: number|null } | null;
  permit_ref: string | null; release_status: Record<string, string>; route: string | null; destination: string | null; driver_id: string | null;
  issued_at: string; expires_at: string; issuing_station_id: string; issuing_station_code: string; issuing_event_id: string;
  status: 'active'|'expired'|'suspended'|'revoked'; honoured_count: number; last_honoured_at: string | null; suspended_reason: string | null;
  signature: string; signer_key_id: string; signature_valid: boolean; source_label: string;   // e.g. "simulated"
}
TokenVerifyOut { valid: boolean; status: string | null; plate: string | null; source: string | null; trust_tier: number | null; gvm_kg: number | null;
  issued_at: string | null; expires_at: string | null; issuing_station: string | null; honoured_count: number | null; signature_valid: boolean; source_label: string | null; note: string | null }
ReleaseOrderIn { weighing_event_id: string; static_gvm_kg?: number | null; transit: boolean; hazardous: boolean; perishable: boolean; journey_ref?: string | null; notes?: string | null }
ReleaseOrderOut {
  id: string; order_ref: string; vehicle_id: string | null; plate: string | null; weighing_event_id: string; decision_id: string; station_code: string;
  measured_gvm_kg: number; allowed_gvm_kg: number; allowance_kg: number; adjusted_gvm_kg: number; overload_kg: number;
  fee_usd: number; fee_multiplier: number; repeat_offence: boolean; detention_days: number; detention_usd: number; total_usd: number;
  transit: boolean; customs_notified: boolean; hazardous: boolean; perishable: boolean;
  officer_user_id: string; officer_name: string | null; officer_signature: string; status: 'issued'|'paid'|'closed'; issued_at: string; valid_until: string;
  journey_ref: string | null; notes: string | null; source_label: string;
}
PermitIn { vehicle_id: string; reference: string; max_length_m: number; max_width_m: number; max_height_m: number; max_gvm_kg: number | null; valid_from: string; valid_to: string; route: string | null }
PermitOut extends PermitIn { id: string; plate: string; status: 'valid'|'expired'|'future' }
RcsStatsOut {
  total: number; by_stream: { port: number; origin: number; untokened: number };
  by_route: { continue: number; verification_lane: number; static_scale: number; port_reweigh: number; hold: number };
  token_coverage: number; tokens_active: number; tokens_issued_by_source: Record<string, number>; honoured_total: number;
  release_orders_open: number;
  per_station: { station_id: string; code: string; kind: string; total: number; routes: Record<string, number>; lane_share: number; static_share: number }[];
}
RcsModelIn {
  avg_loading_pct: number;          // 75..95, default 85
  load_spread_pct: number;          // default 12
  overload_prob: number;            // default 0.015
  token_coverage: number;           // 0..1, default 0.9 (share of trucks with a port or origin token)
  stream_mix: { port: number; origin: number; untokened: number };   // sums to 1; untokened = 1 - coverage when omitted
  port_error_pct: number;           // default 1.0
  origin_error_pct: number;         // default 1.0
  road_error_pct: number;           // default 2.5
  lane_error_pct: number;           // default 1.0
  lane_margin_pct: number;          // default 2.0
  allowance_pct: number;            // default 0
  audit_rate: number;               // default 0.03
  port_legal_grade: boolean;        // default false
  lane_legal_grade: boolean;        // default false
  trucks_per_day: number;           // default 8000
  stop_minutes: number;             // default 6
  lane_minutes: number;             // default 1.5
  peak_per_hour: number;            // default 500
  n: number;                        // trucks simulated, default 200000 (max 600000)
  seed: number;                     // default 1
}
RcsModelOut {
  inputs: RcsModelIn;
  shares: {                         // percentages of all trucks
    road_only_static: number; road_only_with_allowance: number;
    v2_road_static: number; v2_port_reweigh: number;
    first_station_lane: number; first_station_static: number;
    later_station_lane: number; later_station_static: number;
    untokened_lane: number; untokened_static: number;
  };
  truck_hours_saved_per_day: number;            // port-truck table (v1 to v2)
  truck_hours_saved_first_station: number;      // mixed-traffic table
  false_clear_rate: number;                      // share of GREEN continues that were over the limit
  lane_peak_per_hour: number; lane_capacity_per_hour: number; lane_ok: boolean;
  total_reweighs_v1: number; total_reweighs_v2: number;
  assumptions: string[]; label: 'MODELLED';
}
RcsSweepIn { factor: keyof RcsModelIn; values: number[]; base: Partial<RcsModelIn> }
RcsSweepOut { factor: string; rows: ({ value: number } & RcsModelOut['shares'] & { truck_hours_saved_per_day: number; truck_hours_saved_first_station: number; false_clear_rate: number })[]; label: 'MODELLED' }
```

### Existing schemas extended

- `WeighingOut`: `node_kind`, `stream`, `length_m`, `width_m`, `height_m`, `lifted_axle`, `token_id`, `token_ref`.
- `DecisionOut`: `route`, `token_checked_ref`, `token_issued_ref`, `fee_preview_usd` (RED only, indicative).
- `StationOut` / `StationIn`: `kind`. `LaneOut` / `LaneIn`: `legal_grade`; lane `type` accepts the three new values.
- `SimulateIn`: `oversize_prob` (default 0.02), `lifted_axle_prob` (default 0.02).
- `LimitsOut`: `discretion_allowance_pct`, `max_length_m`, `max_width_m`, `max_height_m`, `fee_schedule`.
- Live `clearance.decided` payload: `route`, `token_ref`, `stream`, `node_kind`.
- Ticket payload: `token_ref`, `route`, `node_kind`.

Instructions by route: `continue` "Continue — no stop required", `verification_lane` "Divert to the rolling verification lane (about 10 km/h, no stop)",
`static_scale` "Proceed to the static scale for legal weighing", `port_reweigh` "Return to the port re-weigh lane", `hold` "Hold for corrective action".

## 5. Seed data

- `MBS-GATE18` becomes `kind=port_gate`, lanes: 1 and 2 `port_gateout` (legal_grade false), lane 9 `static` (port re-weigh lane).
- New `BMB-QRY` "Bamburi Cement quarry scale" `kind=origin_site`, lane 1 `origin_scale` (legal_grade true, approved scale).
- `MRK` and `ATH` gain lane 5 `rolling_verification` (legal_grade false).
- Vehicles carry `trust_tier`; `KDC 905D` has a special-load permit; `KCY 377F` (tipper) is an origin-stream truck.

## 6. Simulation (`packages/simulation`)

- `kifaru_sim.rcs_v2`: vectorised Monte Carlo of the clearance chain for three streams (Section 9 of the plan). Reproduces
  the port-truck table (loading 75–90 %) and the mixed-traffic table (coverage 30–90 %). All outputs labelled modelled.
- `kifaru_sim.experiments`: factor sweeps, 30 replications with common random numbers, 95 % CIs, tornado sensitivity,
  go/no-go gate evaluation (road stop share cut ≥ 10 points, false clear ≤ 1 %, port re-weigh practical).
- SimPy station model gains policy `rcs_v2` with token coverage and a rolling verification lane resource.
- CLI: `kifaru-sim v2`, `kifaru-sim v2-sweep`, `kifaru-sim v2-gate`.
