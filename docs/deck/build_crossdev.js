// Cross-dev deck: the cross-dev team presents Rival, a plugin built for The Syndicate on the Upsolve API.
// Run like build.js, then postprocess.py on Upsolve_Plugins.pptx.
const path = require("path");
const { applyTheme } = require(process.env.APPLY_THEME);
const { CROSSDEV, makeDeck, A, HEX, THEME, MED, MONO, X0, RIGHT } = require("./lib");

const { pres, COL, anim, text, row, shot, section, S, codeBlock, team } = makeDeck("Rival");

// ------------------------------------------------------------------ 1. Title
section("Introduction");
{
  const s = S("Blank", "We are the cross-dev team for The Syndicate. Our project is Rival, a plugin that runs inside their app, Upsolve. Everything Rival knows comes from the Upsolve API, which The Syndicate built.");
  s.addImage({ path: A("chevron.png"), x: X0, y: 0.8, w: 0.55, h: 0.55, objectName: "logo" });
  text(s, "Rival", { x: X0, y: 1.45, w: 6.2, h: 1.1, fontFace: MED, fontSize: 60 });
  text(s, "A plugin for Upsolve.", { x: X0, y: 2.6, w: 5.8, h: 0.5, fontSize: 24, color: COL.muted });
  text(s, [
    { text: "Cross-dev project for ", options: { color: COL.muted } },
    { text: "The Syndicate", options: { fontFace: MED, color: COL.ink } },
    { text: ", built on the Upsolve API made by The Syndicate. CS698B.", options: { color: COL.muted } },
  ], { x: X0, y: 3.3, w: 6.0, h: 0.8, fontSize: 15 });
  team(s, { x: X0, y: 4.7, w: 6.1, name: "Cross-dev team", members: CROSSDEV, nameSize: 22 });
  shot(s, "rival_chart.png", { x: 7.1, y: 0.85, w: 5.53, h: 5.8, align: "right" });
}

// ------------------------------------------------------------------ 2. What Rival does
{
  const s = S("Content", "Rival is a complete plugin in about 110 lines. Pick a friend's handle; Rival compares your topic ratings with theirs and finds problems they solved that you are likely to crack next, using Upsolve's model. It needs no server code: all its data comes from the API made by The Syndicate.");
  s.addText("Rival: train against a friend", { placeholder: "title" });
  shot(s, "rival_chart.png", { x: X0, y: 1.55, w: 6.0, h: 5.15 });
  const x = 7.65, w = 4.98;
  row(s, { x, y: 1.75, w, label: "Pick a rival", desc: "Any Codeforces handle; imported automatically if new." });
  row(s, { x, y: 3.05, w, label: "Compare every topic", desc: "Who is ahead, and by how much, topic by topic." });
  row(s, { x, y: 4.35, w, label: "Problems within reach", desc: "What they solved that you haven't, at about a 60% chance for you." });
  row(s, { x, y: 5.65, w, label: "About 110 lines, no server code", desc: "Data from the Upsolve API, made by The Syndicate.", descH: 0.35 });
}

// ------------------------------------------------------------------ 3. How a plugin loads
section("How Rival fits in");
{
  const s = S("Content", "How Rival gets into Upsolve. It is a folder with a manifest and one JavaScript file. Upsolve checks the manifest, loads the file into its page, and Rival adds its own tab, isolated so it can't break the app.");
  s.addText("From a folder to a tab in Upsolve", { placeholder: "title" });
  const steps = [
    ["Drop in a folder", "plugins/your-plugin/ with manifest.json and plugin.js."],
    ["Upsolve checks it", "The manifest is validated and Rival is listed."],
    ["Upsolve loads it", "Rival's JavaScript runs inside the Upsolve page."],
    ["It draws", "Rival adds its own tab, isolated from the rest of the app."],
  ];
  const colW = 2.75, gap = 0.3, top = 2.2;
  s.addShape(pres.shapes.LINE, { x: X0, y: top, w: RIGHT - X0, h: 0, line: { color: HEX.line, width: 1.5 }, objectName: "timeline" });
  steps.forEach(([name, desc], i) => {
    const x = X0 + i * (colW + gap), n = anim();
    s.addShape(pres.shapes.OVAL, { x, y: top - 0.09, w: 0.18, h: 0.18, fill: { color: HEX.blue }, line: { type: "none" }, objectName: `${n}_dot` });
    text(s, [
      { text: `${i + 1}`, options: { fontSize: 14, color: COL.blue, breakLine: true } },
      { text: name, options: { fontFace: MED, fontSize: 22, breakLine: true } },
      { text: desc, options: { fontSize: 14, color: COL.muted } },
    ], { x, y: top + 0.35, w: colW, h: 2.2, paraSpaceAfter: 6, objectName: `${n}_text` });
  });
  const facts = [["No build step", "Plain ES modules"], ["No server code", "Uses The Syndicate's API"], ["Isolated", "Errors and CSS stay inside"], ["On or off", "Users toggle it in Plugins"]];
  facts.forEach(([t, d], i) => row(s, { x: X0 + i * (colW + gap), y: 5.25, w: colW, label: t, desc: d, labelSize: 15, descH: 0.4 }));
}

