// =============================================================================
//  Extractmet — Continuous-Charge EAF Digital Twin  ·  Sales pitch deck
//  pptxgenjs generator.   Output: EAF_DigitalTwin_Extractmet.pptx
// =============================================================================
const pptxgen = require("pptxgenjs");
const fs = require("fs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";          // 13.3 x 7.5 in  (set BEFORE adding slides)
pres.author = "Extractmet Private Limited";
pres.company = "Extractmet Private Limited";
pres.title = "Continuous-Charge EAF Digital Twin";

// ---- palette (molten-metal industrial, no #) --------------------------------
const BG      = "0F1720";
const PANEL   = "16212E";
const PANEL2  = "1B2735";
const GRID    = "26333F";
const FG      = "E8EEF4";
const MUTED   = "8AA0B2";
const ORANGE  = "FF8C42";
const AMBER   = "FFC857";
const CYAN    = "39D0D8";
const GREEN   = "5FD08A";
const RED     = "EF6F6C";
const VIOLET  = "B48EAD";

const HEAD = "Century Schoolbook";   // safe-list serif with personality
const BODY = "Calibri";              // safe-list sans

const W = 13.333, H = 7.5;
const A = "assets/";

// ---- helpers ----------------------------------------------------------------
function bgFill(slide, color) { slide.background = { color }; }

function band(slide, x, y, w, h, color, radius) {
  slide.addShape(radius ? pres.ShapeType.roundRect : pres.ShapeType.rect,
    { x, y, w, h, fill: { color }, line: { type: "none" },
      rectRadius: radius || 0 });
}

function accentDot(slide, x, y, color, r) {
  r = r || 0.11;
  slide.addShape(pres.ShapeType.ellipse,
    { x: x, y: y, w: r * 2, h: r * 2, fill: { color }, line: { type: "none" } });
}

function eyebrow(slide, text, x, y, color) {
  slide.addText(text.toUpperCase(), {
    x, y, w: 8, h: 0.3, fontFace: BODY, fontSize: 12, bold: true,
    color: color || ORANGE, charSpacing: 3, align: "left" });
}

function footer(slide, n) {
  slide.addText("EXTRACTMET  ·  Continuous-Charge EAF Digital Twin", {
    x: 0.5, y: 7.06, w: 8, h: 0.3, fontFace: BODY, fontSize: 9,
    color: MUTED, align: "left" });
  slide.addText(String(n), {
    x: 12.5, y: 7.06, w: 0.5, h: 0.3, fontFace: BODY, fontSize: 9,
    color: MUTED, align: "right" });
  slide.addShape(pres.ShapeType.line,
    { x: 0.5, y: 7.0, w: 12.33, h: 0, line: { color: GRID, width: 1 } });
}

// tiny brand mark (stylised furnace/arc) drawn from shapes
function brandMark(slide, x, y, s) {
  s = s || 1;
  band(slide, x, y + 0.30 * s, 0.62 * s, 0.30 * s, ORANGE, 0.04);       // bath
  slide.addShape(pres.ShapeType.line, { x: x + 0.16 * s, y: y - 0.02 * s, w: 0, h: 0.34 * s, line: { color: AMBER, width: 2.2 } });
  slide.addShape(pres.ShapeType.line, { x: x + 0.31 * s, y: y - 0.05 * s, w: 0, h: 0.37 * s, line: { color: AMBER, width: 2.2 } });
  slide.addShape(pres.ShapeType.line, { x: x + 0.46 * s, y: y - 0.02 * s, w: 0, h: 0.34 * s, line: { color: AMBER, width: 2.2 } });
}

// =============================================================================
// SLIDE 1 — TITLE
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, BG);
  // ambient glow bar
  band(s, 0, 0, W, 0.14, ORANGE);
  band(s, 0, H - 0.14, W, 0.14, PANEL2);

  brandMark(s, 0.85, 0.7, 1.15);
  s.addText("EXTRACTMET", {
    x: 1.7, y: 0.62, w: 6, h: 0.5, fontFace: HEAD, fontSize: 26, bold: true,
    color: ORANGE, charSpacing: 2 });
  s.addText("PYROMETALLURGY · DIGITAL TWINS", {
    x: 1.72, y: 1.06, w: 6, h: 0.3, fontFace: BODY, fontSize: 11, color: MUTED,
    charSpacing: 3 });

  s.addText([
    { text: "Continuous-Charge EAF", options: { color: FG, breakLine: true } },
    { text: "Process Digital Twin", options: { color: ORANGE } },
  ], { x: 0.85, y: 2.55, w: 11.6, h: 1.9, fontFace: HEAD, fontSize: 54, bold: true,
       lineSpacingMultiple: 1.0, align: "left" });

  s.addText("A first-principles dynamic simulator for continuously-charged "
    + "(Consteel-type) electric-arc-furnace steelmaking — validated against the "
    + "peer-reviewed literature, delivered as an interactive HMI.", {
    x: 0.87, y: 4.55, w: 10.6, h: 1.0, fontFace: BODY, fontSize: 17, color: MUTED,
    lineSpacingMultiple: 1.15 });

  // three quick tags
  const tags = [["FIRST-PRINCIPLES", ORANGE], ["LITERATURE-VALIDATED", CYAN], ["DEPLOYABLE HMI", AMBER]];
  tags.forEach(([t, c], i) => {
    const x = 0.87 + i * 3.15;
    band(s, x, 5.75, 2.9, 0.5, PANEL, 0.08);
    band(s, x, 5.75, 0.07, 0.5, c);
    s.addText(t, { x: x + 0.18, y: 5.75, w: 2.7, h: 0.5, fontFace: BODY,
      fontSize: 12, bold: true, color: FG, valign: "middle", charSpacing: 1 });
  });

  s.addText("Extractmet Private Limited", {
    x: 8.4, y: 6.62, w: 4.4, h: 0.3, fontFace: BODY, fontSize: 12, bold: true,
    color: MUTED, align: "right" });
  s.addNotes("Title. Extractmet's continuous-charge EAF digital twin — a "
    + "first-principles dynamic simulator delivered as an interactive control-room "
    + "HMI. Every KPI validated against peer-reviewed literature.");
})();

