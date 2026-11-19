"""Plugin discovery and per-plugin key-value storage.

A plugin is a folder inside `plugins/` containing `manifest.json` and an ES
module entry file. The web app imports the entry and calls its default export
with the Upsolve plugin host (see docs/PLUGINS.md).
"""

import json
import re
import time

from . import config, db

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
SLOTS = {"today", "insights", "plan", "page"}
REQUIRED = ("id", "name", "version", "entry")


def _validate(folder, data: dict) -> list[str]:
    errors = [f"missing '{k}'" for k in REQUIRED if k not in data]
    if "id" in data and (not ID_RE.match(str(data["id"])) or data["id"] != folder.name):
        errors.append("'id' must be lowercase letters/digits/dashes and match the folder name")
    if "entry" in data and (".." in data["entry"] or not (folder / data["entry"]).is_file()):
        errors.append("'entry' file not found")
    bad = [s for s in data.get("slots", []) if s not in SLOTS]
    if bad:
        errors.append(f"unknown slots {bad}; allowed: {sorted(SLOTS)}")
    return errors


def discover(conn) -> list[dict]:
    disabled = set(db.get_meta(conn, "plugins_disabled", []))
    out = []
    if not config.PLUGINS_DIR.exists():
        return out
    for folder in sorted(p for p in config.PLUGINS_DIR.iterdir() if p.is_dir()):
        mf = folder / "manifest.json"
        if not mf.exists():
            continue
        try:
            data = json.loads(mf.read_text())
        except ValueError as exc:
            out.append({"id": folder.name, "valid": False, "errors": [f"manifest.json: {exc}"], "enabled": False})
            continue
        errors = _validate(folder, data)
        out.append({
            "id": data.get("id", folder.name), "name": data.get("name"), "version": data.get("version"),
            "description": data.get("description", ""), "author": data.get("author", ""),
            "slots": data.get("slots", ["page"]),
            "entry_url": f"/plugin-files/{folder.name}/{data.get('entry', '')}",
            "valid": not errors, "errors": errors, "enabled": not errors and folder.name not in disabled,
        })
    return out


def set_enabled(conn, plugin_id: str, enabled: bool) -> None:
    disabled = set(db.get_meta(conn, "plugins_disabled", []))
    (disabled.discard if enabled else disabled.add)(plugin_id)
    db.set_meta(conn, "plugins_disabled", sorted(disabled))
    conn.commit()


def store_list(conn, plugin_id, scope) -> dict:
    rows = conn.execute("SELECT key, value FROM plugin_store WHERE plugin_id=? AND scope=? ORDER BY key",
                        (plugin_id, scope.lower())).fetchall()
    return {r["key"]: json.loads(r["value"]) for r in rows}


def store_get(conn, plugin_id, scope, key):
    row = conn.execute("SELECT value, updated_at FROM plugin_store WHERE plugin_id=? AND scope=? AND key=?",
                       (plugin_id, scope.lower(), key)).fetchone()
    return (json.loads(row["value"]), row["updated_at"]) if row else (None, None)


def store_put(conn, plugin_id, scope, key, value) -> int:
    raw = json.dumps(value)
    if len(raw) > 256_000:
        raise ValueError("Value too large (limit 256 KB)")
    now = int(time.time())
    conn.execute(
        """INSERT INTO plugin_store(plugin_id, scope, key, value, updated_at) VALUES(?,?,?,?,?)
           ON CONFLICT(plugin_id, scope, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (plugin_id, scope.lower(), key, raw, now),
    )
    conn.commit()
    return now


def store_delete(conn, plugin_id, scope, key) -> bool:
    cur = conn.execute("DELETE FROM plugin_store WHERE plugin_id=? AND scope=? AND key=?",
                       (plugin_id, scope.lower(), key))
    conn.commit()
    return cur.rowcount > 0
