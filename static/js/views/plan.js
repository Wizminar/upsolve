import { api } from "../api.js";
import { h, pct, status } from "../ui.js";
import { renderSlot } from "../plugin-host.js";

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
    return h("label", null, cb, h("span", null, t.tag, m ? h("small", null, m.rating) : null));
  }));
  sync();
  const target = h("input", { type: "number", id: "weekly-target", min: 1, max: 30, value: training.weekly_target, required: true });
  return h("form", { class: "settings", "aria-labelledby": "h-settings", onsubmit: async (e) => {
      e.preventDefault();
      try {
        await api.setTraining(ctx.handle, { topics: [...chosen], weekly_target: Number(target.value) });
        status("Saved.");
        onSaved();
      } catch (err) { status(err.message, "error"); }
    } },
    h("h2", { id: "h-settings" }, "Settings"),
    h("div", { class: "settings-grid" },
      h("fieldset", null,
        h("legend", null, "Focus topics"),
        pick,
        h("p", { class: "help" }, "Up to two. Your rating is shown next to topics you've tried.")),
      h("div", { class: "settings-actions" },
        h("label", { for: "weekly-target" }, "Problems per week"), target,
        h("button", { class: "btn btn-ink", type: "submit" }, "Save"))));
}

export async function renderPlan(view, ctx) {
  view.replaceChildren(h("p", { class: "skeleton" }, "Loading…"));
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
  const share = Math.min(100, Math.round(plan.progress / plan.weekly_target * 100));

  const week = h("ol", { class: "week", "aria-label": "This week, Monday to Sunday" }, plan.days.map((d) => {
    const isToday = d.day === todayKey;
    const extra = d.solved.filter((x) => !d.planned.some((p) => p.problem_id === x.problem_id));
    const rows = [
      ...d.planned.filter((p) => p.problem_id).map((p) =>
        h("a", { class: p.done ? "slot is-done" : "slot", href: p.url, target: "_blank", rel: "noopener" },
          h("b", null, p.name), h("span", null, `${p.rating}, ${pct(p.probability)}`),
          p.done ? h("span", { class: "visually-hidden" }, " (solved)") : null)),
      ...extra.map((x) => h("div", { class: "slot slot-solved" },
        h("b", null, x.name || x.problem_id), h("span", null, x.counts ? "solved" : "solved, other topic"))),
    ];
    return h("li", { class: isToday ? "day is-today" : "day", "aria-current": isToday ? "date" : null },
      h("h3", null, isToday ? "Today" : d.weekday),
      h("div", { class: "day-items" }, rows.length ? rows : h("span", { class: "day-empty" }, "Rest")));
  }));

  view.replaceChildren(
    h("div", { class: "plan-top" },
      h("div", null,
        h("div", { class: "view-head" }, h("div", null,
          h("h2", null, `Week of ${start.toLocaleDateString(undefined, { day: "numeric", month: "long" })}`),
          h("p", null, plan.focus.length
            ? `Focused on ${plan.focus.join(" and ")}. Easier early in the week, harder later.`
            : "No focus topics, so the week mixes topics near your level."))),
        h("div", { class: "progress" },
          h("div", { class: "progress-bar", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": plan.weekly_target,
            "aria-valuenow": plan.progress, "aria-label": "Solved this week" }, h("span", { style: { width: `${share}%` } })),
          h("p", null, h("b", null, `${plan.progress} of ${plan.weekly_target}`), " solved. ",
            left > 0 ? "Sync after solving to update." : "Target reached.")),
        week),
      settingsForm(ctx, training, allTopics, myTopics, () => renderPlan(view, ctx))));
  renderSlot("plan", view, { plan });
}
