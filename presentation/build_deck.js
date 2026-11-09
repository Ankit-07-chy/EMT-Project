// Builds presentation/TDR_Cable_Fault_Detection.pptx from the project's own results.
//   cd presentation && node build_deck.js      (after collect_data.py; NODE_PATH=presentation/node_modules)
// Every number comes from deck_data.json (report/results/*); every picture from the repo.
"use strict";
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const ROOT = path.resolve(HERE, "..");
const SKILL = process.env.PPTX_SKILL_DIR || "";
const D = JSON.parse(fs.readFileSync(path.join(HERE, "deck_data.json"), "utf8"));
const OUTFILE = path.join(HERE, "TDR_Cable_Fault_Detection.pptx");

const THEME = {
  name: "TDR Copper and Teal", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1B1B1B", lt1: "FFFFFF", dk2: "14213D", lt2: "EEF2F5", accent1: "1F7A8C", accent2: "B85C24",
            accent3: "5E48B8", accent4: "2E7D32", accent5: "B26A00", accent6: "5F6670", hlink: "1F7A8C", folHlink: "5E48B8" },
};
const H = THEME.colors;
const TINT = { teal: "E2F1F4", copper: "F9ECE2", purple: "ECE8F8", green: "E6F2E7", amber: "FFF3DC", gray: "F0F1F3", navy: "E8EBF2" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "TDR Cable Fault Detection with Physics-Informed Machine Learning";
pres.author = "[Team members]";
pres.subject = "Final project presentation";
const C = pres.SchemeColor || pptxgen.SchemeColor;

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
  title: "TITLE", background: { color: H.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 1.7, w: 11.9, h: 1.9, fontSize: 40, bold: true, color: C.background1, valign: "bottom", align: "left", fontFace: THEME.headFontFace }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.7, y: 3.75, w: 11.9, h: 1.0, fontSize: 20, color: C.background2 }, text: "" } },
    { placeholder: { options: { name: "meta", type: "body", x: 0.7, y: 5.2, w: 11.9, h: 1.6, fontSize: 14, color: C.background2 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "SECTION", background: { color: H.dk2 },
  objects: [
    { placeholder: { options: { name: "num", type: "body", x: 0.7, y: 2.0, w: 6, h: 0.6, fontSize: 18, bold: true, color: C.accent2 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 2.6, w: 11.9, h: 1.3, fontSize: 38, bold: true, color: C.background1, align: "left", fontFace: THEME.headFontFace }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.7, y: 4.0, w: 11.4, h: 1.6, fontSize: 16, color: C.background2 }, text: "" } },
  ],
  slideNumber: { x: 12.4, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: "CADCE6" },
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: H.lt1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.28, w: 12.3, h: 0.8, fontSize: 30, bold: true, color: C.text2, valign: "middle", align: "left", fontFace: THEME.headFontFace }, text: "" } },
    { text: { text: "TDR cable fault detection with physics-informed ML", options: { x: 0.5, y: 7.05, w: 7, h: 0.3, fontSize: 10, color: "8A9099" } } },
  ],
  slideNumber: { x: 12.4, y: 7.05, w: 0.6, h: 0.3, fontSize: 10, color: "8A9099" },
});

// ------------------------------------------------------------------ helpers
let SECTION = "Introduction";
function section(num, title, sub, notes) {
  SECTION = title;
  pres.addSection({ title });
  const s = pres.addSlide({ masterName: "SECTION", sectionTitle: title });
  s.addText(num, { placeholder: "num" });
  // long titles would wrap to two lines and crowd the subtitle: keep them on one line (run-level size)
  if (title.length > 44) s.addText([{ text: title, options: { fontSize: 31 } }], { placeholder: "title" });
  else s.addText(title, { placeholder: "title" });
  if (sub) s.addText(sub, { placeholder: "body" });
  if (notes) s.addNotes(notes);
  return s;
}
function slide(title, notes) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: SECTION });
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}
function exists(p) { return fs.existsSync(p); }
function P(...a) { return path.join(ROOT, ...a); }
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
// place an image inside a box, keeping its aspect ratio (centred)
function img(s, file, x, y, w, h, alt, align = "center") {
  if (!exists(file)) {
    s.addText(`[missing figure: ${path.relative(ROOT, file)}]`, { x, y, w, h, isTextBox: true, fontSize: 12, color: C.accent5, align: "center", valign: "middle" });
    return { x, y, w, h };
  }
  const { w: pw, h: ph } = pngSize(file);
  const r = Math.min(w / pw, h / ph);
  const iw = pw * r, ih = ph * r;
  const ix = align === "left" ? x : x + (w - iw) / 2;
  const iy = y + (h - ih) / 2;
  s.addImage({ path: file, x: ix, y: iy, w: iw, h: ih, altText: alt || path.basename(file) });
  return { x: ix, y: iy, w: iw, h: ih };
}
// bullets: items are strings or [lead, rest]
function bullets(s, items, x, y, w, h, fs_ = 15, opts = {}) {
  const runs = [];
  items.forEach((it, i) => {
    const last = i === items.length - 1;
    if (Array.isArray(it)) {
      runs.push({ text: it[0] + " ", options: { bold: true, color: opts.lead || C.text2, bullet: opts.nobullet ? false : { indent: 14 } } });
      runs.push({ text: it[1], options: { breakLine: !last } });
    } else {
      runs.push({ text: it, options: { bullet: opts.nobullet ? false : { indent: 14 }, breakLine: !last } });
    }
  });
  s.addText(runs, { x, y, w, h, isTextBox: true, fontSize: fs_, color: C.text1, valign: "top", paraSpaceAfter: opts.space || 6, margin: 0.05 });
}
function card(s, x, y, w, h, title, body, color = "teal", fsb = 13, sp = 3) {
  const ec = { teal: H.accent1, copper: H.accent2, purple: H.accent3, green: H.accent4, amber: H.accent5, gray: H.accent6, navy: H.dk2 }[color];
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: TINT[color] }, line: { color: ec, width: 1.25 }, rectRadius: 0.08 });
  s.addText(title, { x: x + 0.15, y: y + 0.08, w: w - 0.3, h: 0.42, isTextBox: true, fontSize: 15, bold: true, color: ec, margin: 0, valign: "top" });
  if (body) {
    const items = Array.isArray(body) ? body : [body];
    s.addText(items.map((t, i) => ({ text: t, options: { breakLine: i < items.length - 1 } })),
      { x: x + 0.15, y: y + 0.52, w: w - 0.3, h: h - 0.6, isTextBox: true, fontSize: fsb, color: C.text1, valign: "top", margin: 0, paraSpaceAfter: sp });
  }
}
function stat(s, x, y, w, value, label, color = H.accent1) {
  s.addText(value, { x, y, w, h: 0.95, isTextBox: true, fontSize: 40, bold: true, color, margin: 0, fontFace: THEME.headFontFace });
  s.addText(label, { x, y: y + 0.95, w, h: 0.75, isTextBox: true, fontSize: 12, color: C.text1, margin: 0, valign: "top" });
}
function table(s, rows, x, y, w, opts = {}) {
  const fs_ = opts.fs || 11;
  const head = rows[0].map((t) => ({ text: String(t), options: { bold: true, color: "FFFFFF", fill: { color: H.dk2 }, fontSize: fs_ } }));
  const body = rows.slice(1).map((r, i) => r.map((t) => {
    const cell = typeof t === "object" && t !== null ? t : { text: String(t) };
    return { text: cell.text, options: Object.assign({ fill: { color: i % 2 ? "F6F8FA" : "FFFFFF" }, fontSize: fs_, color: H.dk1 }, cell.options || {}) };
  }));
  const fill = opts.fill === undefined ? Math.max(0, 6.35 - y) : opts.fill;
  const rowH = opts.rowH || (fill ? Math.max(0.26, Math.min(0.7, fill / rows.length)) : undefined);
  s.addTable([head, ...body], { x, y, w, colW: opts.colW, border: { type: "solid", pt: 0.5, color: "D5DAE0" }, fontFace: THEME.bodyFontFace,
    valign: "middle", margin: 0.05, rowH, autoPage: false });
}
function code(s, text, x, y, w, h, fs_ = 10.5) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: "F4F6F8" }, line: { color: "D5DAE0", width: 0.75 }, rectRadius: 0.05 });
  s.addText(text, { x: x + 0.12, y: y + 0.08, w: w - 0.24, h: h - 0.16, isTextBox: true, fontFace: "Courier New", fontSize: fs_, color: H.dk1, valign: "top", margin: 0 });
}
function takeaway(s, text, y = 6.45, x = 0.5, w = 12.3, h = 0.5) {
  s.addText(text, { x, y, w, h, isTextBox: true, fontSize: 14, italic: true, color: C.accent1, margin: 0, valign: "middle" });
}
const f2 = (v) => (v === null || v === undefined || Number.isNaN(v) ? "–" : Number(v).toFixed(2));
const f3 = (v) => (v === null || v === undefined || Number.isNaN(v) ? "–" : Number(v).toFixed(3));
const pc = (v, d = 0) => (v === null || v === undefined ? "–" : (100 * v).toFixed(d) + " %");
const FAM = { RF: "Random Forest", ET: "Extra Trees", KNN: "k-NN", MLP: "MLP", CNN: "1-D CNN" };
const mname = (k) => (k === "Baseline" ? "Baseline (classical)" : `${FAM[k.split("-")[0]] || k} ${k.endsWith("-A") ? "(raw)" : "(features)"}`);
const find = (arr, key, val) => (arr || []).find((r) => r[key] === val) || {};
const METHODS = ["Baseline", "RF-A", "RF-B", "ET-A", "ET-B", "KNN-A", "KNN-B", "MLP-A", "MLP-B", "CNN-A"];
const best = D.analysis.best_regressor || D.summary.best_regressor || "ET-B";
const bestc = D.analysis.best_classifier || D.summary.best_classifier || "CNN-A";
const L = (m) => find(D.loc_all, "method", m);
const LF = (m) => find(D.loc_fair, "method", m);
const DET = (m) => find(D.det, "method", m);
const fig = (n) => P("report", "figures", n);
const dia = (n) => P("presentation", "diagrams", n);
const cir = (n) => P("hardware", "circuits", n);
const scr = (n) => P("presentation", "screens", n);
const featRows = D.features || [];
const nPass = featRows.filter((r) => r.status === "Pass").length;

