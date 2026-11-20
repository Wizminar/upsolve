// Main Upsolve presentation: a quick tour of what it does, then the ETL, AI/ML and VIZ components
// in depth, then app, plugins and testing. Transitions and entrance animations are added by
// postprocess.py. Run: NODE_PATH=docs/deck/node_modules APPLY_THEME=<skill>/scripts/apply_theme.js node docs/deck/build.js
const path = require("path");
const { applyTheme } = require(process.env.APPLY_THEME);
const { SYNDICATE, makeDeck, A, data, HEX, THEME, MED, MONO, X0, RIGHT } = require("./lib");

const { pres, COL, anim, text, row, shot, section, S, divider, codeBlock, team } = makeDeck("Upsolve");

// ------------------------------------------------------------------ 1. Title
section("Introduction");
{
  const s = S("Blank", "Upsolve is a Codeforces practice coach. Enter a handle and it picks problems you have about a 60% chance of solving, explains why, and tracks you topic by topic. First a one-minute tour, then the three components in depth: data engineering, the machine learning, and the visualisations.");
  s.addImage({ path: A("chevron.png"), x: X0, y: 0.9, w: 0.55, h: 0.55, objectName: "logo" });
  text(s, "Upsolve", { x: X0, y: 1.6, w: 6, h: 1.2, fontFace: MED, fontSize: 66 });
  text(s, "Practice problems that fit you.", { x: X0, y: 2.85, w: 5.6, h: 0.5, fontSize: 24, color: COL.muted });
  text(s, "A Codeforces practice coach. CS698B course project.", { x: X0, y: 3.5, w: 5.6, h: 0.4, fontSize: 15, color: COL.faint });
  team(s, { x: X0, y: 4.55, w: 6.7, name: "The Syndicate", members: SYNDICATE });
  shot(s, "hero.png", { x: 6.9, y: 0.85, w: 5.73, h: 5.8, align: "right" });
}

// ------------------------------------------------------------------ 2. What it does
{
  const s = S("Content", "What a user sees. Type any Codeforces handle. Upsolve imports their history, then shows five unsolved problems with a chance of solving each, a rating for every topic, and a weekly plan. No account needed.");
  s.addText("What Upsolve does", { placeholder: "title" });
  shot(s, "hero.png", { x: X0, y: 1.55, w: 6.2, h: 5.1 });
  const x = 7.65, w = 4.98;
  row(s, { x, y: 1.75, w, label: "Type any Codeforces handle", desc: "Upsolve imports the full history in the background. No sign-up." });
  row(s, { x, y: 3.05, w, label: "Get five problems near 60%", desc: "Each with a predicted chance and reasons you can read." });
  row(s, { x, y: 4.35, w, label: "See every topic's rating", desc: "Charts of strengths, history, activity and a weekly plan." });
}

// ------------------------------------------------------------------ 3. End to end
{
  const s = S("Content", "End to end, in four steps, and which course component each belongs to. Import and clean is ETL. Rating every topic and predicting the chance is the AI/ML part. Recommending and showing it is the app and the visualisations. All of it runs live, in one Python server, for whichever handle you type.");
  s.addText("How it works, end to end", { placeholder: "title" });
  const steps = [
    ["ETL", "Import and clean", "Codeforces API to a clean table of attempts in SQLite."],
    ["AI/ML", "Rate every topic", "An adaptive Elo rating per topic, updated attempt by attempt."],
    ["AI/ML", "Predict the chance", "Logistic regression gives P(solve) for every unsolved problem."],
    ["APP + VIZ", "Recommend and show", "Five problems near 60%, with charts of how you are doing."],
  ];
  const colW = 2.75, gap = 0.3, top = 2.2;
  s.addShape(pres.shapes.LINE, { x: X0, y: top, w: RIGHT - X0, h: 0, line: { color: HEX.line, width: 1.5 }, objectName: "timeline" });
  steps.forEach(([comp, name, desc], i) => {
    const x = X0 + i * (colW + gap), n = anim();
    s.addShape(pres.shapes.OVAL, { x, y: top - 0.09, w: 0.18, h: 0.18, fill: { color: HEX.blue }, line: { type: "none" }, objectName: `${n}_dot` });
    text(s, [
      { text: comp, options: { fontSize: 14, color: COL.blue, breakLine: true } },
      { text: name, options: { fontFace: MED, fontSize: 22, breakLine: true } },
      { text: desc, options: { fontSize: 14, color: COL.muted } },
    ], { x, y: top + 0.35, w: colW, h: 2.2, paraSpaceAfter: 6, objectName: `${n}_text` });
  });
  const stack = [["FastAPI + Uvicorn", "Web server and REST API"], ["SQLite", "One file, no database server"], ["NumPy + scikit-learn", "Training and predictions"], ["HTML, CSS, JS", "Hand-drawn SVG charts"]];
  stack.forEach(([t, d], i) => row(s, { x: X0 + i * (colW + gap), y: 5.25, w: colW, label: t, desc: d, labelSize: 15, descH: 0.4 }));
}

