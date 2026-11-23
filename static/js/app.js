// Upsolve web app: routing, sync flow, and the profile shell around the views.
import { api } from "./api.js";
import { h, status, rankClass, ago } from "./ui.js";
import { loadPlugins, setHandle, emit, pagePanels, renderPanel } from "./plugin-host.js";
import { renderLanding } from "./views/landing.js";
import { renderToday } from "./views/today.js";
import { renderInsights } from "./views/insights.js";
import { renderPlan } from "./views/plan.js";
import { renderPlugins } from "./views/plugins.js";

const main = document.getElementById("main");
const VIEWS = [
  { id: "today", label: "Today", render: renderToday },
  { id: "insights", label: "Insights", render: renderInsights },
  { id: "plan", label: "Week", render: renderPlan },
  { id: "plugins", label: "Plugins", render: renderPlugins },
];

const state = { handle: null, view: "today", profile: null };

function parseLocation() {
  const m = location.pathname.match(/^\/u\/([^/]+)(?:\/([^/]+))?/);
  return m ? { handle: decodeURIComponent(m[1]), view: m[2] || "today" } : { handle: null, view: null };
}

export function go(handle, view = "today", replace = false) {
  const url = handle ? `/u/${encodeURIComponent(handle)}${view && view !== "today" ? `/${view}` : ""}` : "/";
  history[replace ? "replaceState" : "pushState"](null, "", url);
  route();
}

async function route() {
  const { handle, view } = parseLocation();
  document.getElementById("text-link").href = handle ? `/text/${encodeURIComponent(handle)}` : "/";
  document.body.classList.toggle("is-landing", !handle);
  if (!handle) {
    state.handle = null;
    document.title = "Upsolve";
    renderLanding(main, { go });
    return;
  }
  const changed = !state.handle || state.handle.toLowerCase() !== handle.toLowerCase();
  state.view = view;
  if (changed || !state.profile) {
    state.handle = handle;
    state.profile = null;
    main.replaceChildren(h("p", { class: "skeleton" }, `Loading ${handle}…`));
    try {
      state.profile = await api.profile(handle);
    } catch (e) {
      if (e.status === 404) return syncThenRender(handle);
      main.replaceChildren(errorBox(e));
      return;
    }
    if (state.profile.handle !== handle) return go(state.profile.handle, view, true);
    setHandle(state.profile.handle);
  }
  renderShell();
}

function errorBox(e) {
  return h("div", { class: "empty", role: "alert" },
    h("h2", null, "Couldn't load this page"),
    h("p", null, e.message),
    h("button", { class: "btn", type: "button", onclick: () => route() }, "Try again"));
}

// ---------------------------------------------------------------- sync

let polling = null;
export async function syncThenRender(handle) {
  clearTimeout(polling);
  main.replaceChildren(h("div", { class: "empty" },
    h("h2", null, `Importing ${handle}`),
    h("p", null, "Upsolve is fetching the profile, every submission and the contest history from Codeforces. " +
      "Codeforces allows one request every two seconds, so a first import takes up to a minute.")));
  try {
    await api.startSync(handle);
  } catch (e) {
    status(e.message, "error");
    return;
  }
  const poll = async () => {
    let job;
    try { job = await api.syncStatus(handle); } catch (e) { status(e.message, "error"); return; }
    if (job.status === "done") {
      status(`Synced ${job.handle}: ${job.new_submissions} new submissions.`);
      state.profile = null;
      emit("sync", { handle: job.handle });
      if (state.handle && state.handle.toLowerCase() === job.handle.toLowerCase() && job.handle !== state.handle)
        return go(job.handle, state.view, true);
      return route();
    }
    if (job.status === "failed") {
      status(job.message || "Sync failed.", "error", { label: "Try again", run: () => syncThenRender(handle) });
      if (!state.profile) main.replaceChildren(h("div", { class: "empty", role: "alert" },
        h("h2", null, "Import stopped"), h("p", null, job.message || ""),
        h("button", { class: "btn btn-ink", type: "button", onclick: () => syncThenRender(handle) }, "Try again")));
      return;
    }
    status(`Syncing ${handle}: ${job.stage || job.status}…`, "busy");
    polling = setTimeout(poll, 1200);
  };
  poll();
}

