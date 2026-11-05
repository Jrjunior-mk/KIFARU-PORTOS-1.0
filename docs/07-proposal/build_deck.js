/**
 * KIFARU PORTOS - RCS v2 proposal deck (pptxgenjs, structured: theme + layouts + placeholders + sections).
 *   NODE_PATH=<dir with pptxgenjs> node docs/07-proposal/build_deck.js
 * Reads the simulation outputs in ./assets so the charts are native PowerPoint charts of the modelled results.
 */
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL_DIR + "/scripts/apply_theme.js");

const HERE = __dirname;
const A = path.join(HERE, "assets");
const OUT = path.join(HERE, "KIFARU-PORTOS-Proposal-Deck.pptx");
const chain = JSON.parse(fs.readFileSync(path.join(A, "chain-results.json"), "utf8"));
const simpy = JSON.parse(fs.readFileSync(path.join(A, "simpy-comparison.json"), "utf8"));
const LIVE = "kifaru-portos-1-0.vercel.app";

const THEME = {
  name: "Kifaru Harbour",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: { dk1: "0F172A", lt1: "FFFFFF", dk2: "334155", lt2: "F1F5F9", accent1: "0D9488", accent2: "D97706", accent3: "DC2626", accent4: "16A34A", accent5: "0EA5E9", accent6: "64748B", hlink: "0D9488", folHlink: "0D9488" },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "KIFARU PORTOS - RCS v2 port-anchored clearance - project proposal";
pres.author = "KIFARU PORTOS project team";
pres.subject = "Project proposal deck";
const C = pres.SchemeColor;

const FOOTER = "KIFARU PORTOS  |  RCS v2 port-anchored clearance  |  simulation figures are modelled, not measured";

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
  title: "DARK",
  background: { color: HEX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.45, w: 8.8, h: 1.4, fontSize: 36, bold: true, color: C.background1, valign: "bottom", margin: 0 } } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 2.95, w: 8.8, h: 1.2, fontSize: 18, color: "CBD5E1", valign: "top", margin: 0 } } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: HEX.lt1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.28, w: 9.0, h: 0.9, fontSize: 24, bold: true, color: C.text1, valign: "middle", margin: 0 } } },
    { text: { text: FOOTER, options: { x: 0.5, y: 5.22, w: 8.0, h: 0.25, fontSize: 8, color: C.accent6, margin: 0 } } },
  ],
  slideNumber: { x: 9.0, y: 5.22, w: 0.5, h: 0.25, fontSize: 8, color: HEX.accent6, align: "right" },
});