// ================================================================== ETL
section("ETL");
divider("Component 1: ETL", "Data engineering", "From the public Codeforces API to clean, de-duplicated attempts, refreshed incrementally.",
  "First component, ETL. Extract from the Codeforces API, transform raw submissions into attempts, load into SQLite.");

// ------------------------------------------------------------------ Extract
{
  const s = S("Content", "Extract. Six methods of the free public Codeforces API. Requests are paced 2.1 seconds apart to respect their rate limit, retried on failure, and run as a background job so the page never blocks. Later syncs fetch only submissions newer than the last one we stored.");
  s.addText("Extract: six Codeforces API calls", { placeholder: "title" });
  const calls = [
    ["user.info", "Profile, rank and contest rating"],
    ["user.status", "Every submission with verdict and time"],
    ["user.rating", "Contest rating history"],
    ["problemset.problems", "11,526 problems with difficulty and tags"],
    ["contest.ratingChanges", "Which contests were rated for the user"],
    ["contest.list", "Contest dates, to place problems in time"],
  ];
  calls.forEach(([m, d], i) => row(s, { x: X0, y: 1.6 + i * 0.86, w: 6.2, label: m, desc: d, labelFont: MONO, labelSize: 15, descH: 0.3, name: `static_c${i}` }));
  const x = 7.65, w = 4.98;
  row(s, { x, y: 1.6, w, label: "Paced", value: "2.1 s", desc: "Between requests, inside the API's limit." });
  row(s, { x, y: 2.9, w, label: "Incremental", desc: "Later syncs fetch only new submissions." });
  row(s, { x, y: 4.0, w, label: "Background jobs", desc: "Sync runs in a worker thread; the page shows progress." });
  row(s, { x, y: 5.1, w, label: "Cached", desc: "The problem catalogue refreshes once a day." });
}

// ------------------------------------------------------------------ Transform
{
  const s = S("Content", "Transform. Raw submissions are noisy: many tries on the same problem, compilation errors, duplicates between Div 1 and Div 2. We group them into one attempt per problem, and call it solved only if accepted within 24 hours of the first try. Gym problems and special tags are dropped.");
  s.addText("Transform: submissions become attempts", { placeholder: "title" });
  const rules = [
    ["One attempt per problem", "Repeated submissions grouped together."],
    ["Solved = accepted within 24 hours", "Upsolving the same day still counts."],
    ["Compilation errors don't count", "Neither do pending verdicts."],
    ["Duplicates removed", "The same Div. 1 and Div. 2 problem counted once."],
    ["Noise dropped", "Gym problems and the *special tag are ignored."],
  ];
  rules.forEach(([l, d], i) => row(s, { x: X0, y: 1.6 + i * 1.02, w: 6.2, label: l, desc: d, name: `static_${i}`, labelSize: 17, descH: 0.35 }));
  const x = 7.65, w = 4.98;
  row(s, { x, y: 1.6, w, label: "Problems", value: "11,526", desc: "Full catalogue with difficulty and tags." });
  row(s, { x, y: 2.9, w, label: "Training users", value: "200", desc: "20 per 200-point rating band, 800 to 2800." });
  row(s, { x, y: 4.2, w, label: "Training examples", value: "182,242", valueColor: COL.blue, desc: "Attempts plus contest problems seen but not solved." });
}

