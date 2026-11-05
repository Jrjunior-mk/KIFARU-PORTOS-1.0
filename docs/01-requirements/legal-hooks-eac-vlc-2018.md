# Legal hooks: EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018

Status: engineering reading of the Regulations for design purposes, 2026-11-05. It is not legal advice. Phase 0–1 of
the RCS v2 roadmap requires a legal opinion on Reg 10(2), Reg 5, Reg 3(4) and digital certificates before any live
pilot. Values marked *indicative* are placeholders in configuration until the schedule tables are loaded and confirmed
with KeNHA and the national weights-and-measures body.

Source: EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018 (full text at bdears.busitema.ac.ug).
Platform locations refer to `apps/api/kifaru/` unless stated.

## 1. Regulation by regulation

| Regulation | What it says (plain words) | Design consequence | Where the platform enforces or records it |
|---|---|---|---|
| Reg 3(3) | The roads authority may outsource weighbridge operation, management and maintenance to private operators | A legal route for a private partner role; the platform is a registry and node operator in partnership on road feeds, not a competing weighbridge | Integration adapters (`routers/integrations.py`) for the KeNHA control centre and WIM feed; `mode=mock` until authorised |
| Reg 3(4) | Weighbridge tickets and release orders for overloaded vehicles are issued by authorised officers | The system prepares the fee and the certificate; an officer approves every red case | `POST /rcs/release-orders` requires `weighbridge_operator` or `platform_admin` with MFA; `ReleaseOrder.officer_user_id`, `officer_signature`; `static_certified` tickets only from `POST /weighing/events/{id}/static-verify` |
| Reg 4(5)–(6) | Mobile weighbridges and surveillance technology may be used. A vehicle found in breach is escorted to the nearest static weighbridge for accurate weighing | RCS readings decide who needs a static weighing. They never replace it as proof of overload | Engine: no path issues a legal certificate from a WIM, port or lane reading; routes `verification_lane`, `static_scale`, `port_reweigh`; `Lane.legal_grade` false by default |
| Reg 5 | Any weighbridge, including mobile, needs approval and a certificate from the national weights-and-measures body | Port, origin and lane scales need approval. Whether screening devices need it must be confirmed | `Lane.legal_grade` (set true only when the approval certificate exists); origin tokens only from `origin_scale` lanes |
| Reg 6 | Calibration at least every three months by an accredited calibrator | Quarterly calibration is a legal requirement; budget for it | `CalibrationRecord` (valid_from, valid_to, performed_by); `Lane.calibration_valid_to`; quality flag `calibration_expired` blocks GREEN (`QUALITY_BLOCKING`); seeded validity must be replaced with 90-day records |
| Reg 8 | An audit of the weighbridge every twelve months | Annual audit record alongside the calibration register | `CalibrationRecord.method` and `notes`; audit log (`AuditEvent`); annual audit entry to be added in Phase 4 |
| Reg 9(1) | The duty to submit for weighing arises on direction by an authorised officer or a weighbridge road sign | Driver signals (VMS, lane signs) must be approved signs. No direction means no duty to stop | `edge/gateway/kifaru_gateway/vms.py` messages; sign approval is a Phase 0–1 action, not software |
| Reg 10(2) | Except for a vehicle previously confirmed within limits by surveillance or screening devices, a transporter must produce the certificate on request | The legal hook for a digital green status (the Load Compliance Token) replacing the paper certificate at later stations | `LoadComplianceToken`; engine `TOKEN_PRESENT`, `TOKEN_COVERS_MARGIN`; public verification `GET /rcs/tokens/verify/{token_ref}` |
| Reg 10(4) | A certificate from any weighbridge is accepted as proof, unless there is apparent forgery, tampering or manifest error | Digital certificates and tokens must be tamper-evident and signed | Ed25519 signatures on tickets and tokens (`security.sign_payload`), signer key pinning, hash-chained ledger (`services/ledger.py`) |
| Reg 11(3) | The weighbridge certificate is signed by the authorised officer | E-signature workflow for officers | `ReleaseOrder.officer_signature` (platform signature bound to the officer's user id); remote e-sign to be confirmed in the legal opinion |
| Reg 12(3) | Fees may be paid electronically | Electronic payment status in the registry | `ReleaseOrder.status` (`issued` → `paid` → `closed`), `POST /rcs/release-orders/{id}/status`; payment adapter `mock` |
| Reg 13 | Legal axle and gross limits (with the Third Schedule); handling of hazardous and perishable loads | Limits are configuration with a version string; hazardous and perishable flags change the handling of a red truck | `services/limits.py` (`LimitSet`, `limits_version` stored with every decision); `ReleaseOrderIn.hazardous`, `perishable`; `Shipment.cargo_type` |
| Reg 14 | A release order must be kept for the journey and shown at later weighbridges. If the vehicle is found overloaded again in the same journey, the fees are tripled | A digital release-order registry visible to every station; repeat detection within the journey | `ReleaseOrder` (`journey_ref`, `valid_until`, `repeat_offence`, `fee_multiplier` = 3 on repeat); `LimitSet.repeat_offence_multiplier` |
| Reg 18 | Transit cargo certificates are shown at every later weighbridge. A surveillance-detected overload is verified on a static scale. An overloaded transit vehicle is detained until a customs officer breaks the seal with the transporter present | Integrate with KRA tracking seals and customs officers; alert customs when an overload is confirmed | `ElectronicSeal`, rule `SEAL_BREACH`; `ReleaseOrder.transit`, `customs_notified`; KRA adapter `mock` |
| Reg 20, Fifth Schedule | Demerit points against the vehicle, transporter and driver declared in the trip plan, with bans from the regional network | The registry holds trip-plan and demerit data; audit rate rises with demerit points | `Vehicle.demerit_points`, `Vehicle.trust_tier`; `audit_rate_by_tier`; trip plan fields on the token (`route`, `destination`, `driver_id`) |
| Second Schedule | The certificate records measured load, allowed load, a discretion allowance of less than 5 % of the allowed load, adjusted load, overload and fee | Allowance is a policy value agreed with KeNHA; it changes the stop share materially (plan Section 9) | `LimitSet.discretion_allowance_pct` (default 0; policy < 5); engine rule `DISCRETION_ALLOWANCE`; `ReleaseOrder.allowance_kg`, `adjusted_gvm_kg` |
| Third Schedule | Legal weights: steering axle 8 t, single drive axle 10 t, tandem 18 t, tridem 24 t; overload fee table 2021–2030; detention free for three days, then 50 USD a day | Fee computation in the registry from the table; strong incentive to join the clearance programme | `LimitSet.steering_single_kg`, `single_drive_kg`, `tandem_kg`, `tridem_kg`; `LimitSet.overload_fee()` (indicative table), `detention_free_days` 3, `detention_usd_per_day` 50 |

## 2. Fee example (indicative)

The Third Schedule fee table for 2021–2030 gives about 2,990 USD for 5,000 kg over the gross limit. The platform
holds an **indicative** piecewise-linear table anchored on that point (`LimitSet.fee_schedule`, exposed by
`GET /rcs/policy`). Until the full Third Schedule table is loaded and confirmed with KeNHA, every fee the platform
computes is labelled indicative and must not be presented to a transporter as the legal amount.

Worked example with the current configuration (indicative):

| Item | Value | Rule |
|---|---|---|
| Measured gross (static scale) | 55,000 kg | Reg 4(6): static reading is the proof |
| Allowed gross (6-axle, Third Schedule) | 50,000 kg | `LimitSet.gvm_limit_for_config` |
| Discretion allowance | 0 kg at the default policy (up to < 5 % = 2,500 kg if KeNHA applies it) | Second Schedule, `discretion_allowance_pct` |
| Overload | 5,000 kg | `ReleaseOrder.overload_kg` |
| Fee | about 2,990 USD | Third Schedule, `overload_fee(5000)` |
| Detention | free for 3 days, then 50 USD a day | `detention_free_days`, `detention_usd_per_day` |
| Second overload in the same journey | fee × 3 (about 8,970 USD) | Reg 14, `repeat_offence_multiplier` |
| Transit cargo | detained until a customs officer breaks the seal; customs alerted by the registry | Reg 18, `customs_notified` |

## 3. Two limits the software never crosses

1. A reading from screening devices (high-speed WIM, port gate-out scale, rolling verification lane) cannot replace
   static weighing as proof of overload (Reg 4(6), Reg 18(3)). The engine's `certain over` rules produce a RED route
   to the static scale; they never produce a fee by themselves.
2. Fees, weighbridge tickets and release orders for overloaded vehicles come from an authorised officer (Reg 3(4),
   Reg 11(3)). The platform prepares the record and the officer e-signs it under MFA.

## 4. Items for the Phase 0–1 legal opinion

- Can the Reg 10(2) exemption apply to a digital Load Compliance Token, and which body approves the screening devices?
- Can an authorised officer e-sign a release order remotely (Reg 3(4), 11(3))?
- Can low-speed in-motion weighing (port node, verification lane) be approved as legal-grade under Reg 5?
- Is the discretion allowance (Second Schedule) applied routinely, and at what value?
- Which route-specific limits apply, and does the 34-tonne container limit still hold?
- Whether the reported gross limits by axle count (2 axles 18 t, 3 axles 26 t, 4 axles 30 t, 6 axles 50 t) match
  the current schedules for each configuration (`REPORTED_GVM_BY_AXLES in services/limits.py`, flagged).
