// Hand-drawn SVG charts. Each returns a <figure> with a text alternative and a data-table toggle.
import { h, s, RANKS, rankOf, fillVar, needsDarkText, fmtDate, dataTable } from "./ui.js";

const RANK_BANDS = RANKS.map((r, i) => ({ ...r, hi: (RANKS[i + 1] || { lo: 4000 }).lo }));

function niceTicks(lo, hi, step) {
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}

// ---------------------------------------------------------------- the rating ladder

/**
 * Vertical ladder of rank bands with recommended problems pinned at their rating.
 * items: [{problem_id, rating}], you: practice rating.
 */
export function ladder({ you, zone, items, onPin }) {
  const ratings = items.map((i) => i.rating).concat([you, zone[0], zone[1]]);
  const lo = Math.max(800, Math.floor((Math.min(...ratings) - 300) / 100) * 100);
  const hi = Math.min(3600, Math.ceil((Math.max(...ratings) + 300) / 100) * 100);
  const W = 168, H = 560, top = 10, bottom = 10;
  const y = (r) => top + (hi - r) / (hi - lo) * (H - top - bottom);
  const bandX = 36, bandW = 22;

  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `Rating ladder from ${lo} to ${hi}. Your practice rating is ${you}. ` +
      items.map((i) => `${i.problem_id} at ${i.rating}`).join(", ") });

  for (const b of RANK_BANDS) {
    const a = Math.max(b.lo, lo), z = Math.min(b.hi, hi);
    if (a >= z) continue;
    svg.append(s("rect", { x: bandX, y: y(z), width: bandW, height: y(a) - y(z), fill: `var(--r-${b.key})` },
      s("title", null, `${b.name}: ${b.lo}–${b.hi - 1}`)));
  }
  for (const t of niceTicks(lo, hi, 200)) {
    svg.append(s("text", { class: "tick", x: bandX - 6, y: y(t) + 4, "text-anchor": "end" }, t));
    svg.append(s("line", { x1: bandX - 3, x2: bandX, y1: y(t), y2: y(t), stroke: "var(--graphite)" }));
  }

  const [zLo, zHi] = zone;  // from the model: where an unfamiliar problem scores 50–70%
  const pat = s("pattern", { id: "zone-hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" },
    s("line", { x1: 0, y1: 0, x2: 0, y2: 6, stroke: "var(--ink)", "stroke-width": 1.5, opacity: 0.35 }));
  svg.append(s("defs", null, pat));
  svg.append(s("rect", { x: bandX + bandW, y: y(zHi), width: W - bandX - bandW, height: y(zLo) - y(zHi), fill: "url(#zone-hatch)" },
    s("title", null, `Stretch zone: ${zLo}–${zHi}`)));

  svg.append(s("line", { x1: bandX - 4, x2: W, y1: y(you), y2: y(you), stroke: "var(--ink)", "stroke-width": 2 }));
  svg.append(s("text", { class: "you", x: W, y: y(you) - 6, "text-anchor": "end" }, `You ${you}`));

  // Pins, nudged apart so labels never overlap.
  const sorted = [...items].sort((a, b) => b.rating - a.rating);
  let lastY = -Infinity;
  const pins = [];
  for (const it of sorted) {
    let py = y(it.rating);
    if (py - lastY < 22) py = lastY + 22;
    lastY = py;
    const g = s("g", { class: "pin", tabindex: "-1", "data-pid": it.problem_id,
      style: `transform: translateY(${H - py + 20}px)` });
    g.append(
      s("line", { x1: bandX + bandW, x2: 70, y1: y(it.rating), y2: py, stroke: "var(--ink)", "stroke-width": 1.5 }),
      s("rect", { x: 70, y: py - 10, width: 66, height: 20, rx: 2, fill: fillVar(it.rating), stroke: "var(--ink)", "stroke-width": 1.5 }),
      s("circle", { cx: 78, cy: py, r: 2.5, fill: "var(--paper)", stroke: "var(--ink)" }),
      s("text", { class: "pin-label", x: 84, y: py + 4, style: `fill:${needsDarkText(it.rating) ? "#16233F" : "#fff"}` }, it.problem_id),
      s("title", null, `${it.problem_id}, rated ${it.rating} (${rankOf(it.rating).name})`),
    );
    if (onPin) g.addEventListener("click", () => onPin(it.problem_id));
    pins.push(g);
    svg.append(g);
  }
  // One orchestrated moment: pins rise into place.
  setTimeout(() => pins.forEach((p, i) => {
    p.style.transitionDelay = `${i * 70}ms`;
    p.style.transform = "translateY(0)";
  }), 30);

  return h("figure", { class: "ladder" }, svg,
    h("figcaption", null, `Hatched: problems rated ${zone[0]}–${zone[1]} give you roughly a 50–70% chance.`));
}

// ---------------------------------------------------------------- line chart

/**
 * series: [{name, points: [{x: unixSeconds, y}], dashed?}]
 */