// ------------------------------------------------------------------ Load
{
  const s = S("Content", "Load. Everything lands in one SQLite file in WAL mode, so the web server can read while a sync writes. Thirteen tables in three groups: raw Codeforces data, what we derive from it, and what the app itself needs. The training set is a table too, so the model can be retrained at any time.");
  s.addText("Load: one SQLite database", { placeholder: "title" });
  const groups = [
    ["Raw Codeforces data", "problems, problem_tags, users, submissions, rating_changes"],
    ["Derived", "attempts, topic_ratings, topic_rating_history, training"],
    ["App state", "recommendation_log, sync_jobs, plugin_store, meta"],
  ];
  groups.forEach(([l, d], i) => {
    const n = anim(), y = 1.6 + i * 1.5;
    s.addShape(pres.shapes.LINE, { x: X0, y, w: 6.2, h: 0, line: { color: HEX.line, width: 1 }, objectName: `${n}_rule` });
    text(s, [
      { text: l, options: { fontFace: MED, fontSize: 18, breakLine: true } },
      { text: d, options: { fontFace: MONO, fontSize: 13, color: COL.muted } },
    ], { x: X0, y: y + 0.18, w: 6.2, h: 1.1, paraSpaceAfter: 6, objectName: `${n}_text` });
  });
  const x = 7.65, w = 4.98;
  row(s, { x, y: 1.6, w, label: "Tables", value: "13", desc: "Raw, derived and app state kept apart." });
  row(s, { x, y: 2.9, w, label: "WAL mode", desc: "Reads keep working while a sync writes." });
  row(s, { x, y: 4.0, w, label: "Training set as a table", desc: "Rebuilt by scripts/build_dataset.py; model retrains from it." });
}

// ================================================================== AI/ML
section("AI/ML");
divider("Component 2: AI/ML", "Predicting your chance", "Two models working together: an adaptive rating for every topic, and a classifier that turns it into P(solve).",
  "Second component, the machine learning. It answers one question for every user and problem: what is the chance this person solves this problem? It runs live for any handle.");

// ------------------------------------------------------------------ Target curve
{
  const s = S("Content", "Why predict a chance at all. For a real user rated 1487, our model's chance of solving falls as problems get harder. Too easy teaches nothing, too hard gets abandoned. Upsolve aims for the 50 to 70 percent band: hard enough to learn, close enough to finish.");
  s.addText("The target: problems you solve about 60% of the time", { placeholder: "title" });
  const xs = data.curve.ratings;
  s.addChart(pres.charts.SCATTER, [
    { name: "Rating", values: xs },
    { name: "Chance of solving", values: data.curve.chance },
    { name: "70%", values: xs.map(() => 70) },
    { name: "50%", values: xs.map(() => 50) },
  ], {
    x: X0, y: 1.55, w: 7.5, h: 4.95, objectName: "chart_curve",
    valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 25, catAxisMinVal: 1000, catAxisMaxVal: 2800, catAxisMajorUnit: 300,
    catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
    valGridLine: { color: HEX.line, size: 1 }, catGridLine: { style: "none" }, catAxisLineShow: false, valAxisLineShow: false,
    showCatAxisTitle: true, catAxisTitle: "Problem rating", catAxisTitleColor: HEX.faint, catAxisTitleFontSize: 11,
    showValAxisTitle: true, valAxisTitle: "Chance of solving (%)", valAxisTitleColor: HEX.faint, valAxisTitleFontSize: 11,
    showLegend: false, chartColors: [HEX.ink, HEX.blue, HEX.blue], lineSize: 3, lineDataSymbol: "circle", lineDataSymbolSize: 3,
  });
  text(s, "Predicted chance for a real user (contest rating 1487). Blue lines mark 50% and 70%.", { x: X0, y: 6.6, w: 7.5, h: 0.4, fontSize: 11, color: COL.faint });
  const x = 8.75, w = 3.88;
  row(s, { x, y: 1.75, w, label: "Too easy", value: "85%+", desc: "Up to about 1500 for this user. Little to learn." });
  row(s, { x, y: 3.25, w, label: "Stretch zone", value: "50–70%", valueColor: COL.blue, desc: "About 1800–2000. Hard enough to learn, close enough to finish." });
  row(s, { x, y: 4.75, w, label: "Too hard", value: "<25%", desc: "2400 and up. Usually abandoned." });
}

