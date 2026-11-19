import { api } from "../api.js";
import { h, status } from "../ui.js";
import { loadPlugins } from "../plugin-host.js";

export async function renderPlugins(view, ctx) {
  view.replaceChildren(h("p", { class: "skeleton" }, "Loading plugins…"));
  const list = await api.plugins();
  const items = list.map((p) => h("li", { class: "plugin-item" },
    h("div", null,
      h("h3", null, p.name || p.id, " ", h("small", null, p.version ? `v${p.version}` : "")),
      h("p", null, p.description),
      p.author ? h("p", null, `By ${p.author}. Appears in: ${p.slots.join(", ")}.`) : null,
      p.errors.length ? h("p", { class: "errors" }, `Can't load: ${p.errors.join("; ")}`) : null),
    h("label", { class: "switch" },
      h("input", { type: "checkbox", checked: p.enabled || null, disabled: !p.valid || null,
        onchange: async (e) => {
          await api.togglePlugin(p.id, e.target.checked);
          await loadPlugins();
          status(`${p.name} turned ${e.target.checked ? "on" : "off"}.`);
          ctx.refresh();
        } }),
      p.enabled ? "On" : "Off")));
  view.replaceChildren(
    h("div", { class: "view-head" }, h("div", null,
      h("h2", null, "Plugins"),
      h("p", null, "Plugins add panels and pages to Upsolve using its public API. Drop a folder into plugins/ and reload to install one."))),
    list.length ? h("ul", { class: "plugin-list" }, items)
      : h("div", { class: "empty" }, h("p", null, "No plugins installed.")),
    h("p", { class: "hint", style: { marginTop: "24px" } },
      "Building one? Read docs/PLUGINS.md and the ", h("a", { href: "/api/docs" }, "API reference"), "."));
}