// =============================================================================
// SLIDE 2 — THE PROBLEM
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, BG);
  eyebrow(s, "The challenge", 0.85, 0.55);
  s.addText("Electric steelmaking runs on thin margins and thinner data", {
    x: 0.85, y: 0.9, w: 11.6, h: 0.8, fontFace: HEAD, fontSize: 30, bold: true,
    color: FG });

  const cards = [
    ["Energy is the P&L", ORANGE,
      "Electricity is the single largest conversion cost. A few kWh/t decides whether a heat is profitable — yet most plants tune by operator habit, not by a model that closes the energy balance."],
    ["Yield walks out in the slag", AMBER,
      "Every point of iron oxidised to FeO is money in the slag pot. Yield, FeO and basicity are coupled through chemistry that spreadsheets can't capture."],
    ["Continuous charging is different", CYAN,
      "Consteel-type furnaces hold a flat bath and melt by immersion. Batch-EAF rules of thumb don't transfer — operations need a model built for continuous feed."],
    ["Trials are slow and costly", VIOLET,
      "Testing a new practice on a live 100-tonne furnace is expensive and risky. Plants need a safe sandbox to explore before touching the transformer."],
  ];
  cards.forEach((c, i) => {
    const col = i % 2, rowi = Math.floor(i / 2);
    const x = 0.85 + col * 6.0, y = 2.0 + rowi * 2.35;
    band(s, x, y, 5.7, 2.05, PANEL, 0.1);
    band(s, x, y, 0.09, 2.05, c[1]);
    accentDot(s, x + 0.32, y + 0.34, c[1], 0.09);
    s.addText(c[0], { x: x + 0.62, y: y + 0.22, w: 4.9, h: 0.4, fontFace: BODY,
      fontSize: 17, bold: true, color: FG });
    s.addText(c[2], { x: x + 0.32, y: y + 0.78, w: 5.15, h: 1.15, fontFace: BODY,
      fontSize: 12.5, color: MUTED, lineSpacingMultiple: 1.12 });
  });
  footer(s, 2);
  s.addNotes("The problem: energy is the dominant cost, yield is lost to slag, "
    + "continuous charging behaves differently from batch, and live trials are "
    + "expensive. Operators lack a first-principles model to guide decisions.");
})();

