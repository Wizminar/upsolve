import { api } from "../api.js";
import { h, fillVar, rankOf, fmtDate, pct, status, dataTable } from "../ui.js";
import { lineChart, heatmap, calibration } from "../charts.js";
import { renderSlot } from "../plugin-host.js";

let selectedTag = null;
let showAllTopics = false;

function topicBars(topics, overall, onPick) {
  const lo = Math.min(overall, ...topics.map((t) => t.rating)) - 150;
  const hi = Math.max(overall, ...topics.map((t) => t.rating)) + 50;
  const w = (r) => `${Math.max(2, (r - lo) / (hi - lo) * 100)}%`;
  const shown = showAllTopics ? topics : topics.filter((t) => t.attempts >= 5 || t.focus || t.tag === selectedTag);
  const hidden = topics.length - shown.length;
  const list = h("ul", { class: "topic-bars", "aria-label": "Topic ratings, strongest first" });
  for (const t of shown) {
    const btn = h("button", {
        class: "topic-row", type: "button", "data-tag": t.tag, "aria-pressed": String(t.tag === selectedTag),
        "aria-label": `${t.tag}: rating ${t.rating}, ${t.rank}, from ${t.attempts} attempts, ${t.confidence} evidence${t.focus ? ", training focus" : ""}`,
        onclick: () => onPick(t.tag) },
      h("span", { class: "topic-name" }, t.focus ? h("mark", null, t.tag) : t.tag),
      h("span", { class: "topic-track", "aria-hidden": "true" },
        h("span", { class: "topic-bar", "data-confidence": t.confidence, "data-focus": t.focus || null, style: { width: w(t.rating) } }),
        h("span", { class: "topic-overall", style: { left: w(overall) } })),
      h("span", { class: "topic-num", "aria-hidden": "true" }, h("b", null, t.rating), h("span", null, `${t.attempts} attempts`)));
    list.append(h("li", null, btn));
  }
  list.addEventListener("keydown", (e) => {
    if (!["ArrowDown", "ArrowUp"].includes(e.key)) return;
    const btns = [...list.querySelectorAll("button")];
    const i = btns.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    btns[Math.min(btns.length - 1, Math.max(0, i + (e.key === "ArrowDown" ? 1 : -1)))].focus();
  });
  const more = topics.length > shown.length || showAllTopics
    ? h("button", { class: "linkish", type: "button", style: { margin: "8px 0 0 4px" },
        onclick: () => { showAllTopics = !showAllTopics; onPick(selectedTag, true); } },
        showAllTopics ? "Show only topics with 5+ attempts" : `Show ${hidden} more topics with fewer than 5 attempts`)
    : null;
  return h("div", null, list, more,
    h("ul", { class: "legend" },
      h("li", null, h("span", { class: "swatch", style: { background: "var(--blue)" } }), "Focus topic"),
      h("li", null, h("span", { class: "swatch swatch-hatch" }), "Fewer than 5 attempts"),
      h("li", null, h("span", { class: "swatch swatch-dash" }), `Overall rating ${overall}`)),
    dataTable("Topic ratings", ["Topic", "Rating", "Rank", "Attempts", "Solved", "Evidence"],
      topics.map((t) => [t.tag, t.rating, t.rank, t.attempts, pct(t.solve_rate || 0), t.confidence])));
}