// =====================================================================================
// PART 1: INTRODUCTION
pres.addSection({ title: "Introduction" });
{
  const s = pres.addSlide({ masterName: "TITLE", sectionTitle: "Introduction" });
  s.addText("TDR Cable Fault Detection with Physics-Informed Machine Learning", { placeholder: "title" });
  s.addText("Finding and classifying coaxial-cable faults from one reflectometry trace: classical baseline vs ML / neural networks, from simulation to real data", { placeholder: "body" });
  s.addText([{ text: "[Team members]  ·  Guide: [Guide]", options: { breakLine: true } }, { text: "[Institution]  ·  [Course]  ·  November 2026" }], { placeholder: "meta" });
  s.addNotes("Title slide. Replace the bracketed placeholders with the team, guide and institution. The talk goes from zero (what a cable fault and TDR are) to the measured results and what is still pending.");
}
{
  const s = slide("What this presentation covers", "The deck follows the project from the first idea to the current state. Parts 6 and 7 (localization and detection) are the core technical results; part 11 is the testing evidence; part 14 separates what is done from what is pending.");
  const parts = ["1 Introduction and basics", "2 Development journey", "3 System architecture", "4 Hardware", "5 Software", "6 Localization (ML/NN)",
    "7 Detection (ML/NN)", "8 End-to-end working", "9 Hardware–software integration", "10 Feature by feature", "11 Testing and validation",
    "12 Performance analysis", "13 Problems and solutions", "14 Achievements and status", "15 Limitations and future", "16 Conclusion + appendix"];
  parts.forEach((p, i) => {
    const col = i % 4, row = Math.floor(i / 4);
    const colr = ["teal", "copper", "purple", "green"][col];
    card(s, 0.5 + col * 3.1, 1.35 + row * 1.35, 2.9, 1.15, p.split(" ")[0], p.split(" ").slice(1).join(" "), colr, 14);
  });
}
{
  const s = slide("The project in one slide", "What: a system that finds where a coaxial cable is faulty and what kind of fault it is, from one oscilloscope trace. Why: manual reading is slow and fails for weak echoes in noise. How: physics simulation trains ML models; a classical method is the reference. Status: software complete and tested; simulation and real-data (Zenodo) results measured; our own lab session pending.");
  card(s, 0.5, 1.3, 3.0, 3.25, "What", ["Send a voltage step into a cable.", "Record the echo with an oscilloscope.", "Software answers: is there a fault, which kind, and how far away?"], "teal", 14);
  card(s, 3.65, 1.3, 3.0, 3.25, "Why", ["Faults hide inside cables.", "Manual reading is slow and subjective.", "Weak echoes drown in noise.", "Lab instruments add ringing and jitter."], "copper", 14);
  card(s, 6.8, 1.3, 3.0, 3.25, "How", ["Physics simulator makes labelled traces.", "Classical baseline vs 5 ML families × 2 inputs.", "Calibration ties simulation to the real setup.", "Tested on 16 real measured traces (Zenodo)."], "purple", 14);
  card(s, 9.95, 1.3, 2.9, 3.25, "Status", ["Software: complete, 62 tests + self-test.", `Best distance model: ${mname(best)}.`, `Best fault-type model: ${mname(bestc)}.`, "Own lab measurements: pending."], "green", 14);
  stat(s, 0.5, 4.85, 3.0, `${f2(L(best).MAE_m)} m`, `mean distance error, ${best}, every faulted test trace`, H.accent1);
  stat(s, 3.65, 4.85, 3.0, pc(L("Baseline").coverage), "of faults the classical baseline locates at all", H.accent2);
  stat(s, 6.8, 4.85, 3.0, f3(find(D.cls, "method", bestc).F1), `macro-F1 of ${bestc} over 4 fault classes`, H.accent3);
  stat(s, 9.95, 4.85, 2.9, `${nPass}/${featRows.length}`, "features pass the end-to-end self-test", H.accent4);
}
{
  const s = slide("The real-world problem: faults hidden inside cables", "Every type of damage changes the cable's local impedance. That is why one technique, reflectometry, can see them all: the echo's sign separates high-impedance faults (breaks) from low-impedance ones (shorts, wet insulation).");
  const faults = [["Break (open)", "conductor cut → very high impedance → echo positive (Γ = +1)", "copper"],
    ["Short", "conductors touching → zero impedance → echo negative (Γ = −1)", "teal"],
    ["Damaged insulation / water", "partial leakage path → lower impedance → small negative echo", "purple"],
    ["Bad connector / corrosion", "series resistance → higher impedance → small positive echo", "amber"],
    ["Wrong-impedance repair", "50 Ω joined to 75 Ω → impedance step → Γ = +0.2", "gray"]];
  faults.forEach(([t, b, c], i) => card(s, 0.5, 1.3 + i * 1.02, 6.2, 0.92, t, b, c, 13));
  img(s, dia("d01_tdr_principle.png"), 7.0, 1.3, 5.85, 5.0, "TDR principle");
  takeaway(s, "One measurement from one end of the cable can reveal all of these faults.");
}
{
  const s = slide("Why reading the echo is hard", "These four effects are exactly what the simulator models and what the experiments vary: SNR (E1), distance range (E2), real instruments (E3/E4), weak faults (E5).");
  card(s, 0.5, 1.35, 6.0, 2.4, "Noise", ["Small echoes from partial faults sink into noise.", "A threshold low enough to see them also fires on noise."], "teal", 17, 10);
  card(s, 6.85, 1.35, 6.0, 2.4, "Edge speed (resolution)", ["Lab generators rise in 5–15 ns.", "Faults closer than vp·t_rise/2 (≈ 0.4–1.5 m) merge with the step."], "copper", 17, 10);
  card(s, 0.5, 3.95, 6.0, 2.4, "Cable loss and dispersion", ["The echo returns smaller and slower than it left.", "This biases both timing (distance) and height (fault type)."], "purple", 17, 10);
  card(s, 6.85, 3.95, 6.0, 2.4, "Real instruments", ["Ringing, adapter reflections, trigger jitter, 8-bit ADC, drift.", "A simple threshold mistakes them for faults."], "amber", 17, 10);
}
{
  const s = slide("TDR from zero: send a step, time its echo", "Explain the picture from top to bottom: the step travels at vp (about 20 cm per ns in RG-58); at the fault part of it reflects with coefficient Γ; the scope at the tee sees the step and, Δt later, the echo. Distance d = vp·Δt/2 because the signal goes there and back. The table on the right is the whole physics needed to classify faults.");
  img(s, dia("d01_tdr_principle.png"), 0.5, 1.2, 12.3, 5.75, "TDR principle with simulated open, short and matched traces");
}
{
  const s = slide("Key terms used in this presentation", "Every abbreviation used later is defined here once.");
  table(s, [["Term", "Meaning", "Term", "Meaning"],
    ["TDR", "time-domain reflectometry: send a step, time its echo", "SNR", "signal-to-noise ratio, 20·log10(V_inc/σ) in dB"],
    ["Z0", "characteristic impedance of the cable (50 Ω for RG-58)", "Rise time t_r", "10–90 % time of the edge; sets the resolution"],
    ["Γ (gamma)", "reflection coefficient (ZL − Z0)/(ZL + Z0)", "ML / NN", "machine learning / neural network"],
    ["V_inc", "height of the incident step at the tee", "RF / ET", "Random Forest / Extra Trees: averages of many decision trees"],
    ["vp, VF", "wave speed in the cable; VF = vp/c ≈ 0.66", "k-NN", "k-nearest neighbours: answer of the most similar training traces"],
    ["Δt", "round-trip time of the echo; d = vp·Δt/2", "MLP / CNN", "multi-layer perceptron / convolutional neural network"],
    ["Localization", "estimating the distance d to the fault", "Method A / B", "model input: raw trace (256 samples) / 23 physics features"],
    ["Detection", "deciding fault vs no fault and its class", "MAE / F1", "mean absolute error (m) / harmonic mean of precision and recall"]],
    0.5, 1.3, 12.3, { colW: [1.5, 4.65, 1.5, 4.65], fs: 12.5 });
}
{
  const s = slide("Existing methods and their limitations", "Our classical baseline is the threshold method of row 2, implemented carefully; the matched filter of row 4 is our baseline on the Zenodo pulse data. The gap we address is in the last column of row 5.");
  table(s, [["Method", "How it works", "Limitation"],
    ["Manual scope reading", "operator measures Δt with cursors", "slow, subjective, impossible for small echoes in noise"],
    ["Threshold / peak detection", "first derivative lobe above a noise threshold", "misses weak echoes at low SNR; ringing causes false early detections"],
    ["Commercial TDR instruments", "dedicated fast-edge hardware + vendor software", "expensive, closed algorithms, not in a student lab"],
    ["Matched filter (Shin et al. 2005)", "correlate with the expected echo shape", "needs a known pulse shape; still a threshold at the end"],
    ["Published ML on TDR (Scarpetta 2021, Slimani 2024/25, Smail 2011)", "CNN / k-NN / neural inverse model", "each uses its own data; rarely compared with a classical baseline on identical traces"]],
    0.5, 1.35, 12.3, { colW: [3.4, 4.2, 4.7], fs: 14, fill: 4.3 });
  takeaway(s, "Our angle: five model families × two inputs vs a classical baseline on identical traces, then the same chain on real data.", 5.9);
}
{
  const s = slide("Our proposed solution", "Six design decisions. The first three are about fair, reproducible ML; the last three connect it to the real world.");
  const items = [["1 Physics first", "transmission-line simulator → unlimited labelled traces", "teal"],
    ["2 One processing chain", "simulated and measured traces go through identical code", "teal"],
    ["3 Fair comparison", "5 families × 2 inputs vs baseline, chosen on validation only", "purple"],
    ["4 Calibration", "vp, t0, rise, V_inc measured → simulator re-centred", "copper"],
    ["5 Real-data test", "16 measured traces + 1 M simulated (Zenodo 5720438)", "gray"],
    ["6 Lab tooling", "auto-capture, labelled log, live check, beginner hardware guide", "green"]];
  items.forEach(([t, b, c], i) => card(s, 0.5 + (i % 3) * 4.15, 1.35 + Math.floor(i / 3) * 2.55, 3.95, 2.3, t, b, c, 17));
}
{
  const s = slide("Objectives and expected outcome", "Status column is honest: O5 needs our own lab session. Everything else is implemented and measured.");
  table(s, [["#", "Objective", "Implemented in", "Status"],
    ["O1", "Simulate realistic labelled TDR traces", "src/sim_tdr.py", "Done, physics-checked"],
    ["O2", "Classical baseline to beat", "src/baseline.py", "Done"],
    ["O3", "ML for distance + fault type; raw vs features", "features.py, models.py, train.py", "Done, 18 models"],
    ["O4", "Experiments E1–E6", "src/evaluate.py, analysis.py", "Done on simulation"],
    ["O5", "Lab setup, calibration, labelled real data", "capture.py, calibrate.py, hardware/", "Software done; lab pending"],
    ["O6", "Interactive demonstrator", "app/dashboard.py", "Done"],
    ["O7", "Validate on real measured traces", "src/zenodo.py", "Done (16 Zenodo traces)"]],
    0.5, 1.35, 12.3, { colW: [0.6, 4.9, 3.9, 2.9], fs: 13 });
}