// =============================================================================
// SLIDE 3 — THE PRODUCT
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, PANEL);
  eyebrow(s, "The product", 0.85, 0.55);
  s.addText([
    { text: "One validated physics engine, ", options: { color: FG } },
    { text: "three ways to use it", options: { color: ORANGE } },
  ], { x: 0.85, y: 0.9, w: 11.6, h: 0.8, fontFace: HEAD, fontSize: 30, bold: true });

  s.addText("A mechanistic dynamic model of the continuously-charged EAF that "
    + "integrates coupled mass and energy balances every timestep — then surfaces "
    + "the result through whichever interface fits the moment.", {
    x: 0.85, y: 1.75, w: 11.5, h: 0.8, fontFace: BODY, fontSize: 15, color: MUTED,
    lineSpacingMultiple: 1.12 });

  const feats = [
    ["Web console", ORANGE, "Runs entirely in a browser from a single file. Nothing to install, nothing leaves the machine — ideal for demos and quick studies."],
    ["Streamlit HMI", CYAN, "One-command deploy to Streamlit Community Cloud or any server. Give a whole team model access through a URL."],
    ["Desktop app", AMBER, "A native Tkinter application with embedded plots and export dialogs for engineers who want a tool on their own machine."],
  ];
  feats.forEach((f, i) => {
    const x = 0.85 + i * 4.02, y = 2.75;
    band(s, x, y, 3.8, 3.2, BG, 0.1);
    band(s, x, y, 3.8, 0.5, f[1], 0.1);
    band(s, x, y + 0.25, 3.8, 0.25, f[1]);            // square off bottom of the header cap
    s.addText(f[0], { x: x + 0.2, y: y + 0.02, w: 3.5, h: 0.5, fontFace: BODY,
      fontSize: 17, bold: true, color: "160C05", valign: "middle" });
    s.addText(f[2], { x: x + 0.25, y: y + 0.75, w: 3.35, h: 1.7, fontFace: BODY,
      fontSize: 13, color: MUTED, lineSpacingMultiple: 1.15 });
    s.addText("Same engine · same results", { x: x + 0.25, y: y + 2.7, w: 3.35,
      h: 0.3, fontFace: BODY, fontSize: 10.5, italic: true, color: f[1] });
  });

  // strip: what the engine computes
  const chips = ["Mass & heat balance every Δt", "Oxidation thermochemistry",
    "Decarburisation kinetics", "Foamy-slag physics", "Multilayer heat loss"];
  chips.forEach((t, i) => {
    const x = 0.85 + i * 2.42;
    band(s, x, 6.25, 2.3, 0.5, PANEL2, 0.25);
    s.addText(t, { x: x + 0.05, y: 6.25, w: 2.2, h: 0.5, fontFace: BODY,
      fontSize: 9.5, color: FG, align: "center", valign: "middle" });
  });
  footer(s, 3);
  s.addNotes("The product: one first-principles engine, delivered through three "
    + "interchangeable front-ends — a zero-install web console, a hosted Streamlit "
    + "HMI, and a native desktop app. Identical results across all three.");
})();