// ------------------------------------------------------------------ Model 1: Elo
{
  const s = S("Content", "Model one, an adaptive Elo rating. Every attempt is a game between the user and the problem; the rating moves by how surprising the result was. Plain Elo is fooled by selection: people mostly submit problems they expect to solve, so this user came out at 2238 against a contest rating of 1487. We anchor to the contest rating with a fading form offset, keep a separate offset per topic, and count unattempted problems in rated rounds as misses. Result: 1637.");
  s.addText("Model 1: an adaptive rating for every topic", { placeholder: "title" });
  const bars = [["Contest rating", 1487, HEX.muted, COL.ink], ["Plain Elo", 2238, HEX.red, COL.ink], ["Upsolve rating", 1637, HEX.blue, COL.blue]];
  const bx = X0 + 2.15, bw = 3.6, scale = (v) => ((v - 1000) / 1400) * bw;
  bars.forEach(([label, v, fill, vcol], i) => {
    const n = anim(), y = 1.85 + i * 1.05;
    text(s, label, { x: X0, y: y + 0.05, w: 2.0, h: 0.45, fontSize: 16, color: COL.ink, objectName: `${n}_label` });
    s.addShape(pres.shapes.RECTANGLE, { x: bx, y, w: scale(v), h: 0.55, fill: { color: fill }, line: { type: "none" }, objectName: `${n}_bar` });
    text(s, String(v), { x: bx + scale(v) + 0.15, y: y + 0.02, w: 1.0, h: 0.5, fontFace: MED, fontSize: 20, color: vcol, objectName: `${n}_value` });
  });
  text(s, "One real user (Mann_Chauhan). Bars start at 1000. Plain Elo overshoots by 750 points.", { x: X0, y: 5.05, w: 6.4, h: 0.4, fontSize: 11, color: COL.faint });
  codeBlock(s, "K = max(16, 80 / sqrt(1 + n))\nr += K * (solved − expected(r, difficulty))", { x: X0, y: 5.6, w: 6.2, h: 1.05, size: 13, name: "static_code" });
  const x = 7.65, w = 4.98;
  row(s, { x, y: 1.75, w, label: "Anchored to contest rating", desc: "A fading practice-form offset on top, so selection bias can't inflate it.", descH: 0.75 });
  row(s, { x, y: 3.15, w, label: "A rating per topic", desc: "Topic offsets re-centred to mean zero: they measure relative strength.", descH: 0.75 });
  row(s, { x, y: 4.55, w, label: "Misses count too", desc: "Unattempted problems in rated contests are real failures.", descH: 0.75 });
}

// ------------------------------------------------------------------ Model 2: logistic regression
{
  const s = S("Content", "Model two, logistic regression. Eleven features, all measured before each attempt so nothing leaks from the future. The Elo estimate is one feature; the others capture what Elo misses, like how much evidence there is for each topic, recent form and time away. Trained with scikit-learn on the oldest 80 percent of attempts, tested on the newest 20 percent.");
  s.addText("Model 2: logistic regression on 11 features", { placeholder: "title" });
  const feats = [
    "Elo estimate (log-odds)", "Gap to overall rating", "Gap to weakest topic", "Evidence in the topics",
    "Past solve rate in the topics", "Recent form", "Total attempts so far", "Days since last attempt",
    "Number of tags", "Problem difficulty", "Seen in a contest",
  ];
  feats.forEach((f, i) => {
    const col = i < 6 ? 0 : 1, r = i < 6 ? i : i - 6;
    row(s, { x: X0 + col * 3.3, y: 1.6 + r * 0.82, w: 3.0, label: f, labelSize: 14.5, descH: 0, name: `static_f${i}`, labelFont: "Helvetica Neue" });
  });
  const x = 7.65, w = 4.98;
  row(s, { x, y: 1.6, w, label: "Training examples", value: "145,793", desc: "Oldest 80% of attempts, 200 users." });
  row(s, { x, y: 2.9, w, label: "Test examples", value: "36,449", valueColor: COL.blue, desc: "Newest 20%, never seen in training." });
  row(s, { x, y: 4.2, w, label: "Stored as model.json", desc: "Weights and scaling; the server reloads it when retrained." });
  row(s, { x, y: 5.3, w, label: "Explainable", desc: "Each feature's contribution becomes a written reason." });
}