// PART 2: JOURNEY
section("Part 2", "Development journey", "How the project went from a brief to a tested system, stage by stage");
{
  const s = slide("Milestones in the order they were built", "Each milestone depended on the previous: the baseline needed the simulator to test against theory; the models needed the processing chain; evaluation needed models; the lab software needed the processing chain; the review came last and changed the code before the final runs.");
  img(s, dia("d10_timeline.png"), 0.5, 1.2, 12.3, 5.75, "Development timeline");
}
{
  const s = slide("Research and planning: from literature to model choice", "We read the reading list and mapped each paper to something we build or compare against. The key insight from Slimani: a simple k-NN beat a 1-D CNN at localisation, so classical ML must be in the comparison, not only deep learning.");
  table(s, [["Source", "What it contributed", "What we built"],
    ["Brief (WP1–WP8)", "RF / ET with physics features, E1–E6", "baseline, RF-B, ET-B, experiments"],
    ["Smail et al. 2011", "train a neural network on physics simulations, invert on real data", "simulator + MLP"],
    ["Slimani et al. 2024/25", "k-NN beat a 1-D CNN for localisation (RG-58 simulations)", "k-NN on both inputs"],
    ["Scarpetta et al. 2021", "1-D CNN on pulse TDR + public dataset with real traces", "1-D CNN, Zenodo pipeline"],
    ["Shin et al. 2005", "cross-correlation detection, resolution limited by rise time", "matched-filter baseline (Zenodo)"],
    ["Chang & Park 2019", "time-frequency CNN", "noted as future work (P3-7)"]],
    0.5, 1.35, 12.3, { colW: [2.8, 5.3, 4.2], fs: 13 });
}
{
  const s = slide("Requirements we set before coding", "Functional requirements come from the brief; non-functional ones came from the lab situation (unknown scope model, limited lab time, need for a demo).");
  card(s, 0.5, 1.35, 6.0, 4.9, "Functional", ["Locate a fault (distance in m) from one trace.", "Classify: open / short / matched / partial.", "Work with any common lab scope (unknown model).", "Calibrate the setup from measurements.", "Compare classical vs ML on identical traces.", "Show results interactively."], "teal", 17, 12);
  card(s, 6.85, 1.35, 6.0, 4.9, "Non-functional", ["Runs on a student laptop (CPU only).", "Reproducible: fixed seeds, stored settings.", "Fair: hyper-parameters chosen on validation only.", "Safe with downloaded data (no code execution).", "Usable without hardware (simulated scope).", "Every feature testable automatically."], "copper", 17, 12);
}
{
  const s = slide("Technology selection and why", "All open-source Python; PyTorch CPU build because no GPU is assumed; Streamlit because a dashboard is one Python file; PyVISA because it talks to every major scope vendor through one API.");
  table(s, [["Need", "Choice", "Why this one"],
    ["Numerics, signal processing", "NumPy, SciPy", "FFT-based simulator, filters, least-squares fit"],
    ["Classical ML", "scikit-learn", "RF, ET, k-NN, MLP with one fit/predict interface"],
    ["Neural network (1-D CNN)", "PyTorch (CPU)", "flexible, runs on a laptop, streams large datasets"],
    ["Instrument control", "PyVISA + pyvisa-py", "one API for USB/LAN scopes; driver-free fallback"],
    ["Dashboard", "Streamlit + Plotly", "interactive web app from one Python file, zoomable plots"],
    ["Figures", "Matplotlib, schemdraw", "report figures; circuit diagrams as code"],
    ["Data", "pandas, joblib", "tables, model bundles"],
    ["Testing", "pytest + own self-test", "unit tests + end-to-end runs in a sandbox"]],
    0.5, 1.35, 12.3, { colW: [3.3, 3.0, 6.0], fs: 13 });
}
{
  const s = slide("Development environment and first run", "Steps a new team member follows. The self-test proves the installation works without any hardware.");
  code(s, [
    "# 1. Python environment (Windows, Python 3.11+)",
    "python -m venv .venv",
    ".venv\\Scripts\\pip install -r requirements.txt",
    ".venv\\Scripts\\pip install torch --index-url https://download.pytorch.org/whl/cpu",
    "",
    "# 2. Check packages, VISA backends, calibration, models",
    ".venv\\Scripts\\python index.py check",
    "",
    "# 3. Train and evaluate on simulation (about 1 h on a laptop)",
    ".venv\\Scripts\\python index.py train",
    ".venv\\Scripts\\python index.py evaluate",
    ".venv\\Scripts\\python index.py analyze",
    "",
    "# 4. Prove every feature works (temporary folder, no hardware)",
    ".venv\\Scripts\\python index.py selftest",
    "",
    "# 5. Demo",
    ".venv\\Scripts\\python index.py dashboard"].join("\n"), 0.5, 1.3, 8.1, 5.55, 11.5);
  card(s, 8.8, 1.3, 4.05, 5.55, "What each step gives", ["requirements.txt pins numpy, scipy, pandas, matplotlib, scikit-learn, streamlit, plotly, pyvisa, pytest, schemdraw.", "", "check: [ok] per package, VISA backend, calibration and model status.", "", "train: models/tdr_models.joblib (18 models).", "", "evaluate / analyze: report/results + figures.", "", "selftest: report/results/feature_tests.md."], "gray", 13);
}
{
  const s = slide("Stage by stage: what, why, input, output", "Read row by row. The 'next depends on' column explains the order of the timeline.");
  table(s, [["Stage", "What we did / why", "Input → output", "Challenge → resolution"],
    ["Simulator", "frequency-domain transmission line, all fault kinds: labelled data at no cost", "parameters → (t, v) + labels", "tail of incident edge looked like an echo → shared lobe boundary"],
    ["Baseline", "threshold + lobe detector: the reference to beat", "trace → Δt, d, Γ, class", "noise false alarms → MAD noise, adaptive smoothing"],
    ["Features / datasets", "Method A grid, 23 features; cached sets", "traces → X (n×256), F (n×23)", "stale caches → config fingerprint in names"],
    ["Models + training", "5 families, grid search on validation", "train/val → bundle", "no sample weights in k-NN/MLP → row repetition"],
    ["Evaluation", "E1–E6, 10 figures, then deep analysis", "bundle + test sets → tables", "unfair comparison → 'fair' subset metric"],
    ["Lab software", "PyVISA capture, universal CSV, calibration, fit", "scope → CSV + log → calibration.json", "unknown scope → 4 vendor drivers + CSV fallback"],
    ["Real data", "Zenodo 5720438, 4.18 GB, safe parsing", "archive → Z1–Z3 results", "pickled labels → restricted unpickler"],
    ["Review + tests", "independent review: 14 findings, 12 fixed, 1 documented, 1 not occurring; self-test", "code → fixes + evidence", "see Part 13"]],
    0.5, 1.3, 12.3, { colW: [1.8, 4.0, 3.0, 3.5], fs: 11.5 });
}

// PART 3: ARCHITECTURE
section("Part 3", "System architecture", "Three layers: lab hardware, online software per trace, offline simulation/training/evaluation");
{
  const s = slide("Overall system block diagram", "Top: the physical signal path. Middle: what happens to each measured trace. Bottom: the offline loop that produces the models. Calibration is the bridge: it is measured on the hardware and re-centres the simulator. The Zenodo box is the external real-data test.");
  img(s, dia("d02_system_block.png"), 0.5, 1.2, 12.3, 5.75, "System block diagram");
}
{
  const s = slide("Software architecture: four layers", "Entry points call pipelines; pipelines use the core library; everything reads and writes plain files. TDR_HOME moves all storage, which is how tests run without touching real results.");
  img(s, dia("d03_software_architecture.png"), 0.5, 1.2, 12.3, 5.75, "Software architecture");
}
{
  const s = slide("Data flow inside one trace", "Six preprocessing steps make every trace look the same; then three consumers: the classical detector and the two model inputs. If the incident edge cannot be found the trace gets no prediction rather than a made-up one.");
  img(s, dia("d04_signal_pipeline.png"), 0.5, 1.2, 12.3, 5.75, "Signal processing pipeline");
}
{
  const s = slide("Complete workflow, start to finish", "Steps 1–6 happen at the bench for every configuration; 7–12 once after the session. All software steps are rehearsed end to end with the simulated scope.");
  img(s, dia("d09_end_to_end.png"), 0.5, 1.2, 12.3, 5.75, "End-to-end workflow");
}