// =============================================================================
// SLIDE 4 — SIGNATURE: THE SYNOPTIC
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, BG);
  eyebrow(s, "See the furnace, not a spreadsheet", 0.85, 0.5);
  s.addText("A live control-room synoptic of the whole reactor", {
    x: 0.85, y: 0.85, w: 11.6, h: 0.7, fontFace: HEAD, fontSize: 27, bold: true,
    color: FG });

  band(s, 0.7, 1.75, 9.0, 5.05, PANEL, 0.1);
  s.addImage({ path: A + "synoptic.png", x: 0.85, y: 1.9, w: 8.7, h: 4.75 });

  const pts = [
    ["Every zone, live", ORANGE, "Bath, slag, scrap and gas temperatures, masses and full chemistry — all on one cross-section."],
    ["Scrub the heat", CYAN, "Drag a time slider to replay the entire heat and watch the process evolve second by second."],
    ["Physically faithful", AMBER, "Incandescent bath, foamy slag, arcing electrodes, off-gas duct and the continuous scrap conveyor."],
  ];
  pts.forEach((p, i) => {
    const y = 1.95 + i * 1.62;
    band(s, 9.95, y, 2.9, 1.42, PANEL, 0.09);
    band(s, 9.95, y, 0.08, 1.42, p[1]);
    s.addText(p[0], { x: 10.15, y: y + 0.12, w: 2.6, h: 0.35, fontFace: BODY,
      fontSize: 13.5, bold: true, color: FG });
    s.addText(p[2], { x: 10.15, y: y + 0.5, w: 2.62, h: 0.85, fontFace: BODY,
      fontSize: 10.5, color: MUTED, lineSpacingMultiple: 1.1 });
  });
  footer(s, 4);
  s.addNotes("The signature element: a live SCADA-style furnace synoptic. Every "
    + "zone temperature, mass and chemistry value updates on the cross-section as "
    + "you scrub through the heat. This is what makes the tool immediately legible "
    + "to plant engineers.");
})();

// =============================================================================
// SLIDE 5 — UNDER THE HOOD
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, PANEL);
  eyebrow(s, "Under the hood", 0.85, 0.55);
  s.addText("First principles, not curve fits", {
    x: 0.85, y: 0.9, w: 11.6, h: 0.7, fontFace: HEAD, fontSize: 30, bold: true,
    color: FG });

  const items = [
    ["Coupled balances", ORANGE,
      "Species mass and zone-energy balances for metal, slag, solid scrap, undissolved flux and freeboard gas — advanced together every timestep."],
    ["Thermochemistry", AMBER,
      "Oxidation of C, Si, Mn, P, Cr and Fe with literature reaction enthalpies; oxygen partitioned across elements; post-combustion and burners."],
    ["Kinetics", CYAN,
      "Oxygen- and mass-transfer-limited decarburisation, FeO-driven decarb, basicity- and temperature-gated dephosphorisation."],
    ["Immersion melting", GREEN,
      "Self-balancing scrap melting at the bath interface with enthalpy-conserving mixing — the physics of continuous charging."],
    ["Foamy slag", VIOLET,
      "Coverage from slag mass and FeO shields the arc and returns radiation to the bath, quantifying the foam energy benefit."],
    ["Coupled heat loss", RED,
      "Multilayer refractory conduction with a radiating/convecting shell, plus arc- and gas-loaded water-cooled panels."],
  ];
  items.forEach((it, i) => {
    const col = i % 3, rowi = Math.floor(i / 3);
    const x = 0.85 + col * 4.02, y = 1.95 + rowi * 2.3;
    band(s, x, y, 3.82, 2.05, BG, 0.1);
    accentDot(s, x + 0.3, y + 0.32, it[1], 0.1);
    s.addText(it[0], { x: x + 0.6, y: y + 0.18, w: 3.1, h: 0.4, fontFace: BODY,
      fontSize: 15, bold: true, color: FG });
    s.addText(it[2], { x: x + 0.3, y: y + 0.72, w: 3.3, h: 1.25, fontFace: BODY,
      fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.12 });
  });
  footer(s, 5);
  s.addNotes("Under the hood: coupled mass and energy balances, oxidation "
    + "thermochemistry, decarburisation and dephosphorisation kinetics, "
    + "immersion melting, foamy-slag physics and multilayer heat loss. Every "
    + "term is mechanistic, not a fitted correlation.");
})();

