import { api } from "../api.js";
import { h, status } from "../ui.js";
import { renderSlot } from "../plugin-host.js";

let refresh = 0;
let topicFilter = "";

async function addFocus(handle, tag, onDone) {
  const t = await api.training(handle);
  if (t.topics.includes(tag)) return status(`${tag} is already a focus topic.`);
  if (t.topics.length >= 2) {
    return status(`You already focus on ${t.topics.join(" and ")}. Remove one under Week first.`, "error");
  }
  await api.setTraining(handle, { topics: [...t.topics, tag], weekly_target: t.weekly_target });
  status(`Added ${tag} to your focus topics.`);
  onDone();
}

function item(p, focus, handle, onChange) {
  const bodyId = `why-${p.problem_id}`;
  const weak = p.reasons.find((x) => x.kind === "weak")?.text.match(/topic: ([^(]+) \(/)?.[1]?.trim();
  const trainTag = weak || p.tags.find((t) => !focus.includes(t));
  const body = h("div", { class: "item-body", id: bodyId, hidden: true },
    h("ul", { class: "reasons" }, p.reasons.map((x) => h("li", { "data-kind": x.kind }, x.text))),
    h("div", { class: "route-actions" },
      h("a", { class: "btn btn-ink btn-small", href: p.url, target: "_blank", rel: "noopener" }, "Open on Codeforces"),
      trainTag && !focus.includes(trainTag)
        ? h("button", { class: "btn btn-small", type: "button", onclick: () => addFocus(handle, trainTag, onChange) }, `Focus on ${trainTag}`)
        : null));
  const toggle = h("button", { class: "item-toggle", type: "button", "aria-expanded": "false", "aria-controls": bodyId,
    onclick: () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      toggle.textContent = open ? "Why this problem" : "Hide";
      body.hidden = open;
    } }, "Why this problem");

  return h("li", { class: "item" },
    h("div", { class: "item-top" },
      h("a", { class: "item-title", href: p.url, target: "_blank", rel: "noopener" }, p.name,
        h("span", { class: "visually-hidden" }, " (opens Codeforces)")),
      h("span", { class: "item-chance", "aria-label": `${Math.round(p.probability * 100)} percent chance` },
        `${Math.round(p.probability * 100)}%`)),
    h("div", { class: "item-meta" },
      h("span", null, p.problem_id),
      h("span", null, p.rating),
      h("span", null, p.tags.map((t, i) => [i ? ", " : "", focus.includes(t) ? h("span", { class: "is-focus" }, t) : t])),
      p.upsolve ? h("span", null, "tried before") : null),
    toggle, body);
}

export async function renderToday(view, ctx) {
  const { handle } = ctx;
  view.classList.add("view-narrow");
  view.replaceChildren(h("p", { class: "skeleton" }, "Loading…"));
  let recs, topics;
  try {
    [recs, topics] = await Promise.all([
      api.recommendations(handle, { count: 5, topic: topicFilter || undefined, refresh }),
      api.allTopics(),
    ]);
  } catch (e) {
    view.replaceChildren(h("div", { class: "empty", role: "alert" }, h("p", null, e.message)));
    return;
  }

  const select = h("select", { id: "topic-filter", "aria-label": "Topic", onchange: (e) => { topicFilter = e.target.value; renderToday(view, ctx); } },
    h("option", { value: "" }, "All topics"),
    topics.map((t) => h("option", { value: t.tag, selected: t.tag === topicFilter || null }, t.tag)));

  const head = h("div", { class: "view-head", style: { alignItems: "center" } },
    h("p", { class: "lead" }, recs.focus.length
      ? `Five problems for today, focused on ${recs.focus.join(" and ")}.`
      : "Five problems for today, each about a 50–70% chance for you."),
    h("div", { class: "controls" }, select,
      h("button", { class: "btn", type: "button", onclick: () => { refresh += 1; renderToday(view, ctx); } }, "Shuffle")));

  if (!recs.items.length) {
    view.replaceChildren(head, h("div", { class: "empty" },
      h("h2", null, "Nothing here"),
      h("p", null, topicFilter ? `No unsolved ${topicFilter} problem is near your level. Try another topic.`
        : "You've solved everything near your level. Sync again after your next contest.")));
    return;
  }

  const items = [...recs.items].sort((a, b) => a.rating - b.rating);
  view.replaceChildren(head,
    h("ol", { class: "list", "aria-label": "Today's problems, easiest first" },
      items.map((p) => item(p, recs.focus, handle, () => renderToday(view, ctx)))),
    h("p", { class: "zone-note" },
      `Problems rated ${recs.stretch_zone[0]}–${recs.stretch_zone[1]} are in your 50–70% range. Your practice rating is ${recs.practice_rating}.`,
      recs.source === "elo" ? " Chances use Elo ratings only." : ""));
  renderSlot("today", view, { recommendations: recs });
}