export function lineChart({ series, title, caption, bands = true, height = 280, yUnit = "rating", tableRows }) {
  const all = series.flatMap((s_) => s_.points);
  const W = 640, H = height, m = { l: 46, r: 12, t: 12, b: 28 };
  if (!all.length) return h("p", { class: "empty" }, "Nothing to plot yet.");
  const xs = all.map((p) => p.x), ys = all.map((p) => p.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs) || x0 + 1;
  const y0 = Math.floor((Math.min(...ys) - 100) / 100) * 100, y1 = Math.ceil((Math.max(...ys) + 100) / 100) * 100;
  const X = (v) => m.l + (x1 === x0 ? 0.5 : (v - x0) / (x1 - x0)) * (W - m.l - m.r);
  const Y = (v) => m.t + (y1 - v) / (y1 - y0) * (H - m.t - m.b);

  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": caption });
  if (bands) {
    for (const b of RANK_BANDS) {
      const a = Math.max(b.lo, y0), z = Math.min(b.hi, y1);
      if (a >= z) continue;
      svg.append(s("rect", { x: m.l, y: Y(z), width: W - m.l - m.r, height: Y(a) - Y(z),
        fill: `var(--r-${b.key})`, opacity: 0.13 }, s("title", null, b.name)));
    }
  }
  const step = (y1 - y0) > 1200 ? 400 : (y1 - y0) > 500 ? 200 : 100;
  const axis = s("g", { class: "axis" });
  for (const t of niceTicks(y0, y1, step)) {
    axis.append(s("line", { x1: m.l, x2: W - m.r, y1: Y(t), y2: Y(t) }));
    axis.append(s("text", { x: m.l - 6, y: Y(t) + 4, "text-anchor": "end" }, t));
  }
  const span = x1 - x0, yearly = span > 2 * 365 * 86400;
  const nT = 5;
  for (let i = 0; i <= nT; i++) {
    const v = x0 + span * i / nT;
    axis.append(s("text", { x: X(v), y: H - 8, "text-anchor": i === 0 ? "start" : i === nT ? "end" : "middle" },
      fmtDate(v, yearly ? { year: "numeric" } : { month: "short", year: "2-digit" })));
  }
  svg.append(axis);

  series.forEach((ser) => {
    const d = ser.points.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("");
    svg.append(s("path", { d, fill: "none", stroke: "var(--ink)", "stroke-width": 2,
      "stroke-dasharray": ser.dashed ? "6 4" : null, "stroke-linejoin": "round" }));
    if (!ser.dashed && ser.points.length < 400) {
      for (const p of ser.points) {
        svg.append(s("circle", { cx: X(p.x), cy: Y(p.y), r: 3, fill: fillVar(p.y), stroke: "var(--ink)", "stroke-width": 1 },
          s("title", null, `${p.label ? p.label + ": " : ""}${p.y} ${yUnit} on ${fmtDate(p.x)}`)));
      }
    }
  });

  const legend = series.length > 1
    ? h("ul", { class: "legend" }, series.map((ser) => h("li", null,
        h("span", { class: ser.dashed ? "swatch swatch-dash" : "swatch", style: ser.dashed ? null : { background: "var(--ink)" } }), ser.name)))
    : null;
  return h("figure", { class: "chart" }, svg,
    h("figcaption", null, h("span", null, caption)),
    legend,
    tableRows ? dataTable(title, tableRows.headers, tableRows.rows) : null);
}

// ---------------------------------------------------------------- activity heatmap