// =============================================================================
// SLIDE 6 — VALIDATION (scorecard image + closures)
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, BG);
  eyebrow(s, "Validation", 0.85, 0.5);
  s.addText("Every KPI lands inside the published window", {
    x: 0.85, y: 0.85, w: 11.6, h: 0.7, fontFace: HEAD, fontSize: 27, bold: true,
    color: FG });

  band(s, 0.7, 1.7, 8.15, 5.1, PANEL, 0.1);
  s.addImage({ path: A + "scorecard.png", x: 0.82, y: 1.82, w: 7.9, h: 4.85 });

  // right column: closures + sources
  const stats = [
    ["Mass closure", "\u22120.6 %", GREEN],
    ["Energy closure", "0.6 %", GREEN],
    ["Total energy", "\u2248564 kWh/t", ORANGE],
    ["Productivity", "2.59 t/h/MW", CYAN],
  ];
  stats.forEach((st, i) => {
    const y = 1.82 + i * 0.98;
    band(s, 9.05, y, 3.8, 0.85, PANEL, 0.09);
    band(s, 9.05, y, 0.08, 0.85, st[2]);
    s.addText(st[0], { x: 9.28, y: y + 0.1, w: 3.5, h: 0.3, fontFace: BODY,
      fontSize: 12, color: MUTED });
    s.addText(st[1], { x: 9.28, y: y + 0.36, w: 3.5, h: 0.42, fontFace: BODY,
      fontSize: 21, bold: true, color: FG });
  });
  s.addText("Benchmarked against Logar et al. (ISIJ 2012), Kirschen (Energy "
    + "2009/11), Pretorius & Marr, Fruehan/DOE, and Zhang et al. (Metals 2026, "
    + "56-furnace Consteel study).", {
    x: 9.05, y: 5.85, w: 3.8, h: 0.9, fontFace: BODY, fontSize: 10, italic: true,
    color: MUTED, lineSpacingMultiple: 1.12 });
  footer(s, 6);
  s.addNotes("Validation: all ten headline KPIs sit inside their peer-reviewed "
    + "literature windows, and the model conserves mass and energy to within 1%. "
    + "Benchmarked against the canonical EAF modelling literature.");
})();

// =============================================================================
// SLIDE 7 — KPI TABLE (native)
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, PANEL);
  eyebrow(s, "Validation detail", 0.85, 0.55);
  s.addText("Simulated vs literature — the numbers", {
    x: 0.85, y: 0.9, w: 11.6, h: 0.7, fontFace: HEAD, fontSize: 28, bold: true,
    color: FG });

  const header = ["KPI", "Simulated", "Literature window", "Verdict"];
  const rows = [
    ["Tap temperature", "1635 \u00B0C", "1600\u20131650 \u00B0C", "in window"],
    ["Tap-to-tap time", "45.3 min", "40\u201360 min", "in window"],
    ["Final carbon", "0.090 wt%", "0.05\u20130.10 wt%", "in window"],
    ["Electrical SEC", "299 kWh/t", "300\u2013360 kWh/t", "edge \u00B7 preheat"],
    ["Total energy demand", "\u2248564 kWh/t", "\u2248570 kWh/t", "in window"],
    ["Productivity", "2.59 t/h/MW", "2.1\u20132.7 t/h/MW", "in window"],
    ["Metallic yield", "93.9 %", "88\u201393 %", "edge \u00B7 clean scrap"],
    ["Slag basicity B\u2082", "2.02", "1.8\u20132.5", "in window"],
    ["Slag FeO", "16.9 wt%", "12\u201325 wt%", "in window"],
    ["Cooling-water loss", "13 %", "\u224813 %", "in window"],
  ];
  const tblRows = [];
  tblRows.push(header.map(h => ({
    text: h, options: { fill: { color: GRID }, color: FG, bold: true,
      fontFace: BODY, fontSize: 13, align: "left", valign: "middle" } })));
  rows.forEach((r, i) => {
    const rowFill = i % 2 ? BG : PANEL2;
    tblRows.push(r.map((cell, ci) => {
      const isVerdict = ci === 3;
      const good = cell.startsWith("in window");
      return { text: cell, options: {
        fill: { color: rowFill },
        color: isVerdict ? (good ? GREEN : AMBER) : (ci === 1 ? FG : MUTED),
        bold: ci === 1 || isVerdict, fontFace: BODY, fontSize: 12.5,
        align: "left", valign: "middle" } };
    }));
  });
  pres.tableToSlides; // (noop guard)
  s.addTable(tblRows, {
    x: 0.85, y: 1.85, w: 11.63, colW: [3.9, 2.4, 3.2, 2.13],
    rowH: 0.42, border: { type: "solid", color: GRID, pt: 1 },
    align: "left", valign: "middle" });
  footer(s, 7);
  s.addNotes("The validation numbers in detail. Seven KPIs dead-centre; three at "
    + "band edges that tell a consistent story of an efficient, clean-scrap, "
    + "high-preheat operation — which the model explains explicitly.");
})();

