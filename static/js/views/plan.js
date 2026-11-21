import { api } from "../api.js";
import { h, s, fillVar, pct, status } from "../ui.js";
import { renderSlot } from "../plugin-host.js";

// Progress drawn as logbook tally marks: four strokes and a strike-through per five.
function tally(done, target) {
  const groups = Math.ceil(Math.max(done, target) / 5);
  const W = groups * 46, H = 44;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true" });
  for (let i = 0; i < Math.max(done, target); i++) {
    const g = Math.floor(i / 5), k = i % 5, x0 = g * 46 + 4;
    const filled = i < done;
    const attrs = { stroke: filled ? "var(--ink)" : "var(--rule)", "stroke-width": 3.5, "stroke-linecap": "round" };
    if (k < 4) svg.append(s("line", { ...attrs, x1: x0 + k * 9, y1: 6, x2: x0 + k * 9 + 1, y2: 38 }));
    else svg.append(s("line", { ...attrs, x1: x0 - 4, y1: 32, x2: x0 + 32, y2: 12 }));
  }
  return svg;
}

function settingsForm(ctx, training, allTopics, myTopics, onSaved) {
  const mine = new Map(myTopics.map((t) => [t.tag, t]));
  const chosen = new Set(training.topics);
  const boxes = [];
  const sync = () => boxes.forEach((b) => { b.disabled = !b.checked && chosen.size >= 2; });
  const pick = h("div", { class: "topic-pick" }, allTopics.map((t) => {
    const cb = h("input", { type: "checkbox", value: t.tag, checked: chosen.has(t.tag) || null,
      onchange: (e) => { e.target.checked ? chosen.add(t.tag) : chosen.delete(t.tag); sync(); } });
    boxes.push(cb);
    const m = mine.get(t.tag);
    return h("label", null, cb, h("span", null, t.tag, m ? ` (${m.rating})` : ""));
  }));
  sync();
  const target = h("input", { type: "number", id: "weekly-target", min: 1, max: 30, value: training.weekly_target, required: true });
  return h("form", { class: "settings", "aria-labelledby": "h-settings", onsubmit: async (e) => {
      e.preventDefault();
      try {
        await api.setTraining(ctx.handle, { topics: [...chosen], weekly_target: Number(target.value) });
        status("Training settings saved.");
        onSaved();
      } catch (err) { status(err.message, "error"); }
    } },
    h("h2", { id: "h-settings" }, "Training settings"),
    h("div", { class: "settings-grid" },
      h("fieldset", null,
        h("legend", null, "Focus topics"),
        pick,
        h("p", { class: "help" }, "Choose up to two. Your current rating is shown next to topics you've tried.")),
      h("div", null,
        h("fieldset", null,
          h("legend", null, h("label", { for: "weekly-target" }, "Weekly solve target")),
          target,
          h("p", { class: "help" }, "Accepted problems in your focus topics count toward this (all topics if none are chosen).")),
        h("button", { class: "btn btn-ink", type: "submit" }, "Save settings"))));
}

export async function renderPlan(view, ctx) {
  view.replaceChildren(h("p", { class: "skeleton" }, "Planning your week…"));
  let plan, training, allTopics, myTopics;
  try {
    [plan, training, allTopics, myTopics] = await Promise.all([
      api.plan(ctx.handle), api.training(ctx.handle), api.allTopics(), api.topics(ctx.handle)]);
  } catch (e) {
    view.replaceChildren(h("div", { class: "empty", role: "alert" }, h("p", null, e.message)));
    return;
  }
  const todayKey = new Date().toLocaleDateString("sv-SE");
  const start = new Date(plan.week_start + "T00:00:00");
  const left = plan.weekly_target - plan.progress;

  const week = h("ol", { class: "week", "aria-label": "This week, Monday to Sunday" }, plan.days.map((d) => {
    const isToday = d.day === todayKey;
    const date = new Date(d.day + "T00:00:00");
    return h("li", { class: isToday ? "day is-today" : "day", "aria-current": isToday ? "date" : null },
      h("h3", null, h("span", null, d.weekday), h("span", null, date.getDate())),
      d.planned.map((p) => p.problem_id
        ? h("a", { class: p.done ? "slot is-done" : "slot", href: p.url, target: "_blank", rel: "noopener",
            style: { "--band": fillVar(p.rating) } },
            h("b", null, p.problem_id), p.name, h("br"),
            h("span", null, `${p.rating}, ${pct(p.probability)} chance`),
            p.done ? h("span", { class: "visually-hidden" }, " (solved)") : null)
        : h("p", { class: "slot" }, "No match found for this slot.")),
      d.solved.filter((x) => !d.planned.some((p) => p.problem_id === x.problem_id)).map((x) =>
        h("div", { class: "slot slot-solved", style: { "--band": fillVar(x.rating) } },
          h("b", null, `✓ ${x.problem_id}`), x.name || "",
          h("br"), h("span", null, x.counts ? "solved, counts" : "solved, other topic"))));
  }));

  view.replaceChildren(
    h("div", { class: "plan-top" },
      h("div", null,
        h("div", { class: "view-head" }, h("div", null,
          h("h2", null, `Week of ${start.toLocaleDateString(undefined, { day: "numeric", month: "long" })}`),
          h("p", null, plan.focus.length
            ? `Training ${plan.focus.join(" and ")}. Problems start near a 70% chance on Monday and stretch toward 50% by the weekend.`
            : "No focus topics set, so the plan mixes topics near your level."))),
        h("div", { class: "tally" },
          tally(plan.progress, plan.weekly_target),
          h("p", null, `${plan.progress} of ${plan.weekly_target} solved`,
            h("small", null, left > 0 ? `${left} to go this week. Progress updates when you sync.` : "Target reached. Anything more is a bonus."))),
        week),
      settingsForm(ctx, training, allTopics, myTopics, () => renderPlan(view, ctx))));
  renderSlot("plan", view, { plan });
}
