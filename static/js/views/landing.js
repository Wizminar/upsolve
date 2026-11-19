import { api } from "../api.js";
import { h, s, RANKS, rankClass } from "../ui.js";

const EXAMPLE = { handle: "tourist" };

function ladderStrip() {
  // The full Codeforces rank ladder, 800 to 3600, drawn to scale.
  const lo = 800, hi = 3600, W = 1000, H = 120, bandY = 40, bandH = 36;
  const x = (r) => (r - lo) / (hi - lo) * W;
  const svg = s("svg", { viewBox: `0 -4 ${W} ${H}`, role: "img",
    "aria-label": "The Codeforces rating ladder from 800 to 3600, coloured by rank." });
  // Ranks that share a colour are drawn as one band with a short name.
  const SHORT = { newbie: "Newbie", pupil: "Pupil", specialist: "Specialist", expert: "Expert",
    cm: "CM", master: "Master", gm: "Grandmaster" };
  const groups = [];
  RANKS.forEach((r, i) => {
    const z = (RANKS[i + 1] || { lo: hi }).lo;
    const last = groups[groups.length - 1];
    if (last && last.key === r.key) { last.hi = z; last.names.push(r.name); }
    else groups.push({ key: r.key, lo: r.lo, hi: z, names: [r.name] });
  });
  for (const g of groups) {
    const a = Math.max(g.lo, lo), z = Math.min(g.hi, hi);
    if (a >= z) continue;
    svg.append(s("rect", { x: x(a), y: bandY, width: x(z) - x(a), height: bandH, fill: `var(--r-${g.key})` },
      s("title", null, `${g.names.join(", ")}: ${g.lo}–${g.hi - 1}`)));
    svg.append(s("text", { x: x(a) + 4, y: bandY - 10, "font-size": 14, fill: "var(--ink)", "font-weight": 600 }, SHORT[g.key]));
  }
  for (let t = 800; t <= 3600; t += 400)
    svg.append(s("text", { x: x(t), y: bandY + bandH + 22, "font-size": 14, fill: "var(--graphite)",
      "text-anchor": t === 800 ? "start" : t === 3600 ? "end" : "middle" }, t));
  return h("figure", { class: "ladder-strip" }, svg,
    h("figcaption", null, "The Codeforces rank ladder. Upsolve pins each day's problems on it, a step above where you're comfortable."));
}

export async function renderLanding(main, { go }) {
  const input = h("input", { name: "handle", "aria-label": "Codeforces handle", placeholder: "your handle",
    autocomplete: "off", spellcheck: "false", required: true, pattern: "[A-Za-z0-9_.\\-]{3,24}" });
  const recent = h("div", { class: "recent" });

  main.replaceChildren(
    h("section", { class: "landing" },
      h("h1", null, "Practise the problems you can almost solve."),
      h("p", { class: "lede" },
        "Upsolve reads your public Codeforces history, rates you topic by topic, and picks problems you have about a 50–70% chance of solving. Hard enough to teach you something, but still within reach."),
      h("form", { class: "landing-form", onsubmit: (e) => { e.preventDefault(); go(input.value.trim()); } },
        input, h("button", { class: "btn btn-ink", type: "submit" }, "Start practising")),
      h("p", { class: "hint" }, "No account needed. Try ",
        h("a", { href: `/u/${EXAMPLE.handle}`, onclick: (e) => { e.preventDefault(); go(EXAMPLE.handle); } }, EXAMPLE.handle),
        " to see how it works."),
      ladderStrip(),
      recent,
      h("section", { class: "how", "aria-label": "How Upsolve works" },
        h("div", null, h("h3", null, "Reads your history"),
          h("p", null, "Every submission is grouped into one attempt per problem. An attempt counts as solved if it was accepted within 24 hours. Compilation errors don't count against you.")),
        h("div", null, h("h3", null, "Rates each topic"),
          h("p", null, "An Elo-style rating per tag (dp, graphs, greedy and so on) moves up when you beat a problem and down when one beats you.")),
        h("div", null, h("h3", null, "Estimates your chances"),
          h("p", null, "A logistic-regression model trained on 200 public histories turns those ratings into a solve probability for every unsolved problem.")))));

  try {
    const users = await api.users();
    if (users.length) {
      recent.append(h("h2", null, "Recently synced"),
        h("ul", null, users.slice(0, 12).map((u) => h("li", null,
          h("a", { class: rankClass(u.rating), href: `/u/${encodeURIComponent(u.handle)}`,
            onclick: (e) => { e.preventDefault(); go(u.handle); } }, u.handle)))));
    }
  } catch { /* the list is optional */ }
}