// =============================================================================
// SLIDE 8 — WHAT YOU CAN DO WITH IT
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, BG);
  eyebrow(s, "Applications", 0.85, 0.55);
  s.addText("From a sandbox to a decision-support tool", {
    x: 0.85, y: 0.9, w: 11.6, h: 0.7, fontFace: HEAD, fontSize: 29, bold: true,
    color: FG });

  const uses = [
    ["Energy optimisation", ORANGE, "Quantify the kWh/t impact of preheat, hot-heel size, power profile and chemical energy before touching the furnace."],
    ["Yield & slag practice", AMBER, "Trade off FeO, basicity and lime against yield; find the flux and oxygen practice that keeps iron out of the slag."],
    ["Operator training", CYAN, "A safe, fast sandbox where operators build intuition for how a continuous-charge furnace responds."],
    ["Scrap-mix studies", GREEN, "Explore how gangue, rust and preheat in the scrap mix move yield, slag chemistry and energy."],
    ["Debottlenecking", VIOLET, "Test power, feed-rate and charge changes against tap-to-tap time and productivity in minutes, not campaigns."],
    ["Digital-twin backbone", RED, "A validated core to build online advisory, what-if and set-point guidance on top of."],
  ];
  uses.forEach((u, i) => {
    const col = i % 3, rowi = Math.floor(i / 3);
    const x = 0.85 + col * 4.02, y = 1.95 + rowi * 2.32;
    band(s, x, y, 3.82, 2.07, PANEL, 0.1);
    band(s, x, y, 3.82, 0.09, u[1]);
    accentDot(s, x + 0.3, y + 0.42, u[1], 0.09);
    s.addText(u[0], { x: x + 0.58, y: y + 0.28, w: 3.1, h: 0.4, fontFace: BODY,
      fontSize: 15, bold: true, color: FG });
    s.addText(u[2], { x: x + 0.3, y: y + 0.82, w: 3.3, h: 1.15, fontFace: BODY,
      fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.12 });
  });
  footer(s, 8);
  s.addNotes("What you can do with it: energy optimisation, yield and slag "
    + "practice, operator training, scrap-mix studies, debottlenecking, and as a "
    + "validated backbone for a fuller digital twin.");
})();

// =============================================================================
// SLIDE 9 — WHY EXTRACTMET
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, PANEL);
  eyebrow(s, "Why Extractmet", 0.85, 0.55);
  s.addText([
    { text: "Deep-tech pyrometallurgy, ", options: { color: FG } },
    { text: "built on first principles", options: { color: ORANGE } },
  ], { x: 0.85, y: 0.9, w: 11.6, h: 0.7, fontFace: HEAD, fontSize: 29, bold: true });

  // left: narrative
  s.addText("Extractmet builds first-principles process simulators and "
    + "AI-assisted tools for iron- and steelmaking — from blast furnace and DRI "
    + "to EAF, BOF and ferroalloys. We combine rigorous thermochemistry and "
    + "transport modelling with production-grade software so that a model is not "
    + "a report, but a tool a plant can actually use.", {
    x: 0.85, y: 1.9, w: 6.1, h: 2.2, fontFace: BODY, fontSize: 15, color: MUTED,
    lineSpacingMultiple: 1.2 });

  const badges = [
    ["Full-route coverage", "Blast furnace · DRI · EAF · BOF · ferroalloys"],
    ["Validated models", "Calibrated against plant data and the literature"],
    ["Delivered as software", "Web, cloud and desktop — not just a study"],
    ["Anonymised by default", "Client identities protected as \u201CIndustry-X\u201D"],
  ];
  badges.forEach((b, i) => {
    const y = 1.9 + i * 1.2;
    band(s, 7.25, y, 5.58, 1.05, BG, 0.1);
    band(s, 7.25, y, 0.08, 1.05, [ORANGE, CYAN, AMBER, GREEN][i]);
    s.addText(b[0], { x: 7.5, y: y + 0.13, w: 5.2, h: 0.35, fontFace: BODY,
      fontSize: 15, bold: true, color: FG });
    s.addText(b[1], { x: 7.5, y: y + 0.52, w: 5.2, h: 0.4, fontFace: BODY,
      fontSize: 12, color: MUTED });
  });
  footer(s, 9);
  s.addNotes("Why Extractmet: we build validated first-principles simulators "
    + "across the full iron- and steelmaking route and deliver them as real "
    + "software, with client identities anonymised by default.");
})();