// ---------------------------------------------------------------- shell

function renderShell() {
  const p = state.profile;
  document.title = `${p.handle} – Upsolve`;
  const views = VIEWS.concat(pagePanels().map((pp) => ({ id: `p-${pp.plugin.id}`, label: pp.title, panel: pp })));
  if (!views.some((v) => v.id === state.view)) state.view = "today";

  const tabs = h("div", { class: "tabs", role: "tablist", "aria-label": "Views" },
    views.map((v) => h("button", {
      role: "tab", type: "button", id: `tab-${v.id}`, "aria-controls": "view",
      "aria-selected": String(v.id === state.view), tabindex: v.id === state.view ? "0" : "-1",
      onclick: () => go(p.handle, v.id),
    }, v.label)));
  tabs.addEventListener("keydown", (e) => {
    const btns = [...tabs.querySelectorAll("[role=tab]")];
    const i = btns.indexOf(document.activeElement);
    if (i < 0) return;
    let j = null;
    if (e.key === "ArrowRight") j = (i + 1) % btns.length;
    if (e.key === "ArrowLeft") j = (i - 1 + btns.length) % btns.length;
    if (e.key === "Home") j = 0;
    if (e.key === "End") j = btns.length - 1;
    if (j !== null) { e.preventDefault(); btns[j].focus(); btns[j].click(); }
  });

  const rank = p.rank ? p.rank[0].toUpperCase() + p.rank.slice(1) : "Unrated";
  const who = h("section", { class: "who", "aria-label": "Profile" },
    h("h1", { class: rankClass(p.rating) }, p.handle),
    h("p", { class: "who-line" },
      h("span", null, `${rank} `, h("b", null, p.rating ?? "–"), p.max_rating ? ` (max ${p.max_rating})` : ""),
      h("span", null, "Practice rating ", h("b", null, p.practice_rating)),
      h("span", null, h("b", null, p.problems_solved), " solved"),
      h("span", null, `Synced ${ago(p.last_synced_at)}. `,
        h("button", { class: "linkish", type: "button", onclick: () => syncThenRender(p.handle) }, "Sync now"))));

  const viewEl = h("div", { class: "view", id: "view", role: "tabpanel", "aria-labelledby": `tab-${state.view}` });
  main.replaceChildren(who, tabs, viewEl);
  const v = views.find((x) => x.id === state.view);
  const ctx = { handle: p.handle, profile: p, go: (view) => go(p.handle, view), refresh: () => { state.profile = null; route(); } };
  if (v.panel) viewEl.append(renderPanel(v.panel, ctx));
  else v.render(viewEl, ctx);
}

// ---------------------------------------------------------------- boot

document.getElementById("handle-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const handle = e.target.handle.value.trim();
  if (!handle) return;
  e.target.handle.value = "";
  state.profile = null;
  state.handle = null;
  go(handle);
});
window.addEventListener("popstate", route);

const themeBtn = document.getElementById("theme-toggle");
function syncThemeButton() {
  if (!themeBtn) return;
  const dark = document.documentElement.dataset.theme !== "light";
  themeBtn.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
}
themeBtn?.addEventListener("click", () => {
  const root = document.documentElement;
  const next = root.dataset.theme === "light" ? "dark" : "light";
  root.classList.add("theme-fading");
  root.dataset.theme = next;
  setTimeout(() => root.classList.remove("theme-fading"), 650);
  try { localStorage.setItem("upsolve-theme", next); } catch { /* private mode: theme just won't persist */ }
  syncThemeButton();
});
syncThemeButton();

loadPlugins().finally(route);