async function renderInspect(box, ctx, topics, onFocusChange) {
  const t = topics.find((x) => x.tag === selectedTag);
  if (!t) { box.replaceChildren(); return; }
  box.replaceChildren(h("p", { class: "skeleton" }, `Loading ${t.tag}…`));
  const [hist, overall, attempts, training] = await Promise.all([
    api.topicHistory(ctx.handle, t.tag), api.topicHistory(ctx.handle, "__overall__"),
    api.attempts(ctx.handle, { limit: 8, tag: t.tag }), api.training(ctx.handle),
  ]);
  const isFocus = training.topics.includes(t.tag);
  const toggle = async () => {
    const topics_ = isFocus ? training.topics.filter((x) => x !== t.tag) : [...training.topics, t.tag];
    if (topics_.length > 2) return status(`You already train ${training.topics.join(" and ")}. Remove one first.`, "error");
    await api.setTraining(ctx.handle, { topics: topics_, weekly_target: training.weekly_target });
    status(isFocus ? `Removed ${t.tag} from your training focus.` : `Added ${t.tag} to your training focus.`);
    onFocusChange();
  };
  const from = hist.length ? hist[0].at : 0;
  box.replaceChildren(h("div", { class: "inspect" },
    h("h3", null, t.tag,
      h("button", { class: isFocus ? "btn btn-small" : "btn btn-ink btn-small", type: "button", onclick: toggle },
        isFocus ? "Remove focus" : "Focus on this")),
    h("dl", { class: "facts" },
      h("div", null, h("dt", null, "Rating"), h("dd", { class: `rk-${rankOf(t.rating).key}` }, t.rating)),
      h("div", null, h("dt", null, "vs overall"), h("dd", null, `${t.relative >= 0 ? "+" : ""}${t.relative}`)),
      h("div", null, h("dt", null, "Attempts"), h("dd", null, t.attempts)),
      h("div", null, h("dt", null, "Solved within 24 h"), h("dd", null, pct(t.solve_rate || 0))),
      h("div", null, h("dt", null, "Hardest solved"), h("dd", null, t.hardest_solved ?? "none"))),
    lineChart({
      title: `${t.tag} rating over time`,
      caption: `${t.tag} rating, one point per day you practised, against your overall rating.`,
      series: [
        { name: `${t.tag}`, points: hist.map((p) => ({ x: p.at, y: p.rating })) },
        { name: "Overall", dashed: true, points: overall.filter((p) => p.at >= from).map((p) => ({ x: p.at, y: p.rating })) },
      ],
      height: 220,
      tableRows: { headers: ["Date", "Rating"], rows: hist.map((p) => [fmtDate(p.at), p.rating]) },
    }),
    h("h4", { style: { marginTop: "28px", color: "var(--muted)", fontWeight: 500 } }, "Recent attempts"),
    h("ul", { class: "attempt-list" }, attempts.map((a) => h("li", null,
      h("span", { class: a.ever_solved ? "mark-ok" : "mark-no" }, a.ever_solved ? "✓" : "✗",
        h("span", { class: "visually-hidden" }, a.ever_solved ? " solved" : " not solved")),
      h("a", { href: `https://codeforces.com/problemset/problem/${a.contest_id}/${a.idx}`, target: "_blank", rel: "noopener" },
        `${a.problem_id} ${a.name || ""}`),
      h("span", null, a.rating ?? "unrated"))))));
}

function modelPanel(model, feedback) {
  const panel = h("section", { class: "panel span-all", "aria-labelledby": "h-model" },
    h("h2", { id: "h-model" }, "How accurate are the chances?"));
  if (model.source !== "model") {
    panel.append(h("p", null, "No trained model is loaded, so chances come from Elo ratings alone. Run scripts/train_model.py to train one."));
    return panel;
  }
  const m = model.metrics.model, e = model.metrics.elo_baseline;
  panel.append(
    h("p", { class: "panel-note" },
      `Trained on ${model.split.train_attempts.toLocaleString()} examples from ${model.split.users} public histories (attempts, plus contest problems people saw but never solved) ` +
      `and tested on the ${model.split.test_attempts.toLocaleString()} most recent ones, which it never saw. A chance means: if you try this problem, how likely you are to get it accepted within a day.`),
    h("div", { class: "grid-2" },
      calibration(m.calibration, "Each circle groups test attempts by predicted chance. Circles near the dashed diagonal mean the estimates are honest."),
      h("div", null,
        h("dl", { class: "stat-line" },
          h("div", null, h("dt", null, "AUC"), h("dd", null, m.auc.toFixed(3))),
          h("div", null, h("dt", null, "Brier score"), h("dd", null, m.brier.toFixed(3))),
          h("div", null, h("dt", null, "Log loss"), h("dd", null, m.log_loss.toFixed(3)))),
        h("p", null, `The Elo ratings alone score AUC ${e.auc.toFixed(3)} and Brier ${e.brier.toFixed(3)}; ` +
          `the trained model ${m.auc >= e.auc ? "improves on" : "does not beat"} that baseline.`),
        m.target_band.n ? h("p", null, `Of the test attempts it placed in the 50–70% zone, ${pct(m.target_band.observed_rate)} were actually solved (${m.target_band.n.toLocaleString()} attempts).`) : null,
        feedback.attempted
          ? h("p", null, `Your own record: you tried ${feedback.attempted} of the ${feedback.shown} problems Upsolve showed you and solved ${feedback.solved}. ` +
              `Average predicted chance ${pct(feedback.mean_predicted)}, actual ${pct(feedback.observed_rate)}.`)
          : h("p", null, `Upsolve has shown you ${feedback.shown} problems so far. Try some and sync again to see how the estimates hold up for you.`))));
  return panel;
}