// ------------------------------------------------------------------ 4. Folder and manifest
{
  const s = S("Content", "The folder name is the plugin id. The manifest says what it is called, which file to load and where it draws. Upsolve reports any mistake in it.");
  s.addText("A folder and a manifest", { placeholder: "title" });
  codeBlock(s, [
    "plugins/",
    "  rival/",
    "    manifest.json",
    "    plugin.js",
    "",
    "{",
    "  \"id\": \"rival\",",
    "  \"name\": \"Rival\",",
    "  \"version\": \"1.0.0\",",
    "  \"description\": \"Compare your topic ratings...\",",
    "  \"author\": \"Cross-dev team\",",
    "  \"entry\": \"plugin.js\",",
    "  \"slots\": [\"page\"],",
    "  \"api_version\": \"1\"",
    "}",
  ].join("\n"), { x: X0, y: 1.55, w: 6.1, h: 5.15, size: 13, name: "static_code" });
  const x = 7.25, w = 5.38;
  row(s, { x, y: 1.6, w, label: "id", desc: "Must match the folder name.", labelFont: MONO, labelSize: 15, descH: 0.35 });
  row(s, { x, y: 2.55, w, label: "entry", desc: "The ES module to load from the folder.", labelFont: MONO, labelSize: 15, descH: 0.35 });
  row(s, { x, y: 3.5, w, label: "slots", desc: "Where it draws: page (its own tab), today, insights or plan.", labelFont: MONO, labelSize: 15, descH: 0.35 });
  row(s, { x, y: 4.45, w, label: "api_version", desc: "\"1\", the current host API.", labelFont: MONO, labelSize: 15, descH: 0.35 });
  row(s, { x, y: 5.4, w, label: "Other files", desc: "Served at /plugin-files/<id>/...", labelSize: 15, descH: 0.35 });
}

// ------------------------------------------------------------------ 5. What Rival uses
{
  const s = S("Content", "Rival doesn't fetch anything from Codeforces itself. Everything it shows comes from the Upsolve API, which The Syndicate built: topic ratings, solved problems, the chance of solving from their model, and a small store for Rival's own settings.");
  s.addText("Built on the API made by The Syndicate", { placeholder: "title" });
  const uses = [
    ["Topic ratings", "Both users' rating in every topic."],
    ["Solved problems", "What the rival solved that you haven't."],
    ["Chance of solving", "From Upsolve's machine-learning model, for you."],
    ["Storage", "Remembers your chosen rival."],
  ];
  uses.forEach(([l, d], i) => row(s, { x: X0 + (i % 2) * 6.0, y: 1.8 + Math.floor(i / 2) * 1.5, w: 5.6, label: l, desc: d, labelSize: 22, descH: 0.5 }));
  text(s, [
    { text: "Upsolve and its API: ", options: { color: COL.muted } },
    { text: "The Syndicate", options: { fontFace: MED, color: COL.ink, breakLine: true } },
    { text: "Rival: ", options: { color: COL.muted } },
    { text: "the cross-dev team", options: { fontFace: MED, color: COL.ink } },
  ], { x: X0, y: 5.2, w: 11.9, h: 0.9, fontSize: 18, paraSpaceAfter: 6, objectName: anim() });
}

