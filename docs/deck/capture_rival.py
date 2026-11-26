"""Capture the Rival plugin in full (comparison chart and suggested problems) for the cross-dev deck."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "shots"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="dark")
    ctx.add_init_script("try{localStorage.setItem('upsolve-theme','dark')}catch(e){}")
    page = ctx.new_page()
    page.goto("http://localhost:8000/")
    page.fill(".landing-form input", "Mann_Chauhan")
    page.click(".landing-form button")
    page.wait_for_selector(".list .item")
    page.click(".tabs button >> nth=4")
    page.wait_for_timeout(9000)
    # full-page shot of the plugin, then the bottom half (problems list)
    page.screenshot(path=str(OUT / "rival_full.png"), full_page=True)
    h = page.evaluate("document.documentElement.scrollHeight")
    print("page height", h)
    b.close()
