# Source Document Review — Rolling Clearance System (RCS)

**Status: ORIGINAL DOCUMENT NOT AVAILABLE — baseline reconstructed from the Master Prompt.**
Date of review: 2026-11-04

## 1. What was searched

| Location | Result |
|---|---|
| Workspace `c:\Users\muchi\Downloads\Soko-Mind-main` | Contains only the unrelated *Soko Mind* farming app (React/Vite/Gemini). No RCS material. |
| `C:\Users\muchi\Downloads` (file names containing *rolling*, *clearance*, *weigh*, *kifaru*, *portos*, *proposal*) | No matches. |
| Untitled WhatsApp PDFs/DOCX in Downloads | Course reports (transmission lines, cellphone detector), textbooks, a CV. Not RCS. |
| April-2026 photographs in Downloads | Complex-analysis coursework and personal photos. Not RCS handwritten notes. |
| Session uploads | None. |

**Action required from the project owner:** place the original *Rolling Clearance System* proposal and scans of the handwritten notes in
`kifaru-portos/docs/01-requirements/source/` (any format). The traceability matrix has a `Source` column that currently cites
"Master Prompt §x"; when the originals arrive every row will be re-cited to a page/paragraph of the original and the
Preserve / Enhance / Replace / New disposition will be re-validated.

## 2. Reconstructed baseline — the original RCS concept

The Master Prompt (§2, §3 Modules 1–2, §16 "Preserve the original weighing and rolling-clearance concept") describes the
original idea with enough detail to reconstruct it. The original Rolling Clearance System is understood to be:

1. **Weigh-in-motion (WIM) lane** on the Northern Corridor approach to the Mariakani weighbridge (and later Port of Mombasa gates)
   that measures axle loads and gross vehicle mass (GVM) while the truck is moving.
2. **Automatic truck identification** at the lane (ANPR camera and/or RFID tag) so the measurement is tied to a registered vehicle.
3. **A three-colour clearance decision** — GREEN (continue without stopping), AMBER (go to static scale for verification),
   RED (suspected overload / non-compliance, inspection).
4. **The static weighbridge remains the legal reference**; the rolling lane only *pre-screens* so that compliant trucks are not stopped.
5. **A digital weighing ticket / record** for every event so that the stop-or-go decision is auditable.
6. **Reduction of queues, idling and fuel wastage** at Mariakani as the primary benefit.

Items that the Master Prompt marks as *new* for KIFARU PORTOS (and therefore were not in the original) are: predictive queue
intelligence, backhaul marketplace, digital cargo passport, predictive cargo release, small-cargo-owner platform, environmental
intelligence, multi-agent AI, digital twin, and the full live-cloud platform.

## 3. Disposition summary

| Disposition | Meaning | Examples |
|---|---|---|
| **Preserve** | Original concept kept as-is because it is the core value and legally correct | WIM pre-screen; static scale as legal reference; GREEN/AMBER/RED |
| **Enhance** | Original concept kept but made rigorous | Add measurement-uncertainty and sensor-health gating to the decision; evidence record; identity confidence; conservative margins |
| **Replace** | Original approach superseded by a technically necessary one | HX711-class 80 SPS load-cell ADC → 24-bit simultaneous-sampling delta-sigma ADC at 5–10 kHz/channel; single sensor → multi-sensor fusion |
| **New** | Introduced by KIFARU PORTOS | Modules 3–9, cloud platform, digital twin, stakeholder apps |

## 4. Open questions for the owner (to be answered from the original document)

1. Which weighbridge(s) did the original target — Mariakani only, or also Athi River / Gilgil / Webuye?
2. Did the original specify a sensor technology (piezo-quartz, piezo-polymer, bending plate, load cell)?
3. Did the original propose any lane geometry (number of sensor rows, spacing, lane length)?
4. Was there a stated target accuracy or vehicle speed range?
5. Which regulator interactions (KeNHA, KRA, NTSA) did the original envisage?
6. Did the handwritten notes contain circuit sketches or firmware pseudocode that should be preserved verbatim?

## 5. Update 2026-11-05 — RCS v2 plan supplied

The project owner supplied the full **RCS v2: port-anchored clearance, implementation and simulation plan** (12
sections). It is now the primary requirements source for the clearance system and is held, with implementation
cross-references, in `rcs-v2-port-anchored-clearance.md`. The legal reading is in `legal-hooks-eac-vlc-2018.md`, the
simulation plan in `../06-operations/rcs-v2-simulation-plan.md`, and the traceability rows in section L of the RTM.
The original v1 RCS proposal and the handwritten notes are still missing; section 1 above stands.

### What v2 adds to the reconstructed v1 baseline

v1 (section 2) weighs trucks on the road and pre-screens them against the legal limit with a GREEN/AMBER/RED decision.
v2 keeps that engine and adds: a first trusted weighing point before the road (port gate-out node or approved origin
scale), a signed Load Compliance Token honoured downstream, three truck streams, trust tiers and risk-based audits, a
Rolling Verification Lane for doubtful trucks, dimension, lifted-axle and per-wheel sensing, permits, digital release
orders, the discretion-allowance and fee policy from the 2018 Regulations, and a whole-chain simulation.

### Disposition of each v2 element

| Earlier (v1) | Now (v2) | Disposition | Why |
|---|---|---|---|
| Weigh only on the road | Weigh at each truck's first trusted point (port exit, origin site or first road station) and honour it downstream | **Enhance** | Gives a reference and removes repeat stops |
| Port trucks only | All heavy trucks in three streams | **New** | Mines, quarries and factories are part of the traffic |
| Weight only | Weight, dimensions, axle configuration, lifted axles, per-wheel balance, permits, certificates | **New** | High-speed WIM misses most of what KeNHA checks at static bridges |
| Judge absolute weight against the limit | Compare with the token, absolute rule as fallback | **Enhance** | Removes the near-limit accuracy problem for tokened trucks |
| Build our own road high-speed scales | Reuse KeNHA's high-speed WIM feed, add our own verification lane | **Replace** | Lower cost, and the lane supplies what the feed lacks |
| Static scale for every doubtful truck | Rolling Verification Lane for doubtful trucks, static scale for red cases | **Replace** | One rolling lane equals about 25 static lanes |
| Plate and RFID identity | Add container OCR, e-seal, release status, permits and fleet enrolment | **Enhance** | Removes repeated manual checks |
| Periodic calibration | Quarterly by an accredited calibrator, plus the audit loop | **Enhance** | Required by Reg 6 |
| Assumed pre-screening is acceptable | Use Reg 10(2), seek approval under Reg 5, approved signs under Reg 9 | **Enhance** | A legal basis for green decisions |
| Compete with the weighbridge operator | Registry, port and origin nodes, and the lane, in partnership on road feeds | **Replace** | Fits Reg 3(3) and the contractor model |
| Simulate one road station | Simulate the whole chain for three truck streams | **Enhance** | The gain comes from moving and merging work |
| WIM pre-screen, static scale as legal reference, GREEN/AMBER/RED, signed tickets, evidence record | Unchanged | **Preserve** | Core value and legally correct (Reg 4(6), Reg 10(4)) |

### Open questions carried from the v2 plan (owner to answer)

See `rcs-v2-port-anchored-clearance.md` §11: stream mix at Mariakani, access to the KeNHA WIM feed, whether the port
already weighs imports, KeNHA dimension and lifted-axle enforcement practice, applicability of Reg 10(2) to a digital
token and remote e-signing, legal-grade approval of low-speed in-motion weighing, routine use of the 5 % allowance,
route-specific limits and the 34-tonne container limit.