// PART 4: HARDWARE
section("Part 4", "Hardware", "Standard lab instruments, coaxial cables and a few passive parts. No microcontroller, no firmware. Built in the order of hardware/README.md");
{
  const s = slide("Hardware set-up at a glance", "The tee directly on the scope input is the reference plane: every distance is measured from there. A short generator lead keeps secondary echoes out of the window.");
  img(s, cir("p01_wiring_overview.png"), 0.5, 1.2, 8.6, 5.4, "Wiring overview");
  bullets(s, [["Generator:", "50 Ω source, square 0 → 2 V, 100 kHz"], ["Tee on CH1:", "joins generator, cable and scope"],
    ["Cable:", "RG-58, 2 / 5 / 10 m"], ["Load:", "open, short, 50 Ω or an approved fault"], ["Laptop:", "USB-TMC to the scope, runs capture"]], 9.3, 1.4, 3.6, 5.0, 14);
}
{
  const s = slide("Component inventory (bill of materials)", "Full list with specifications, quantities and tick boxes in hardware/README.md §3. Specifications are minimums; the column 'why' is the selection reason.");
  table(s, [["Component", "Specification", "Purpose / why selected"],
    ["Function generator", "50 Ω out; 0 V/2 V levels; edge ≤ 15 ns (≤ 5 ns better)", "makes the incident step; 50 Ω absorbs returning echoes"],
    ["Digital oscilloscope", "≥ 100 MHz, ≥ 500 MSa/s, 1 MΩ, USBTMC, CSV export", "records the step and echo; bandwidth sets rise time"],
    ["Coaxial cables RG-58", "Z0 50 Ω, VF ≈ 0.66; 2, 5, 10 m (+ 3, 2, 1 m pieces)", "lines under test; ≥ 2 lengths needed for calibration"],
    ["BNC tee ×2, short lead ≤ 0.5 m", "50 Ω, UG-274 style", "reference plane at CH1; second tee for shunt/stub"],
    ["Terminations", "50 Ω end + feed-through, shorting cap, 75 Ω", "matched / short / joint loads"],
    ["Fault parts", "22, 49.9, 100 Ω 1 % 0.25 W; binding-post adapters; series box; RG-59", "partial faults with known Γ"],
    ["Tools", "multimeter, tape (mm), USB stick, camera", "check parts, lengths, CSV fallback, setup photo"],
    ["Optional pulser", "74AC14, 4 × 180 Ω, 5 V", "≈ 2–3 ns edge for better resolution"]],
    0.5, 1.3, 12.3, { colW: [2.9, 4.8, 4.6], fs: 12 });
}
{
  const s = slide("Component deep-dive: generator, oscilloscope, cable", "Each component's operating principle in one line, how we use it, what we expect, and the common problem with its fix.");
  card(s, 0.5, 1.3, 4.0, 5.55, "Function generator", ["Principle: internal source Vs behind Rs = 50 Ω.", "Use: square 0→2 V, 100 kHz; high time 5 µs ≫ round trip.", "I/O: OUTPUT BNC → short lead → tee.", "Power: mains, earthed socket.", "Expect: 2.0 V open, 1.0 V into 50 Ω (H3).", "Problem: plateau doubled → 'Load = 50 Ω' display setting only."], "copper", 14.5, 8);
  card(s, 4.67, 1.3, 4.0, 5.55, "Oscilloscope", ["Principle: samples V(t) with an 8-bit ADC after a trigger.", "Use: CH1 1 MΩ, DC, BW limit off, trigger rising 0.5 V Normal.", "I/O: CH1 BNC in; USB-B (USBTMC) or LAN out.", "Expect: step to 1 V, echo at 2L/vp.", "Problem: half-height plateau → input set to 50 Ω."], "teal", 14.5, 8);
  card(s, 8.84, 1.3, 4.0, 5.55, "Coax + tee + loads", ["Principle: wave travels at vp; impedance changes reflect.", "RG-58: Z0 50 Ω, VF 0.66, 16 dB/100 m @100 MHz.", "Tee: male stem on CH1, two female ports.", "Loads: open (Γ +1), short (−1), 50 Ω (0).", "Problem: extra echoes → long lead or tee not on CH1."], "purple", 14.5, 8);
}
{
  const s = slide("Fault fixtures: how each discontinuity is assembled", "Only instructor-approved fixtures are built. Measured resistor values go into the log, not nominal ones.");
  img(s, cir("p02_fault_fixtures.png"), 0.5, 1.2, 12.3, 5.75, "Fault fixtures");
}
{
  const s = slide("Circuit diagrams: generator check and basic TDR set-up", "Left: H3 checks the generator's output resistance (V_open/V_50 − 1 times 50 Ω). Right: the measurement circuit used for every trace; the scope input is modelled as 1 MΩ ∥ 15 pF.");
  img(s, cir("c01_generator_check.png"), 0.5, 1.3, 6.0, 5.2, "Generator check circuit");
  img(s, cir("c02_tdr_setup.png"), 6.8, 1.3, 6.0, 5.2, "Basic TDR circuit");
}
{
  const s = slide("Circuit diagrams of the partial faults", "Series and shunt resistors at 3 m with a matched far end, the 50/75 Ω joint and the open stub. Expected levels: 1.33 V, 0.67 V, 1.2 V, dip to ≈ 0.67 V.");
  img(s, cir("c07_series_resistor.png"), 0.5, 1.25, 6.0, 2.75, "Series resistor circuit");
  img(s, cir("c08_shunt_resistor.png"), 6.8, 1.25, 6.0, 2.75, "Shunt resistor circuit");
  img(s, cir("c09_75ohm_joint.png"), 0.5, 4.15, 6.0, 2.75, "75 ohm joint circuit");
  img(s, cir("c10_tee_open_stub.png"), 6.8, 4.15, 6.0, 2.75, "Open stub circuit");
}
{
  const s = slide("Expected scope pictures (simulated before the lab)", "Produced by our simulator for RG-58, 5 ns rise, 1 V incident step. At the bench these are the 'is it right?' reference: the levels and the 2L/vp delays must match.");
  img(s, cir("w03_open_end.png"), 0.5, 1.25, 6.0, 2.8, "Expected open-end traces");
  img(s, cir("w04_short_end.png"), 6.8, 1.25, 6.0, 2.8, "Expected short traces");
  img(s, cir("w06_resistive_end.png"), 0.5, 4.15, 6.0, 2.8, "Expected resistive loads");
  img(s, cir("w10_tee_open_stub.png"), 6.8, 4.15, 6.0, 2.8, "Expected open stub");
}
{
  const s = slide("Port-to-port connection table (set-up B)", "Every connection is a BNC bayonet. Fault set-ups only change what is attached to tee side port 2 (hardware/README.md §5.3).");
  table(s, [["#", "From (port, connector)", "Via", "To (port, connector)"],
    ["B1", "Scope CH1 input, BNC female", "–", "tee male stem, directly on CH1"],
    ["B2", "Generator OUTPUT, BNC female", "short lead ≤ 0.5 m (M–M)", "tee side port 1"],
    ["B3", "Tee side port 2", "–", "cable under test, end A"],
    ["B4", "Cable end B", "–", "open / shorting cap / 50 Ω terminator / fault"],
    ["B5", "Laptop USB-A", "USB A-B cable", "scope rear USB Device (USBTMC)"]],
    0.5, 1.35, 12.3, { colW: [0.7, 3.9, 3.3, 4.4], fs: 15, fill: 4.2 });
  takeaway(s, "Ground reference: BNC shells, tied to mains earth through both instruments' earthed sockets.", 5.85);
}
{
  const s = slide("Optional fast-edge pulser: schematic and pinout", "74AC14 Schmitt inverters: gate A is an RC oscillator (≈ 100 kHz), gate B buffers, four gates in parallel drive the BNC through 180 Ω each, about 48 Ω source impedance to match the cable. AC family, not HC: HC edges are 6–10 ns.");
  img(s, cir("c12_fast_edge_pulser.png"), 0.5, 1.25, 7.4, 5.6, "74AC14 pulser schematic");
  table(s, [["Pin", "Connects to"], ["1 (1A)", "R1 10 kΩ + C1 1 nF"], ["2 (1Y)", "R1 (feedback), pin 3"], ["4 (2Y)", "pins 5, 9, 11, 13"],
    ["6, 8, 10, 12", "180 Ω each → BNC centre"], ["7 GND", "ground plane, BNC shell"], ["14 VCC", "+5 V, 100 nF + 10 µF"]],
    8.1, 1.4, 4.75, { colW: [1.5, 3.25], fs: 12.5 });
}
{
  const s = slide("Power distribution and safety", "Only the optional pulser needs a DC supply; everything else is mains-powered instruments and passive parts. Safety rules are from the lab procedure and override convenience.");
  table(s, [["Equipment", "Supply", "Draw / note"],
    ["Generator, scope", "mains via earthed sockets", "< 100 W each; never defeat the earth pin"],
    ["Laptop", "battery or charger", "run on battery if 50/60 Hz hum appears"],
    ["Cables, loads", "none (passive)", "max ≈ 17 mW in a 22 Ω load"],
    ["Pulser (optional)", "5.0 V ± 0.25 V, ≥ 150 mA", "≈ 10 mA idle, ≈ 105 mA peak into a short"]],
    0.5, 1.35, 7.4, { colW: [2.0, 2.6, 2.8], fs: 14, rowH: [0.55, 1.05, 1.05, 1.05, 1.05] });
  card(s, 8.2, 1.35, 4.65, 4.75, "Safety rules", ["Generator ≤ 5 V peak (2 V used); an open end doubles it.", "Scope on 1 MΩ; never the 50 Ω input above its rating.", "Discharge long cables before connecting.", "Generator output OFF while changing loads.", "Only instructor-approved modifications.", "No high-voltage (avalanche) pulsers."], "amber", 15, 10);
}
{
  const s = slide("Hardware assembly and test sequence (S1–S15)", "The beginner manual gives each step a what / why / you need / how / done-when. The software side of every step is ready; the lab steps need lab access.");
  table(s, [["Step", "Task", "Done when", "Status"],
    ["S1–S2", "approvals; collect and multimeter-check parts", "every BOM row ticked, parts verified", "pending (lab)"],
    ["S3", "laptop install + rehearsal", "check ok, selftest no Fail", "ready"],
    ["S4–S5", "equipment discovery; laptop ↔ scope", "*IDN? string printed", "pending (lab)"],
    ["S6–S7", "generator check (Rs 45–55 Ω); basic set-up", "flat 1 V plateau, echo where expected", "pending (lab)"],
    ["S8", "calibration: open at ≥ 2 lengths + matched", "VF 0.64–0.68, σ(vp)/vp < 1 %, |t0| < 3 ns", "pending (lab)"],
    ["S9–S11", "test matrix, partial faults, low-SNR", "≈ 180 + fault + low-SNR traces logged", "pending (lab)"],
    ["S12–S14", "data check + backup; process; report", "E3/E4 marked LAB", "software ready"],
    ["S15", "optional pulser", "Rs 45–55 Ω, faster edge", "optional"]],
    0.5, 1.3, 12.3, { colW: [1.2, 4.5, 4.4, 2.2], fs: 12.5 });
}
{
  const cal = find(featRows, "id", "F04");
  const s = slide("Calibration: method and rehearsal result", "Calibration fits Δt = (2/vp)·L + t0 over open-circuit traces at several lengths. The rehearsal uses the simulated scope, whose true vp is known, so it measures the method's accuracy; the real values come from the lab.");
  bullets(s, [["Measure:", "20 open-circuit traces at each of ≥ 2 lengths (2, 5, 10 m), 10 matched traces."], ["Fit:", "straight line Δt vs L → slope 2/vp, intercept t0 (tee + trigger delay)."],
    ["Also:", "rise time → resolution vp·t_r/2; V_inc and noise at the normal amplitude."], ["Used by:", "every later command automatically (calibration.json)."],
    ["Rehearsal (simulated scope):", cal.actual || "see feature_tests.md"]], 0.5, 1.35, 6.4, 4.1, 17, { space: 10 });
  img(s, cir("w03_open_end.png"), 7.1, 1.35, 5.75, 4.1, "Open-end traces used for calibration");
  takeaway(s, "Status: method tested; real calibration values pending the lab session.", 5.75);
}