// ------------------------------------------------------------------ 6. Rival step by step
section("Inside Rival");
{
  const s = S("Content", "What Rival's render function does, in order. It reads the saved rival from its store. It fetches both users' topic ratings, and if the rival is new it starts an import and waits. It draws the comparison chart, scores the rival's solved problems with Upsolve's model for you, and saves a record of the comparison.");
  s.addText("Rival, step by step", { placeholder: "title" });
  codeBlock(s, [
    "export default function register(host) {",
    "  async function render(el) {",
    "    const rival = await host.store.get(\"rival\");",
    "    const theirs = await host.api.topics(rival);",
    "    const mine = await host.api.topics(host.handle);",
    "    el.append(diverging(mine, theirs));",
    "",
    "    const picks = await Promise.all(pool.map(",
    "      (p) => host.api.predict(host.handle, p.problem_id)));",
    "    // keep the five closest to a 60% chance",
    "  }",
    "  host.addPanel({ slot: \"page\", title: \"Rival\", render });",
    "}",
  ].join("\n"), { x: X0, y: 1.55, w: 6.6, h: 5.15, size: 12, name: "static_code" });
  const steps = [
    ["Read the saved rival", "host.store.get(\"rival\")"],
    ["Fetch both topic lists", "Imports the rival first if new"],
    ["Draw the comparison", "SVG via host.ui.s, plus a data table"],
    ["Score their solved problems", "host.api.predict, for you"],
    ["Save the comparison", "host.store.set(\"last_compare\")"],
  ];
  steps.forEach(([l, d], i) => row(s, { x: 7.7, y: 1.6 + i * 1.0, w: 4.93, label: `${i + 1}  ${l}`, desc: d, labelSize: 16, descH: 0.35 }));
}

// ------------------------------------------------------------------ 7. The chart
{
  const s = S("Content", "The comparison chart. One row per topic both users have tried at least three times. Solid bars to the right are topics where you rate higher; dashed outlines to the left are topics where your rival does. The shape, not only colour, carries the meaning, and the same numbers are in a table underneath.");
  s.addText("A diverging chart, drawn in SVG", { placeholder: "title" });
  shot(s, "rival_chart.png", { x: X0, y: 1.55, w: 5.4, h: 5.15 });
  const x = 6.9, w = 5.73;
  row(s, { x, y: 1.75, w, label: "Solid bars: you're ahead", desc: "Dashed outlines: your rival is ahead. Shape carries the meaning, not colour." });
  row(s, { x, y: 3.05, w, label: "Topics you both tried", desc: "At least three attempts each, sorted by the gap." });
  row(s, { x, y: 4.35, w, label: "Readable without seeing it", desc: "role=\"img\", a full aria-label and host.ui.dataTable with every number." });
}

// ------------------------------------------------------------------ 8. Within reach
{
  const s = S("Content", "The second half uses Upsolve's machine-learning model. Rival takes up to 25 problems the rival solved and you haven't, gets your chance on each from Upsolve's model through The Syndicate's API, and keeps the five closest to 60 percent.");
  s.addText("Problems within reach, from Upsolve's model", { placeholder: "title" });
  shot(s, "rival_reach.png", { x: X0, y: 1.55, w: 7.4, h: 4.8 });
  const x = 8.6, w = 4.03;
  row(s, { x, y: 1.75, w, label: "Their solves, not yours", desc: "Up to 25 problems the rival solved that you haven't." });
  row(s, { x, y: 3.05, w, label: "Your chance on each", desc: "From Upsolve's model, via The Syndicate's API." });
  row(s, { x, y: 4.35, w, label: "Five near 60%", desc: "Sorted by distance from a 60% chance." });
}

// ------------------------------------------------------------------ Last. Thanks
section("Close");
{
  const s = S("Blank", "Thank you. Rival is our cross-dev project for The Syndicate, built entirely on the Upsolve API they made. Scan the code to try it inside Upsolve.");
  s.addImage({ path: A("chevron.png"), x: X0, y: 1.0, w: 0.55, h: 0.55, objectName: "logo" });
  text(s, "Thank you", { x: X0, y: 1.7, w: 8, h: 1.1, fontFace: MED, fontSize: 60 });
  text(s, [
    { text: "Rival is our cross-dev project for ", options: { color: COL.muted } },
    { text: "The Syndicate", options: { fontFace: MED, color: COL.ink } },
    { text: ", built on the Upsolve API made by The Syndicate.", options: { color: COL.muted } },
  ], { x: X0, y: 2.95, w: 7.8, h: 0.9, fontSize: 20 });
  team(s, { x: X0, y: 4.5, w: 7.4, name: "Cross-dev team", members: CROSSDEV, nameSize: 22 });
  s.addImage({ path: A("qr.png"), x: 9.25, y: 2.15, w: 3.2, h: 3.2, objectName: anim(), altText: "QR code linking to upsolve.mohitupawar.com" });
  text(s, "Try Rival in Upsolve", { x: 9.0, y: 5.45, w: 3.7, h: 0.3, fontSize: 12, color: COL.faint, align: "center" });
}

(async () => {
  const out = path.join(__dirname, "Upsolve_Plugins.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
