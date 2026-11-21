import { api } from "../api.js";
import { h, rankClass } from "../ui.js";

const EXAMPLE = "tourist";

// What a day's list looks like, for a solver around 1500.
const SAMPLE = [
  { name: "Maximum Median", id: "1201C", rating: 1400, tags: "binary search, greedy", chance: 68 },
  { name: "Special Permutation", id: "1352G", rating: 1600, tags: "constructive algorithms", chance: 62 },
  { name: "Spy-string", id: "1360F", rating: 1700, tags: "brute force, strings", chance: 55 },
];

export async function renderLanding(main, { go }) {
  const input = h("input", { name: "handle", "aria-label": "Codeforces handle", placeholder: "Codeforces handle",
    autocomplete: "off", spellcheck: "false", required: true, pattern: "[A-Za-z0-9_.\\-]{3,24}" });
  const recent = h("div", { class: "recent" });

  main.replaceChildren(
    h("section", { class: "landing" },
      h("h1", null, "Practice problems that fit you."),
      h("p", { class: "lede" },
        "Upsolve looks at your Codeforces history and picks unsolved problems you have about a 60% chance of solving. Not too easy, not hopeless."),
      h("form", { class: "landing-form", onsubmit: (e) => { e.preventDefault(); go(input.value.trim()); } },
        input, h("button", { class: "btn btn-ink", type: "submit" }, "Continue")),
      h("p", { class: "hint" }, "No account needed. Or try ",
        h("a", { href: `/u/${EXAMPLE}`, onclick: (e) => { e.preventDefault(); go(EXAMPLE); } }, EXAMPLE), "."),

      h("section", { class: "sample", "aria-labelledby": "h-sample" },
        h("h2", { id: "h-sample" }, "Example"),
        h("ul", { class: "list" }, SAMPLE.map((p) => h("li", { class: "item" },
          h("div", { class: "item-top" }, h("span", { class: "item-title" }, p.name), h("span", { class: "item-chance" }, `${p.chance}%`)),
          h("div", { class: "item-meta" }, h("span", null, p.id), h("span", null, p.rating), h("span", null, p.tags)))))),

      recent,

      h("section", { class: "facts-row", "aria-label": "How it works" },
        h("div", null, h("h3", null, "Your history"),
          h("p", null, "Every problem you've submitted to, grouped into attempts. Accepted within a day counts as solved.")),
        h("div", null, h("h3", null, "A rating per topic"),
          h("p", null, "dp, graphs, greedy and the rest each get their own rating, so weak spots show up.")),
        h("div", null, h("h3", null, "A chance for every problem"),
          h("p", null, "A model trained on 200 public histories estimates how likely you are to solve each one.")))));

  try {
    const users = await api.users();
    if (users.length) {
      recent.append(h("h2", null, "Recently opened"),
        h("ul", null, users.slice(0, 12).map((u) => h("li", null,
          h("a", { class: rankClass(u.rating), href: `/u/${encodeURIComponent(u.handle)}`,
            onclick: (e) => { e.preventDefault(); go(u.handle); } }, u.handle)))));
    }
  } catch { /* optional */ }
}
