"""Prepare deck assets: framed screenshot crops, a QR code, and chart data from the real model."""

import json
import sys
import time
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import elo  # noqa: E402
from app.model import Predictor  # noqa: E402

HERE = Path(__file__).parent
SHOTS, ASSETS = HERE / "shots", HERE / "assets"
ASSETS.mkdir(exist_ok=True)

BG = (14, 14, 16)
BORDER = (42, 42, 46)


def framed(name, box, out, radius=28):
    """Crop a 2x screenshot (box in CSS px) and give it rounded corners and a 2px border."""
    x0, y0, x1, y1 = (v * 2 for v in box)
    im = Image.open(SHOTS / f"{name}.png").convert("RGB").crop((x0, y0, x1, y1))
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius, fill=255)
    rgba = im.convert("RGBA")
    rgba.putalpha(mask)
    ImageDraw.Draw(rgba).rounded_rectangle((1, 1, w - 2, h - 2), radius, outline=BORDER + (255,), width=3)
    rgba.save(ASSETS / f"{out}.png")
    return [w, h]


sizes = {
    "hero": framed("today", (180, 64, 1260, 900), "hero"),
    "today_why": framed("today_why", (100, 0, 1000, 760), "today_why"),
    "insights": framed("insights_graphs", (180, 350, 1260, 900), "insights"),
    "charts": framed("insights_charts", (180, 90, 1260, 430), "charts"),
    "week": framed("week", (180, 312, 960, 860), "week"),
    "model": framed("insights_model", (180, 40, 1300, 760), "model"),
    "plugins": framed("plugins", (180, 230, 1260, 600), "plugins"),
    "light": framed("theme_light", (180, 64, 1260, 700), "light"),
    "rival_chart": framed("rival_full", (180, 300, 1260, 1370), "rival_chart"),
    "rival_reach": framed("rival_full", (180, 1375, 1260, 1810), "rival_reach"),
    "rival_head": framed("rival_full", (180, 300, 1260, 480), "rival_head"),
}

qr = qrcode.QRCode(border=1, box_size=20)
qr.add_data("https://upsolve.mohitupawar.com")
qr.make(fit=True)
qr.make_image(fill_color=(242, 242, 244), back_color=BG).save(ASSETS / "qr.png")

# Solve chance against problem rating for a real synced user, from the trained model.
from app import db  # noqa: E402
with db.session() as conn:
    state = elo.state_for(conn, "Mann_Chauhan")
pred = Predictor.get()
ratings = list(range(1000, 2801, 100))
probs = pred.predict_many([state.features(r, [], int(time.time()), 1) for r in ratings])
art = pred.artifact
data = {
    "sizes": sizes,
    "curve": {"ratings": ratings, "chance": [round(float(p) * 100, 1) for p in probs]},
    "calibration": art["metrics"]["model"]["calibration"],
    "metrics": {k: {m: art["metrics"][k][m] for m in ("auc", "brier", "log_loss")} for k in ("model", "elo_baseline")},
    "band": art["metrics"]["model"]["target_band"],
    "split": art["split"],
}
(ASSETS / "data.json").write_text(json.dumps(data, indent=1))
print(json.dumps({"sizes": sizes, "curve": data["curve"]}, indent=0)[:900])
