// Small DOM helpers. Every piece of text goes through textContent, never innerHTML.

const SVG_NS = "http://www.w3.org/2000/svg";

function build(el, attrs, children) {
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") {
      for (const [prop, val] of Object.entries(v)) {
        if (prop.startsWith("--")) el.style.setProperty(prop, val);
        else el.style[prop] = val;
      }
    }
    else if (k === "dataset") Object.assign(el.dataset, v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export const h = (tag, attrs, ...children) => build(document.createElement(tag), attrs, children);
export const s = (tag, attrs, ...children) => build(document.createElementNS(SVG_NS, tag), attrs, children);

export const RANKS = [
  { lo: 0, key: "newbie", name: "Newbie" },
  { lo: 1200, key: "pupil", name: "Pupil" },
  { lo: 1400, key: "specialist", name: "Specialist" },
  { lo: 1600, key: "expert", name: "Expert" },
  { lo: 1900, key: "cm", name: "Candidate Master" },
  { lo: 2100, key: "master", name: "Master" },
  { lo: 2300, key: "master", name: "International Master" },
  { lo: 2400, key: "gm", name: "Grandmaster" },
  { lo: 2600, key: "gm", name: "International Grandmaster" },
  { lo: 3000, key: "gm", name: "Legendary Grandmaster" },
];

export function rankOf(rating) {
  if (rating === null || rating === undefined) return { key: "newbie", name: "Unrated", lo: 0 };
  let r = RANKS[0];
  for (const x of RANKS) if (rating >= x.lo) r = x;
  return r;
}
export const fillVar = (rating) => `var(--r-${rankOf(rating).key})`;
export const rankClass = (rating) => `rk-${rankOf(rating).key}`;
// Bands whose fill is light enough that white text would fail contrast.
export const needsDarkText = (rating) => ["master", "specialist", "newbie"].includes(rankOf(rating).key);

export const pct = (p) => `${Math.round(p * 100)}%`;
export const fmtDate = (ts, opts = { day: "numeric", month: "short", year: "numeric" }) =>
  new Date(ts * 1000).toLocaleDateString(undefined, opts);
export function ago(ts) {
  const d = (Date.now() / 1000 - ts);
  if (d < 90) return "just now";
  if (d < 3600) return `${Math.round(d / 60)} min ago`;
  if (d < 86400) return `${Math.round(d / 3600)} h ago`;
  return fmtDate(ts);
}

const statusEl = () => document.getElementById("status");
export function status(text, tone = "info", action = null) {
  const el = statusEl();
  el.replaceChildren();
  el.dataset.tone = tone;
  if (!text) return;
  el.append(h("span", null, text));
  if (action) el.append(h("button", { class: "btn btn-small", type: "button", onclick: action.run }, action.label));
}

// A <details> toggle that reveals the data behind a chart as a table.
export function dataTable(caption, headers, rows) {
  return h("details", { class: "table-toggle" },
    h("summary", { class: "linkish" }, "Show data as a table"),
    h("div", { class: "table-wrap" },
      h("table", { class: "data-table" },
        h("caption", null, caption),
        h("thead", null, h("tr", null, headers.map((x) => h("th", { scope: "col" }, x)))),
        h("tbody", null, rows.map((r) => h("tr", null, r.map((c) => h("td", null, c))))))));
}