// PART 5: SOFTWARE
section("Part 5", "Software", "Python 3.13 · NumPy/SciPy · scikit-learn · PyTorch · PyVISA · Streamlit/Plotly · pytest");
{
  const s = slide("Folder structure", "Code in src/ and app/; results regenerate into report/; data/ and models/ are produced by commands (and moveable with TDR_HOME).");
  code(s, ["D:\\EMT", "├─ index.py              one CLI for every step", "├─ src/", "│  ├─ config.py           paths, cable presets, SimConfig", "│  ├─ sim_tdr.py          transmission-line simulator",
    "│  ├─ preprocess.py       align · normalise · denoise", "│  ├─ baseline.py         classical detector", "│  ├─ features.py         Method A grid, 23 features", "│  ├─ dataset.py          build / save / load sets",
    "│  ├─ models.py           RF·ET·KNN·MLP·1-D CNN", "│  ├─ train.py · evaluate.py · analysis.py", "│  ├─ scope_io.py · capture.py · calibrate.py · fit_sim.py", "│  ├─ zenodo.py           external real data",
    "│  └─ selftest.py         every feature end to end", "├─ app/dashboard.py      Streamlit + Plotly", "├─ tests/                62 pytest tests", "├─ hardware/             manual, procedure, circuits/",
    "├─ docs/  report/        documentation, results, figures", "└─ presentation/         this deck + diagrams"].join("\n"), 0.5, 1.3, 7.3, 5.55, 11.5);
  card(s, 8.1, 1.3, 4.75, 5.55, "Main execution flow", ["1 index.py parses the command.", "2 Dispatch to src/<module>.main() inside a CLI error handler.", "3 config.load_calibration() merges calibration.json with defaults.",
    "4 The module reads its inputs (traces, datasets, bundle).", "5 Writes outputs to data/, models/ or report/.", "6 Wrong inputs: one-line error, exit code ≠ 0 (TDR_DEBUG=1 for a traceback)."], "teal", 14.5, 10);
}
{
  const s = slide("Modules: purpose, inputs and outputs (1/2)", "Core library. Every module is a plain Python file with functions; no hidden global state except the configuration.");
  table(s, [["Module", "Purpose", "Input → output", "Key algorithm"],
    ["config.py", "paths, presets, ranges, calibration", "calibration.json → settings", "merge with datasheet defaults; cfg fingerprint"],
    ["sim_tdr.py", "make labelled traces", "params → (t, v), labels", "Γ_in(f) recursion, IFFT, scope model"],
    ["scope_io.py", "read any scope CSV", "file → Waveform", "dialect detection, unit parsing"],
    ["preprocess.py", "normalise every trace", "(t, v) → Processed", "MAD noise, V_inc, 50 % alignment, Gaussian"],
    ["baseline.py", "classical detection", "Processed → Δt, d, Γ, class", "derivative threshold + lobe walk"],
    ["features.py", "model inputs", "Processed → grid, 23 features", "resampling, crossings, energies"],
    ["models.py", "model zoo", "params → estimator", "sklearn pipelines, PyTorch CNN"]],
    0.5, 1.3, 12.3, { colW: [1.8, 3.2, 3.4, 3.9], fs: 12.5 });
}
{
  const s = slide("Modules: purpose, inputs and outputs (2/2)", "Pipelines: one per CLI command.");
  table(s, [["Module", "Purpose", "Input → output"],
    ["dataset.py", "build/save/load simulated and lab sets", "traces + labels → CSV, X.npy, raw.npz"],
    ["train.py", "grid search on validation, bundle", "train/val → models/tdr_models.joblib"],
    ["evaluate.py", "E1–E6, ten figures, summary", "bundle + test sets → report/results"],
    ["analysis.py", "error stats, P/R/F1, latency, sizes", "bundle + test sets → analysis_*.csv, a1–a6"],
    ["capture.py", "scope capture, labelled log, quick check", "VISA scope → CSV + lab_log.csv"],
    ["calibrate.py / fit_sim.py", "vp, t0, rise, V_inc; simulator fit", "open traces → calibration.json, fig0 / fig5"],
    ["zenodo.py", "external dataset pipeline", "4.18 GB archive → Z1–Z3"],
    ["selftest.py", "run every feature in a sandbox", "→ feature_tests.md"],
    ["app/dashboard.py", "interactive analysis", "bundle + results + traces → web UI"]],
    0.5, 1.3, 12.3, { colW: [2.6, 4.9, 4.8], fs: 12.5 });
}
{
  const s = slide("Inside the simulator (sim_tdr.py)", "The load seen at the input is computed per frequency, then transformed to time. This is what makes thousands of realistic traces per minute possible, with exact labels.");
  code(s, ["# per frequency f (simplified from transfer_function)", "gamma = alpha(f) + 1j*2*pi*f/vp          # cable: loss + delay",
    "G_d   = fault_reflection(kind, ZL, R, Z2, stub, f)", "G_in  = G_d * exp(-2*gamma*d)             # back to the input", "Z_in  = Z0 * (1 + G_in) / (1 - G_in)",
    "Z_tee = Z_in || Z_scope(1 MOhm, C)         # scope at the tee", "H     = Z_tee / (Rs + Z_tee)               # divider with generator",
    "H    *= gaussian_edge(f, rise)", "v = cumsum(irfft(H)) * Vs                  # step response", "v = scope(v, jitter, drift, noise@SNR, 8-bit)"].join("\n"), 0.5, 1.3, 12.3, 2.8, 15);
  bullets(s, [["Fault kinds:", "end load, series R, shunt R, impedance step, open stub."], ["Loss:", "α(f) = α_dc + k_s√f + k_d·f from datasheet points."],
    ["Randomised:", "d, Γ, rise 2–10 ns, SNR 10–40 dB, Rs ±8 %, scope C, sampling."], ["Checked:", "final level = 1 + Γ within 0.015, delay = 2L/vp (F09)."]], 0.5, 4.35, 12.3, 2.3, 17, { space: 10 });
}
{
  const s = slide("Inside preprocessing: one normalised trace from any source", "The fix from the code review is visible here: V_inc is estimated per measured trace, so traces taken at a different generator amplitude (the low-SNR set) are normalised correctly.");
  code(s, ["def preprocess_measured(t, v, cal, v_inc=None):", "    est = preprocess(t, v, v_inc=None)     # estimate from this trace", "    ref = cal['v_inc_v'] if calibrated else None",
    "    use_ref = (not est.ok                  # estimate failed", "               or 0.8 <= est.v_inc/ref <= 1.25   # same amplitude",
    "               or est.rise_inc > 1.6*cal['rise_time_s'])  # echo merged", "    return preprocess(t, v, v_inc=ref) if use_ref else est"].join("\n"), 0.5, 1.3, 12.3, 2.05, 14);
  bullets(s, [["1 Baseline:", "median of pre-trigger samples removed."], ["2 V_inc:", "plateau after the first big rise."], ["3 Normalise:", "plateau = 1, open → 2, short → 0."]], 0.5, 3.6, 6.0, 2.2, 17, { space: 10 });
  bullets(s, [["4 Align:", "incident 50 % crossing → t = 0 (removes trigger jitter)."], ["5 Denoise:", "Gaussian, 0.3–0.9 × rise time depending on noise."], ["6 Grid:", "256 points, 1 ns, −16…239 ns (Method A)."]], 6.85, 3.6, 6.0, 2.2, 17, { space: 10 });
  takeaway(s, "Same code for simulated, Zenodo-style and lab traces: the models never see a different preprocessing.", 6.0);
}
{
  const s = slide("Inside the classical baseline (baseline.py)", "The baseline is deliberately strong: robust noise estimate, a threshold that adapts to both noise and edge size, skipping of tiny ADC lobes, loss-compensated Γ and a merged-edge mode for very close faults.");
  code(s, ["ds  = d/dt smooth(trace)", "thr = max(0.03*peak_incident_slope, 4.5*MAD(ds))", "for lobe in lobes_after_incident(ds, thr):", "    if abs(lobe.area) >= 0.02:   # skip ADC / noise lobes",
    "        dt = t50(lobe) - t_offset; amp = lobe.area; break", "d     = vp*dt/2", "gamma = amp*exp(2*alpha(0.1/rise)*d)", "cls   = matched if |amp|<0.035 else open if gamma>=0.82",
    "        else short if gamma<=-0.82 else partial"].join("\n"), 0.5, 1.3, 12.3, 2.55, 15);
  bullets(s, [["Output:", "found?, Δt, d, amplitude, Γ, class, second echo."], ["Merged mode:", "same-polarity echo inside the incident edge → Δt from the lobe centroid."],
    ["Strength:", "very accurate when it finds the echo."], ["Weakness:", "misses weak echoes at low SNR; ringing → false early lobes."]], 0.5, 4.1, 12.3, 2.4, 17, { space: 10 });
}
{
  const s = slide("Method B: the 23 physics features", "Features are computed automatically from every trace; the true distance, Γ and attenuation are never inputs. 8 come from the baseline detector.");
  table(s, [["Group", "Features"], ["Timing", "delta_t_ns, t_dpeak_ns, t_cross10/25/50_ns, second_t_ns, dev_centroid_ns"],
    ["Amplitude / sign", "refl_amp_ratio, polarity, v_final_ratio, gamma_est, second_amp, slope_ratio"],
    ["Shape", "refl_rise_ns, inc_rise_ns, energy_0_60, energy_60_120, energy_120_180, energy_180_240"],
    ["Quality / flags", "noise_sigma, ts_ns, refl_found, merged"]], 0.5, 1.35, 6.9, { colW: [1.9, 5.0], fs: 15, rowH: [0.5, 1.05, 1.05, 1.05, 1.05] });
  img(s, fig("fig9_feature_importance.png"), 7.6, 1.35, 5.25, 4.8, "Feature importance");
}
{
  const s = slide("Instrument control (capture.py)", "One driver class per vendor family behind the same acquire() interface. The preamble converts raw ADC bytes into volts and seconds. SimScope replaces the instrument for rehearsals and tests.");
  code(s, ["class Rigol(ScopeDriver):", "    def read(self, ch):", "        self.w(f':WAV:SOUR CHAN{ch}')", "        self.w(':WAV:MODE NORM'); self.w(':WAV:FORM BYTE')",
    "        pre = [float(x) for x in self.q(':WAV:PRE?').split(',')]", "        raw = self.inst.query_binary_values(':WAV:DATA?', datatype='B')",
    "        v = (raw - yorig - yref) * yinc     # from the preamble", "        t = (arange(n) - xref) * xinc + xorig", "        return t, v"].join("\n"), 0.5, 1.3, 7.55, 4.5, 12);
  table(s, [["Vendor", "Command set"], ["Rigol", ":WAV:PRE? / :WAV:DATA?"], ["Keysight/Agilent", ":WAVeform:PREamble? / DATA?"], ["Tektronix", "WFMOutpre? / CURVE?"],
    ["Siglent (X-E)", "C1:WF? DAT2 + TRDL?"], ["unknown", "Keysight-style fallback"], ["--simulate", "SimScope (no hardware)"]], 8.25, 1.3, 4.6, { colW: [1.7, 2.9], fs: 13, fill: 4.5 });
  takeaway(s, "Every repeat: acquire → save CSV with all labels → append lab_log.csv → print a live baseline check.", 6.05);
}
{
  const s = slide("Dashboard: analyze any trace live", "Sidebar chooses the source (simulate any fault, upload a scope CSV, or a saved lab trace). The cards show baseline and best ML answers against the truth; the plot marks the incident edge, the baseline, the ML estimate and the true position.");
  img(s, scr("s01_analyze_open.png"), 0.5, 1.2, 12.3, 5.6, "Dashboard analyze tab");
}
{
  const s = slide("Dashboard: the other four tabs", "Model comparison (E1–E6 tables and charts), real data (Zenodo results), calibration and lab log, and a physics tab with the Γ calculator and a bounce diagram.");
  img(s, scr("s03_model_comparison.png"), 0.5, 1.2, 6.05, 2.8, "Model comparison tab");
  img(s, scr("s04_real_data_zenodo.png"), 6.8, 1.2, 6.05, 2.8, "Real data tab");
  img(s, scr("s05_calibration_lab.png"), 0.5, 4.1, 6.05, 2.8, "Calibration tab");
  img(s, scr("s06_physics.png"), 6.8, 4.1, 6.05, 2.8, "Physics tab");
}
{
  const s = slide("Error handling, isolation and data safety", "These are the non-functional requirements made concrete. Each item is tested: the self-test F16 runs seven deliberately wrong commands.");
  card(s, 0.5, 1.3, 4.0, 5.5, "Error handling", ["CLI-wide handler: missing file, bad CSV, bad value → one-line 'error: …', exit 1.", "argparse errors → usage + exit 2.", "Dashboard: unreadable file → sidebar message, app keeps running.", "Failed preprocessing → no prediction (not a made-up one).", "TDR_DEBUG=1 shows tracebacks."], "teal", 15, 10);
  card(s, 4.67, 1.3, 4.0, 5.5, "Isolation and reproducibility", ["TDR_HOME moves data/, models/, report/.", "pytest and selftest run in temporary folders.", "Seeds fixed per dataset; config fingerprint in cache names.", "Bundle stores selected params, forest size, training-set name, sim config."], "purple", 15, 10);
  card(s, 8.84, 1.3, 4.0, 5.5, "Downloaded data safety", ["Zenodo archive treated as untrusted.", "Labels read with a whitelist unpickler (no code runs).", "Arrays memory-mapped inside the zip.", "Archive's TensorFlow model never loaded.", "Python reads it in isolated mode (-I)."], "amber", 15, 10);
}

