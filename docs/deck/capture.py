"""Drive the real Upsolve site in Chrome and capture 2x screenshots plus element boxes.

Each step saves shots/<name>.png (viewport, 2x) and records element rectangles (CSS px)
in shots/meta.json, used by the deck and by the video's zoom/cursor keyframes.
Usage: .venv/bin/python docs/deck/capture.py [base_url]
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
HANDLE = "Mann_Chauhan"
OUT = Path(__file__).parent / "shots"
OUT.mkdir(exist_ok=True)
W, H = 1440, 900
meta = {"viewport": [W, H], "scale": 2, "steps": {}}


def box(page, selector, nth=0):
    loc = page.locator(selector).nth(nth)
    b = loc.bounding_box()
    return [round(b["x"]), round(b["y"]), round(b["width"]), round(b["height"])] if b else None


def snap(page, name, **boxes):
    page.screenshot(path=str(OUT / f"{name}.png"))
    meta["steps"][name] = {k: v for k, v in boxes.items()}
    print("captured", name, {k: v for k, v in boxes.items()})


def settle(page, ms=900):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=2, color_scheme="dark")
    ctx.add_init_script("try{localStorage.setItem('upsolve-theme','dark')}catch(e){}")
    page = ctx.new_page()

    # Landing and typing a handle
    page.goto(f"{BASE}/")
    settle(page)
    inp = ".landing-form input"
    snap(page, "landing", input=box(page, inp), button=box(page, ".landing-form button"))
    for i, prefix in enumerate(["Ma", "Mann_", "Mann_Cha", HANDLE]):
        page.fill(inp, prefix)
        page.wait_for_timeout(120)
        snap(page, f"type{i}", input=box(page, inp), button=box(page, ".landing-form button"))

    # Today
    page.click(".landing-form button")
    page.wait_for_selector(".list .item")
    settle(page, 1200)
    snap(page, "today",
         first=box(page, ".list .item"), chance=box(page, ".item-chance"),
         toggle=box(page, ".item-toggle"), list=box(page, ".list"), who=box(page, ".who"),
         tab_insights=box(page, ".tabs button", 1), tab_week=box(page, ".tabs button", 2),
         tab_rival=box(page, ".tabs button", 4), theme=box(page, "#theme-toggle"))
    page.click(".item-toggle >> nth=0")
    page.wait_for_timeout(500)
    snap(page, "today_why", first=box(page, ".list .item"), body=box(page, ".item-body"),
         tab_insights=box(page, ".tabs button", 1))

    # Insights
    page.click(".tabs button >> nth=1")
    page.wait_for_selector(".topic-row")
    settle(page, 1200)
    snap(page, "insights", topics=box(page, ".topic-bars"), inspect=box(page, ".inspect"),
         chart=box(page, ".inspect figure.chart"), graphs=box(page, ".topic-row[data-tag='graphs']"))
    page.click(".topic-row[data-tag='graphs']")
    page.wait_for_timeout(2500)
    snap(page, "insights_graphs", inspect=box(page, ".inspect"), chart=box(page, ".inspect figure.chart"),
         facts=box(page, ".inspect .facts"))
    page.evaluate("window.scrollTo(0, document.querySelector('#h-rating').getBoundingClientRect().top + scrollY - 120)")
    page.wait_for_timeout(600)
    snap(page, "insights_charts", rating=box(page, "#h-rating"), activity=box(page, "#h-activity"))
    page.evaluate("window.scrollTo(0, document.querySelector('#h-model').getBoundingClientRect().top + scrollY - 60)")
    page.wait_for_timeout(600)
    snap(page, "insights_model", model=box(page, "#h-model"), calib=box(page, ".span-all figure.chart"),
         stats=box(page, ".stat-line"))
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)

    # Week
    page.click(".tabs button >> nth=2")
    page.wait_for_selector(".week")
    settle(page, 1000)
    snap(page, "week", progress=box(page, ".progress"), week=box(page, ".week"))

    # Plugins list and the Rival plugin
    page.click(".tabs button >> nth=3")
    page.wait_for_selector(".plugin-item")
    settle(page, 600)
    snap(page, "plugins", list=box(page, ".plugin-list"))
    page.click(".tabs button >> nth=4")
    page.wait_for_timeout(5000)
    snap(page, "rival", frame=box(page, ".plugin-frame"))

    # Theme toggle: dark then light
    page.click(".tabs button >> nth=0")
    page.wait_for_selector(".list .item")
    settle(page, 1000)
    snap(page, "theme_dark", theme=box(page, "#theme-toggle"))
    page.click("#theme-toggle")
    page.wait_for_timeout(1200)
    snap(page, "theme_light", theme=box(page, "#theme-toggle"))
    page.click("#theme-toggle")
    page.wait_for_timeout(800)

    # API docs
    page.goto(f"{BASE}/api/docs")
    settle(page, 1500)
    snap(page, "apidocs")

    browser.close()

(OUT / "meta.json").write_text(json.dumps(meta, indent=1))
print("done", len(meta["steps"]), "steps")
