import { api } from "../api.js";
import { h, pct, rankOf, fillVar, needsDarkText, status } from "../ui.js";
import { ladder } from "../charts.js";
import { renderSlot } from "../plugin-host.js";

let refresh = 0;
let topicFilter = "";

function meter(p) {
  return h("div", { class: "meter", "aria-hidden": "true" },
    h("div", { class: "fill", style: { width: `${Math.round(p * 100)}%` } }),
    h("div", { class: "zone" }));
}

async function addFocus(handle, tag, onDone) {
  const t = await api.training(handle);
  if (t.topics.includes(tag)) return status(`${tag} is already a training focus.`);
  if (t.topics.length >= 2) {
    return status(`You already train two topics (${t.topics.join(" and ")}). Remove one in Week plan first.`, "error");
  }
  await api.setTraining(handle, { topics: [...t.topics, tag], weekly_target: t.weekly_target });
  status(`Added ${tag} to your training focus.`);
  onDone();
}

function routeCard(item, focus, handle, onChange) {
  const r = rankOf(item.rating);
  const weakest = item.reasons.find((x) => x.kind === "weak")?.text.match(/topic: ([^(]+) \(/)?.[1]?.trim()
    || item.tags.find((t) => !focus.includes(t));
  return h("li", { class: "route", id: `route-${item.problem_id}`, "data-pid": item.problem_id,
      style: { "--band": fillVar(item.rating) }, "data-dark-text": needsDarkText(item.rating) || null },
    h("div", { class: "route-grade" },
      h("b", null, item.rating),
      h("span", null, r.name)),
    h("div", { class: "route-body" },
      h("div", { class: "route-title" },
        h("h3", null, h("a", { href: item.url, target: "_blank", rel: "noopener" },
          h("span", { class: "route-id" }, item.problem_id), item.name,
          h("span", { class: "visually-hidden" }, " (opens Codeforces in a new tab)"))),
        h("div", { class: "chance" },
          meter(item.probability),
          h("strong", null, pct(item.probability)),
          h("span", { class: "visually-hidden" }, "estimated chance of solving"))),
      h("ul", { class: "taglist", "aria-label": "Topics" },
        item.tags.map((t) => h("li", { class: focus.includes(t) ? "is-focus" : null }, t,
          focus.includes(t) ? h("span", { class: "visually-hidden" }, " (training focus)") : null))),
      h("ul", { class: "reasons", "aria-label": "Why this problem" },
        item.reasons.map((x) => h("li", { "data-kind": x.kind }, x.text))),
      h("div", { class: "route-actions" },
        h("a", { class: "btn btn-ink btn-small", href: item.url, target: "_blank", rel: "noopener" }, "Open on Codeforces"),
        weakest && !focus.includes(weakest)
          ? h("button", { class: "btn btn-small", type: "button", onclick: () => addFocus(handle, weakest, onChange) },
              `Train ${weakest}`)
          : null)));
}

export async function renderToday(view, ctx) {
  const { handle } = ctx;
  view.replaceChildren(h("p", { class: "skeleton" }, "Choosing problems…"));
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

  const select = h("select", { id: "topic-filter", onchange: (e) => { topicFilter = e.target.value; renderToday(view, ctx); } },
    h("option", { value: "" }, "Any topic"),
    topics.map((t) => h("option", { value: t.tag, selected: t.tag === topicFilter || null }, t.tag)));

  const focusLine = recs.focus.length
    ? `Training focus: ${recs.focus.join(" and ")}. Problems in those topics are ranked higher.`
    : "No training focus yet. Choose up to two topics in Week plan, or use a Train button below.";

  const head = h("div", { class: "view-head" },
    h("div", null,
      h("h2", null, "Today's problems"),
      h("p", null, `Picked for a ${Math.round(recs.target[0] * 100)}–${Math.round(recs.target[1] * 100)}% chance at your practice rating of ${recs.practice_rating}. ${focusLine}`),
      recs.source === "elo" ? h("p", { class: "hint" }, "Estimates come from Elo ratings alone because no trained model is loaded.") : null),
    h("div", { class: "controls" },
      h("label", { for: "topic-filter" }, "Topic"), select,
      h("button", { class: "btn", type: "button", onclick: () => { refresh += 1; renderToday(view, ctx); } }, "Show a different set")));

  if (!recs.items.length) {
    view.replaceChildren(head, h("div", { class: "empty" },
      h("h2", null, "No problems match"),
      h("p", null, topicFilter
        ? `Nothing unsolved in ${topicFilter} is near your level. Choose another topic or Any topic.`
        : "You've solved everything near your level. Impressive. Sync again after your next contest.")));
    return;
  }

  const highlight = (pid, on) => {
    view.querySelectorAll(".pin").forEach((p) => p.classList.toggle("is-active", on && p.dataset.pid === pid));
  };
  const list = h("ol", { class: "routes", "aria-label": "Recommended problems" },
    recs.items.map((it) => routeCard(it, recs.focus, handle, () => renderToday(view, ctx))));
  list.querySelectorAll(".route").forEach((card) => {
    const pid = card.dataset.pid;
    card.addEventListener("mouseenter", () => highlight(pid, true));
    card.addEventListener("mouseleave", () => highlight(pid, false));
    card.addEventListener("focusin", () => highlight(pid, true));
    card.addEventListener("focusout", () => highlight(pid, false));
  });

  const lad = ladder({
    you: recs.practice_rating, zone: recs.stretch_zone, items: recs.items,
    onPin: (pid) => document.getElementById(`route-${pid}`)?.querySelector("a")?.focus(),
  });

  view.replaceChildren(head, h("div", { class: "today" }, lad, list));
  renderSlot("today", view, { recommendations: recs });
}
