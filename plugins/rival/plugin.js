// Example Upsolve plugin. It uses only the public plugin host:
//   host.api    – the REST client (/api/v1)
//   host.store  – per-plugin storage, scoped to the current handle
//   host.ui     – DOM and chart helpers
//   host.addPanel – mounts UI in a slot ("page" adds a tab)

export default function register(host) {
  const { h, s, fillVar, pct } = host.ui;

  function diverging(mine, theirs, me, rival) {
    const rows = mine
      .filter((t) => theirs.has(t.tag) && t.attempts >= 3 && theirs.get(t.tag).attempts >= 3)
      .map((t) => ({ tag: t.tag, a: t.rating, b: theirs.get(t.tag).rating, diff: t.rating - theirs.get(t.tag).rating }))
      .sort((x, y) => y.diff - x.diff);
    if (!rows.length) return h("p", { class: "empty" }, "You have no topics in common with at least 3 attempts each.");
    const max = Math.max(100, ...rows.map((r) => Math.abs(r.diff)));
    const W = 640, row = 24, mid = 320, H = rows.length * row + 30;
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
      "aria-label": `Topic rating difference between ${me} and ${rival}. ` +
        rows.map((r) => `${r.tag}: ${r.diff >= 0 ? "+" : ""}${r.diff}`).join(", ") });
    svg.append(s("text", { x: mid + 8, y: 12, "font-size": 12, fill: "var(--ink)", "font-weight": 700 }, `${me} ahead`));
    svg.append(s("text", { x: mid - 8, y: 12, "font-size": 12, fill: "var(--ink)", "font-weight": 700, "text-anchor": "end" }, `${rival} ahead`));
    rows.forEach((r, i) => {
      const y = 24 + i * row, w = Math.abs(r.diff) / max * 200;
      const ahead = r.diff >= 0;
      svg.append(
        s("rect", { x: ahead ? mid : mid - w, y: y + 4, width: Math.max(w, 1), height: row - 8,
          fill: ahead ? "var(--ink)" : "none", stroke: "var(--ink)", "stroke-width": 1.5,
          "stroke-dasharray": ahead ? null : "4 2" }),
        s("text", { x: ahead ? mid - 8 : mid + 8, y: y + 16, "font-size": 12, fill: "var(--ink)",
          "text-anchor": ahead ? "end" : "start" }, r.tag),
        s("text", { x: ahead ? mid + w + 6 : mid - w - 6, y: y + 16, "font-size": 12, fill: "var(--graphite)",
          "text-anchor": ahead ? "start" : "end" }, `${ahead ? "+" : "−"}${Math.abs(r.diff)}`));
    });
    svg.append(s("line", { x1: mid, x2: mid, y1: 18, y2: H, stroke: "var(--graphite)" }));
    return h("figure", { class: "chart" }, svg,
      h("figcaption", null, h("span", null, `Solid bars: topics where ${me} rates higher. Dashed outlines: topics where ${rival} rates higher.`)),
      host.ui.dataTable("Topic ratings side by side", ["Topic", me, rival, "Difference"],
        rows.map((r) => [r.tag, r.a, r.b, r.diff])));
  }

  async function waitForSync(handle, onStage) {
    for (;;) {
      const job = await host.api.syncStatus(handle);
      if (job.status === "done") return job;
      if (job.status === "failed") throw new Error(job.message);
      onStage(job.stage || job.status);
      await new Promise((r) => setTimeout(r, 1200));
    }
  }

  async function render(el) {
    const me = host.handle;
    const rival = await host.store.get("rival");
    const input = h("input", { id: "rival-handle", value: rival || "", placeholder: "friend's handle", required: true,
      style: { font: "inherit", padding: "8px 10px", border: "1.5px solid var(--ink)", borderRadius: "3px" } });
    const out = h("div", { "aria-live": "polite" });
    el.replaceChildren(
      h("p", null, "Pick a friend to train against. Upsolve compares your topic ratings and finds problems they solved that sit in your stretch zone."),
      h("form", { class: "controls", onsubmit: async (e) => {
          e.preventDefault();
          await host.store.set("rival", input.value.trim());
          render(el);
        } },
        h("label", { for: "rival-handle" }, "Rival"), input,
        h("button", { class: "btn btn-ink", type: "submit" }, rival ? "Change rival" : "Compare")),
      out);
    if (!rival) return;

    out.replaceChildren(h("p", { class: "skeleton" }, `Loading ${rival}…`));
    let theirTopics;
    try {
      theirTopics = await host.api.topics(rival);
    } catch (e) {
      if (e.status !== 404) throw e;
      await host.api.startSync(rival);
      await waitForSync(rival, (st) => out.replaceChildren(h("p", { class: "skeleton" }, `Importing ${rival}: ${st}…`)));
      theirTopics = await host.api.topics(rival);
    }
    const mine = await host.api.topics(me);
    const theirs = new Map(theirTopics.map((t) => [t.tag, t]));

    // Problems the rival solved that you haven't, scored by Upsolve's model for *you*.
    const [theirAttempts, myAttempts] = await Promise.all([
      host.api.attempts(rival, { limit: 300 }), host.api.attempts(me, { limit: 500 })]);
    const mineSolved = new Set(myAttempts.filter((a) => a.ever_solved).map((a) => a.problem_id));
    const pool = theirAttempts.filter((a) => a.ever_solved && a.rating && !mineSolved.has(a.problem_id)).slice(0, 25);
    const scored = (await Promise.all(pool.map((a) => host.api.predict(me, a.problem_id).catch(() => null))))
      .filter(Boolean)
      .sort((a, b) => Math.abs(a.probability - 0.6) - Math.abs(b.probability - 0.6))
      .slice(0, 5);

    await host.store.set("last_compare", { rival, at: Date.now(), common: mine.filter((t) => theirs.has(t.tag)).length });

    out.replaceChildren(
      h("h3", null, `${me} vs ${rival}`),
      diverging(mine, theirs, me, rival),
      h("h3", { style: { marginTop: "28px" } }, `Solved by ${rival}, within your reach`),
      scored.length
        ? h("ol", { class: "routes" }, scored.map((p) => h("li", { class: "route", style: { "--band": fillVar(p.rating) } },
            h("div", { class: "route-grade" }, h("b", null, p.rating)),
            h("div", { class: "route-body" },
              h("div", { class: "route-title" },
                h("h3", null, h("a", { href: `https://codeforces.com/problemset/problem/${p.problem_id.match(/^\d+/)[0]}/${p.problem_id.replace(/^\d+/, "")}`,
                  target: "_blank", rel: "noopener" }, h("span", { class: "route-id" }, p.problem_id), p.name)),
                h("div", { class: "chance" }, h("strong", null, pct(p.probability)))),
              h("ul", { class: "taglist" }, p.tags.map((t) => h("li", null, t)))))))
        : h("p", { class: "empty" }, `${rival} has no recent solves that you haven't solved too.`));
  }

  host.addPanel({ slot: "page", title: "Rival", render });
}