export function heatmap(days) {
  const byDay = new Map(days.map((d) => [d.day, d]));
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const start = new Date(today); start.setDate(start.getDate() - 364 - start.getDay());
  const cell = 11, gap = 2, m = { l: 26, t: 18 };
  const weeks = Math.ceil(((today - start) / 86400000 + 1) / 7);
  const W = m.l + weeks * (cell + gap), H = m.t + 7 * (cell + gap) + 4;
  const counts = days.map((d) => d.submissions).filter((x) => x > 0).sort((a, b) => a - b);
  const q = (f) => counts[Math.floor(f * (counts.length - 1))] || 1;
  const cuts = [q(0.25), q(0.5), q(0.75)];
  const level = (n) => n === 0 ? 0 : n <= cuts[0] ? 1 : n <= cuts[1] ? 2 : n <= cuts[2] ? 3 : 4;

  const total = days.reduce((a, d) => a + d.submissions, 0);
  const active = days.filter((d) => d.submissions > 0).length;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `Activity over the last year: ${total} submissions on ${active} days.` });
  ["Mon", "Wed", "Fri"].forEach((d, i) =>
    svg.append(s("text", { x: 0, y: m.t + (1 + 2 * i) * (cell + gap) + 9, "font-size": 10 }, d)));
  let lastMonth = -1;
  for (let w = 0; w < weeks; w++) {
    for (let d = 0; d < 7; d++) {
      const dt = new Date(start); dt.setDate(start.getDate() + w * 7 + d);
      if (dt > today) continue;
      const key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
      const rec = byDay.get(key);
      const n = rec ? rec.submissions : 0;
      if (d === 0 && dt.getMonth() !== lastMonth) {
        lastMonth = dt.getMonth();
        svg.append(s("text", { x: m.l + w * (cell + gap), y: 11, "font-size": 10 },
          dt.toLocaleDateString(undefined, { month: "short" })));
      }
      svg.append(s("rect", { x: m.l + w * (cell + gap), y: m.t + d * (cell + gap), width: cell, height: cell, rx: 2,
        fill: `var(--heat-${level(n)})` },
        s("title", null, `${dt.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}: ` +
          `${n} submission${n === 1 ? "" : "s"}${rec ? `, ${rec.accepted} accepted` : ""}`)));
    }
  }
  const legend = h("ul", { class: "legend", "aria-label": "Colour scale" },
    h("li", null, "Fewer"),
    [0, 1, 2, 3, 4].map((l) => h("li", null, h("span", { class: "swatch", style: { background: `var(--heat-${l})` } }),
      l === 0 ? "0" : l === 1 ? `≤${cuts[0]}` : l === 2 ? `≤${cuts[1]}` : l === 3 ? `≤${cuts[2]}` : `>${cuts[2]}`)),
    h("li", null, "more submissions per day"));
  return h("figure", { class: "chart" }, svg,
    h("figcaption", null, h("span", null, `${total} submissions on ${active} active days in the last 12 months.`)),
    legend,
    dataTable("Submissions per day (days with activity)", ["Day", "Submissions", "Accepted"],
      days.slice().reverse().map((d) => [d.day, d.submissions, d.accepted])));
}

// ---------------------------------------------------------------- calibration

export function calibration(bins, caption) {
  const S = 300, m = 44;
  const P = (v) => m + v * (S - 2 * m);
  const svg = s("svg", { viewBox: `0 0 ${S} ${S}`, role: "img", "aria-label": caption });
  const axis = s("g", { class: "axis" });
  for (const t of [0, 0.25, 0.5, 0.75, 1]) {
    axis.append(s("line", { x1: P(0), x2: P(1), y1: S - P(t), y2: S - P(t) }));
    axis.append(s("text", { x: P(0) - 6, y: S - P(t) + 4, "text-anchor": "end", "font-size": 10 }, `${t * 100}%`));
    axis.append(s("text", { x: P(t), y: S - m + 16, "text-anchor": "middle", "font-size": 10 }, `${t * 100}%`));
  }
  svg.append(axis);
  svg.append(s("rect", { x: P(0.5), y: S - P(0.7), width: P(0.7) - P(0.5), height: P(0.7) - P(0.5), fill: "var(--highlighter)", opacity: 0.6 },
    s("title", null, "Target zone 50–70%")));
  svg.append(s("line", { x1: P(0), y1: S - P(0), x2: P(1), y2: S - P(1), stroke: "var(--graphite)", "stroke-dasharray": "4 4" }));
  const maxN = Math.max(...bins.map((b) => b.count));
  const pts = bins.map((b) => [P(b.mean_predicted), S - P(b.observed_rate)]);
  svg.append(s("path", { d: pts.map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join(""), fill: "none", stroke: "var(--ink)", "stroke-width": 2 }));
  bins.forEach((b, i) => svg.append(s("circle", { cx: pts[i][0], cy: pts[i][1], r: 3 + 6 * Math.sqrt(b.count / maxN),
    fill: "var(--sheet)", stroke: "var(--ink)", "stroke-width": 2 },
    s("title", null, `Predicted ${Math.round(b.mean_predicted * 100)}%, observed ${Math.round(b.observed_rate * 100)}% (${b.count} attempts)`))));
  svg.append(s("text", { x: S / 2, y: S - 2, "text-anchor": "middle", "font-size": 11 }, "Predicted chance"));
  svg.append(s("text", { x: 10, y: S / 2, "text-anchor": "middle", "font-size": 11, transform: `rotate(-90 10 ${S / 2})` }, "Actually solved"));
  return h("figure", { class: "chart", style: { maxWidth: "380px" } }, svg,
    h("figcaption", null, h("span", null, caption)),
    h("ul", { class: "legend" },
      h("li", null, h("span", { class: "swatch swatch-dash" }), "Perfect calibration"),
      h("li", null, h("span", { class: "swatch", style: { background: "var(--highlighter)" } }), "50–70% target zone"),
      h("li", null, "Circle size: number of attempts")),
    dataTable("Calibration on held-out attempts", ["Predicted bin", "Mean predicted", "Observed", "Attempts"],
      bins.map((b) => [`${b.low * 100}–${b.high * 100}%`, `${Math.round(b.mean_predicted * 100)}%`, `${Math.round(b.observed_rate * 100)}%`, b.count])));
}