// ------------------------------------------------------------------ Evaluation
{
  const s = S("Content", "Evaluation on the held-out newest 20 percent. AUC 0.947 versus 0.907 for Elo alone, Brier score 0.059 versus 0.147. And it's calibrated: of the problems it placed in the 50 to 70 percent zone, 68 percent were actually solved. When it says 60 percent, about 60 percent get solved.");
  s.addText("Evaluation: better than Elo, and calibrated", { placeholder: "title" });
  const m = data.metrics.model, e = data.metrics.elo_baseline;
  const kpis = [
    [m.auc.toFixed(3), "AUC", `Elo alone: ${e.auc.toFixed(3)}`],
    [m.brier.toFixed(3), "Brier score", `Elo alone: ${e.brier.toFixed(3)}`],
    [`${Math.round(data.band.observed_rate * 100)}%`, "solved in the 50–70% zone", `${data.band.n.toLocaleString("en-US")} test problems`],
    [m.log_loss.toFixed(3), "Log loss", `Elo alone: ${e.log_loss.toFixed(3)}`],
  ];
  kpis.forEach(([v, l, d], i) => {
    const n = anim(), x = X0 + i * 3.05;
    s.addShape(pres.shapes.LINE, { x, y: 1.55, w: 2.75, h: 0, line: { color: HEX.line, width: 1 }, objectName: `${n}_rule` });
    text(s, [
      { text: v, options: { fontFace: MED, fontSize: 34, color: i === 2 ? COL.blue : COL.ink, breakLine: true } },
      { text: l, options: { fontSize: 14, color: COL.ink, breakLine: true } },
      { text: d, options: { fontSize: 12, color: COL.faint } },
    ], { x, y: 1.7, w: 2.75, h: 1.5, paraSpaceAfter: 2, objectName: `${n}_text` });
  });
  const cal = data.calibration;
  s.addChart(pres.charts.SCATTER, [
    { name: "Predicted", values: cal.map((b) => +(b.mean_predicted * 100).toFixed(1)) },
    { name: "Actually solved", values: cal.map((b) => +(b.observed_rate * 100).toFixed(1)) },
    { name: "Perfect", values: cal.map((b) => +(b.mean_predicted * 100).toFixed(1)) },
  ], {
    x: X0, y: 3.45, w: 5.6, h: 3.5, objectName: "chart_cal",
    chartColors: [HEX.ink, HEX.faint], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 8, lineDash: "solid",
    valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 25, catAxisMinVal: 0, catAxisMaxVal: 100, catAxisMajorUnit: 25,
    catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
    valGridLine: { color: HEX.line, size: 1 }, catGridLine: { style: "none" }, catAxisLineShow: false, valAxisLineShow: false,
    showValAxisTitle: true, valAxisTitle: "Actually solved (%)", valAxisTitleColor: HEX.faint, valAxisTitleFontSize: 11,
    showCatAxisTitle: true, catAxisTitle: "Predicted chance (%)", catAxisTitleColor: HEX.faint, catAxisTitleFontSize: 11,
    showLegend: false,
  });
  const x = 7.0, w = 5.63;
  row(s, { x, y: 3.6, w, label: "Calibrated", desc: "Points sit near the grey diagonal: when Upsolve says 60%, about 60% get solved.", descH: 0.75 });
  row(s, { x, y: 4.85, w, label: "No peeking at the future", desc: "Chronological split; features use only what was known before each attempt.", descH: 0.75 });
  row(s, { x, y: 6.1, w, label: "Always works", desc: "Falls back to Elo estimates if the model file is missing.", descH: 0.4 });
}

