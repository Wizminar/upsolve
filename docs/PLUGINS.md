# Building an Upsolve plugin

Upsolve plugins run **inside the Upsolve web app**. A plugin adds a page (its own tab) or a
panel to the Today, Insights or Week plan views. It reads Upsolve's data and model output through
the public REST API and saves its own data in a per-plugin store. A plugin needs no server code
and no build step.

The complete working example is [`plugins/rival`](../plugins/rival). It compares two users' topic
ratings and uses the solve-probability model to find problems a friend solved that you are likely
to crack next.

## 1. Folder layout

```
plugins/
  your-plugin/          ← folder name = plugin id (lowercase letters, digits, dashes)
    manifest.json
    plugin.js           ← ES module entry
    (any other files)   ← served at /plugin-files/your-plugin/...
```

Restart the server or reload the page and the plugin appears under **Plugins**, switched on.

## 2. manifest.json

```json
{
  "id": "your-plugin",
  "name": "Contest Countdown",
  "version": "1.0.0",
  "description": "One sentence shown in the Plugins list.",
  "author": "Team name",
  "entry": "plugin.js",
  "slots": ["page"],
  "api_version": "1"
}
```

| Field | Required | Notes |
|---|---|---|
| `id` | yes | Must match the folder name. |
| `name`, `version` | yes | Shown in the UI. |
| `entry` | yes | Path to the ES module inside the folder. |
| `slots` | no | Informational list of where the plugin draws: `page`, `today`, `insights`, `plan`. |

`GET /api/v1/plugins` reports validation errors for any manifest that is wrong.

## 3. The entry module

The default export receives the **host** object:

```js
export default function register(host) {
  host.addPanel({
    slot: "insights",            // "page" (new tab), "today", "insights" or "plan"
    title: "Streak",
    async render(el, ctx) {      // el: your container (inside a shadow root), ctx.handle: current user
      const days = await host.api.activity(ctx.handle, 60);
      el.replaceChildren(host.ui.h("p", null, `${days.length} active days in the last 60.`));
    },
  });
}
```

`render` runs every time the view is shown. Each panel is rendered inside its own **shadow root**
that already loads Upsolve's stylesheet. Your CSS can't leak out, and you can reuse Upsolve's
classes (`btn`, `btn-ink`, `empty`, `data-table`, `route`, `taglist`, `legend`, …) and colour
tokens (`var(--ink)`, `var(--r-expert)`, `var(--highlighter)` …).

### Host reference

| Member | What it does |
|---|---|
| `host.apiVersion` | `"1"`. |
| `host.plugin` | `{id, name, version}` from your manifest. |
| `host.handle` | Handle currently open in the app, or `null`. |
| `host.api` | REST client. Helpers: `profile(h)`, `topics(h)`, `topicHistory(h, tag)`, `ratingHistory(h)`, `activity(h, days)`, `attempts(h, {limit, tag})`, `recommendations(h, {count, topic, refresh})`, `predict(h, problemId)`, `feedback(h)`, `training(h)`, `setTraining(h, body)`, `plan(h)`, `startSync(h)`, `syncStatus(h)`, `allTopics()`, `model()`. Raw access: `get(path)`, `put(path, body)`, `post(path, body)`, `del(path)` with paths relative to `/api/v1`. Errors throw `ApiError` with `.status`. |
| `host.store.get(key, {scope})` | Read a stored JSON value (`undefined` if missing). |
| `host.store.set(key, value, {scope})` | Save any JSON value (≤ 256 KB). |
| `host.store.list({scope})` / `remove(key, {scope})` | List or delete. |
| | `scope` defaults to the current handle; use `{scope: "_global"}` for data not tied to a user. |
| `host.on(event, fn)` | Events: `handle` (`{handle}`) when the user switches handle, `sync` (`{handle}`) after a sync finishes. Returns an unsubscribe function. |
| `host.addPanel({slot, title, render})` | Mount UI. |
| `host.notify(text)` | Show a message in the app's status bar (announced to screen readers). |
| `host.ui` | `h(tag, attrs, ...children)` and `s(...)` for HTML/SVG, `rankOf(rating)`, `fillVar(rating)`, `pct(p)`, `fmtDate(ts)`, `dataTable(caption, headers, rows)`, and `charts.lineChart / heatmap / calibration`. |

## 4. REST API

Interactive docs: **http://localhost:8000/api/docs** (Swagger UI) or `/api/redoc`.
The OpenAPI 3 document is served at `/api/v1/openapi.json` and exported to
[`docs/openapi.json`](openapi.json).

Typical flow:

```bash
curl -X POST localhost:8000/api/v1/users/tourist/sync          # 202, starts import
curl localhost:8000/api/v1/users/tourist/sync                  # poll until "status": "done"
curl localhost:8000/api/v1/users/tourist/topics
curl "localhost:8000/api/v1/users/tourist/recommendations?count=5&topic=dp"
curl localhost:8000/api/v1/users/tourist/predict/1520A
curl -X PUT localhost:8000/api/v1/plugins/rival/store/tourist/rival \
     -H 'Content-Type: application/json' -d '{"value": "jiangly"}'
```

Every user endpoint returns **404** with a message until that handle has been synced.

## 5. Accessibility checklist for plugins

Upsolve is graded on accessibility, and your panel is part of it:

- Give charts `role="img"` and an `aria-label`, and offer `host.ui.dataTable(...)` with the numbers.
- Never use colour alone: pair rank colours with the rating number or name, as the core app does.
- Use real `<button>`s and `<a>`s so keyboard users can reach everything.
- Write empty and error states that say what to do next.

## 6. Working against Upsolve during development

```bash
git clone <repo> && cd upsolve
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --reload-dir app --reload-dir plugins
```

Put your folder in `plugins/` and reload the browser. Static files are served with
`Cache-Control: no-cache`, so edits appear on reload. If you prefer to keep your plugin in another
folder, set `UPSOLVE_PLUGINS_DIR` (and copy `plugins/rival` there to keep the example).