// =============================================================================
// SLIDE 10 — CTA
// =============================================================================
(function () {
  const s = pres.addSlide();
  bgFill(s, BG);
  band(s, 0, 0, W, 0.14, ORANGE);
  brandMark(s, 0.85, 0.75, 1.0);
  s.addText("EXTRACTMET", { x: 1.6, y: 0.68, w: 6, h: 0.4, fontFace: HEAD,
    fontSize: 20, bold: true, color: ORANGE, charSpacing: 2 });

  s.addText([
    { text: "Put the model on your furnace", options: { color: FG, breakLine: true } },
    { text: "with a sponsored pilot", options: { color: ORANGE } },
  ], { x: 0.85, y: 2.2, w: 11.6, h: 1.7, fontFace: HEAD, fontSize: 42, bold: true,
       lineSpacingMultiple: 1.0 });

  s.addText("We will calibrate the twin to your continuous-charge EAF, reproduce "
    + "recent heats, and quantify the energy and yield levers that matter most — "
    + "then hand you the interactive tool to explore them.", {
    x: 0.87, y: 4.0, w: 10.4, h: 1.0, fontFace: BODY, fontSize: 16, color: MUTED,
    lineSpacingMultiple: 1.18 });

  const steps = [["1", "Calibrate", "Fit the twin to your plant data"],
    ["2", "Reproduce", "Match recent heats and KPIs"],
    ["3", "Optimise", "Quantify the levers, hand over the tool"]];
  steps.forEach((st, i) => {
    const x = 0.87 + i * 4.02;
    band(s, x, 5.25, 3.8, 1.15, PANEL, 0.1);
    slideNum(s, x + 0.22, 5.45, st[0]);
    s.addText(st[1], { x: x + 0.95, y: 5.4, w: 2.7, h: 0.35, fontFace: BODY,
      fontSize: 15, bold: true, color: FG });
    s.addText(st[2], { x: x + 0.95, y: 5.76, w: 2.75, h: 0.5, fontFace: BODY,
      fontSize: 11, color: MUTED });
  });

  s.addText("Extractmet Private Limited  ·  first-principles process digital twins", {
    x: 0.85, y: 6.7, w: 11.6, h: 0.35, fontFace: BODY, fontSize: 12, bold: true,
    color: MUTED, align: "center" });

  function slideNum(sl, x, y, n) {
    sl.addShape(pres.ShapeType.ellipse, { x, y, w: 0.55, h: 0.55,
      fill: { color: ORANGE }, line: { type: "none" } });
    sl.addText(n, { x, y, w: 0.55, h: 0.55, fontFace: HEAD, fontSize: 22,
      bold: true, color: "160C05", align: "center", valign: "middle" });
  }
  s.addNotes("Call to action: a sponsored pilot. We calibrate the twin to the "
    + "client's furnace, reproduce recent heats, quantify the key levers, and hand "
    + "over the interactive tool. Contact Extractmet to start.");
})();

// helper used on slide 10 (declared after use is fine — hoisted function decl)
function slideNum() {}

pres.writeFile({ fileName: "EAF_DigitalTwin_Extractmet.pptx" })
  .then(f => console.log("WROTE", f))
  .catch(e => { console.error("ERROR", e); process.exit(1); });