// ------------------------------------------------------------------ Live: recommender (+ Morph zoom)
{
  const s = S("Content", "This is where the ML runs live. When you open a handle, the server rates every topic, predicts a chance for every unsolved problem, and scores them: a bonus inside the 50 to 70 percent zone, a penalty for distance from 60 percent, extra weight for focus and weak topics and for problems you tried before. Then it picks five with varied topics, easiest first.");
  s.addText("Live in the app: five picks, scored", { placeholder: "title" });
  shot(s, "today_why.png", { x: X0, y: 1.55, w: 6.25, h: 5.2, name: "!!today" });
  const x = 7.65, w = 4.98;
  const terms = [
    ["Inside the 50–70% zone", "+1.5"], ["Distance from 60%", "−4 × |p − 0.6|"], ["Focus topic", "+1.2"],
    ["Weak topic", "+0.8 × weakness"], ["Tried before (upsolve)", "+0.5"],
  ];
  terms.forEach(([l, v], i) => {
    const n = anim(), y = 1.6 + i * 0.78;
    s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: HEX.line, width: 1 }, objectName: `${n}_rule` });
    text(s, l, { x, y: y + 0.2, w: 2.6, h: 0.4, fontSize: 15, objectName: `${n}_l` });
    text(s, v, { x: x + 2.6, y: y + 0.2, w: w - 2.6, h: 0.4, fontFace: MONO, fontSize: 14, color: COL.blue, align: "right", objectName: `${n}_v` });
  });
  text(s, "Then five with varied topics, easiest first. Every pick is logged with its prediction so we can check it later.", { x, y: 5.6, w, h: 0.8, fontSize: 13, color: COL.muted });
}
{
  const s = S("Blank", "Zooming in: the reasons for one problem. They come straight from the model's features: the chance is in the stretch zone, it's 363 above this user's practice rating, it matches their focus topic graphs, and it builds a weaker topic, combinatorics.");
  const px = 1800, py = 1520;
  const reg = { x: 216, y: 940, w: 1440, h: 310 };
  const sc = 11.3 / reg.w;
  s.addImage({ path: A("today_why.png"), x: 1.0 - reg.x * sc, y: 1.35 - reg.y * sc, w: px * sc, h: py * sc, objectName: "!!today" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.25, w: 13.333, h: 3.25, fill: { color: HEX.bg }, line: { type: "none" }, objectName: "mask" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.333, h: 0.9, fill: { color: HEX.bg }, line: { type: "none" }, objectName: "mask_top" });
  text(s, "Every pick explains itself", { x: 1.0, y: 4.7, w: 11.3, h: 0.7, fontFace: MED, fontSize: 32, objectName: anim() });
  text(s, "No black box: the features the model uses are turned into plain sentences.", { x: 1.0, y: 5.45, w: 11.3, h: 0.5, fontSize: 18, color: COL.muted, objectName: anim() });
}

// ================================================================== VIZ
section("VIZ");
divider("Component 3: VIZ", "Seeing your progress", "Every chart drawn by our own code in SVG, with no chart library, and a data table behind each one.",
  "Third component, the visualisations. Every chart is drawn by our own code as SVG, works in dark and light mode, and has a table view for screen readers.");

// ------------------------------------------------------------------ Topic ratings
{
  const s = S("Content", "Insights, part one. A bar for every topic's rating, focus topics in blue, thin evidence in grey. Click a topic to see its rating history against the overall rating, with the hardest problem solved and recent attempts.");
  s.addText("A rating for every topic, with its history", { placeholder: "title" });
  shot(s, "insights.png", { x: X0, y: 1.55, w: 7.6, h: 4.6 });
  const x = 8.75, w = 3.88;
  row(s, { x, y: 1.75, w, label: "Topic bars", desc: "Focus topics in blue, thin evidence in grey." });
  row(s, { x, y: 3.05, w, label: "History line", desc: "One topic against your overall rating, day by day." });
  row(s, { x, y: 4.35, w, label: "Facts at a glance", desc: "Attempts, solve rate, hardest solved, recent problems." });
}

// ------------------------------------------------------------------ Contest + activity
{
  const s = S("Content", "Insights, part two. The contest rating graph sits on the official Codeforces rank colours. The activity heatmap shows a year of practice, one square per day, shaded by submissions.");
  s.addText("Contest rating and a year of activity", { placeholder: "title" });
  const b = shot(s, "charts.png", { x: X0, y: 1.6, w: RIGHT - X0, h: 3.9 });
  const y = b.y + b.h + 0.4, cw = 3.75, gap = 0.33;
  row(s, { x: X0, y, w: cw, label: "Rating graph", desc: "Every rated contest, on Codeforces rank bands.", descH: 0.5 });
  row(s, { x: X0 + cw + gap, y, w: cw, label: "Activity heatmap", desc: "A year of practice, one square per day.", descH: 0.5 });
  row(s, { x: X0 + 2 * (cw + gap), y, w: cw, label: "Hover for values", desc: "Every point and square shows its exact number.", descH: 0.5 });
}