// PART 6: LOCALIZATION
section("Part 6", "Localization with ML / NN", "How far away is the fault? Classical timing vs five learned regressors");
{
  const s = slide("What localization is and how we do it", "Localization = estimating the distance d to the fault. Both paths end in d = vp·Δt/2 with the calibrated vp. The ML models predict Δt, not d: Δt is what the trace contains, and the calibrated vp converts it.");
  img(s, dia("d06_localization_flow.png"), 0.5, 1.2, 12.3, 5.75, "Localization flow");
}
{
  const s = slide("Training data and methodology", "Training and selection never see the test sets. The same seeds reproduce every set.");
  img(s, dia("d11_datasets.png"), 0.5, 1.2, 8.3, 4.7, "Datasets");
  bullets(s, [["Train:", "20 000 simulated traces."], ["Validation:", "4 000, only for choosing hyper-parameters."], ["Test:", "6 000 mixed + E1 (7 × 1 200) + E5 (8 × 600)."],
    ["Target:", "Δt = 2d/vp (ns), traces with a fault only."], ["Excluded:", "traces with no incident edge."]], 9.0, 1.35, 3.85, 5.0, 14);
  takeaway(s, "Real-data test: 16 measured traces from Zenodo 5720438 (Part 12).", 6.1);
}
{
  const s = slide("The five model families and their architecture", "Same interface for all five; the CNN works on the raw 256-sample trace only, because convolutions need a sequence. The flatten layer keeps position information, which is exactly the target.");
  img(s, dia("d05_ml_architecture.png"), 0.5, 1.2, 12.3, 5.75, "Model architectures");
}
{
  const s = slide("Selected model configuration (validation grid search)", "Each row is what the validation set chose. Size is the compressed joblib size; the detail column gives trees and nodes, weights or stored traces.");
  const rows = [["Model", "Task", "Selected parameters", "Val. score", "Size (MB)", "Detail"]];
  (D.cfg || []).forEach((r) => rows.push([r.key, r.task === "reg" ? "distance" : "class", String(r.params).replace(/'/g, ""), r.task === "reg" ? f2(r.val_score) + " ns" : f3(r.val_score), f2(r.size_MB), r.detail || ""]));
  table(s, rows.slice(0, 19), 0.5, 1.25, 12.3, { colW: [0.9, 0.9, 4.6, 1.1, 0.9, 3.9], fs: 9.5 });
}
{
  const s = slide("Localization results on the mixed test set", "Two views. 'Fair' MAE uses only the faults the baseline located, so every method answers the same traces. 'All' MAE includes the hard traces where the baseline gave no answer but the models still had to. Coverage is the share of faulted traces that got a distance.");
  const rows = [["Method", "Coverage", "MAE fair (m)", "MAE all (m)", "Median (m)", "P95 (m)", "Max (m)", "≤ 0.25 m"]];
  METHODS.forEach((m) => { const a = L(m), f = LF(m); if (a.method) rows.push([mname(m), pc(a.coverage), f2(f.MAE_m), f2(a.MAE_m), f2(a.MedAE_m), f2(a.P95_m), f2(a.max_m), pc(a.within_0_25m)]); });
  table(s, rows, 0.5, 1.25, 7.9, { colW: [2.2, 0.85, 0.9, 0.85, 0.85, 0.75, 0.75, 0.75], fs: 11, fill: 5.0 });
  const labels = METHODS.filter((m) => L(m).method);
  s.addChart(pres.charts.BAR, [{ name: "fair MAE (m)", labels: labels, values: labels.map((m) => LF(m).MAE_m || 0) },
    { name: "all-traces MAE (m)", labels: labels, values: labels.map((m) => L(m).MAE_m || 0) }],
  { x: 8.55, y: 1.2, w: 4.35, h: 5.1, barDir: "bar", barGrouping: "clustered", chartColors: [H.accent1, H.accent2], showLegend: true, legendPos: "b", legendFontSize: 10,
    catAxisLabelFontSize: 9, valAxisLabelFontSize: 9, catAxisLabelColor: "555B66", valAxisLabelColor: "555B66", valGridLine: { color: "E4E3DF", size: 0.5 },
    catGridLine: { style: "none" }, showTitle: true, title: "MAE per method (m)", titleFontSize: 12, catAxisOrientation: "maxMin", catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", legendFontFace: "+mn-lt" });
  takeaway(s, `Best regressor (fair MAE): ${mname(best)}. The baseline is accurate when it answers but leaves ${pc(1 - (L("Baseline").coverage || 0))} of faults unlocated.`, 6.45);
}
{
  const s = slide("How the localization error is distributed", "Cumulative distribution: the curve's height at x is the share of located faults with error ≤ x. Steeper and higher is better. The legend gives each method's coverage.");
  img(s, fig("a1_error_cdf.png"), 0.5, 1.2, 7.9, 5.6, "Error CDF");
  img(s, fig("fig2_pred_vs_true.png"), 8.6, 1.2, 4.25, 5.6, "Predicted vs true");
}
{
  const s = slide("Accuracy vs noise (E1)", "MAE on the same traces for every method, by SNR. The best ML models (Extra Trees on features, 1-D CNN) stay at or below 0.35 m even at 10 dB, where the baseline rises to 0.51 m and locates only 44 % of faults. Not every model is robust: Random Forest on raw samples is worse than the baseline at 10 dB.");
  img(s, fig("fig1_error_vs_snr.png"), 0.5, 1.2, 12.3, 3.3, "Error vs SNR");
  const rows = [["SNR (dB)", "Baseline", mname(best).split(" (")[0] + " " + best.split("-")[1], "CNN-A"]];
  (D.e1_fair || []).forEach((r) => rows.push([String(r.snr_db), f2(r.Baseline), f2(r[best]), f2(r["CNN-A"])]));
  table(s, rows, 0.5, 4.65, 5.2, { colW: [1.25, 1.25, 1.5, 1.2], fs: 10.5, rowH: 0.27 });
  takeaway(s, "MAE (m) on faults the baseline located (E1, 1 200 traces per SNR). At 10 dB the baseline locates only 44 % of faults; the models answer all.", 4.65, 6.1, 6.75, 2.16);
}
{
  const s = slide("Which conditions make localization harder", "Same traces for every method (faults the baseline located; its share is under each label). Open stubs are the hardest fault for every method (CNN 0.50 m, Extra Trees 0.55 m, baseline 0.77 m), then impedance steps. The baseline locates only 58-65 % of the partial-type faults but 95 % of opens and shorts. Right: the error grows with distance because loss and dispersion slow the echo.");
  img(s, fig("a2_mae_by_fault_type.png"), 0.5, 1.2, 6.2, 5.6, "MAE by fault type");
  img(s, fig("fig3_error_vs_distance.png"), 6.85, 1.2, 6.0, 5.6, "Error vs distance");
}
{
  const s = slide("Rise time and fault strength", "Same traces for every method (faults the baseline located; its share is under each label). Weak faults with |Γ| < 0.1 are hard for every method: the baseline locates only 14 % of them, and errors rise to 0.56-0.86 m (k-NN about 2 m). Between 0.1 and 0.3 the CNN is clearly best (0.23 m vs 0.38 m baseline). Rise time between 2 and 10 ns changes the error little.");
  img(s, fig("a3_mae_vs_rise_and_gamma.png"), 0.5, 1.2, 12.3, 5.6, "MAE vs rise time and gamma");
}
{
  const s = slide("Generalisation to unseen distances (E2)", "Models were retrained without 4–6 m and without > 14 m. Interpolation inside the gap costs a little accuracy; extrapolation beyond the trained range fails for every learned model. The baseline has no training range.");
  img(s, fig("fig6_e2_heldout.png"), 0.5, 1.3, 8.0, 3.6, "Held-out distances");
  const rows = [["Band", "Baseline", best, "CNN-A"]];
  ["in-range (trained)", "gap 4-6 m (interpolation)", "beyond 14 m (extrapolation)"].forEach((b) => {
    const g = (m) => (D.e2 || []).find((r) => r.band === b && r.method === m) || {};
    rows.push([b, f2(g("Baseline").MAE_m), f2(g(best).MAE_m), f2(g("CNN-A").MAE_m)]);
  });
  table(s, rows, 8.7, 1.4, 4.15, { colW: [1.75, 0.8, 0.8, 0.8], fs: 12.5, rowH: [0.55, 0.95, 0.95, 0.95] });
  takeaway(s, "Consequence: train on the full distance range of the cables you will test (limitation L3).", 5.3);
}
{
  const s = slide(`Worst cases of the best regressor (${best})`, "The largest errors, with their conditions. In 14 of these 15 cases the baseline found no echo either: the trace carries almost no usable information (weak partial faults, stubs, low SNR), and the model falls back to a guess in the middle of the trained range (8-14 m). A confidence threshold or the hybrid rule (future work) would flag these.");
  const rows = [["True d (m)", "Predicted (m)", "Error (m)", "Fault", "Γ", "SNR (dB)", "Rise (ns)", "Baseline found?"]];
  (D.worst || []).forEach((r) => rows.push([f2(r.true_d_m), f2(r.pred_d_m), f2(r.error_m), r.fault, f2(r.gamma_true), f2(r.snr_db), f2(r.rise_ns), r.baseline_found ? "yes" : "no"]));
  table(s, rows, 0.5, 1.3, 12.3, { colW: [1.3, 1.4, 1.2, 2.6, 1.0, 1.2, 1.2, 2.4], fs: 12 });
}

// PART 7: DETECTION
section("Part 7", "Detection with ML / NN", "Is there a fault, and what kind? Rules vs learned classifiers");
{
  const s = slide("What detection is and how we do it", "Detection = deciding whether there is a fault and which class. The baseline uses rules on the echo's size and sign; the classifiers learn the decision from data and return a probability per class.");
  img(s, dia("d07_detection_flow.png"), 0.5, 1.2, 12.3, 5.75, "Detection flow");
}
{
  const s = slide("Detection results: binary and four-class", "Binary: fault present or not (matched = no fault). Four-class: open / short / matched / partial; macro-F1 averages the four classes equally.");
  const rows = [["Method", "Precision", "Recall", "F1 (binary)", "False alarms", "Misses", "Accuracy (4-class)", "Macro-F1"]];
  METHODS.forEach((m) => { const d = DET(m), c = find(D.cls, "method", m); if (d.method) rows.push([mname(m), f3(d.precision), f3(d.recall), f3(d.F1), pc(d.false_alarm_rate, 1), pc(d.miss_rate, 1), f3(c.accuracy), f3(c.F1)]); });
  table(s, rows, 0.5, 1.25, 8.2, { colW: [2.3, 0.85, 0.8, 0.85, 0.9, 0.8, 0.85, 0.85], fs: 11, fill: 5.0 });
  const labels = METHODS.filter((m) => find(D.cls, "method", m).method);
  s.addChart(pres.charts.BAR, [{ name: "macro-F1 (4 classes)", labels, values: labels.map((m) => find(D.cls, "method", m).F1 || 0) }],
    { x: 8.85, y: 1.2, w: 4.05, h: 5.1, barDir: "bar", chartColors: [H.accent3], showLegend: false, catAxisLabelFontSize: 9, valAxisLabelFontSize: 9,
      catAxisLabelColor: "555B66", valAxisLabelColor: "555B66", valGridLine: { color: "E4E3DF", size: 0.5 }, catGridLine: { style: "none" }, valAxisMinVal: 0.8, valAxisMaxVal: 1.0,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", dataLabelFontSize: 8, showTitle: true, title: "Macro-F1", titleFontSize: 12, catAxisOrientation: "maxMin",
      catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt" });
  takeaway(s, `Best classifier: ${mname(bestc)} (macro-F1 ${f3(find(D.cls, "method", bestc).F1)}) vs baseline ${f3(find(D.cls, "method", "Baseline").F1)}.`, 6.45);
}
{
  const s = slide("Confusion matrices: baseline vs best classifier", "Rows are the true class, columns the prediction; the diagonal is correct. The baseline's dominant error: 539 of 1 461 partial faults called matched (echo below its threshold); about 5 % of opens and shorts are called matched or partial. The CNN misses 82 partial faults and raises 18 false alarms.");
  img(s, fig("a5_confusion_baseline_vs_best.png"), 0.5, 1.2, 12.3, 5.65, "Confusion matrices");
}
{
  const s = slide("Misses and false alarms", "Misses dominate the baseline's errors: it misses 87 % of faults with |Γ| < 0.1 and 40 % of all faults at 10-15 dB (CNN: 34 % and 5.5 %). False alarms are rare for both; the CNN's 5.2 % at 10-15 dB (baseline 1.6 %) is the price of its higher sensitivity.");
  const rows = [["Method", "Kind", "Condition", "n", "Rate"]];
  (D.fnfp || []).forEach((r) => rows.push([r.method, r.kind.replace(" (fault called matched)", "").replace(" (matched called fault)", ""), `${r.factor} ${r.level}`, String(r.n), pc(r.rate, 1)]));
  table(s, rows.slice(0, 15), 0.5, 1.25, 6.4, { colW: [0.9, 1.4, 2.2, 0.8, 1.1], fs: 10 });
  img(s, fig("a4_detection_vs_snr.png"), 7.05, 1.25, 5.8, 5.5, "Detection vs SNR");
}
{
  const s = slide("Weak (soft) faults and the input representation", "E5: partial faults with |Γ| from 0.01 to 0.3 at 30 dB. E6: the same family with raw samples (A, dashed) or physics features (B, solid).");
  img(s, fig("fig7_e5_soft_faults.png"), 0.5, 1.2, 12.3, 2.75, "Soft faults");
  img(s, fig("fig10_e6_method_a_vs_b.png"), 0.5, 4.1, 12.3, 2.75, "Method A vs B");
}

// PART 8–9: END TO END + INTEGRATION
section("Part 8–9", "End-to-end working and hardware–software integration", "What happens, step by step, from power-on to a located fault");
{
  const s = slide("Capture session: what happens in one repeat", "The operator runs one command per configuration; the software does the rest and prints a check for every repeat, so a mislabelled set-up is caught at the bench.");
  img(s, dia("d08_sequence_capture.png"), 0.5, 1.2, 12.3, 5.75, "Capture sequence");
}
{
  const s = slide("Integration layer by layer", "Each layer has a check that proves it works. The trigger defines t = 0, and software re-aligns every trace on the incident 50 % crossing, so trigger jitter does not bias Δt.");
  img(s, dia("d12_integration.png"), 0.5, 1.2, 12.3, 5.75, "Integration layers");
}
{
  const s = slide("Real execution example (self-test, simulated scope)", "Actual console output from index.py selftest: 7 set-ups × 4 repeats captured, logged, checked live; the 5 m trace inspected; calibration solved; simulator fitted.");
  const ids = ["F02", "F03", "F04", "F05", "F06"];
  const rows = [["Feature", "Actual output"]];
  ids.forEach((i) => { const r = find(featRows, "id", i); if (r.id) rows.push([r.feature, r.actual]); });
  table(s, rows, 0.5, 1.3, 12.3, { colW: [3.3, 9.0], fs: 13.5, rowH: [0.5, 0.95, 0.95, 0.95, 0.95, 0.95] });
}
{
  const s = slide("Example: one trace through the dashboard", "A simulated 50 Ω shunt resistor at 5 m: the baseline and the ML models both find the step down, and the classifiers call it partial. The plot shows where each method puts the echo against the true position.");
  img(s, scr("s02_analyze_shunt.png"), 0.5, 1.2, 12.3, 5.6, "Dashboard shunt example");
}

// PART 10–11: FEATURES + TESTING
section("Part 10–11", "Features, testing and validation", "Every feature executed for real, with expected vs actual output");
{
  const s = slide("Testing strategy", "Four levels. The self-test is the system/integration level: it runs the actual CLI commands in a sandbox and compares results with expectations.");
  card(s, 0.5, 1.3, 3.0, 5.5, "Unit", ["62 pytest tests:", "physics levels and delays", "baseline on clean traces", "every scope CSV dialect", "every model family", "safe unpickler, zip memmap", "16 regression tests for review findings"], "teal", 15, 8);
  card(s, 3.65, 1.3, 3.0, 5.5, "Integration", ["capture → calibrate → fit → lab‑dataset", "evaluate with a lab log (E3/E4 = LAB)", "dashboard driven through all inputs"], "purple", 15, 8);
  card(s, 6.8, 1.3, 3.0, 5.5, "System / performance", ["full self-test (19 features)", "latency per model", "Zenodo pipeline on 1 M traces", "real-trace test (16)"], "copper", 15, 8);
  card(s, 9.95, 1.3, 2.9, 5.5, "Robustness / edge cases", ["7 wrong CLI calls", "low amplitude traces", "2 traces only, zero noise", "blank channel cells", "relative paths"], "amber", 15, 8);
}
const chunk = (arr, n) => Array.from({ length: Math.ceil(arr.length / n) }, (_, i) => arr.slice(i * n, i * n + n));
chunk(featRows, 7).forEach((rowsPart, k, all) => {
  const s = slide(`Feature test matrix (${k + 1}/${all.length})`, "From report/results/feature_tests.csv, written by index.py selftest. Expected is set before the run; actual is copied from the command output.");
  const rows = [["ID", "Feature", "Expected", "Actual", "Status"]];
  rowsPart.forEach((r) => rows.push([r.id, r.feature, r.expected, String(r.actual).slice(0, 230), { text: r.status, options: { bold: true, color: r.status === "Pass" ? H.accent4 : r.status === "Fail" ? "B42318" : H.accent5 } }]));
  table(s, rows, 0.5, 1.25, 12.3, { colW: [0.55, 2.4, 3.0, 5.35, 1.0], fs: 9.5 });
});
{
  const s = slide("Independent code review: findings and fixes", "A reviewer with no stake in the code read every module and reproduced each finding. Findings 1-12 are fixed (11 pinned by regression tests or re-runs; the Siglent fix needs a Siglent scope to confirm). 13 (Zenodo k-NN size) is documented; 14 (real-trace noise level) was measured and does not occur.");
  table(s, [["#", "Finding", "Effect before the fix", "Fix"],
    ["1", "one calibration V_inc normalised every lab trace", "low-amplitude traces misclassified", "V_inc per trace, calibration as reference"],
    ["2", "relative capture paths unresolvable", "lab log silently unusable", "paths relative to the log, POSIX"],
    ["3", "fixture offset t0 removed only from Δt", "~10 cm bias in model inputs", "t0 removed from both model inputs"],
    ["4", "blank channel cell → float channel", "lab files skipped", "integral floats accepted"],
    ["5", "test overwrote a real report figure", "fake calibration in dashboard", "tests run in a temp TDR_HOME"],
    ["6", "calibrate crashed on 2 traces / zero noise", "traceback", "guarded fit and SNR"],
    ["7", "failed trace encoded like a short", "confident wrong answers", "no prediction, counted as not covered"],
    ["8", "Zenodo test noise = training noise", "biased k-NN result", "noise seed per split"],
    ["9–12", "options ignored, stale caches, Siglent delay, crash paths", "inconsistent runs", "bundle settings, cache fingerprint, TRDL, handlers"]],
    0.5, 1.25, 12.3, { colW: [0.6, 4.2, 3.4, 4.1], fs: 11 });
}

// PART 12: PERFORMANCE
section("Part 12", "Performance analysis", "Speed, resources, real data and the objectives check");
{
  const s = slide("Speed: inference latency per model", "Measured on the project laptop's CPU. The front end (preprocessing, baseline and 23 features) dominates; every model answers in milliseconds, so the system is interactive.");
  img(s, fig("a6_latency.png"), 0.5, 1.2, 7.4, 5.6, "Latency");
  const lat = D.lat || [];
  const fe = lat.find((r) => r.stage !== "model") || {};
  const m = lat.filter((r) => r.stage === "model");
  const mx = m.reduce((a, r) => (r.single_ms > (a.single_ms || 0) ? r : a), {});
  stat(s, 8.2, 1.4, 4.6, `${f2(fe.single_ms)} ms`, "front end per trace (preprocess + baseline + features)", H.accent1);
  stat(s, 8.2, 3.2, 4.6, `${f2(mx.single_ms)} ms`, `slowest single-trace model call (${mx.model || "–"} ${mx.task || ""})`, H.accent2);
  bullets(s, ["Training all 18 models: 44 min wall time on 16 cores while sharing the CPU (≈ 20 min of model fitting alone; the CNN is the largest share).", "E1–E6 evaluation: 31 min."], 8.2, 5.0, 4.6, 1.5, 13);
}
{
  const s = slide("Real measured data: Zenodo 5720438", "External test on someone else's measurements. Models are trained on that dataset's simulated traces only. Z1: 20 000 held-out simulated traces; Z2: noise x1-30 (left); Z3: the 16 real measured traces (right). On real traces the CNN finds the first fault within 1.2 m on average (baseline 8.6 m) and Extra Trees on features measures the cable length within 0.6 m (baseline 13.2 m). At high noise (x10, x30) the matched filter is the most robust first-fault locator: the models were trained at noise x1 only.");
  img(s, fig("zfig2_zenodo_noise.png"), 0.5, 1.2, 6.1, 2.2, "Zenodo noise sweep");
  const z3 = fs.readdirSync(P("report", "figures")).find((n) => n.startsWith("zfig3"));
  if (z3) img(s, fig(z3), 6.75, 1.2, 6.1, 2.2, "Zenodo real traces");
  const rows = [["Model", "Z1 sim: first fault MAE (m)", "Z1 sim: length MAE (m)", "Z3 REAL: first fault MAE (m)", "Z3 REAL: length MAE (m)", "Z3 REAL: type correct"]];
  const zall = D.zall || [];
  const order = ["Baseline", "ET-B", "RF-B", "CNN-A", "ET-A", "RF-A", "MLP-A", "MLP-B", "KNN-B", "KNN-A"];
  order.forEach((m) => {
    const a = zall.find((r) => r.set === "Z1" && r.method === m), z = zall.find((r) => r.set === "Z3" && r.method === m);
    if (!a || !z) return;
    const star = String(a.source || "").startsWith("run 1") ? " *" : "";
    rows.push([(m === "Baseline" ? "Matched filter" : m) + star, f2(a.MAE_d_first_m), f2(a.MAE_length_m), f2(z.MAE_d_first_m), f2(z.MAE_length_m), `${Math.round(16 * z.acc_first_cls)}/16`]);
  });
  table(s, rows, 0.5, 3.55, 12.3, { colW: [2.0, 2.0, 2.0, 2.2, 2.1, 2.0], fs: 10, rowH: 0.26 });
  s.addText("* raw-input forests evaluated in the first run (Z1 noise shared with training; the seed check shows < 2 % effect).", { x: 0.5, y: 6.65, w: 12.3, h: 0.28, isTextBox: true, fontSize: 10, color: "6B7280", margin: 0, valign: "top" });
}
{
  const s = slide("Sim-to-lab gap (E3/E4, proxy until the lab session)", "Until our own traces exist, E3/E4 use a proxy set: simulation with lab-like artifacts (adapter reflection, ringing, 1/f noise). On the faults the baseline locates, the ML models keep a clear advantage (about 0.25-0.35 m vs 0.70 m). Fine-tuning with 149 labelled proxy traces (E4) changes the error by at most about 0.05 m, so it does not close the gap: the artifacts need either more targeted data or training with artifacts on (domain randomisation).");
  img(s, fig("fig8_e3_e4_sim_to_lab.png"), 0.5, 1.2, 8.0, 5.6, "Sim to lab");
  card(s, 8.7, 1.3, 4.15, 5.4, "Reading the proxy result", [`Data: ${D.summary.e3_e4_data || "PROXY"} (1 351 test traces).`, "E3: trained on clean simulation, tested with lab-like artifacts: every method gets worse (baseline 0.70 m).", "On the faults the baseline locates, ML stays at about 0.25-0.35 m.", "E4: +149 labelled proxy traces (×5 weight) changes MAE by ≤ 0.05 m: not enough.", "Switches to LAB automatically once ≥ 20 logged traces exist."], "amber", 14.5, 8);
}
{
  const s = slide("Objectives vs measured results", "Green = measured and met; amber = measured on simulation/proxy only, or pending lab. No untested feature is claimed as working.");
  const ok = { options: { color: H.accent4, bold: true } }, am = { options: { color: H.accent5, bold: true } };
  table(s, [["Objective", "Measured evidence", "Verdict"],
    ["Realistic labelled simulation", "levels within 0.015 of 1 + Γ; delay exact (F09)", { text: "met", ...ok }],
    ["Baseline to beat", `MAE ${f2(L("Baseline").MAE_m)} m on ${pc(L("Baseline").coverage)} coverage`, { text: "met", ...ok }],
    ["ML beats baseline", `${best}: MAE ${f2(L(best).MAE_m)} m on all faults; fair ${f2(LF(best).MAE_m)} vs ${f2(LF("Baseline").MAE_m)} m`, { text: "met (simulation)", ...am }],
    ["Fault type", `${bestc} macro-F1 ${f3(find(D.cls, "method", bestc).F1)} vs baseline ${f3(find(D.cls, "method", "Baseline").F1)}`, { text: "met (simulation)", ...am }],
    ["Real data", "16 measured Zenodo traces (Z3)", { text: "measured", ...ok }],
    ["Own lab data + calibration", "procedure and software ready; rehearsed", { text: "pending lab", ...am }],
    ["Interactive demo", "dashboard, 5 tabs, tested (F14, F15)", { text: "met", ...ok }]],
    0.5, 1.3, 12.3, { colW: [3.0, 7.0, 2.3], fs: 12.5 });
}

// PART 13: PROBLEMS
section("Part 13", "Problems, debugging and solutions", "What went wrong, why, and how we know it is fixed");
{
  const s = slide("Problems found during development", "Each row: symptom, root cause, fix, and the test that now guards it.");
  table(s, [["Problem", "Root cause", "Solution", "Verified by"],
    ["Incident tail detected as an echo", "lobe boundary inside the incident edge", "echo lobe may not start before the incident lobe ends", "baseline unit tests"],
    ["False alarms at low SNR", "noise from the pre-trigger only; fixed smoothing", "MAD noise, adaptive Gaussian, longer pre-trigger", "E1 false-alarm rates"],
    ["Γ over-compensated", "loss evaluated at the edge knee", "loss at 0.1/rise", "physics tests"],
    ["Zenodo download broke (curl 56)", "unstable connection", "resumable retries, robust range reads", "4.18 GB verified"],
    ["Pulse tail triggered events", "slow tail of the transmitted pulse", "high-pass before correlating, blanking", "Z1 baseline"],
    ["Feature windows moved with t0", "windows anchored on shifted axis", "windows anchored on the incident edge", "test_t_offset_shifts_every_time_feature"],
    ["E2 lost its training set after cache rename", "name changed, loader not", "training-set name stored in bundle", "selftest F13"]],
    0.5, 1.25, 12.3, { colW: [2.8, 3.0, 3.7, 2.8], fs: 11.5 });
}
{
  const s = slide("Before and after: amplitude-independent normalisation", "Review finding 1. The before column is the reviewer's run on the old code (5 m RG-58, calibration at 2 V EMF). The after column is the regression test test_vinc_per_trace_any_amplitude: open and short at 5 m with the step at 0.25×, 0.6×, 1× and 1.5× the calibration amplitude, all correct.");
  card(s, 0.5, 1.3, 6.0, 4.9, "Before (one stored V_inc)", ["0.5 V generator: open → 'no reflection' / matched.", "1.2 V: open and short → 'partial'.", "3.0 V: merged-edge path, d = 0.29 m.", "Calibration V_inc averaged over all open rows (low-SNR rows pulled it down)."], "copper", 18, 14);
  card(s, 6.85, 1.3, 6.0, 4.9, "After (V_inc per trace)", ["Estimated from each trace; calibration used when they agree.", "All 8 amplitude/class cases: correct class, |d − 5| < 0.3 m.", "Calibration uses only normal-amplitude rows for V_inc.", "Pinned by test_vinc_per_trace_any_amplitude (8 cases)."], "green", 18, 14);
}

// PART 14–16
section("Part 14–16", "Achievements, limitations, future and conclusion", "Separating what is done from what is pending");
{
  const s = slide("Status: completed, partial, pending, unverified", "Everything that can be done without the lab is done and measured. The lab session is the remaining critical path.");
  card(s, 0.5, 1.3, 3.0, 5.5, "Completed", ["Simulator, baseline, features", "18 models, E1–E6, analysis", "Dashboard (5 tabs)", "Capture, CSV reader, calibration, fit", "Zenodo pipeline + 16 real traces", "62 tests + 19-feature self-test", "Hardware manual + 13 circuits"], "green", 15, 8);
  card(s, 3.65, 1.3, 3.0, 5.5, "Partial", ["E3/E4 on proxy data (switches to LAB automatically)", "Report draft: lab sections empty"], "amber", 15, 8);
  card(s, 6.8, 1.3, 3.0, 5.5, "Pending (needs lab)", ["Instructor approvals (S1)", "Real calibration (S8)", "≈ 180 + fault traces (S9–S11)", "Retrain on calibration, E3/E4 LAB", "Setup photo, demo rehearsal"], "copper", 15, 8);
  card(s, 9.95, 1.3, 2.9, 5.5, "Unverified", ["Scope drivers on a real instrument (written per vendor docs)", "Fast-edge pulser (optional, not built)"], "gray", 15, 8);
}
{
  const s = slide("Key results in numbers", "All measured by the project's own scripts; simulation unless marked real.");
  stat(s, 0.5, 1.4, 4.0, `${f2(L(best).MAE_m)} m`, `${mname(best)}: mean distance error on every faulted test trace (simulation)`, H.accent1);
  stat(s, 4.6, 1.4, 4.0, `${pc(L("Baseline").coverage)}`, "share of faults the classical baseline located at all", H.accent2);
  stat(s, 8.7, 1.4, 4.1, `${f3(find(D.cls, "method", bestc).F1)}`, `${mname(bestc)}: macro-F1 over 4 classes`, H.accent3);
  stat(s, 0.5, 4.1, 4.0, `${nPass}/${featRows.length}`, "features passing the end-to-end self-test", H.accent4);
  stat(s, 4.6, 4.1, 4.0, "62", "unit and regression tests passing", H.accent4);
  stat(s, 8.7, 4.1, 4.1, "16", "real measured traces tested (Zenodo Z3)", H.accent6);
}
{
  const s = slide("Limitations", "Stated plainly so the results are read correctly.");
  table(s, [["#", "Limitation", "Consequence / mitigation"],
    ["L1", "no own lab data yet", "E3/E4 are proxy; switch to LAB after the session"],
    ["L2", "resolution ≈ vp·t_r/2", "faults < 0.4–1.5 m from the tee merge; pulser helps"],
    ["L3", "learned models do not extrapolate (E2)", "train on the full distance range used"],
    ["L4", "very weak faults (|Γ| < 0.05)", "inconsistent detection by every method (E5)"],
    ["L5", "simulation fidelity (connectors, scope front end)", "fit_sim and calibration narrow the gap; Zenodo shows a real gap"],
    ["L6", "single fault per trace in our own data", "multi-fault only in Zenodo labels"],
    ["L7", "Zenodo k-NN stores 100 k raw traces per target", "fine for evaluation, too large to deploy"]],
    0.5, 1.3, 12.3, { colW: [0.6, 5.0, 6.7], fs: 13 });
}
{
  const s = slide("Future scope", "Ordered by expected benefit for the effort.");
  card(s, 0.5, 1.3, 4.0, 5.5, "Better models", ["Domain randomisation: train with lab artifacts on.", "Hybrid: ML inside its range, baseline outside.", "Fine-tune on our lab traces (E4).", "Multi-fault outputs (Zenodo labels).", "Time-frequency CNN (Chang & Park)."], "purple", 16, 12);
  card(s, 4.67, 1.3, 4.0, 5.5, "Better signals", ["Matched-load reference subtraction (cancels generator ringing).", "74AC14 fast-edge pulser: ≈ 2× resolution.", "Averaging + narrow pulses for long cables."], "teal", 16, 12);
  card(s, 8.84, 1.3, 4.0, 5.5, "Better system", ["Second cable type (RG-174 / RG-59).", "Compact k-NN (shared neighbours) or distillation.", "Live capture inside the dashboard.", "Confidence-based abstention."], "copper", 16, 12);
}
{
  const s = slide("Conclusion", "Close with the problem, the solution, the evidence and what remains.");
  bullets(s, [["Problem:", "locate and classify cable faults from one TDR trace, robustly in noise and with real instruments."],
    ["Solution:", "physics simulator → one processing chain → classical baseline vs five ML families on two inputs, calibrated to the setup."],
    ["Built with:", "Python, NumPy/SciPy, scikit-learn, PyTorch, PyVISA, Streamlit/Plotly; tested with 62 unit tests and a 19-feature self-test."],
    ["Achieved:", `${mname(best)} locates every fault with MAE ${f2(L(best).MAE_m)} m (simulation); ${mname(bestc)} classifies with macro-F1 ${f3(find(D.cls, "method", bestc).F1)}; tested on 16 real traces.`],
    ["Remaining:", "our own lab session: calibration, labelled traces, E3/E4 on real data, final report sections."],
    ["Potential:", "a low-cost, explainable cable diagnostic for student labs and field maintenance."]], 0.5, 1.4, 12.3, 5.35, 20, { space: 18 });
}
{
  const s = pres.addSlide({ masterName: "TITLE", sectionTitle: SECTION });
  s.addText("Thank you: questions?", { placeholder: "title" });
  s.addText([{ text: "Demo: python index.py dashboard  ·  Evidence: report/results/", options: { breakLine: true } }, { text: "Docs: docs/PROJECT_DOCUMENTATION.md" }], { placeholder: "body" });
  s.addText("Technical appendix and source references follow.", { placeholder: "meta" });
}

// APPENDIX
section("Appendix", "Technical appendix", "Formulas, configuration, file formats and source references (docs/TECHNICAL_APPENDIX.md)");
{
  const s = slide("Formulas", "All formulas used in the project, with the symbols defined on the key-terms slide.");
  table(s, [["Quantity", "Formula"], ["Wave speed", "vp = c/√εr = VF·c"], ["Incident step", "V_inc = Vs·Z0/(Rs + Z0)"], ["Reflection coefficient", "Γ = (ZL − Z0)/(ZL + Z0)"],
    ["Series / shunt R", "Γ = R/(R + 2Z0)  /  Γ = −Z0/(Z0 + 2R)"], ["Distance", "d = vp·Δt/2"], ["Calibration", "Δt = (2/vp)·L + t0"], ["Resolution", "Δd_min ≈ vp·t_r/2"],
    ["Loss", "α(f) = α_dc + k_s√f + k_d·f;  Γ ≈ amp·e^(2αd)"], ["Robust noise", "σ = 1.4826·median|x − median(x)|"], ["MAE / RMSE", "mean|d̂ − d|  /  √mean(d̂ − d)²"],
    ["Precision / recall / F1", "TP/(TP+FP) · TP/(TP+FN) · 2PR/(P+R)"]], 0.5, 1.3, 12.3, { colW: [3.5, 8.8], fs: 13 });
}
{
  const s = slide("Configuration values", "From src/config.py and src/train.py; the full list is in the technical appendix.");
  table(s, [["Setting", "Value", "Setting", "Value"], ["distance", "0.5–20 m", "rise time", "2–10 ns"], ["SNR", "10–40 dB", "generator Rs", "0.92–1.08 × Z0"],
    ["scope input", "1 MΩ ∥ 8–20 pF", "sampling", "0.5, 1, 2 ns"], ["partial |Γ|", "0.05–0.70", "ADC", "8 bit"], ["Method A grid", "256 × 1 ns, −16…239 ns", "Method B", "23 features"],
    ["forest", "100 trees", "k-NN", "k ∈ {5, 15}, distance"], ["MLP", "(128,64)/(256,128), α 1e-4", "CNN", "16/32/64/64 ch, k7, ≤ 40 epochs"],
    ["train / val / test", "20 000 / 4 000 / 6 000", "seeds", "1 / 2 / 3"]], 0.5, 1.3, 12.3, { colW: [2.4, 3.75, 2.4, 3.75], fs: 13 });
}
{
  const s = slide("Source references: where every claim comes from", "Use this slide to find the evidence behind any number in the deck.");
  table(s, [["Topic", "Source file(s)"], ["Physics, simulator", "src/sim_tdr.py, docs/theory_sheet.md, tests/test_physics_baseline.py"], ["Baseline, features", "src/baseline.py, src/features.py, docs/data_dictionary.md"],
    ["Models, grids, selection", "src/models.py, src/train.py, report/results/validation_grid.csv, analysis_model_config.csv"],
    ["Simulation results E1–E6", "report/results/summary.md, e*_*.csv, report/figures/fig1–fig10"], ["Localization / detection analysis", "report/results/ml_analysis_summary.md, analysis_*.csv, figures a1–a6"],
    ["Real data", "report/results/zenodo_summary.md, zenodo_z*.csv, figures zfig1–3"], ["Testing", "report/results/feature_tests.md, tests/, docs/TESTING_REPORT.md"],
    ["Hardware", "hardware/README.md, HARDWARE_GUIDE.md, LAB_PROCEDURE.md, circuits/"], ["Literature", "docs/literature.md, docs/model_selection.md"]],
    0.5, 1.3, 12.3, { colW: [3.4, 8.9], fs: 12.5 });
}

// ------------------------------------------------------------------ write
(async () => {
  await pres.writeFile({ fileName: OUTFILE });
  if (SKILL) {
    const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));
    await applyTheme(OUTFILE, THEME);
  }
  console.log("wrote", OUTFILE);
})();