export async function renderInsights(view, ctx) {
  view.replaceChildren(h("p", { class: "skeleton" }, "Loading insights…"));
  let topics, ratings, activity, model, feedback;
  try {
    [topics, ratings, activity, model, feedback] = await Promise.all([
      api.topics(ctx.handle), api.ratingHistory(ctx.handle), api.activity(ctx.handle),
      api.model(), api.feedback(ctx.handle)]);
  } catch (e) {
    view.replaceChildren(h("div", { class: "empty", role: "alert" }, h("p", null, e.message)));
    return;
  }
  const overall = ctx.profile.practice_rating;
  if (!topics.length) {
    view.replaceChildren(h("div", { class: "empty" }, h("h2", null, "No rated attempts yet"),
      h("p", null, "Solve a few rated problems on Codeforces, then choose Sync again.")));
    return;
  }
  if (!topics.some((t) => t.tag === selectedTag)) {
    const weak = topics.filter((t) => t.attempts >= 10).sort((a, b) => a.relative - b.relative)[0];
    selectedTag = (weak || topics[0]).tag;
  }

  const inspectBox = h("div", { "aria-live": "polite" });
  const rerender = () => renderInsights(view, ctx);
  const pick = (tag, rebuild = false) => {
    selectedTag = tag;
    if (rebuild) return rerender();
    view.querySelectorAll(".topic-row").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tag === tag)));
    renderInspect(inspectBox, ctx, topics, rerender);
  };

  const ratingPanel = h("section", { class: "panel", "aria-labelledby": "h-rating" },
    h("h2", { id: "h-rating" }, "Contest rating"),
    ratings.length
      ? lineChart({
          title: "Official contest rating history",
          caption: `${ratings.length} rated contests. Coloured bands are Codeforces ranks.`,
          series: [{ name: "Contest rating", points: ratings.map((r) => ({ x: r.at, y: r.new_rating, label: r.contest_name })) }],
          tableRows: { headers: ["Date", "Contest", "Rank", "Rating"],
            rows: ratings.slice().reverse().map((r) => [fmtDate(r.at), r.contest_name, r.rank, `${r.old_rating} → ${r.new_rating}`]) },
        })
      : h("p", { class: "empty" }, "No rated contests yet."));

  view.replaceChildren(
    h("div", { class: "view-head" }, h("p", { class: "lead" }, "A rating for each topic. Select one to see how it changed.")),
    h("div", { class: "grid-2" },
      h("section", { class: "panel", "aria-labelledby": "h-topics" },
        h("h2", { id: "h-topics" }, "Topics"),
        topicBars(topics, overall, pick)),
      h("section", { class: "panel", "aria-label": "Selected topic" }, inspectBox),
      ratingPanel,
      h("section", { class: "panel", "aria-labelledby": "h-activity" },
        h("h2", { id: "h-activity" }, "Activity"),
        heatmap(activity)),
      modelPanel(model, feedback)));
  renderInspect(inspectBox, ctx, topics, rerender);
  renderSlot("insights", view, { topics });
}