// ------------------------------------------------------------------ Model chart in the app
{
  const s = S("Content", "The model reports on itself, inside the app. The calibration chart and the test scores are visible to every user, so they can judge how much to trust the percentages.");
  s.addText("The model's accuracy, shown to every user", { placeholder: "title" });
  shot(s, "model.png", { x: X0, y: 1.55, w: 7.3, h: 5.15 });
  const x = 8.5, w = 4.13;
  row(s, { x, y: 1.75, w, label: "Calibration chart", desc: "Predicted against actual, with the target zone shaded." });
  row(s, { x, y: 3.05, w, label: "Test scores", desc: "AUC, Brier and log loss against the Elo baseline." });
  row(s, { x, y: 4.35, w, label: "Your own record", desc: "How many problems Upsolve has shown you so far." });
}

// ------------------------------------------------------------------ Week
{
  const s = S("Content", "The weekly plan. Users pick up to two focus topics and a weekly target. Early in the week problems sit near 70 percent and stretch towards 50 percent by Sunday. Progress updates from real accepted submissions after each sync.");
  s.addText("A plan for the week", { placeholder: "title" });
  const x = X0, w = 5.2;
  row(s, { x, y: 1.75, w, label: "Up to two focus topics", desc: "The week leans towards what you want to train." });
  row(s, { x, y: 3.0, w, label: "Easier early, harder later", desc: "Monday near 70%, Sunday near 50%." });
  row(s, { x, y: 4.25, w, label: "Progress from real solves", desc: "Updates from accepted submissions after each sync." });
  shot(s, "week.png", { x: 6.4, y: 1.55, w: 6.23, h: 5.15, align: "right" });
}

// ------------------------------------------------------------------ Accessible charts
{
  const s = S("Content", "Accessible visualisation. Every chart has a table view and a written label for screen readers, colour is never the only signal, everything works by keyboard, and there is a light theme and a text-only page.");
  s.addText("Charts everyone can read", { placeholder: "title" });
  const acc = [
    ["Data table behind every chart", "One click shows the numbers."],
    ["Colour never the only signal", "Ranks also carry their name and number."],
    ["Labels for screen readers", "Each chart describes itself."],
    ["Full keyboard support", "Every control reachable without a mouse."],
    ["Dark and light themes", "Plus a text-only page for text browsers."],
  ];
  acc.forEach(([l, d], i) => row(s, { x: X0, y: 1.6 + i * 1.0, w: 5.6, label: l, desc: d, labelSize: 17, descH: 0.35, name: `static_a${i}` }));
  shot(s, "light.png", { x: 6.9, y: 1.6, w: 5.73, h: 4.6, align: "right" });
  text(s, "The same Today view in the light theme.", { x: 6.9, y: 6.3, w: 5.73, h: 0.3, fontSize: 11, color: COL.faint, align: "right" });
}

// ================================================================== APP + DEV
section("App and plugins");
{
  const s = S("Content", "The app and the developer side. Everything the app does is available through a versioned REST API with 21 endpoints, documented in OpenAPI. Other teams extend Upsolve with plugins that run inside it; our cross-dev deck covers that in detail with the Rival plugin.");
  s.addText("An open API, and plugins inside the app", { placeholder: "title" });
  const apis = [
    ["POST /users/{handle}/sync", "Import a handle"],
    ["GET /users/{handle}/topics", "Topic ratings"],
    ["GET /users/{handle}/recommendations", "Daily problems with reasons"],
    ["GET /users/{handle}/predict/{id}", "The model's chance for one problem"],
    ["PUT /plugins/{id}/store/{scope}/{key}", "Plugin storage"],
  ];
  apis.forEach(([p, d], i) => row(s, { x: X0, y: 1.6 + i * 0.92, w: 5.9, label: p, desc: d, labelFont: MONO, labelSize: 13, descH: 0.3, name: `static_p${i}` }));
  text(s, "21 endpoints, documented at /api/docs.", { x: X0, y: 6.25, w: 5.9, h: 0.4, fontSize: 13, color: COL.faint });
  const b = shot(s, "plugins.png", { x: 7.0, y: 1.6, w: 5.63, h: 2.6, align: "right" });
  const x = 7.0, w = 5.63;
  row(s, { x, y: b.y + b.h + 0.35, w, label: "A folder, a manifest, one JS file", desc: "Drop it into plugins/ and reload.", descH: 0.35 });
  row(s, { x, y: b.y + b.h + 1.35, w, label: "Isolated in a shadow root", desc: "A broken plugin can't break the app.", descH: 0.35 });
}

