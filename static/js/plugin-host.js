// The plugin host: loads plugins listed by /api/v1/plugins and gives each one a sandboxed
// set of capabilities (API client, per-plugin storage, events, UI slots). See docs/PLUGINS.md.
import { api } from "./api.js";
import { h, s, rankOf, fillVar, pct, fmtDate, dataTable, status } from "./ui.js";
import * as charts from "./charts.js";

export const HOST_API_VERSION = "1";
const bus = new EventTarget();
const panels = { today: [], insights: [], plan: [], page: [] };
let loaded = [];
let current = { handle: null };

export function setHandle(handle) {
  current.handle = handle;
  emit("handle", { handle });
}
export function emit(name, detail) {
  bus.dispatchEvent(new CustomEvent(name, { detail }));
}

function makeHost(manifest) {
  const scopeOf = (opts) => (opts && opts.scope) || current.handle || "_global";
  const base = (scope) => `/plugins/${manifest.id}/store/${encodeURIComponent(scope)}`;
  return Object.freeze({
    apiVersion: HOST_API_VERSION,
    plugin: { id: manifest.id, name: manifest.name, version: manifest.version },
    api,
    get handle() { return current.handle; },
    store: {
      async get(key, opts) {
        try { return (await api.get(`${base(scopeOf(opts))}/${encodeURIComponent(key)}`)).value; }
        catch (e) { if (e.status === 404) return undefined; throw e; }
      },
      set: (key, value, opts) => api.put(`${base(scopeOf(opts))}/${encodeURIComponent(key)}`, { value }),
      list: (opts) => api.get(base(scopeOf(opts))),
      remove: (key, opts) => api.del(`${base(scopeOf(opts))}/${encodeURIComponent(key)}`),
    },
    on(event, fn) {
      const wrapped = (e) => fn(e.detail);
      bus.addEventListener(event, wrapped);
      return () => bus.removeEventListener(event, wrapped);
    },
    addPanel({ slot = "page", title, render }) {
      if (!panels[slot]) throw new Error(`Unknown slot '${slot}'. Use one of: ${Object.keys(panels).join(", ")}`);
      panels[slot].push({ plugin: manifest, title: title || manifest.name, render });
    },
    notify: (text) => status(text),
    ui: { h, s, rankOf, fillVar, pct, fmtDate, dataTable, charts },
  });
}

export async function loadPlugins() {
  Object.values(panels).forEach((list) => list.splice(0));
  let list = [];
  try { list = await api.plugins(); } catch { return []; }
  loaded = [];
  for (const m of list.filter((p) => p.enabled)) {
    try {
      const mod = await import(m.entry_url);
      if (typeof mod.default !== "function") throw new Error("entry module has no default export");
      await mod.default(makeHost(m));
      loaded.push({ ...m, error: null });
    } catch (e) {
      console.error(`Plugin ${m.id} failed to load`, e);
      loaded.push({ ...m, error: String(e.message || e) });
    }
  }
  return list;
}

export const pagePanels = () => panels.page;

/** Render every panel registered for `slot` into `container`. Each panel gets its own shadow root. */
export function renderSlot(slot, container, extra = {}) {
  const list = panels[slot] || [];
  if (!list.length) return;
  const wrap = h("section", { class: "plugin-slot", "aria-label": "Plugins" });
  for (const p of list) wrap.append(renderPanel(p, extra));
  container.append(wrap);
}

export function renderPanel(p, extra = {}) {
  const host = h("div");
  const shadow = host.attachShadow({ mode: "open" });
  shadow.append(h("link", { rel: "stylesheet", href: "/static/css/app.css" }));
  const body = h("div", { class: "plugin-body" });
  shadow.append(body);
  const frame = h("section", { class: "plugin-frame", "aria-label": p.title },
    h("header", null, h("h2", null, p.title), h("small", null, `Plugin: ${p.plugin.name} ${p.plugin.version}`)),
    host);
  Promise.resolve()
    .then(() => p.render(body, { handle: current.handle, ...extra }))
    .catch((e) => {
      body.replaceChildren(h("p", { class: "empty" }, `This plugin stopped with an error: ${e.message || e}`));
    });
  return frame;
}