// ------------------------------------------------------------------ helpers
const txt = (slide, text, o) => slide.addText(text, { isTextBox: true, margin: 0, fontSize: 14, color: C.text2, valign: "top", ...o });
function card(slide, x, y, w, h, { fill = C.background2, name = "card" } = {}) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08, objectName: name });
}
function badge(slide, x, y, label, color, size = 0.42) {
  slide.addShape(pres.ShapeType.ellipse, { x, y, w: size, h: size, fill: { color }, line: { color }, objectName: "badge " + label });
  slide.addText(label, { x, y, w: size, h: size, isTextBox: true, margin: 0, align: "center", valign: "middle", fontSize: size > 0.4 ? 13 : 11, bold: true, color: C.background1, objectName: "badge label " + label });
}
function stat(slide, x, y, w, value, label, color = C.accent1, vsize = 36) {
  txt(slide, value, { x, y, w, h: 0.75, fontSize: vsize, bold: true, color, valign: "middle", objectName: "stat " + label });
  txt(slide, label, { x, y: y + 0.78, w, h: 0.66, fontSize: 11, color: C.accent6, objectName: "stat label " + label });
}
function bullets(slide, items, o) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } })), { isTextBox: true, margin: 0, fontSize: 13, color: C.text2, valign: "top", ...o });
}
const chartText = { catAxisLabelColor: HEX.dk2, valAxisLabelColor: HEX.dk2, catAxisLabelFontSize: 10, valAxisLabelFontSize: 10, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", dataLabelFontSize: 9, dataLabelColor: HEX.dk2, legendFontFace: "+mn-lt", legendFontSize: 10, legendColor: HEX.dk2, valGridLine: { color: "E2E8F0", size: 0.5 }, catGridLine: { style: "none" }, titleFontFace: "+mj-lt", titleFontSize: 12, titleColor: HEX.dk1 };
const f1 = (v) => Number(v).toFixed(1);
const pt = Object.fromEntries(chain.port_table.map((r) => [r.avg_loading_pct, r]));
const mx = Object.fromEntries(chain.mixed_table.map((r) => [Math.round(r.token_coverage * 100), r]));
const d = chain.defaults;

// ================================================================== 1 title
pres.addSection({ title: "Opening" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Opening" });
txt(s, "KIFARU PORTOS", { x: 0.6, y: 0.7, w: 8.8, h: 0.5, fontSize: 16, bold: true, color: C.accent1, charSpacing: 4, objectName: "brand" });
s.addText("Weigh once. Honour it everywhere.", { placeholder: "title" });
s.addText("RCS v2 port-anchored clearance for heavy trucks on the Mombasa - Northern Corridor route\nProject proposal  |  5 November 2026", { placeholder: "body" });
txt(s, "Live platform: " + LIVE, { x: 0.6, y: 4.7, w: 8.8, h: 0.3, fontSize: 11, color: "94A3B8", objectName: "live link" });
s.addNotes("Open with the one-line idea: every heavy truck is weighed once at its first trusted point and later weighbridges honour a signed token instead of weighing again. The platform already exists and is live.");

// ================================================================== 2 the problem
pres.addSection({ title: "The case" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The case" });
s.addText("Compliant trucks stop too often; overloads are caught late", { placeholder: "title" });
const probs = [
  ["1", "Weight is measured last", "Identity, cargo and releases are checked repeatedly at the port, yet the first weighing happens on the highway, far from cranes, customs and yard space."],
  ["2", "Every station repeats the work", "Paper certificates and release orders travel with the driver; Mariakani, Mtwapa and Athi River each weigh the same truck again."],
  ["3", "High-speed WIM is not enough", "It estimates axle loads only. Dimensions, lifted axles, per-wheel balance, permits and certificates are still checked by hand at static bridges."],
];
probs.forEach(([n, h, b], i) => {
  const x = 0.5 + i * 3.1;
  card(s, x, 1.3, 2.9, 2.55, { name: "problem card " + n });
  badge(s, x + 0.2, 1.5, n, HEX.accent1);
  txt(s, h, { x: x + 0.2, y: 2.05, w: 2.5, h: 0.5, fontSize: 14, bold: true, color: C.text1, objectName: "problem head " + n });
  txt(s, b, { x: x + 0.2, y: 2.55, w: 2.5, h: 1.25, fontSize: 11.5, objectName: "problem body " + n });
});
stat(s, 0.5, 4.05, 2.9, f1(pt[85].road_only_static) + " %", "of port trucks sent to a static scale at 85 % average loading under road-only screening (modelled)", C.accent3);
stat(s, 3.6, 4.05, 2.9, "8 000", "trucks a day at Mariakani; one percentage point of stops is 8 truck-hours a day");
stat(s, 6.7, 4.05, 2.8, "2 990 USD", "indicative fee for 5 000 kg over the gross limit, tripled on a repeat in the same journey", C.accent2);
s.addNotes("The gap: the port chain verifies everything except weight, and the road weighs everything again. Numbers are from the chain model and the 2018 Regulations fee table, both to be confirmed.");

// ================================================================== 3 the idea
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The case" });
s.addText("Weigh at the first trusted point, honour it downstream", { placeholder: "title" });
s.addImage({ path: path.join(A, "fig-chain.png"), x: 0.5, y: 1.2, w: 6.0, h: 2.47, objectName: "clearance chain diagram" });
card(s, 6.75, 1.2, 2.75, 3.85, { name: "idea card" });
txt(s, "One rule for all streams", { x: 6.95, y: 1.35, w: 2.4, h: 0.4, fontSize: 14, bold: true, color: C.text1, objectName: "idea head" });
bullets(s, [
  "A signed Load Compliance Token is issued at the first verified weighing: port exit, approved origin scale, or first road station.",
  "Later stations only check that identity and weight are unchanged, so compliant trucks keep moving.",
  "Doubtful trucks roll through a verification lane at about 10 km/h.",
  "Red cases still go to the static scale and an authorised officer: the legal reference never moves.",
], { x: 6.95, y: 1.8, w: 2.4, h: 3.2, fontSize: 11 });
txt(s, "Legal hook: Reg 10(2) of the EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018 excuses vehicles previously confirmed compliant by screening devices from producing the paper certificate.", { x: 0.5, y: 3.85, w: 6.0, h: 1.1, fontSize: 11.5, italic: true, color: C.accent6, objectName: "legal hook" });
s.addNotes("Walk the diagram left to right: port and origin nodes issue tokens; the road node checks consistency; green continues, doubtful goes to the lane, certain overloads go to the static scale and the officer. The registry links everything.");

// ================================================================== 4 three streams
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The case" });
s.addText("Three truck streams, one token", { placeholder: "title" });
const streams = [
  ["A", "Port trucks", "Containers from Mombasa", "First weight at the port gate-out node, beside the i-Gate: plate, tag, container OCR, e-seal and releases captured once.", "Trust tier 1  |  audit 2 %", HEX.accent1],
  ["B", "Industrial origin", "Mines, quarries, cement, sugar, fuel depots, farms, factories", "An approved loading-site scale sends a signed ticket; trust is earned by comparing origin readings with road and lane readings.", "Trust tier 2  |  audit 4 %, falling with a clean record", HEX.accent5],
  ["C", "Untokened trucks", "Spot loads, traders, small fleets, first-time users", "The first road station or the rolling verification lane issues the token; more uncertainty, so more go through the lane.", "Trust tier 3  |  audit 3 %", HEX.accent2],
];
streams.forEach(([n, h, who, b, tier, col], i) => {
  const x = 0.5 + i * 3.1;
  card(s, x, 1.3, 2.9, 3.7, { name: "stream card " + n });
  badge(s, x + 0.2, 1.5, n, col, 0.5);
  txt(s, h, { x: x + 0.85, y: 1.5, w: 2.0, h: 0.5, fontSize: 14, bold: true, color: C.text1, valign: "middle", objectName: "stream head " + n });
  txt(s, who, { x: x + 0.2, y: 2.15, w: 2.5, h: 0.5, fontSize: 11, italic: true, color: C.accent6, objectName: "stream who " + n });
  txt(s, b, { x: x + 0.2, y: 2.7, w: 2.5, h: 1.5, fontSize: 11.5, objectName: "stream body " + n });
  txt(s, tier, { x: x + 0.2, y: 4.4, w: 2.5, h: 0.45, fontSize: 10.5, bold: true, color: col, objectName: "stream tier " + n });
});
s.addNotes("Enforcement effort follows risk: audit rates rise with demerit points and fall for fleets with a clean record. On-board records (tier 4) inform the risk score but never issue a token.");

// ================================================================== 5 token + lane
pres.addSection({ title: "The design" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The design" });
s.addText("The token and the rolling verification lane", { placeholder: "title" });
card(s, 0.5, 1.3, 4.4, 3.75, { name: "token card" });
txt(s, "What the token carries", { x: 0.7, y: 1.45, w: 4.0, h: 0.4, fontSize: 14, bold: true, color: C.text1, objectName: "token head" });
bullets(s, [
  "Tractor and trailer plates, RFID tag, container number (check digit) and e-seal",
  "Axle-group loads, gross weight, expected weight and the variance between them",
  "Issuing node, time stamp and validity window; snapshot of customs, shipping-line and KPA release status",
  "Route, destination, declared driver; dimensions, axle configuration, permit reference",
  "Source and trust tier, which set the audit rate; Ed25519 signature so it cannot be altered",
], { x: 0.7, y: 1.9, w: 4.0, h: 3.05, fontSize: 11 });
txt(s, "Rolling Verification Lane", { x: 5.2, y: 1.3, w: 4.3, h: 0.4, fontSize: 14, bold: true, color: C.text1, objectName: "lane head" });
stat(s, 5.2, 1.75, 2.1, "10 km/h", "doubtful trucks roll through per-wheel scales and a LiDAR portal, no stop");
stat(s, 7.4, 1.75, 2.1, "20-30 s", "to capture the full static-bridge parameter set", C.accent2);
stat(s, 5.2, 3.2, 2.1, "~370 / h", "one lane at 27 m headway; a static lane does about 15", C.accent4);
stat(s, 7.4, 3.2, 2.1, "~25 x", "static lanes replaced by one rolling lane", C.accent5);
txt(s, "Layout: 100-150 m approach, flat 15 m measuring zone, 50 m exit. Legal grade only after weights-and-measures approval (Reg 5).", { x: 5.2, y: 4.6, w: 4.3, h: 0.55, fontSize: 10, color: C.accent6, objectName: "lane note" });
s.addNotes("The token makes the road check a consistency test rather than an accuracy test; the lane supplies everything high-speed WIM lacks without stopping the truck.");

// ================================================================== 6 beyond weight
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The design" });
s.addText("Everything KeNHA checks at a static bridge, covered", { placeholder: "title" });
const params = [
  ["Gross and axle-group loads", "Per-wheel scales in the lane, error target 1 %; static scale remains legal proof for red cases"],
  ["Axle count and lifted axles", "Side LiDAR and camera classification matched to the registered configuration"],
  ["Height, width, length", "Overhead LiDAR portal and light curtain; checked against special-load permits"],
  ["Left-right imbalance", "Per-wheel scales; wheel-track position from the WIM rows"],
  ["Certificates, release orders, seals", "Held in the registry and shown to every station; e-seal status from KRA; customs alerted on a transit overload"],
  ["Fee, signature, calibration", "Fee computed from the schedule and allowance policy; officer e-signs; quarterly calibration register"],
];
params.forEach(([h, b], i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.5 + col * 3.1, y = 1.3 + row * 1.85;
  card(s, x, y, 2.9, 1.65, { name: "param card " + i });
  s.addShape(pres.ShapeType.ellipse, { x: x + 0.2, y: y + 0.2, w: 0.3, h: 0.3, fill: { color: HEX.accent1 }, line: { color: HEX.accent1 }, objectName: "dot " + i });
  txt(s, h, { x: x + 0.62, y: y + 0.12, w: 2.2, h: 0.5, fontSize: 12, bold: true, color: C.text1, valign: "middle", objectName: "param head " + i });
  txt(s, b, { x: x + 0.2, y: y + 0.62, w: 2.5, h: 0.95, fontSize: 10.5, objectName: "param body " + i });
});
s.addNotes("Two limits from the regulations: screening never replaces static weighing as proof of overload, and fees and release orders come from an authorised officer. The system prepares; the officer approves.");

// ================================================================== 7 decision rules
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The design" });
s.addText("Decision rules at the road screening node", { placeholder: "title" });
const rules = [
  ["GREEN", "Continue", HEX.accent4, ["Valid token, identity match, weight within tolerance of the token (8 % port or origin, 11 % road)", "Dimensions inside limits, axle count matches registration", "Or no token but weight below the limit by the full margin: a road token is issued"]],
  ["AMBER", "Divert to lane", HEX.accent2, ["No token and weight inside the margin band", "Weight inconsistent with the token (cargo changed)", "Dimension or axle-count mismatch, unreadable identity, or random audit", "Lane pass issues or renews the token"]],
  ["RED", "Static + officer", HEX.accent3, ["Over the limit beyond the margin on any node", "Dimension or permit breach, or inconclusive lane result", "Officer e-signs the release order (Reg 14); hazardous and perishable flags change the handling"]],
];
rules.forEach(([tag, head, col, items], i) => {
  const x = 0.5 + i * 3.1;
  card(s, x, 1.3, 2.9, 3.75, { name: "rule card " + tag });
  s.addShape(pres.ShapeType.roundRect, { x: x + 0.2, y: 1.5, w: 0.95, h: 0.38, fill: { color: col }, line: { color: col }, rectRadius: 0.06, objectName: "rule tag " + tag });
  s.addText(tag, { x: x + 0.2, y: 1.5, w: 0.95, h: 0.38, isTextBox: true, margin: 0, align: "center", valign: "middle", fontSize: 12, bold: true, color: C.background1, objectName: "rule tag text " + tag });
  txt(s, head, { x: x + 1.25, y: 1.5, w: 1.55, h: 0.38, fontSize: 12.5, bold: true, color: C.text1, valign: "middle", objectName: "rule head " + tag });
  bullets(s, items, { x: x + 0.2, y: 2.05, w: 2.5, h: 2.9, fontSize: 11 });
});
s.addNotes("For loads in the margin band the road reading no longer has to be accurate against the limit; it only has to confirm the weight is unchanged since the first trusted weighing.");

// ================================================================== 8 legal
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The design" });
s.addText("Anchored in the 2018 Enforcement Regulations", { placeholder: "title" });
const regs = [
  ["Reg 10(2)", "Vehicles previously confirmed within limits by screening devices need not produce the paper certificate.", "The legal basis for a digital green status."],
  ["Reg 4(6) and 18(3)", "A vehicle found in breach by surveillance is weighed on a static scale.", "Screening decides who needs a static weighing; it never replaces it as proof."],
  ["Reg 3(4) and 11(3)", "Tickets and release orders for overloaded vehicles come from authorised officers.", "The platform prepares the red case; the officer e-signs with MFA."],
  ["Reg 5, 6 and 8", "Scales need weights-and-measures approval; calibration every three months; annual audit.", "Legal-grade flag per lane; quarterly calibration register; expired calibration blocks green."],
  ["Reg 14 and 18", "Release orders travel with the journey; a repeat overload triples the fee; transit overloads wait for customs.", "Digital release-order registry with repeat detection and automatic customs alert."],
  ["Second and Third Schedules", "Discretion allowance below 5 %; legal weights and the fee table.", "Allowance is a policy value to agree with KeNHA; it changes the stop share materially."],
];
regs.forEach(([r, says, means], i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.5 + col * 3.1, y = 1.3 + row * 1.85;
  card(s, x, y, 2.9, 1.65, { name: "reg card " + i });
  txt(s, r, { x: x + 0.2, y: y + 0.1, w: 2.5, h: 0.3, fontSize: 12, bold: true, color: C.accent1, objectName: "reg " + i });
  txt(s, says, { x: x + 0.2, y: y + 0.4, w: 2.5, h: 0.62, fontSize: 9.5, color: C.accent6, objectName: "reg says " + i });
  txt(s, means, { x: x + 0.2, y: y + 1.02, w: 2.5, h: 0.6, fontSize: 10, bold: true, color: C.text1, objectName: "reg means " + i });
});
s.addNotes("Open legal questions for Phase 0-1: whether Reg 10(2) covers a digital token, who approves the devices, whether an officer may e-sign remotely, and whether low-speed in-motion weighing can be approved as legal-grade.");

// ================================================================== 9 what's built
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "The design" });
s.addText("Not a blank sheet: the platform is built, tested and live", { placeholder: "title" });
const built = [
  ["Clearance engine 2.0", "Deterministic rules: token consistency, dimensions, lifted axles, permits, allowance, tiered audits, routes; evidence hash per decision", HEX.accent1],
  ["Clearance registry", "Tokens with public verification, Reg 14 release orders with officer e-signature, permits, trust-tier policy, stream and route statistics", HEX.accent1],
  ["Web platform", "Control centre, weighbridge console, registry, model explorer, transporter, driver, cargo owner, warehouse, admin, 3D digital twin", HEX.accent5],
  ["Roadside gateway and hardware", "Store-and-forward gateway (built); STM32 acquisition firmware, analog front end, lane and port-node layouts (designed, not fabricated)", HEX.accent2],
  ["Simulation package", "RCS v2 chain Monte Carlo, experiments with replications and gate, SimPy station model with tokens and lane, SUMO adapter", HEX.accent4],
  ["Cloud and security", "Live on Vercel (Dublin) with Supabase PostgreSQL; RBAC, MFA, signed records, hash-chained ledger, PII encryption, DPIA", HEX.accent6],
];
built.forEach(([h, b, col], i) => {
  const c2 = i % 2, row = Math.floor(i / 2);
  const x = 0.5 + c2 * 4.65, y = 1.3 + row * 1.0;
  s.addShape(pres.ShapeType.ellipse, { x, y: y + 0.12, w: 0.3, h: 0.3, fill: { color: col }, line: { color: col }, objectName: "built dot " + i });
  txt(s, h, { x: x + 0.45, y, w: 4.0, h: 0.35, fontSize: 13, bold: true, color: C.text1, valign: "middle", objectName: "built head " + i });
  txt(s, b, { x: x + 0.45, y: y + 0.35, w: 4.0, h: 0.6, fontSize: 10, objectName: "built body " + i });
});
card(s, 0.5, 4.35, 9.0, 0.7, { fill: C.text1, name: "live bar" });
txt(s, "164 automated tests passing  |  live at " + LIVE + "  |  every record carries live / simulated / replay and simulated data is never shown as live", { x: 0.7, y: 4.35, w: 8.6, h: 0.7, fontSize: 12, bold: true, color: C.background1, valign: "middle", objectName: "live line" });
s.addNotes("78 API tests, 32 simulation, 22 gateway, 24 DSP, 8 agents. Hardware is designed, not built; regulators have not reviewed the design. These are stated plainly in the proposal.");

// ================================================================== 10 modelled effect: port trucks (native chart)
pres.addSection({ title: "Modelled effect" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Modelled effect" });
s.addText("Port trucks: road stops fall, near-limit checks move to the port", { placeholder: "title" });
const loadings = chain.port_table.map((r) => r.avg_loading_pct + " %");
s.addChart(pres.ChartType.bar, [
  { name: "Road-only screening", labels: loadings, values: chain.port_table.map((r) => +f1(r.road_only_static)) },
  { name: "Road-only with 5 % allowance", labels: loadings, values: chain.port_table.map((r) => +f1(r.road_only_with_allowance)) },
  { name: "RCS v2: road static stops", labels: loadings, values: chain.port_table.map((r) => +f1(r.v2_road_static)) },
  { name: "RCS v2: port re-weigh", labels: loadings, values: chain.port_table.map((r) => +f1(r.v2_port_reweigh)) },
], { x: 0.5, y: 1.2, w: 6.1, h: 3.9, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent6, HEX.dk2, HEX.accent1, HEX.accent2], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", showLegend: true, legendPos: "b", showTitle: true, title: "Share of port trucks (%) by average load, 600 000 trucks per point (modelled)", catAxisTitle: "", valAxisMaxVal: 40, ...chartText });
stat(s, 6.9, 1.25, 2.6, f1(pt[85].road_only_static) + " % to " + f1(pt[85].v2_road_static) + " %", "road static stops at 85 % loading (modelled)", C.accent1, 26);
stat(s, 6.9, 2.7, 2.6, "~" + Math.round(pt[85].truck_hours_saved_per_day), "road truck-hours saved a day at 8 000 trucks and 6 minutes per stop", C.accent4);
txt(s, "Honest reading: total re-weighs stay similar (" + f1(pt[85].v2_road_static) + " % road + " + f1(pt[85].v2_port_reweigh) + " % port vs " + f1(pt[85].road_only_static) + " % road); the gain is relieving road queues and fixing overloads where it is cheap. A 5 % allowance or a legal-grade port scale cuts port re-weighs to about 1 %.", { x: 6.9, y: 3.95, w: 2.6, h: 1.25, fontSize: 9.5, color: C.accent6, objectName: "honest reading" });
s.addNotes("Assumptions: 1.5 % overloaded, load spread 12 % of the limit capped at the limit, port error 1 %, road error 2.5 %, 90 % token coverage, 3 % audits. All to be replaced with measured data in Phase 0-2.");

// ================================================================== 11 modelled effect: coverage (native line chart)
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Modelled effect" });
s.addText("Mixed traffic: token coverage is the lever that matters", { placeholder: "title" });
const covs = chain.mixed_table.map((r) => Math.round(r.token_coverage * 100) + " %");
s.addChart(pres.ChartType.line, [
  { name: "Road-only baseline: static stops", labels: covs, values: chain.mixed_table.map((r) => +f1(r.road_only_baseline_static)) },
  { name: "First station: verification lane", labels: covs, values: chain.mixed_table.map((r) => +f1(r.first_station_lane)) },
  { name: "First station: static scale", labels: covs, values: chain.mixed_table.map((r) => +f1(r.first_station_static)) },
  { name: "Later stations: lane", labels: covs, values: chain.mixed_table.map((r) => +f1(r.later_station_lane)) },
], { x: 0.5, y: 1.2, w: 6.1, h: 3.9, chartColors: [HEX.accent6, HEX.accent2, HEX.accent3, HEX.accent1], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 7, showValue: true, dataLabelPosition: "t", dataLabelFormatCode: "0.0", showLegend: true, legendPos: "b", showTitle: true, title: "Share of all trucks (%) at 85 % loading by share carrying a port or origin token (modelled)", valAxisMaxVal: 25, ...chartText });
stat(s, 6.9, 1.25, 2.6, f1(mx[30].first_station_static) + " % to " + f1(mx[90].first_station_static) + " %", "first-station static visits as coverage rises from 30 % to 90 % (baseline " + f1(mx[90].road_only_baseline_static) + " %)", C.accent3, 26);
stat(s, 6.9, 2.75, 2.6, Number(mx[90].later_station_static).toFixed(2) + " %", "static visits at later stations once every truck carries a token: repeat stops disappear", C.accent1);
txt(s, "Lane capacity: modelled peak " + Math.round(d.lane_peak_per_hour) + " trucks an hour against about " + Math.round(d.lane_capacity_per_hour) + " per lane, so one lane per station is enough. Fleet and loader enrolment is therefore a core workstream.", { x: 6.9, y: 4.15, w: 2.6, h: 1.0, fontSize: 9.5, color: C.accent6, objectName: "lane capacity note" });
s.addNotes("Untokened trucks alone: the lane trims static visits only from about 21 % to 14 % of those trucks; the rest sit inside the 2 % margin and need a legal-grade lane reading or the discretion allowance.");

// ================================================================== 12 sensitivity + gate
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Modelled effect" });
s.addText("What moves the result, and the go/no-go gate", { placeholder: "title" });
const tor = chain.tornado.slice().sort((a, b) => a.swing - b.swing);
s.addChart(pres.ChartType.bar, [{ name: "Swing of the road stop share (points)", labels: tor.map((r) => r.factor.replace(/_pct$/, "").replace(/_/g, " ") + " (" + r.low + " to " + r.high + ")"), values: tor.map((r) => +f1(r.swing)) }],
  { x: 0.5, y: 1.2, w: 5.4, h: 3.9, barDir: "bar", chartColors: [HEX.accent1], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", showLegend: false, showTitle: true, title: "Swing of RCS v2 road stops across each factor's low-high range (points, modelled)", ...chartText });
card(s, 6.2, 1.2, 3.3, 3.9, { name: "gate card" });
txt(s, "Go/no-go gate (Section 10.9)", { x: 6.4, y: 1.35, w: 3.0, h: 0.4, fontSize: 14, bold: true, color: C.text1, objectName: "gate head" });
chain.gate.checks.forEach((c, i) => {
  const y = 1.85 + i * 0.78;
  badge(s, 6.4, y, c.ok ? "ok" : "x", c.ok ? HEX.accent4 : HEX.accent3, 0.38);
  const label = { road_stop_share_cut_points: "Road stop share cut by at least 10 points", false_clear_rate: "False-clear rate at most 1 %", port_reweigh_share_pct: "Port re-weigh volume practical (at most 20 %)" }[c.name] || c.name;
  txt(s, label, { x: 6.9, y: y - 0.02, w: 2.5, h: 0.4, fontSize: 11, bold: true, color: C.text1, objectName: "gate label " + i });
  txt(s, "value " + f1(c.name === "false_clear_rate" ? c.value * 100 : c.value) + (c.name === "false_clear_rate" ? " %" : c.name.includes("points") ? " points" : " %"), { x: 6.9, y: y + 0.36, w: 2.5, h: 0.3, fontSize: 10, color: C.accent6, objectName: "gate value " + i });
});
txt(s, (chain.gate.proceed ? "Met in the model. " : "Not met. ") + "Re-applied to the validated model on measured baseline data before any hardware spend; 30 replications give confidence intervals under 0.1 point, so the uncertainty that matters is in the assumptions.", { x: 6.4, y: 4.2, w: 3.0, h: 0.85, fontSize: 9.5, color: C.accent6, objectName: "gate note" });
s.addNotes("Token coverage swings the road stop share by about 10 points; audit rate about 4; loading about 2.6. Port error and the allowance move the port re-weigh share instead.");

// ================================================================== 13 station queue model
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Modelled effect" });
s.addText("Station model: the lane absorbs doubtful trucks without stops", { placeholder: "title" });
const order = ["baseline_all_stop", "rolling_clearance", "arrivals_+50", "rcs_v2_untokened", "rcs_v2_tokens_90", "rcs_v2_allowance_5pct", "rcs_v2_lane_closure"];
const o = simpy.outcomes;
const names = order.filter((n) => n in o);
const pretty = { baseline_all_stop: "All stop (today)", rolling_clearance: "Rolling clearance (v1)", "arrivals_+50": "v1, +50 % demand", rcs_v2_untokened: "RCS v2, no tokens", rcs_v2_tokens_90: "RCS v2, 90 % tokens", rcs_v2_allowance_5pct: "RCS v2 + 5 % allowance", rcs_v2_lane_closure: "RCS v2, lane closed 2 h" };
s.addChart(pres.ChartType.bar, [
  { name: "Stopped at the static scale", labels: names.map((n) => pretty[n]), values: names.map((n) => +f1(o[n].summary.pct_stopped.mean)) },
  { name: "Rolled through the verification lane", labels: names.map((n) => pretty[n]), values: names.map((n) => +f1(o[n].summary.pct_lane.mean)) },
], { x: 0.5, y: 1.2, w: 6.1, h: 3.9, barDir: "col", barGrouping: "clustered", chartColors: [HEX.accent3, HEX.accent2], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0", showLegend: true, legendPos: "b", showTitle: true, title: "Share of trucks (%), SimPy station model, 12 h, 3 replications (modelled)", valAxisMaxVal: 110, catAxisLabelFontSize: 8, ...chartText, catAxisLabelFontSize: 8 });
const tis = (n) => f1(o[n].summary.mean_tis_min.mean);
stat(s, 6.9, 1.25, 2.6, tis("baseline_all_stop") + " min", "mean time in system when every truck stops (static scale saturated)", C.accent3, 30);
stat(s, 6.9, 2.7, 2.6, tis("rcs_v2_tokens_90") + " min", "with RCS v2 at 90 % token coverage; static utilisation " + Math.round(o.rcs_v2_tokens_90.summary.static_utilisation_pct.mean) + " %", C.accent1, 30);
txt(s, "The station model uses a heavier synthetic population (15 % overloaded) than the chain model, so shares differ; it is used for queues, lane capacity and closures. A two-hour lane closure sends doubtful trucks back to the static scale, as designed.", { x: 6.9, y: 4.0, w: 2.6, h: 1.2, fontSize: 9.5, color: C.accent6, objectName: "simpy note" });
s.addNotes("Decisions in the station model come from the production clearance engine, so the simulation and the live platform cannot disagree on policy.");

// ================================================================== 14 roadmap
pres.addSection({ title: "Delivery" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Delivery" });
s.addText("Roadmap: a gate before any hardware spend", { placeholder: "title" });
const phases = [
  ["0-1", "Access and legal", "Months 0-3", "Agencies, loaders, data requests, legal opinion on Reg 10(2), 5, 3(4)", "MoUs, data access, legal route clear"],
  ["2", "Baseline and design", "Months 3-7", "Time-and-motion at the port exit and Mariakani; classification counts; validated simulation; token and API spec", "Simulation meets the gate"],
  ["3", "Bench prototype", "Months 6-11", "Scale-model rig, token service, OCR, LiDAR portal, per-wheel scales, mock agency APIs", "Latency and repeatability met"],
  ["4", "Shadow pilot", "Months 10-16", "Port exit lane, one origin site, one lane at Mariakani; tokens issued and compared, not acted on", "Accuracy and false-clear targets met"],
  ["5", "Live pilot", "Months 16-24", "Volunteer fleets use the green lane; approved signs; static audits continue; lane scale approval", "Agency approval, then scale out"],
];
phases.forEach(([n, h, when, what, gate], i) => {
  const x = 0.5 + i * 1.84;
  s.addShape(pres.ShapeType.roundRect, { x, y: 1.3, w: 1.7, h: 0.55, fill: { color: i === 4 ? HEX.accent1 : HEX.dk1 }, line: { color: i === 4 ? HEX.accent1 : HEX.dk1 }, rectRadius: 0.06, objectName: "phase pill " + n });
  s.addText("Phase " + n, { x, y: 1.3, w: 1.7, h: 0.55, isTextBox: true, margin: 0, align: "center", valign: "middle", fontSize: 12, bold: true, color: C.background1, objectName: "phase pill text " + n });
  if (i < 4) s.addShape(pres.ShapeType.rightArrow, { x: x + 1.7, y: 1.47, w: 0.14, h: 0.22, fill: { color: HEX.accent6 }, line: { color: HEX.accent6 }, objectName: "arrow " + n });
  txt(s, h, { x, y: 1.95, w: 1.7, h: 0.4, fontSize: 12.5, bold: true, color: C.text1, objectName: "phase head " + n });
  txt(s, when, { x, y: 2.3, w: 1.7, h: 0.3, fontSize: 10, italic: true, color: C.accent6, objectName: "phase when " + n });
  txt(s, what, { x, y: 2.62, w: 1.7, h: 1.35, fontSize: 10, objectName: "phase what " + n });
  card(s, x, 4.05, 1.7, 1.0, { name: "phase gate " + n });
  txt(s, "Exit gate", { x: x + 0.12, y: 4.1, w: 1.5, h: 0.25, fontSize: 8.5, bold: true, color: C.accent1, objectName: "phase gate head " + n });
  txt(s, gate, { x: x + 0.12, y: 4.35, w: 1.5, h: 0.68, fontSize: 9.5, color: C.text1, objectName: "phase gate text " + n });
});
s.addNotes("The 16-week simulation sits inside Phase 2: weeks 1-2 baseline plan and data requests, 3-4 sensor model, 5-8 process model, 9-10 road traffic, 11-14 token service and hardware-in-the-loop, 15-16 validation and committee report.");

// ================================================================== 15 risks
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Delivery" });
s.addText("Main risks and how they are handled", { placeholder: "title" });
const risks = [
  ["KPA may not allow a weigh node in the exit lane", "Start the port node as advisory; the first road station can be the first trusted point"],
  ["Scales lack legal-grade approval", "Seek weights-and-measures approval early; model both cases; apply the allowance where KeNHA agrees"],
  ["Private origin scales under-report", "Approve and audit each scale; compare origin readings with road and lane; suspend tokens on drift"],
  ["Token fraud: plate swaps, cargo added later", "Bind token to plate, tag and seal; weight consistency on the road; audits and demerits"],
  ["Land and civil works for the lane (about 250 m)", "Confirm availability per station early; approved signs for speed discipline"],
  ["Model assumptions differ from reality", "Validate against measured baselines before any claim; tornado analysis; gate re-applied"],
];
risks.forEach(([r, m], i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = 0.5 + col * 4.65, y = 1.3 + row * 1.25;
  card(s, x, y, 4.45, 1.1, { name: "risk card " + i });
  s.addShape(pres.ShapeType.ellipse, { x: x + 0.18, y: y + 0.2, w: 0.26, h: 0.26, fill: { color: HEX.accent2 }, line: { color: HEX.accent2 }, objectName: "risk dot " + i });
  txt(s, r, { x: x + 0.55, y: y + 0.1, w: 3.75, h: 0.45, fontSize: 11, bold: true, color: C.text1, valign: "middle", objectName: "risk " + i });
  txt(s, m, { x: x + 0.55, y: y + 0.55, w: 3.75, h: 0.5, fontSize: 10, objectName: "risk mitigation " + i });
});
s.addNotes("Also: legitimate weight changes (partial offloads, fuel) handled with a validity window and lane renewal; data-sharing delays covered by a two-week provisional study; officers must still sign (e-signature workflow with MFA).");

// ================================================================== 16 decisions
pres.addSection({ title: "Closing" });
s = pres.addSlide({ masterName: "DARK", sectionTitle: "Closing" });
s.addText("Decisions requested", { placeholder: "title" });
const asks = ["Approve the redesign around the port gate-out node and the Load Compliance Token", "Approve Phases 0-2: simulation and baseline study, gated before hardware spend", "Authorise approaches to KPA, KRA, KeNHA, NTSA and the weights-and-measures body", "Nominate an executive sponsor and a legal adviser"];
asks.forEach((t, i) => {
  const y = 2.95 + i * 0.52;
  badge(s, 0.6, y, String(i + 1), HEX.accent1, 0.38);
  txt(s, t, { x: 1.15, y, w: 8.2, h: 0.38, fontSize: 13, color: C.background1, valign: "middle", objectName: "ask " + (i + 1) });
});
txt(s, "Full proposal: docs/07-proposal/KIFARU-PORTOS-Project-Proposal.pdf  |  " + LIVE, { x: 0.6, y: 5.0, w: 8.8, h: 0.3, fontSize: 10, color: "94A3B8", objectName: "closing link" });
s.addNotes("Close on the four decisions. Everything modelled is labelled modelled; the first spend is the baseline study and the legal opinion, not hardware.");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written:", OUT);
})();
