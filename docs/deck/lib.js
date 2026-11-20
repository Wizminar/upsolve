// Shared theme, layouts and helpers for the Upsolve decks (main deck and cross-dev deck).
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const A = (f) => path.join(__dirname, "assets", f);
const data = JSON.parse(fs.readFileSync(A("data.json"), "utf8"));

// Hex values of the website's dark theme (used where pptxgenjs needs hex).
const HEX = { bg: "0E0E10", ink: "F2F2F4", muted: "A0A0A8", faint: "76767E", line: "2A2A2E", wash: "1D1D20", blue: "8C9CFF", red: "FF8A80", green: "5CCB83" };

const THEME = {
  name: "Upsolve",
  headFontFace: "Helvetica Neue Medium",
  bodyFontFace: "Helvetica Neue",
  colors: {
    dk1: HEX.bg, lt1: HEX.ink, dk2: HEX.line, lt2: HEX.muted,
    accent1: HEX.blue, accent2: HEX.faint, accent3: HEX.wash, accent4: HEX.green, accent5: HEX.red, accent6: "2F49D1",
    hlink: HEX.blue, folHlink: HEX.muted,
  },
};

const MED = "Helvetica Neue Medium";
const MONO = "Menlo";
const X0 = 0.7, RIGHT = 12.633, BOTTOM = 6.8;

function makeDeck(title) {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
  pres.title = title;
  pres.author = "The Syndicate";
  pres.company = "CS698B";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  // Dark deck: background is dk1 (text1) and text is lt1 (background1).
  const COL = { bg: C.text1, ink: C.background1, muted: C.background2, line: C.text2, blue: C.accent1, faint: C.accent2, wash: C.accent3 };

  pres.defineSlideMaster({
    title: "Content",
    background: { color: HEX.bg },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: X0, y: 0.55, w: 11.9, h: 0.8, fontFace: MED, fontSize: 32, color: COL.ink, valign: "top", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: 12.0, y: 6.95, w: 0.63, h: 0.3, fontSize: 10, color: COL.faint, align: "right" },
  });
  pres.defineSlideMaster({
    title: "Section",
    background: { color: HEX.bg },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: X0, y: 3.0, w: 11.9, h: 1.1, fontFace: MED, fontSize: 54, color: COL.ink, valign: "top", align: "left", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: 12.0, y: 6.95, w: 0.63, h: 0.3, fontSize: 10, color: COL.faint, align: "right" },
  });
  pres.defineSlideMaster({ title: "Blank", background: { color: HEX.bg }, objects: [] });

  let animN = 0;
  const anim = () => `anim_${String(++animN).padStart(2, "0")}`;
  const text = (slide, t, o) => slide.addText(t, { isTextBox: true, margin: 0, color: COL.ink, fontSize: 16, valign: "top", ...o });

  // The website's list row: thin rule on top, label, optional value on the right, muted description.
  function row(slide, { x, y, w, label, value, desc, valueColor, name, labelSize = 18, descH = 0.6, labelFont = MED }) {
    const n = name || anim();
    const runs = [{ text: label, options: { fontFace: labelFont, fontSize: labelSize, color: COL.ink, breakLine: !!desc } }];
    if (desc) runs.push({ text: desc, options: { fontFace: "Helvetica Neue", fontSize: 14, color: COL.muted } });
    slide.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: HEX.line, width: 1 }, objectName: `${n}_rule` });
    text(slide, runs, { x, y: y + 0.18, w: value ? w - 1.9 : w, h: 0.4 + descH, paraSpaceAfter: 4, objectName: `${n}_text` });
    if (value) text(slide, value, { x: x + w - 1.9, y: y + 0.12, w: 1.9, h: 0.55, align: "right", fontFace: MED, fontSize: 26, color: valueColor || COL.ink, objectName: `${n}_value` });
  }

  // Place a framed screenshot inside a box, keeping its aspect ratio (never spills out of the box).
  function shot(slide, file, { x, y, w, h, name, align = "left" }) {
    const size = data.sizes[file.replace(".png", "")];
    const r = size[0] / size[1];
    let iw = w, ih = w / r;
    if (h && ih > h) { ih = h; iw = h * r; }
    const ix = align === "right" ? x + w - iw : align === "center" ? x + (w - iw) / 2 : x;
    slide.addImage({ path: A(file), x: ix, y, w: iw, h: ih, objectName: name || anim(), altText: `Screenshot of Upsolve: ${file.replace(".png", "").replace("_", " ")}` });
    return { x: ix, y, w: iw, h: ih };
  }

  let currentSection = "";
  const section = (t) => { currentSection = t; pres.addSection({ title: t }); };
  const S = (master, notes) => {
    const s = pres.addSlide({ masterName: master, sectionTitle: currentSection });
    if (notes) s.addNotes(notes);
    return s;
  };

  // Section divider: small blue label (what the component is), big title, one-line summary.
  function divider(label, title, summary, notes) {
    const s = S("Section", notes);
    text(s, label, { x: X0, y: 2.35, w: 8, h: 0.45, fontSize: 18, color: COL.blue, objectName: "div_label" });
    s.addText(title, { placeholder: "title" });
    text(s, summary, { x: X0, y: 4.25, w: 8.5, h: 0.9, fontSize: 20, color: COL.muted, objectName: anim() });
    return s;
  }

  function codeBlock(slide, code, { x, y, w, h, size = 12, name }) {
    const n = name || anim();
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: HEX.wash }, line: { color: HEX.line, width: 1 }, objectName: `${n}_bg` });
    text(slide, code, { x: x + 0.3, y: y + 0.25, w: w - 0.6, h: h - 0.5, fontFace: MONO, fontSize: size, color: COL.ink, lineSpacingMultiple: 1.15, objectName: `${n}_code` });
  }

  // Team block: team name, then members with roll numbers in columns.
  function team(slide, { x, y, w, name, members, cols = 2, nameSize = 26 }) {
    text(slide, name, { x, y, w, h: 0.5, fontFace: MED, fontSize: nameSize, objectName: "team_name" });
    const cw = w / cols, rows = Math.ceil(members.length / cols);
    members.forEach(([n, r], i) => {
      const c = Math.floor(i / rows), k = i % rows;
      text(slide, [
        { text: n, options: { color: COL.ink } },
        { text: `  ${r}`, options: { color: COL.muted } },
      ], { x: x + c * cw, y: y + 0.62 + k * 0.4, w: cw - 0.1, h: 0.35, fontSize: 15, objectName: `team_m${i}` });
    });
  }

  return { pres, C, COL, anim, text, row, shot, section, S, divider, codeBlock, team };
}

const SYNDICATE = [["Ashirvad Dwivedi", "265005"], ["Mohit Shankar Pawar", "265021"], ["Chaitanya Kumar", "265009"], ["Bishal Podder", "265008"]];
const CROSSDEV = [["Divyanshu Anand", "265011"], ["Divyanshu Lohani", "265012"], ["Yash", "265031"], ["Yash Akarsh", "265032"], ["Ishan Aryan", "265016"], ["Gaurav Verma", "265014"]];

module.exports = { SYNDICATE, CROSSDEV, makeDeck, A, data, HEX, THEME, MED, MONO, X0, RIGHT, BOTTOM };
