"""Build the KIFARU PORTOS project proposal PDF (reportlab) from the plan documents and the simulation outputs in ./assets.

    python docs/07-proposal/build_proposal.py        -> docs/07-proposal/KIFARU-PORTOS-Project-Proposal.pdf

Every simulation figure in the document is MODELLED (Monte Carlo and discrete-event models with stated assumptions),
never a measurement; the document says so wherever a number appears.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = Path(__file__).resolve().parent
A = HERE / "assets"
OUT = HERE / "KIFARU-PORTOS-Project-Proposal-Judges.pdf"
port = json.loads((A / "port-results.json").read_text(encoding="utf8"))
chain = json.loads((A / "chain-results.json").read_text(encoding="utf8"))
simpy = json.loads((A / "simpy-comparison.json").read_text(encoding="utf8"))
TODAY = date(2026, 11, 5).strftime("%d %B %Y")
LIVE = "https://kifaru-portos-1-0.vercel.app"
REPO = "https://github.com/Jrjunior-mk/KIFARU-PORTOS-1.0"

NAVY, TEAL, INK, MUTED, LINE = colors.HexColor("#0f172a"), colors.HexColor("#0d9488"), colors.HexColor("#1e293b"), colors.HexColor("#475569"), colors.HexColor("#cbd5e1")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY, spaceBefore=14, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=TEAL, spaceBefore=10, spaceAfter=5)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=INK, spaceBefore=8, spaceAfter=3)
BODY = ParagraphStyle("Body", parent=ss["Normal"], fontName="Helvetica", fontSize=9.6, leading=13.6, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=5)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8.2, leading=10.5, textColor=MUTED, alignment=0)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8.2, leading=10.2, alignment=0, spaceAfter=0)
CELLB = ParagraphStyle("CellB", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
CAP = ParagraphStyle("Cap", parent=SMALL, alignment=TA_CENTER, spaceBefore=2, spaceAfter=8)
NOTE = ParagraphStyle("Note", parent=BODY, backColor=colors.HexColor("#fffbeb"), borderColor=colors.HexColor("#f59e0b"), borderWidth=0.6, borderPadding=5, spaceBefore=4, spaceAfter=8)


def clean(t: str) -> str:
    return (t.replace("≤", "<=").replace("≥", ">=").replace("→", "->").replace("←", "<-").replace("·", "-").replace("≈", "~"))


def P(t, st=BODY):
    return Paragraph(clean(t), st)


def bullets(items, st=BODY):
    return ListFlowable([ListItem(P(i, st), leftIndent=10) for i in items], bulletType="bullet", bulletFontSize=7, leftIndent=12, spaceAfter=6)


def table(head, rows, widths=None, font=8.2, zebra=True):
    data = [[Paragraph(clean(h), CELLB) for h in head]] + [[Paragraph(clean(str(c)), CELL) if not isinstance(c, Paragraph) else c for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if zebra:
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f1f5f9")))
    t.setStyle(TableStyle(style))
    return t


def figure(name, caption, width=165 * mm):
    img = Image(str(A / name))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width, width * ratio
    return KeepTogether([img, P(caption, CAP)])


class Doc(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("H1", "H2"):
            level = 0 if flowable.style.name == "H1" else 1
            text = flowable.getPlainText()
            key = f"h{abs(hash(text))}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=False)
            self.notify("TOCEntry", (level, text, self.page, key))


def on_page(canv, doc):
    canv.saveState()
    canv.setFont("Helvetica", 7.5)
    canv.setFillColor(MUTED)
    canv.drawString(18 * mm, 10 * mm, "KIFARU PORTOS - Proposal to the judging panel - simulation figures are modelled; published figures are cited")
    canv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
    canv.setStrokeColor(LINE)
    canv.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canv.restoreState()


def fmt(v, d=1):
    return f"{v:.{d}f}"


def build():
    s = []
    # ------------------------------------------------------------------ cover
    s += [Spacer(1, 40 * mm), P("KIFARU PORTOS", ParagraphStyle("c1", parent=H1, fontSize=30, leading=36, alignment=TA_CENTER, textColor=NAVY)),
          P("Kenya Intelligent Freight, Access, Routing and Unified Logistics Platform", ParagraphStyle("c2", parent=BODY, fontSize=12, leading=16, alignment=TA_CENTER, textColor=MUTED)),
          Spacer(1, 10 * mm),
          P("Project Proposal to the Judging Panel", ParagraphStyle("c3", parent=H1, fontSize=20, alignment=TA_CENTER, textColor=TEAL)),
          P("Rolling Clearance System v2: port-anchored clearance for heavy trucks on the Mombasa - Northern Corridor route, with implementation and simulation plan",
            ParagraphStyle("c4", parent=BODY, fontSize=11, leading=15, alignment=TA_CENTER)),
          Spacer(1, 18 * mm)]
    s.append(table(["Item", "Detail"], [
        ["Version", "1.0 (proposal), " + TODAY],
        ["Prepared by", "KIFARU PORTOS project team"],
        ["Prepared for", "The judging panel; and, for implementation, KPA, KRA, KeNHA, NTSA, KenTrade, KEBS, the weights-and-measures body, the Kenya Transporters Association and candidate loaders"],
        ["Live platform", LIVE],
        ["Source repository", REPO],
        ["Status of figures", "Two kinds of numbers, always labelled: published figures (KPA, KeNHA, NCTTCA, SCEA, KenTrade) are cited with period and source; stop shares, truck-hours, dwell and queue results are modelled from stated assumptions and are not measurements. Phase 0-2 replaces modelled figures with observed data before any benefit is claimed."],
    ], widths=[35 * mm, 135 * mm]))
    s.append(PageBreak())

    # ------------------------------------------------------------------ TOC
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("t1", parent=BODY, fontName="Helvetica-Bold", fontSize=10, leading=14, spaceBefore=4),
                       ParagraphStyle("t2", parent=BODY, fontSize=9, leading=12, leftIndent=12)]
    s += [P("Contents", H1), toc, PageBreak()]

    # ------------------------------------------------------------------ 1 executive summary
    d = chain["defaults"]["shares"]
    pt = {r["avg_loading_pct"]: r for r in chain["port_table"]}
    mx = {round(r["token_coverage"], 2): r for r in chain["mixed_table"]}
    s.append(P("1. Executive summary", H1))
    s.append(P(
        "Heavy trucks leaving the Port of Mombasa, and trucks loaded at mines, quarries, factories and depots, are checked many times for identity, "
        "cargo and release status, yet their weight is first measured on the highway, where an overload is hardest and most expensive to fix, and the "
        "same truck is then weighed again at every weighbridge on its route. KIFARU PORTOS proposes RCS v2, port-anchored clearance: weigh every "
        "heavy truck once at its first trusted point, issue a signed Load Compliance Token, and let every later station honour that token. For port "
        "cargo the first trusted point is the port exit; for industrial cargo it is an approved loading-site scale; for everyone else it is the first "
        "road station. Doubtful trucks roll through a Rolling Verification Lane at about 10 km/h where weight, dimensions, lifted axles and "
        "per-wheel loads are captured without a stop. Red cases still go to the static scale and an authorised officer, as the EAC Vehicle Load "
        "Control (Enforcement Measures) Regulations, 2018 require."))
    s.append(P("The platform that implements this design is already built in software and running: a FastAPI backend with a deterministic clearance "
               "engine, a clearance registry (tokens, release orders, permits, demerits), a React web application with role dashboards, a public "
               "verification page and a 3D digital twin, a roadside gateway, firmware and hardware designs, and a simulation package. It is deployed "
               f"at {LIVE} on a hosted PostgreSQL database, with 177 automated tests passing."))
    s.append(P("Modelled effect (to be confirmed with field data):", H3))
    s.append(bullets([
        f"At 85 % average loading, static-scale visits by port trucks at the first road station fall from {fmt(pt[85.0]['road_only_static'])} % of trucks under road-only screening to {fmt(pt[85.0]['v2_road_static'])} % with RCS v2, while {fmt(pt[85.0]['v2_port_reweigh'])} % are re-weighed inside the port where cranes and customs are at hand. That is about {fmt(pt[85.0]['truck_hours_saved_per_day'], 0)} truck-hours a day of road queueing removed at 8 000 trucks a day.",
        f"For the full traffic mix, static-scale visits at the first station fall from {fmt(mx[0.3]['road_only_baseline_static'])} % to {fmt(mx[0.3]['first_station_static'])} %, {fmt(mx[0.5]['first_station_static'])} %, {fmt(mx[0.7]['first_station_static'])} % and {fmt(mx[0.9]['first_station_static'])} % as token coverage rises from 30 % to 90 %; later stations send almost nothing to a static scale ({fmt(mx[0.9]['later_station_static'], 2)} %).",
        f"One rolling verification lane handles about {fmt(chain['defaults']['lane_capacity_per_hour'], 0)} trucks an hour, roughly 25 static lanes; the modelled peak demand on it is {fmt(chain['defaults']['lane_peak_per_hour'], 0)} trucks an hour.",
        f"No truck over the limit is modelled as cleared without a stop (false-clear rate {chain['defaults']['false_clear_rate'] * 100:.3f} %); real fraud such as plate swaps is handled by audits and token binding, outside the model.",
        "The go/no-go gate set for the simulation phase (road stop share cut by at least 10 points, false clear at most 1 %, port re-weigh volume practical) is met in the model; the gate is re-evaluated on measured data before any hardware spend.",
    ]))
    pe, ps = port["scenarios"]["existing"], port["scenarios"]["smartport"]
    s.append(P("SmartPort, the port-side layer, follows every truck through eleven stages from pre-arrival registration to delivery, with the "
               "data each stage needs, the agency that owns it, and dwell-time KPIs set against published benchmarks. Calibrated to KPA's published "
               f"2023 truck turnaround of 6.7 hours, the port model shows mean port dwell falling from {pe['avg_dwell_h']:.1f} h to {ps['avg_dwell_h']:.1f} h "
               f"({port['deltas']['avg_dwell_h_pct']:+.0f} %) and weighbridge service from {pe['weigh_service_min']:.1f} to {ps['weigh_service_min']:.1f} minutes (modelled)."))
    s.append(P("1.1 At a glance for the judges", H2))
    s.append(table(["Criterion", "What this proposal shows", "Where"], [
        ["Problem significance", "The Port of Mombasa handled 45.45 million tonnes in 2025; Mariakani weighed 7,954-9,184 trucks a day in Jul-Sep 2026; import container dwell was 87 h against a 60 h target and Mombasa-Nairobi transit 66 h against 29 h (published, NCTTCA).", "Section 2.4"],
        ["Innovation", "Weigh once at the first trusted point and honour a signed Load Compliance Token downstream; a rolling verification lane replacing about 25 static lanes; one registry shared by all agencies; every number tagged with its provenance.", "Sections 4, 6.3"],
        ["Feasibility", "Not a concept: the platform is built, tested (177 automated tests) and live, on a hosted database; legal hooks identified regulation by regulation.", "Sections 5, 6"],
        ["Impact (modelled)", "Road static-scale stops 23.2 % to 5.3 % for port trucks; first-station static visits 20.8 % to 1.5 % at 90 % token coverage; port dwell -42 %.", "Section 8"],
        ["Evidence and rigour", "52-entry data register from KPA, KeNHA, NCTTCA, SCEA and KenTrade; Monte Carlo and discrete-event models with replications, sensitivity and a go/no-go gate.", "Sections 2.4, 7, 8"],
        ["Scalability", "Same token and registry serve every weighbridge on the Northern Corridor and inland depots; cloud platform; agency adapters for KPA, KRA, KenTrade, KEBS, KeNHA, NTSA.", "Sections 6, 9"],
        ["Sustainability", "Partner model allowed by Reg 3(3); loaders and fleets gain by avoiding stops, fees and detention; staged spend gated on validated results.", "Sections 5, 9.4"],
        ["Risks", "Named with mitigations: port access, scale approval, origin under-reporting, token fraud, land for lanes, model risk.", "Section 10"],
    ], widths=[32 * mm, 108 * mm, 30 * mm]))
    s.append(P("Decisions requested: approve the redesign around the port gate-out node and the token; approve Phases 0-2 including the 16-week "
               "simulation and baseline study with a gate before hardware spend; authorise approaches to KPA, KRA, KeNHA, NTSA and the "
               "weights-and-measures body; nominate an executive sponsor and a legal adviser."))

    # ------------------------------------------------------------------ 2 background
    s.append(P("2. Background and problem statement", H1))
    s.append(P("2.1 The corridor today", H2))
    s.append(P("The Northern Corridor carries port cargo from Mombasa to Nairobi and the region, and a large share of non-port traffic from mines, "
               "quarries, cement and sugar works, fuel depots and farms. Axle-load control is enforced at static weighbridges (Mariakani, Mtwapa, "
               "Athi River, Gilgil and others) under the EAC Vehicle Load Control Act and the 2018 Enforcement Regulations. High-speed "
               "weigh-in-motion (WIM) pre-screens traffic at some stations, but a static weighing is still the legal proof of overload, paper "
               "certificates and release orders travel with the driver, and every station repeats checks that an earlier station already made."))
    s.append(P("2.2 Where the chain duplicates checks and leaves gaps", H2))
    s.append(table(["Stage", "Checked today", "Duplication or gap", "RCS v2 response"], [
        ["Before arrival", "Manifest and ACD hold declared cargo weight", "Declared weight is never compared with measured truck weight", "Compute expected gross weight from declarations, container tare and truck tare, then compare with measurement"],
        ["Port entry", "Driver ID, licence, truck and trailer registration, access credentials, loading barcode", "Same identity data re-checked at loading and exit", "Enrol once; recognise by plate plus RFID tag"],
        ["Loading", "Container number matched to loading instruction; condition check; twist locks", "Container number checked again after loading and at exit", "Capture once at the gate-out portal with OCR and attach it to the token"],
        ["Exit inspection", "Container number, registrations, loading slip, seal, scanner, customs, shipping-line and KPA release, i-Gate validation, exit slip, KRA and KPA security verification", "Releases are electronic, yet two agencies re-verify physically and by document", "Show one release-status record to both agencies; physical checks only on exceptions"],
        ["Port exit to road", "No weight is measured", "The first weighing happens far from cranes, customs and yard space", "Weigh at the exit lane"],
        ["Weighbridges", "WIM, then static; paper certificate signed and stamped; presented again at later stations", "Repeated at each station", "Digital certificate and token lookup"],
        ["Transit cargo", "E-seal (ECTS), certificate at every station", "An overloaded transit vehicle waits for a customs officer to break the seal", "Registry alerts customs the moment an overload is confirmed"],
        ["Overload handling", "Fees, detention, paper release order carried through the journey", "Later stations rely on the paper", "Digital release order visible to every station"],
    ], widths=[24 * mm, 48 * mm, 48 * mm, 50 * mm]))
    s.append(P("2.3 Problem statement", H2))
    s.append(P("Compliant trucks lose time at every weighbridge because the system has no trusted record of an earlier weighing, overloaded trucks are "
               "discovered where correction is most disruptive, and high-speed WIM alone cannot supply the dimension, axle-configuration, permit and "
               "certificate checks that KeNHA performs at static bridges. The result is queues, fuel burnt idling, repeated manual verification and "
               "weak data for enforcement and planning."))

    # ------------------------------------------------------------------ 3 objectives
    s.append(P("2.4 The evidence: what published data shows", H2))
    s.append(P("Every figure below is published by an agency or the Northern Corridor Transit and Transport Coordination Authority (NCTTCA) "
               "and is held in the platform's data register with its period, source and classification."))
    s.append(table(["Indicator", "Value", "Period", "Source"], [
        ["Port of Mombasa throughput", "45.45 Mt (+10.9 %); 2.11 M TEU, over 35 % empty", "2025", "NCTTCA 21st edition"],
        ["Containerized import cargo dwell", "106.7 h (target 48 h); 87 h in Jul-Sep 2026 (target 60 h)", "2025; Q3 2026", "NCTTCA"],
        ["Customs release / after-release", "57 h / 79 h", "2025", "NCTTCA 21st edition"],
        ["Port truck turnaround", "6.7 h (7.1 h in 2022)", "2023", "KPA annual bulletin"],
        ["Mariakani trucks weighed per day", "7,954-9,184 (2,501-2,720 a year earlier)", "Jul-Sep 2026", "KeNHA via NCTTCA"],
        ["Mariakani compliance", "99.1-99.9 %", "Jul-Sep 2026", "KeNHA via NCTTCA"],
        ["National axle-load compliance", "98.43 % over 10,776 km", "FY 2024/25", "KeNHA Annual Report 2025"],
        ["Weighbridge crossing time", "about 4 min corridor average; Mariakani 29 min during road works", "2025", "NCTTCA 21st edition (GPS)"],
        ["Mombasa-Nairobi transit", "66 h over 482 km (target 29 h)", "2025", "NCTTCA 21st edition (RECTS)"],
        ["Mombasa-Malaba transit", "94 h (target 55 h)", "Jul-Sep 2026", "NCTTCA (URA RECTS)"],
        ["Agencies issuing permits", "about 26", "2024", "Shippers Council of Eastern Africa"],
    ], widths=[46 * mm, 62 * mm, 24 * mm, 38 * mm]))
    s.append(figure("fig-evidence-mariakani.png", "Figure A. Mariakani daily weighed traffic more than tripled year on year while compliance stayed near 99 % (published)."))
    s.append(P("Reading it: almost every truck is compliant, yet every truck is weighed again at every station, and the port and corridor run well "
               "above their dwell and transit targets. The opportunity is to stop re-checking compliant trucks and to move checks to where they are cheapest."))

    s.append(P("3. Objectives", H1))
    s.append(P("Main objective: remove repeat stops for compliant heavy trucks on the corridor by weighing each truck once at its first trusted point "
               "and honouring that result downstream, while keeping the static scale and the authorised officer as the legal reference for overloads."))
    s.append(P("Specific objectives:", H3))
    s.append(bullets([
        "Design and build the port gate-out weigh node, origin weigh nodes, road screening nodes, the rolling verification lane and the clearance registry, with the Load Compliance Token as the single record that links them.",
        "Cover every parameter KeNHA checks at a static bridge (gross and axle-group loads, axle count and lifted axles, left-right balance, dimensions, permits, certificates, release orders, seals) through sensors and registry checks.",
        "Anchor every decision in the 2018 Regulations: screening never replaces static weighing as proof, officers e-sign red cases, calibration is quarterly, devices are approved.",
        "Quantify the effect with a validated four-level simulation (sensor, process, road traffic, system) and a go/no-go gate before hardware spend.",
        "Run a shadow pilot (port exit lane, one origin site, one verification lane at Mariakani) and only then a live pilot with volunteer fleets.",
    ]))

    # ------------------------------------------------------------------ 4 proposed solution
    s.append(P("4. Proposed solution: RCS v2", H1))
    s.append(figure("fig-chain.png", "Figure 1. The RCS v2 clearance chain: five checkpoints and one registry.", 160 * mm))
    s.append(P("4.1 Three truck streams, one rule", H2))
    s.append(table(["Stream", "Examples", "First trusted weight", "Main risk"], [
        ["A. Port trucks", "Containers from Mombasa", "Port gate-out weigh node (tier 1)", "Cargo changes after the port (low)"],
        ["B. Industrial origin trucks", "Mine, quarry, cement, sugar, fuel depot, farm and factory loads", "Approved scale at the loading site linked to the registry (tier 2)", "Under-reported weights at private scales; bulk loads that shift or settle"],
        ["C. Untokened trucks", "Spot loads, traders, small fleets, first-time users", "First RCS road station or the rolling verification lane (tier 3)", "No earlier weight to compare, so more uncertainty"],
    ], widths=[32 * mm, 50 * mm, 50 * mm, 38 * mm]))
    s.append(P("A signed Load Compliance Token is issued at a truck's first verified weighing point and every later station honours it until it expires or a "
               "consistency check fails. Trust tiers set the audit rate: tier 1 (port) 2 %, tier 2 (approved origin scale) 4 % falling with a clean "
               "record, tier 3 (road node or lane) 3 %, tier 4 (on-board record only) always verified in the lane at first. Audit rates also rise with "
               "demerit points, so enforcement effort follows risk."))
    s.append(P("4.2 The Load Compliance Token", H2))
    s.append(P("Fields: tractor and trailer plates and RFID tag; container number (check digit verified) and e-seal; axle-group loads, gross weight, expected "
               "weight and their variance; issuing node, time stamp and validity window; a snapshot of customs, shipping-line and KPA release status; "
               "route, destination and the declared driver; dimensions, axle configuration and permit reference; token source and trust tier; and an "
               "Ed25519 signature so the record cannot be altered. Road nodes cache active tokens, roughly 8 000 a day."))
    s.append(P("4.3 Parameter coverage beyond weight", H2))
    s.append(table(["Parameter checked at a static bridge", "High-speed WIM alone", "Added in RCS v2"], [
        ["Gross vehicle weight; single axle and axle-group loads", "Estimate only", "Rolling verification lane at about 10 km/h on per-wheel scales (error target 1 %). Static scale remains legal proof for red cases"],
        ["Axle count, configuration, lifted axles", "A lifted axle looks like a missing one", "Side LiDAR and camera classification matched to the registered configuration"],
        ["Left-right imbalance", "Only with per-wheel strips", "Per-wheel scales in the lane, wheel-track position from WIM rows"],
        ["Height, width, length", "Not measured", "Overhead LiDAR portal, light curtain for over-height"],
        ["Special-load permit", "Not checked", "Plate links to a digital permit registry; scanner checks dimensions against the permit"],
        ["Identity, licence, insurance, roadworthiness", "Plate only", "ANPR, RFID and trailer pairing; registry links to NTSA and insurers later (flagged, not blocking)"],
        ["Earlier certificate, release order, transit seal", "Not checked", "Held digitally in the registry and shown to every station; e-seal status from KRA; customs alerted on confirmed overload"],
        ["Fee, certificate, signature, calibration status", "Not done", "Registry computes the fee from the schedule and allowance policy; an officer e-signs; calibration register with quarterly certificates"],
    ], widths=[52 * mm, 36 * mm, 82 * mm]))
    s.append(P("4.4 The Rolling Verification Lane", H2))
    s.append(P("A lane beside each station, reached by a diverge from the mainline screening node. Doubtful trucks and random audits roll through at about "
               "10 km/h over low-speed per-wheel scales, under a LiDAR dimension portal and cameras; the full parameter set is captured in 20-30 seconds "
               "with no stop. At 2.8 m/s and about 27 m per truck (17 m truck plus a 10 m gap) one truck passes every 9.7 seconds, about 370 an hour, "
               "against roughly 15 an hour for a static lane. Layout assumption: 100-150 m approach with speed signs, a flat concrete measuring zone of at "
               "least 15 m and a 50 m exit, about 250 m in all; land and civil works must be confirmed early. If the lane's scales gain "
               "weights-and-measures approval, only red trucks need a static scale; until then, trucks measured within the margin of the limit still do."))
    s.append(P("4.5 Decision rules", H2))
    s.append(table(["Where", "Result", "Conditions"], [
        ["Port", "Green", "Identity and releases valid, gross and axle-group loads below the limit after the margin, measured and expected weight within tolerance. Token issued"],
        ["Port", "Amber", "Near the limit or weight variance too large. Re-weigh in the port, correct if needed (customs present for sealed loads)"],
        ["Port", "Red", "Over the limit beyond the margin. Held for corrective action (blocking gate-out is a policy decision for KPA, KRA and KeNHA)"],
        ["Origin", "Green", "Approved scale reading below the limit after the margin, identity match, signed ticket. Origin token issued"],
        ["Road mainline", "Green", "Valid token and identity match, weight within tolerance of the token weight (about 8 % for port or origin tokens, 11 % for road tokens), dimensions inside limits, axle count matches. Or no token but weight below the limit by the full margin"],
        ["Road mainline", "Divert to lane", "No token and weight inside the margin band, inconsistent weight, dimension or axle-count mismatch, unreadable identity, or random audit"],
        ["Verification lane", "Green", "Full parameter set within limits after the margin. Token issued, valid downstream"],
        ["Verification lane", "Red", "Over the limit beyond the margin, dimension or permit breach, or inconclusive. Static scale and officer; hazardous and perishable flags change the handling"],
    ], widths=[28 * mm, 24 * mm, 118 * mm]))
    s.append(P("For loads in the margin band the road reading no longer has to be accurate against the limit; it only has to confirm that the weight is "
               "unchanged since the first trusted weighing, which is a much easier test."))
    s.append(P("4.6 What changes from the earlier proposal", H2))
    s.append(table(["Earlier", "Now", "Why"], [
        ["Weigh only on the road", "Weigh at each truck's first trusted point and honour it downstream", "Gives a reference and removes repeat stops"],
        ["Port trucks only", "All heavy trucks in three streams", "Mines, quarries and factories are part of the traffic"],
        ["Weight only", "Weight, dimensions, axle configuration, lifted axles, per-wheel balance, permits, certificates", "High-speed WIM misses most of what KeNHA checks at static bridges"],
        ["Judge absolute weight against the limit", "Compare with the token, absolute rule as fallback", "Removes the near-limit accuracy problem for tokened trucks"],
        ["Build our own road high-speed scales", "Reuse KeNHA's high-speed WIM feed, add our own verification lane", "Lower cost, and the lane supplies what the feed lacks"],
        ["Static scale for every doubtful truck", "Rolling lane for doubtful trucks, static scale for red cases", "One rolling lane equals about 25 static lanes"],
        ["Assumed pre-screening is acceptable", "Use Reg 10(2), seek approval under Reg 5, approved signs under Reg 9", "A legal basis for green decisions"],
        ["Simulate one road station", "Simulate the whole chain for three truck streams", "The gain comes from moving and merging work"],
    ], widths=[48 * mm, 62 * mm, 60 * mm]))

    # ------------------------------------------------------------------ 5 legal
    s.append(P("4.7 SmartPort: the eleven-stage port visit", H2))
    s.append(P("RCS v2 decides what happens on the road; SmartPort organises everything before it. One port-visit record follows each truck "
               "and checks that each stage carries the data it needs before the next can start. Stage 7 is the port gate-out weigh node: when a "
               "loaded truck crosses it, the visit records gross and net weight, the discrepancy against the declared weight and the token, with no manual entry."))
    s.append(table(["#", "Stage", "Key data captured", "Owner"], [
        ["1", "Pre-arrival registration and scheduling", "Truck, driver, container, cargo type, declared weight, destination, appointment", "Transporter, clearing agent"],
        ["2", "Customs clearance and document verification", "Declaration, bill of lading, duty, inspection and permit status, hold reason", "KRA, KenTrade, KEBS"],
        ["3", "Arrival and identification", "ANPR plate, RFID tag, appointment validity, queue position and wait", "KPA"],
        ["4", "Gate-in and security", "Gate, access authorisation, vehicle inspection, driver verification, processing time", "KPA"],
        ["5", "Yard allocation", "Terminal, block, container position, loading instruction, yard wait", "KPA"],
        ["6", "Cargo verification and loading", "Equipment, seal, match against documents, condition, loading time", "KPA"],
        ["7", "Automated weighing", "Gross, tare, net, axle loads, discrepancy, calibration, Load Compliance Token", "KPA, KeNHA"],
        ["8", "Final clearance", "Release status, delivery order, gate pass, payment", "KPA, KRA"],
        ["9", "Gate-out", "Exit gate, cargo verified, exit authorised, port dwell time", "KPA"],
        ["10", "Inland transport", "Route, distance, ETA, stoppages, delay reason", "Transporter, KeNHA"],
        ["11", "Delivery and trip closure", "Arrival, proof of delivery, total transit time", "Cargo owner"],
    ], widths=[8 * mm, 48 * mm, 82 * mm, 32 * mm]))
    s.append(P("Agencies keep their own systems: KPA (port operations), KRA (customs), KenTrade (TradeNet single window), KeNHA (axle loads), "
               "NTSA (vehicle registration and roadworthiness) and KEBS (product standards). SmartPort complements them through authorised "
               "adapters and a shared dashboard, so each agency sees release, weighing and location status without re-keying documents."))

    s.append(P("5. Legal and regulatory basis", H1))
    s.append(P("The EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018 set the rules. The platform encodes them as configuration "
               "flagged for verification, never as assumptions buried in code."))
    s.append(table(["Regulation", "What it says", "Design consequence"], [
        ["Reg 3(3)", "The roads authority may outsource weighbridge operation to private operators", "A legal route for a private partner role"],
        ["Reg 3(4), 11(3)", "Tickets and release orders for overloaded vehicles come from authorised officers", "The platform prepares everything; the officer e-signs red cases (MFA)"],
        ["Reg 4(5)-(6)", "Mobile weighbridges and surveillance technology may be used; a vehicle in breach is escorted to the nearest static weighbridge", "RCS readings decide who needs a static weighing; they never replace it as proof"],
        ["Reg 5", "Any weighbridge needs approval and a certificate from the weights-and-measures body", "Port and lane scales need approval; a legal-grade flag gates what a lane reading may settle"],
        ["Reg 6 and 8", "Calibration at least every three months by an accredited calibrator; audit every twelve months", "Quarterly calibration register; expired calibration blocks green"],
        ["Reg 9(1)", "Duty to submit for weighing arises on direction by an officer or a road sign", "Driver signals must be approved signs"],
        ["Reg 10(2)", "A vehicle previously confirmed within limits by screening devices need not produce the paper certificate", "The legal hook for the digital token replacing the paper certificate"],
        ["Reg 10(4)", "Certificates from any weighbridge are accepted as proof unless forged or tampered", "Tokens and certificates are signed and tamper-evident"],
        ["Reg 14", "Release orders travel with the journey; a repeat overload in the same journey triples the fee", "Digital release-order registry with repeat detection in the journey window"],
        ["Reg 18", "Transit certificates shown at every later weighbridge; overloaded transit vehicles detained until customs breaks the seal", "Customs alerted automatically on a confirmed transit overload"],
        ["Reg 20, Fifth Schedule", "Demerit points against vehicle, transporter and driver", "Demerits held in the registry and fed into audit rates"],
        ["Second Schedule", "Certificate records measured load, allowed load, a discretion allowance below 5 %, adjusted load, overload and fee", "Allowance is a policy value to agree with KeNHA; it changes the stop share materially"],
        ["Third Schedule, Reg 13", "Legal weights (steering 8 t, single drive 10 t, tandem 18 t, tridem 24 t); fee table (5 000 kg over gross about 2 990 USD); detention free three days then 50 USD a day", "Values in configuration, flagged for verification; strong incentive to join the programme"],
    ], widths=[28 * mm, 72 * mm, 70 * mm]))
    s.append(P("Two limits follow. A reading from screening devices cannot replace static weighing as proof of overload (Reg 4(6), 18(3)), and fees and "
               "release orders for overloaded trucks must come from an authorised officer. Open legal questions: whether Reg 10(2) covers a digital "
               "status, who must approve the devices, whether an officer may e-sign remotely, and whether low-speed in-motion weighing can be approved "
               "as legal-grade."))

    # ------------------------------------------------------------------ 6 implementation status
    s.append(P("6. System architecture and current implementation", H1))
    s.append(P("6.1 Architecture", H2))
    s.append(table(["Element", "Where", "Job"], [
        ["A. Port gate-out weigh node", "KPA exit lane, beside the i-Gate", "Low-speed weighing of every loaded truck; reads plate, RFID tag, container number and e-seal; compares measured with expected weight; issues the token"],
        ["B. Origin weigh nodes", "Mines, quarries, factories, depots", "Approved scale at the loading site linked to the registry; issues an origin token"],
        ["C. Road screening nodes", "Mariakani, Athi River, Mtwapa and other stations", "Existing high-speed WIM feed plus plate, tag and LiDAR readers; checks tokens and issues road tokens"],
        ["D. Rolling verification lane", "Beside each road station", "Low-speed scales, dimension portal and cameras; captures every static-bridge parameter without stopping"],
        ["E. Static scales", "Existing weighbridges and a port re-weigh lane", "Legal proof for red cases and audits; results feed calibration"],
        ["Clearance registry", "Cloud, with edge caches at each site", "One record per truck-journey: tokens, weights, dimensions, certificates, permits, release orders, demerit points, release status"],
    ], widths=[40 * mm, 46 * mm, 84 * mm]))
    s.append(P("6.2 What is already built", H2))
    s.append(P("The project is not a blank sheet: the software platform exists, is tested and is deployed. The table lists the state on " + TODAY + "."))
    s.append(table(["Component", "State", "Notes"], [
        ["Clearance engine (clr-2.0.0)", "Built, 78 API tests", "Deterministic rules: token consistency, dimension, lifted axle, permit, discretion allowance, tiered audits, route (continue / lane / static / port re-weigh / hold); evidence hash per decision"],
        ["Clearance registry API", "Built", "Load Compliance Tokens (issue, honour, suspend, public verify), Reg 14 release orders with officer e-signature and repeat tripling, special-load permits, trust-tier policy, stream and route statistics"],
        ["Legal configuration", "Built, flagged", "2018 Regulations schedule, allowance, dimension limits, indicative fee table, detention terms; every value marked for verification"],
        ["Web application", "Built, deployed", "Control centre, weighbridge console, clearance registry, RCS v2 model explorer, transporter, driver, cargo owner, warehouse, admin, public verify and About pages, 3D digital twin with sequential truck flow"],
        ["Mobile apps", "Written, not compiled", "Flutter driver (hands-free) and cargo-owner apps"],
        ["Roadside gateway", "Built, 22 tests", "Store-and-forward outbox, local clearance mirror, identity adapters, VMS driver"],
        ["Firmware and hardware", "Designed, not fabricated", "STM32H743 + ADS131M08 acquisition firmware, ESP32 auxiliary node, analog front end, power, enclosure, BOM, verification-lane and port-node layouts"],
        ["Simulation package", "Built, 32 tests", "RCS v2 chain Monte Carlo, experiments (replications, sweeps, tornado, gate), SimPy station model with tokens and lane, SUMO adapter"],
        ["Cloud", "Deployed", "Vercel (functions in Dublin) + Supabase PostgreSQL (Ireland); AWS production design in Terraform, validated, not applied"],
        ["Security", "Built", "RBAC, MFA for privileged roles, Argon2 passwords, Ed25519-signed tickets/tokens/orders, hash-chained ledger, PII encryption, DPIA under the Data Protection Act 2019"],
    ], widths=[40 * mm, 30 * mm, 100 * mm]))
    s.append(P("Honesty rules carried by the platform: every weighing record carries a source of live, simulated or replay and simulated data is never shown "
               "as live; government adapters are mock until credentials are authorised; environmental and chain-model figures are labelled modelled; "
               "accuracy and latency targets remain targets until measured."))

    # ------------------------------------------------------------------ 7 simulation methodology
    s.append(P("6.3 Data provenance", H2))
    s.append(P("Every parameter carries one of four classes: actual (operational records), published (agency or NCTTCA reports), estimated "
               "(design assumptions) or simulated (model output). The register currently holds 52 entries; the port gate service times and "
               "gate-side truck volumes are estimated because they are not published, and are first in line for replacement with KPA gate logs. "
               "The web platform shows the class beside every figure, and simulated records are never displayed as live."))

    s.append(P("7. Simulation methodology", H1))
    s.append(P("7.1 Questions the simulation answers", H2))
    s.append(bullets(["How many stops and how much delay does each design remove?", "How accurate must the port and road scales be?",
                      "How robust is the system to low token coverage, outages and traffic peaks?", "Can the port re-weigh stage cope with the volume?",
                      "Do queues at the port exit and the weighbridge stay stable?"]))
    s.append(P("7.2 Four linked levels", H2))
    s.append(table(["Level", "Simulates", "Tools", "Output"], [
        ["L1 Sensor and algorithm", "Truck dynamics on a rough road, tyre contact, sensor response, temperature drift and noise, then the weight estimator", "Python (NumPy, SciPy), quarter-car model", "Error curves by speed, load and temperature; they set the port and road errors used in L2"],
        ["L2 Process", "The whole chain for three truck streams, as-is and to-be, as a discrete-event model", "SimPy; the Monte Carlo chain model", "Stops, delays, queues, truck-hours, false-clear rate"],
        ["L3 Road traffic", "Approach lanes, diverge lanes, the verification lane and queue spillback onto the mainline", "SUMO with TraCI", "Queue lengths, spillback risk, diverge lane length"],
        ["L4 System and hardware-in-the-loop", "Token service, APIs and edge pipeline under load and failure", "FastAPI mock agencies, Locust, Mosquitto MQTT, recorded signals replayed into the bench rig", "Latency, failover behaviour, data integrity"],
    ], widths=[32 * mm, 56 * mm, 38 * mm, 44 * mm]))
    s.append(P("7.3 The two L2 models used in this proposal", H2))
    s.append(P("The chain model is a vectorised Monte Carlo of the whole clearance chain. Each truck draws a true load from a normal distribution with mean "
               "equal to the average loading (75-90 % of the legal limit) and a spread of 12 % of the limit, capped just below the limit so that heavily "
               "loaded fleets bunch at it; 1.5 % of trucks are overloaded (from the reported 98.5 % compliance), uniformly 0-15 % over. Every node "
               "reads the true load with its own relative error: port 1 %, origin 1 %, road 2.5 %, lane 1 %. A screening node sends a truck for a closer "
               "look when reading x (1 + 2 x error) exceeds the limit (expanded uncertainty, k = 2, the same convention as the clearance engine). A "
               "tokened truck on the road is only checked for consistency: it passes when the road reading is within three combined standard "
               "deviations of the token weight, about 8 % for port and origin tokens and 11 % for road tokens. Random audits of 3 % go through the "
               "lane. Common random numbers make the comparison between policies paired rather than noisy."))
    s.append(P("The station model is a discrete-event queue model in SimPy: non-homogeneous Poisson arrivals with an hour-of-day profile, two high-speed "
               "WIM lanes, five static bays with a four-minute median service, two inspection bays, and in the RCS v2 policy a rolling verification "
               "lane resource (one lane, 90-second median pass), token coverage, token error, a share of trucks whose cargo changed after the token, "
               "and lane closures. Decisions come from the production clearance engine so the simulation and the live platform can never disagree on "
               "policy. The station model keeps a heavier synthetic population (15 % overloaded) than the chain model, so its absolute shares differ; "
               "it is used for queues, lane capacity and closure behaviour, not for the headline stop shares."))
    s.append(P("7.4 Experiment design, verification and validation", H2))
    s.append(bullets([
        "Factors: average loading 75-90 %, port error 0.5-2 %, road error 1.5-4 %, token coverage 50-100 %, peak factor 1.0-2.0, outage frequency and duration, audit share 1-5 %.",
        "30 replications per scenario with different seeds and common random numbers; means reported with 95 % confidence intervals (Student t).",
        "KPIs: stops per 1 000 trucks, mean and 95th-percentile delay, truck-hours a day, maximum queue, false-clear rate, port re-weigh load, port yard dwell effect.",
        "Verification: unit tests, conservation checks (every truck exits once), hand-traced single trucks, comparison of a single-server version with the Erlang C formula.",
        "Validation: compare simulated as-is delays and queues with measured baselines; accept if the mean delay is within about 15 % and peak queues align; review the model with KPA and KeNHA staff. A tornado chart shows the committee which assumptions matter most.",
        "If data access is delayed: a two-week time-and-motion and counting study with cameras and stopwatches, results flagged provisional.",
    ]))

    # ------------------------------------------------------------------ 8 results
    s.append(PageBreak())
    s.append(P("8. Simulation results (modelled)", H1))
    s.append(P("All figures in this section were generated from the repository's simulation package on " + TODAY + " with the assumptions stated in "
               "section 7. They are model outputs, not measurements, and they are the author's estimates to be replaced by observed data in "
               "Phase 0-2.", NOTE))
    s.append(P("8.1 Port trucks: effect by average loading", H2))
    rows = [[fmt(r["avg_loading_pct"], 0) + " %", fmt(r["road_only_static"]) + " %", fmt(r["road_only_with_allowance"]) + " %", fmt(r["v2_road_static"]) + " %", fmt(r["v2_port_reweigh"]) + " %", "about " + fmt(r["truck_hours_saved_per_day"], 0)] for r in chain["port_table"]]
    s.append(table(["Average load (% of limit)", "Road-only screening", "Road-only with 5 % allowance", "RCS v2 road stops", "RCS v2 port re-weigh", "Road truck-hours saved per day (v1 to v2)"], rows,
                   widths=[30 * mm, 26 * mm, 30 * mm, 26 * mm, 28 * mm, 30 * mm]))
    s.append(P("Truck-hours use 8 000 trucks a day and 6 minutes per stop, so one percentage point is 8 truck-hours. 600 000 trucks per row.", SMALL))
    s.append(figure("fig-port-table.png", "Figure 2. Static-scale visits of port trucks by policy and average loading (modelled)."))
    s.append(P("Reading it honestly: v2 does not delete the near-limit checks, it moves them from the public road to the port, where trucks are already in "
               "a controlled area with cranes and customs. At 85 % loading there are still about as many re-weighs in total (5.3 % on the road plus "
               "14.8 % at the port versus 23.2 % on the road). The saving comes from relieving road queues and from fixing overloads where it is cheap, "
               "and the more heavily loaded the fleet, the larger the shift."))
    s.append(P("8.2 Mixed traffic: effect by token coverage", H2))
    rows = [[fmt(r["token_coverage"] * 100, 0) + " %", fmt(r["first_station_lane"]) + " %", fmt(r["first_station_static"]) + " %", fmt(r["road_only_baseline_static"]) + " %", fmt(r["later_station_lane"]) + " %", fmt(r["later_station_static"], 2) + " %", "about " + fmt(r["truck_hours_saved_first_station"], 0)] for r in chain["mixed_table"]]
    s.append(table(["Trucks with a port or origin token", "First station: sent to the lane", "First station: static scale", "Road-only baseline (static)", "Later stations: lane", "Later stations: static", "Truck-hours saved per day at the first station"], rows,
                   widths=[26 * mm, 24 * mm, 24 * mm, 24 * mm, 22 * mm, 22 * mm, 28 * mm]))
    s.append(figure("fig-mixed-coverage.png", "Figure 3. Where trucks are checked at the first and at later stations as token coverage rises (85 % loading, modelled)."))
    s.append(bullets([
        "Later stations: once every truck carries a token (port, origin or road), about 3.3 % go to the lane (audits and mismatches) and almost none to a static scale. This is where the repeat stops disappear.",
        f"Untokened trucks alone: the lane trims static-scale visits only from about 21 % to {fmt(chain['defaults']['shares']['untokened_static'], 0)} % of those trucks. The rest are loaded within the 2 % margin of the limit and need either a legal-grade lane reading or the discretion allowance.",
        f"Capacity: at 500 trucks an hour the modelled lane peak is about {fmt(chain['defaults']['lane_peak_per_hour'], 0)} trucks an hour against a capacity near {fmt(chain['defaults']['lane_capacity_per_hour'], 0)}, so one lane per station is enough.",
        "Fleet enrolment is therefore a core workstream: token coverage is the lever that moves the road stop share most.",
    ]))
    s.append(P("8.3 Sensitivity", H2))
    sw = chain["sweep_coverage"]["rows"]; se = chain["sweep_port_error"]["rows"]; sa = chain["sweep_allowance"]["rows"]
    s.append(bullets([
        "Token coverage: at 85 % loading the road stop share is " + ", ".join(f"{fmt(r['v2_road_static'])} % at {fmt(r['value'] * 100, 0)} %" for r in sw) + " coverage.",
        "Port scale accuracy mainly moves the port re-weigh share (" + ", ".join(f"{fmt(r['v2_port_reweigh'])} % at {r['value']} % error" for r in se) + ") and barely changes the road stop share.",
        "Discretion allowance at the port: re-weighs fall to " + ", ".join(f"{fmt(r['v2_port_reweigh'])} % at {r['value']} %" for r in sa) + ". Applying the allowance is a policy decision for KeNHA; approving the port scale as legal-grade has a similar effect.",
    ]))
    s.append(figure("fig-sensitivity.png", "Figure 4. One-factor sweeps: coverage drives road stops; port error and allowance drive port re-weighs (modelled).", 160 * mm))
    s.append(figure("fig-tornado.png", "Figure 5. Tornado chart: swing of the RCS v2 road stop share across each factor's low-high range (modelled)."))
    s.append(P("8.4 Replication and confidence intervals", H2))
    rep = chain["replicate"]["outputs"]
    rows = [[k.replace("_", " "), fmt(v["mean"], 2), f"{fmt(v['ci_low'], 2)} - {fmt(v['ci_high'], 2)}"] for k, v in rep.items() if k != "false_clear_rate"]
    rows.append(["false clear rate", f"{rep['false_clear_rate']['mean'] * 100:.4f} %", f"{rep['false_clear_rate']['ci_low'] * 100:.4f} - {rep['false_clear_rate']['ci_high'] * 100:.4f} %"])
    s.append(table(["Output (defaults: 85 % loading, 90 % coverage)", "Mean", "95 % confidence interval"], rows, widths=[80 * mm, 30 * mm, 60 * mm]))
    s.append(figure("fig-replications.png", "Figure 6. Means and 95 % confidence intervals over 30 replications (200 000 trucks each). Intervals are narrow: the uncertainty that matters is in the assumptions, not the sampling."))
    s.append(P("8.5 Go/no-go gate", H2))
    g = chain["gate"]
    rows = [[c["name"].replace("_", " "), fmt(c["value"], 2), fmt(c["threshold"], 2), "pass" if c["ok"] else "FAIL", clean(c.get("detail", ""))] for c in g["checks"]]
    s.append(table(["Check", "Value", "Threshold", "Result", "Detail"], rows, widths=[40 * mm, 18 * mm, 20 * mm, 16 * mm, 76 * mm]))
    s.append(P(("The model meets the gate (proceed = yes). " if g["proceed"] else "The model does not meet the gate. ") +
               "The gate is applied again to the validated model after the baseline study: proceed to the shadow pilot only if the validated model "
               "cuts the road stop share by at least 10 points against the measured baseline, or removes recurring peak saturation, with a false-clear "
               "rate at or below 1 % and a port re-weigh volume that KPA confirms is practical. Otherwise the project narrows to a vehicle-side or "
               "registry-only offering."))
    s.append(P("8.6 Station queue model (SimPy)", H2))
    o = simpy["outcomes"]
    order = ["baseline_all_stop", "rolling_clearance", "arrivals_+50", "rcs_v2_untokened", "rcs_v2_tokens_50", "rcs_v2_tokens_90", "rcs_v2_allowance_5pct", "rcs_v2_lane_closure"]
    rows = []
    for n in order:
        if n not in o:
            continue
        m = o[n]["summary"]
        rows.append([n, fmt(m["trucks"]["mean"], 0), fmt(m["mean_tis_min"]["mean"]), fmt(m["p90_tis_min"]["mean"]), fmt(m["max_queue_static"]["mean"], 0), fmt(m["pct_stopped"]["mean"]) + " %", fmt(m["pct_lane"]["mean"]) + " %", fmt(m["static_utilisation_pct"]["mean"], 0) + " %"])
    s.append(table(["Scenario", "Trucks (12 h)", "Mean time in system (min)", "P90 (min)", "Max static queue", "% stopped", "% via lane", "Static utilisation"], rows,
                   widths=[36 * mm, 18 * mm, 24 * mm, 16 * mm, 20 * mm, 18 * mm, 18 * mm, 20 * mm]))
    s.append(P(f"Means over {simpy['replications']} replications of {simpy['hours']:.0f} h; 60 trucks an hour mean demand with a synthetic hour-of-day profile. "
               "The all-stop baseline saturates the static scale (every truck stops); rolling clearance stops about a fifth; RCS v2 moves most of those into "
               "the lane without stopping and keeps the static scale below 10 % utilisation. The +50 % demand scenario shows rolling clearance alone "
               "starting to load the static scale again, which the lane absorbs. A two-hour lane closure sends doubtful trucks back to the static scale, "
               "as designed.", SMALL))
    s.append(figure("fig-simpy-scenarios.png", "Figure 7. Share of trucks stopped at the static scale and share rolling through the verification lane, by scenario (modelled)."))
    s.append(figure("fig-simpy-queue.png", "Figure 8. Mean static-scale queue through the day: all-stop baseline, rolling clearance, RCS v2 with 90 % token coverage (modelled)."))
    s.append(P("8.7 Port process: existing operations vs SmartPort", H2))
    s.append(P(f"A discrete-event model of stages 3-11 (gates, yard, loading, weighing, clearance with document holds, gate-out, inland transit), "
               f"{port['inputs']['reps']} replications. {port['calibration_note']}"))
    keys = [("avg_dwell_h", "Mean port dwell (h)"), ("p90_dwell_h", "P90 port dwell (h)"), ("avg_wait_min", "Queue waiting per truck (min)"),
            ("weigh_service_min", "Weighbridge service (min)"), ("throughput_per_hour", "Gate-out throughput (trucks/h)"),
            ("gate_in_utilisation", "Gate-in utilisation"), ("weigh_utilisation", "Weighbridge utilisation")]
    s.append(table(["KPI", "Existing", "SmartPort", "Change"],
                   [[lab, fmt(pe[k], 2), fmt(ps[k], 2), f"{port['deltas'][k + '_pct']:+.0f} %"] for k, lab in keys], widths=[70 * mm, 30 * mm, 30 * mm, 40 * mm]))
    s.append(figure("fig-port-sim.png", "Figure 9. Port visit KPIs with the KPA 2023 truck-turnaround benchmark (modelled)."))
    s.append(bullets([a for a in port["assumptions"]], SMALL))

    s.append(P("8.8 Not yet counted", H2))
    s.append(P("Time saved from removed duplicate checks at port entry, loading and exit; fees and detention avoided by transporters; customs benefits from "
               "catching weight misdeclaration; fuel and emissions from avoided idling (the platform's environmental model labels these modelled). The "
               "baseline study must time each duplicate check before these are claimed."))

    # ------------------------------------------------------------------ 9 roadmap
    s.append(PageBreak())
    s.append(P("9. Implementation roadmap", H1))
    s.append(table(["Phase", "When", "What happens", "Exit gate"], [
        ["0-1. Access and legal", "Months 0-3", "Meet KPA, KRA, KeNHA, NTSA, KenTrade, the weights-and-measures body, the Kenya Transporters Association and two or three candidate loaders. Request data. Get a legal opinion on Reg 10(2), Reg 5, Reg 3(4) and digital certificates", "MoUs or written interest, data access agreed, legal route clear"],
        ["2. Baseline and design", "Months 3-7", "Time-and-motion study at the port exit and Mariakani; classification count for the real share of port and non-port trucks; study of dimension and lifted-axle violations; run and validate the simulation; specify token, APIs and security", "Simulation shows the gate is met"],
        ["3. Bench prototype", "Months 6-11", "Scale-model rig, token service, OCR on recorded video, LiDAR dimension portal test, per-wheel scale test, mock agency APIs, replay of recorded signals", "Latency and repeatability targets met on the rig"],
        ["4. Shadow pilot", "Months 10-16", "One port exit lane, one origin site and a verification lane at Mariakani; tokens issued and compared, nobody acts on them", "Accuracy and false-clear targets met over a sustained period"],
        ["5. Live pilot", "Months 16-24", "Volunteer fleets and loaders use the green lane; approved signs; static scale audits continue; seek approval of lane scales as legal-grade", "Agency approval to operate live, then scale to other stations"],
    ], widths=[30 * mm, 22 * mm, 80 * mm, 38 * mm]))
    s.append(P("9.1 Simulation work plan (16 weeks, Phase 2)", H2))
    s.append(table(["Weeks", "Work"], [
        ["1-2", "Baseline study plan and data requests"], ["3-4", "L1 sensor and algorithm model"], ["5-8", "L2 process model, verification and first scenarios"],
        ["9-10", "L3 road traffic model"], ["11-14", "L4 token service, mock APIs and hardware-in-the-loop"], ["15-16", "Validation, sensitivity, committee report"],
    ], widths=[25 * mm, 145 * mm]))
    s.append(P("9.2 Integration map", H2))
    s.append(table(["System", "Data exchanged", "Dependency risk"], [
        ["KPA gate systems (i-Gate, KWATOS)", "Gate events, release status, exit slip", "KPA must allow a weigh node in the exit lane"],
        ["KRA (iCMS, ACD, tracking seals)", "Release status, declared weight, seal ID, overload alerts", "Data-sharing agreement"],
        ["KeNHA control centre and WIM feed", "Road weights, static results, certificates, release orders, officer e-signature", "Access to the feed or permission to add readers and a lane"],
        ["Loading-site scales (private)", "Signed tickets, calibration certificates", "Approval and audit of each scale"],
        ["NTSA vehicle and permit records", "Registration, tare, axle configuration, special-load permits", "Data quality"],
        ["KenTrade and clearing agents; insurers (later)", "Document status; insurance validity", "Optional first, deeper later"],
    ], widths=[50 * mm, 70 * mm, 50 * mm]))
    s.append(P("9.3 Deliverables by phase", H2))
    s.append(bullets([
        "Phase 0-1: stakeholder MoUs, data-sharing agreements, legal opinion, data-protection registration plan.",
        "Phase 2: baseline study report, validated simulation with sensitivity analysis, token and API specification, security design, go/no-go recommendation.",
        "Phase 3: bench rig results (latency, repeatability, OCR accuracy, dimension portal accuracy), hardware-in-the-loop report.",
        "Phase 4: shadow pilot accuracy report (WIM and lane versus static), false-clear and identity rates, token consistency statistics, origin drift detection record.",
        "Phase 5: live pilot KPIs, regulator pack, approval applications for the port and lane scales.",
    ]))
    s.append(P("9.4 Cost drivers", H2))
    s.append(P("A costed budget is prepared with stakeholders in Phase 0-1 once site access, the WIM feed arrangement and the number of lanes are known. "
               "The main drivers are: the port gate-out node (low-speed scale, readers, portal, civil works in the KPA exit lane), one rolling verification "
               "lane per station (about 250 m of approach, measuring zone and exit, per-wheel scales, LiDAR portal, cameras, cabinet and power), origin "
               "node readers and registry integration at each approved loader, quarterly accredited calibration and the twelve-month audit (Reg 6 and 8), "
               "weights-and-measures approvals, cloud hosting and support, the baseline study, and fleet enrolment (tags, onboarding). Reusing KeNHA's "
               "high-speed WIM feed rather than building road scales is the largest avoided cost."))

    # ------------------------------------------------------------------ 10 risks
    s.append(P("10. Risks and mitigations", H1))
    s.append(table(["Risk", "Mitigation"], [
        ["KPA may not allow a weigh node in the exit lane, or may not accept weight as a gate-out condition", "Early engagement; the port node can start as advisory (shadow); the design also works with the first road station as the first trusted point"],
        ["A port or lane scale needs weights-and-measures approval; without legal-grade status, near-limit trucks still need static weighing", "Seek approval early; model both cases; apply the discretion allowance where KeNHA agrees"],
        ["Private origin scales may under-report", "Approval and audit of each scale; comparison of origin readings with road and lane readings; token suspension for drift"],
        ["Token fraud: swapped plates or cargo added after the first weighing", "Bind the token to plate, tag and seal; weight consistency on the road; audits; demerits"],
        ["Legitimate weight changes (partial offloads, fuel use)", "Validity window and tolerance; a lane pass renews a token"],
        ["Untokened and first-time trucks carry more uncertainty", "Verification lane; fleet and loader enrolment as a core workstream"],
        ["Land and civil works for the lane at each station", "Confirm availability early; enforce speed discipline with approved signs"],
        ["Officers must still sign tickets and release orders (Reg 3(4), 11(3))", "E-signature workflow with MFA; legal opinion on remote signing"],
        ["Data-sharing delays and cybersecurity", "Signed records, audit logs, DPIA under the Data Protection Act 2019, two-week provisional study if data is late"],
        ["Model risk: assumptions differ from reality", "Validation against measured baselines before any claim; tornado analysis; gate re-applied on validated model"],
    ], widths=[75 * mm, 95 * mm]))

    # ------------------------------------------------------------------ 11 M&E
    s.append(P("11. Monitoring and evaluation", H1))
    s.append(table(["Indicator", "Target (engineering target until measured)", "How measured"], [
        ["False-clear rate among green decisions", "at most 1 %", "Shadow pilot: green decisions paired with static results"],
        ["WIM and lane accuracy", "95 % of gross errors within +/-5 % (WIM); lane error target 1 %", "Paired passes per lane, speed band and temperature band"],
        ["Identity match rate", "at least 97 %", "Confidence at or above 0.90 and correct vehicle versus operator-confirmed plate"],
        ["Decision latency at the edge", "at most 2 000 ms at P99", "Gateway latency distribution"],
        ["Road stop share at the first station", "at least 10 points below the measured baseline", "Station logs before and after"],
        ["Token consistency rate", "reported; suspensions investigated", "Registry statistics"],
        ["Origin scale drift", "detected and acted on", "Origin readings versus road and lane readings"],
        ["Availability", "99.9 % for the registry and nodes", "Monitoring"],
    ], widths=[50 * mm, 60 * mm, 60 * mm]))

    # ------------------------------------------------------------------ 12 decisions
    s.append(P("12. Decisions requested", H1))
    s.append(ListFlowable([ListItem(P(t), leftIndent=10) for t in [
        "Approve the redesign around the port gate-out weigh node and the Load Compliance Token.",
        "Approve Phases 0-2, including the 16-week simulation and the baseline study, with a gate before any hardware spend.",
        "Authorise approaches to KPA, KRA, KeNHA, NTSA and the weights-and-measures body.",
        "Nominate an executive sponsor and a legal adviser.",
    ]], bulletType="1", leftIndent=14))

    # ------------------------------------------------------------------ appendices
    s.append(PageBreak())
    s.append(P("Appendix A. Data requests", H1))
    s.append(table(["Dataset", "Owner", "Use"], [
        ["Gate-out and i-Gate timestamps, exit slips", "KPA", "Port exit delay and duplicate checks"],
        ["Weighbridge logs: time, gross and axle loads, outcome", "KeNHA", "Loading distribution, baseline stops and delays"],
        ["Release timestamps, declared weights sample, tracking-seal events", "KRA", "Expected weight, misdeclaration rate, transit flows"],
        ["Tare weights and axle configurations", "NTSA", "Expected-weight calculation"],
        ["Fleet and trip-plan information", "Kenya Transporters Association", "Enrolment and coverage estimates"],
    ], widths=[70 * mm, 40 * mm, 60 * mm]))
    s.append(P("Plates and driver details are anonymised before analysis, in line with the Data Protection Act, 2019."))
    s.append(P("Appendix B. Open questions to confirm", H1))
    s.append(bullets([
        "What share of trucks at Mariakani and other stations come from the port, from industrial origins and from elsewhere?",
        "Does KeNHA already share road WIM results with KPA or KRA, and can the raw feed be obtained?",
        "Does the port already weigh imports at the gate?",
        "Which dimension limits, lifted-axle and permit checks does KeNHA enforce at static bridges today, and how often are they violated?",
        "Can the Reg 10(2) screening exemption apply to a digital token, who must approve the devices, and can an authorised officer e-sign remotely?",
        "Can low-speed in-motion weighing be approved as legal-grade? Is the 5 % discretion allowance applied routinely?",
        "Which route-specific limits apply, and does the 34-tonne container limit still hold?",
    ]))
    s.append(P("Appendix C. Model assumptions", H1))
    s.append(table(["Parameter", "Value", "How to measure"], [
        ["Static scale lanes and service time", "8 lanes (plan) / 5 bays (station model), 4 minutes", "Observe at Mariakani, request logs"],
        ["Extra time to stop and rejoin traffic", "2 minutes", "Stopwatch and cameras"],
        ["Port exit validation time; duplicate checks", "Unknown", "Time-and-motion at the i-Gate; count and time each"],
        ["Port scale approach speed; lane speed", "10 km/h", "Design choice"],
        ["Token coverage; audit share", "90 %; 3 %", "Enrolment plan; policy"],
        ["Share of loads near the limit", "Mean 75-90 % of limit, spread 12 %", "Weighbridge logs"],
        ["Scale errors: port, origin, road, lane", "1 %, 1 %, 2.5 %, 1 %", "L1 model, calibration records, shadow pilot"],
        ["Lane pass cost; static stop cost; headway", "1.5 min; 6 min; 27 m at 10 km/h", "Design assumption, to time in the pilot"],
        ["Arrivals", "8 000 trucks a day; peak factor 1.5; bursts after vessel discharge", "KPA and KeNHA logs"],
    ], widths=[60 * mm, 55 * mm, 55 * mm]))
    s.append(P("Appendix D. Sources", H1))
    s.append(bullets([
        "NCTTCA, 21st Edition Northern Corridor Transport Observatory Report, April 2026 (2025 data): top.ttcanc.org/uploads/attachments/cmownhhl201qpfmqhl5ikzprd-en-21-top-report.pdf",
        "NCTTCA, Quarterly Performance Report July-September 2026: top.ttcanc.org/uploads/attachments/cmvo7m7gv00qfwznu9zlgz9zh-quarterly-report-july-to-september-2026.pdf",
        "KeNHA Annual Report 2025: kenha.co.ke/wp-content/uploads/2026/06/KeNHA-ANNUAL-REPORT-2025-WEB-VERSION.pdf",
        "KPA annual bulletins via Kenya News Agency and The Star (2023 truck turnaround 6.7 h; 2024 throughput and ship times).",
        "Shippers Council of Eastern Africa (dwell history, permit agencies); KenTrade single window reports (agencies connected, document reduction).",
        "Full list with URLs and periods: docs/06-operations/data-register.md and the live Data register page.",
    ]))
    s.append(bullets([
        "EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018 (full text, bdears.busitema.ac.ug).",
        "Process guide supplied by the project owner covering ship arrival, customs, port release, truck exit and weighbridges, citing KRA, KPA, KeNHA, InfoTrade Kenya and the Kenya Transporters Association; reported gross limits and 2026 events not independently re-verified.",
        "Earlier RCS decision brief and hardware analysis: sensor, calibration and benefit assumptions.",
        "Repository documents: docs/01-requirements/rcs-v2-port-anchored-clearance.md, legal-hooks-eac-vlc-2018.md, docs/06-operations/rcs-v2-simulation-plan.md, simulation-guide.md, the engineering report and the requirements traceability matrix (" + REPO + ").",
        "Simulation outputs used here: docs/07-proposal/assets/chain-results.json and simpy-comparison.json, regenerated with make_charts.py and build_proposal.py.",
    ]))

    doc = Doc(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
              title="KIFARU PORTOS - Project Proposal (RCS v2)", author="KIFARU PORTOS project team", subject="Port-anchored clearance: implementation and simulation plan")
    doc.multiBuild(s, onFirstPage=on_page, onLaterPages=on_page)
    print("written:", OUT)


if __name__ == "__main__":
    build()