// ------------------------------------------------------------------ Tested and deployed
{
  const s = S("Content", "Testing and deployment. 28 automated tests run offline and cover the data rules, the rating model, every endpoint and the plugin store. The app is live on Render with our own domains, and the code is on GitHub.");
  s.addText("Tested and live", { placeholder: "title" });
  const tests = ["Attempt and sync rules", "Elo behaviour and no data leakage", "Model metrics and training", "Every API endpoint", "Plugin registry and storage"];
  text(s, [{ text: "28 tests", options: { color: COL.blue } }, { text: "  run offline with pytest", options: { color: COL.muted } }], { x: X0, y: 1.55, w: 5.6, h: 0.4, fontFace: MED, fontSize: 16 });
  tests.forEach((t, i) => row(s, { x: X0, y: 2.1 + i * 0.8, w: 5.6, label: t, labelSize: 16, descH: 0, name: `static_t${i}` }));
  const x = 7.0, w = 5.63;
  row(s, { x, y: 1.75, w, label: "Hosted on Render", desc: "One Python process: web server and background sync together." });
  row(s, { x, y: 3.05, w, label: "Our own domains", desc: "upsolve.mohitupawar.com and upsolve.wizminar.com" });
  row(s, { x, y: 4.35, w, label: "Open source", desc: "github.com/Wizminar/upsolve" });
}

// ------------------------------------------------------------------ Try it
section("Close");
{
  const s = S("Blank", "It's live. Scan the code or open upsolve.mohitupawar.com and enter any Codeforces handle. It's on a free plan, so the first load after a quiet spell can take about 50 seconds.");
  s.addImage({ path: A("chevron.png"), x: X0, y: 1.25, w: 0.45, h: 0.45, objectName: "logo" });
  text(s, "Try it now", { x: X0, y: 1.95, w: 7, h: 0.6, fontSize: 22, color: COL.muted });
  text(s, "upsolve.mohitupawar.com", { x: X0, y: 2.55, w: 8.2, h: 0.9, fontFace: MED, fontSize: 44 });
  row(s, { x: X0, y: 4.05, w: 6.6, label: "Enter any Codeforces handle", desc: "No account needed. The first load can take ~50 s (free plan).", labelSize: 16, descH: 0.35 });
  row(s, { x: X0, y: 5.0, w: 6.6, label: "API docs", desc: "upsolve.mohitupawar.com/api/docs", labelSize: 16, descH: 0.35 });
  row(s, { x: X0, y: 5.95, w: 6.6, label: "Code", desc: "github.com/Wizminar/upsolve", labelSize: 16, descH: 0.35 });
  s.addImage({ path: A("qr.png"), x: 9.25, y: 2.15, w: 3.2, h: 3.2, objectName: anim(), altText: "QR code linking to upsolve.mohitupawar.com" });
  text(s, "Scan to open", { x: 9.25, y: 5.45, w: 3.2, h: 0.3, fontSize: 12, color: COL.faint, align: "center" });
}
{
  const s = S("Blank", "Thank you. Happy to take questions or show anything live.");
  s.addImage({ path: A("chevron.png"), x: X0, y: 2.0, w: 0.55, h: 0.55, objectName: "logo" });
  text(s, "Thank you", { x: X0, y: 2.75, w: 8, h: 1.1, fontFace: MED, fontSize: 60 });
  text(s, "Questions welcome.", { x: X0, y: 3.95, w: 8, h: 0.5, fontSize: 24, color: COL.muted });
  team(s, { x: X0, y: 5.0, w: 7.0, name: "The Syndicate", members: SYNDICATE });
}

(async () => {
  const out = path.join(__dirname, "Upsolve.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
