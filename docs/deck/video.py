"""Render a launch-style demo video of Upsolve from the captured 2x screenshots.

A camera glides (eased zoom and pan) over a framed browser window, a cursor moves and
clicks, UI states cross-fade or scroll, and short captions appear. Frames are drawn with
Pillow and piped to ffmpeg. Usage: .venv/bin/python docs/deck/video.py [out.mp4]
"""

import json
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
SHOTS = HERE / "shots"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "Upsolve_demo.mp4"
META = json.loads((SHOTS / "meta.json").read_text())["steps"]

FPS = 30
OW, OH = 1920, 1080              # output
CW, CH = 3840, 2160              # internal canvas (2x)
BG = (14, 14, 16)
INK = (242, 242, 244)
MUTED = (160, 160, 168)
FAINT = (118, 118, 126)
LINE = (42, 42, 46)
BLUE = (140, 156, 255)

# Browser window geometry on the canvas
CONT_W, CONT_H = 2816, 1760      # screenshot area (2880x1800 shots are scaled slightly)
BAR = 80
WX = (CW - CONT_W) // 2
WY = 70
CX0, CY0 = WX, WY + BAR          # content origin
K = CONT_W / 1440                # canvas px per CSS px
RADIUS = 36

FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
def font(size, medium=False):
    return ImageFont.truetype(FONT, size, index=10 if medium else 0)


# ------------------------------------------------------------------ helpers

def ease(p):  # ease-in-out cubic
    p = max(0.0, min(1.0, p))
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def lerp(a, b, p):
    return a + (b - a) * p


def css(x, y):
    return CX0 + x * K, CY0 + y * K


def centre(box):
    x, y, w, h = box
    return x + w / 2, y + h / 2


def fit(box, pad=1.25, zmax=2.4):
    """Camera (css centre, zoom) that frames a CSS-px box."""
    x, y, w, h = box
    z = min(CW / (w * K * pad), CH / (h * K * pad), zmax)
    return (x + w / 2, y + h / 2, max(1.0, z))


FULL = ((CW / 2 - CX0) / K, (CH / 2 - CY0) / K, 1.0)


# ------------------------------------------------------------------ assets

def window_template():
    im = Image.new("RGB", (CW, CH), BG)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((WX - 2, WY - 2, WX + CONT_W + 2, WY + BAR + CONT_H + 2), RADIUS + 2, fill=LINE)
    d.rounded_rectangle((WX, WY, WX + CONT_W, WY + BAR + CONT_H), RADIUS, fill=(22, 22, 25))
    for i in range(3):
        cx = WX + 46 + i * 40
        d.ellipse((cx - 12, WY + 28, cx + 12, WY + 52), fill=(58, 58, 64))
    f = font(30)
    url = "upsolve.mohitupawar.com"
    tw = d.textlength(url, font=f)
    pill_w = tw + 120
    d.rounded_rectangle((CW / 2 - pill_w / 2, WY + 16, CW / 2 + pill_w / 2, WY + 64), 24, fill=(32, 32, 36))
    d.text((CW / 2 - tw / 2, WY + 22), url, font=f, fill=MUTED)
    return im


TEMPLATE = window_template()
_mask = Image.new("L", (CONT_W, CONT_H), 255)
ImageDraw.Draw(_mask).rounded_rectangle((0, -RADIUS, CONT_W - 1, CONT_H - 1), RADIUS, fill=255)
_corner = Image.new("L", (CONT_W, CONT_H), 0)
ImageDraw.Draw(_corner).rounded_rectangle((0, -RADIUS * 2, CONT_W - 1, CONT_H - 1), RADIUS, fill=255)
CONTENT_MASK = _corner


@lru_cache(maxsize=24)
def content(name):
    return Image.open(SHOTS / f"{name}.png").convert("RGB").resize((CONT_W, CONT_H), Image.LANCZOS)


CHEVRON = Image.open(HERE / "assets" / "chevron.png").convert("RGBA")


# ------------------------------------------------------------------ timeline
# Part 1 (to ~16 s) shows the basic functioning. Part 2 explains each course component:
# a chapter card (flow + count-up stats), then the camera zooms into the real screens.
# States: (start, name, transition, duration). transition: cut | fade | scroll | scrollup
STATES = [
    (0.0, "landing", "cut", 0),
    (5.75, "type0", "fade", 0.06), (6.15, "type1", "fade", 0.06), (6.55, "type2", "fade", 0.06), (6.95, "type3", "fade", 0.06),
    (8.0, "today", "fade", 0.35),
    (12.15, "today_why", "fade", 0.3),
    (20.0, "today", "cut", 0),                      # ETL (hidden under card when it changes)
    (30.0, "today_why", "cut", 0),                  # AI/ML
    (39.4, "insights_model", "fade", 0.4),
    (46.0, "insights", "cut", 0),                   # VIZ
    (52.0, "insights_graphs", "fade", 0.3),
    (56.0, "insights_charts", "scroll", 0.8),
    (63.0, "week", "cut", 0),                       # APP
    (69.4, "theme_dark", "fade", 0.3),
    (70.65, "theme_light", "fade", 0.65),
    (75.5, "apidocs", "cut", 0),                    # DEV
    (81.9, "plugins", "fade", 0.4),
    (85.4, "rival", "fade", 0.35),
]

M = META
CAM = [  # (start, end, (css_x, css_y, zoom))
    (4.4, 5.3, fit([200, 280, 440, 120], 1.2, 2.6)),
    (7.9, 8.7, FULL),
    (9.3, 10.3, fit([208, 370, 720, 118], 1.15, 2.4)),
    (12.2, 13.1, fit(M["today_why"]["first"], 1.12, 2.2)),
    (15.5, 16.3, FULL),
    # ETL
    (24.4, 25.2, fit(M["today"]["who"], 1.1, 2.2)),
    (27.2, 27.9, FULL),
    # AI/ML
    (33.2, 34.0, fit([208, 370, 720, 100], 1.1, 2.6)),
    (36.0, 36.8, fit(M["today_why"]["body"], 1.1, 2.2)),
    (38.8, 39.4, FULL),
    (40.0, 40.8, fit([200, 190, 1040, 540], 1.08, 1.6)),
    (43.3, 43.9, FULL),
    # VIZ
    (49.0, 49.8, fit([200, 360, 500, 470], 1.1, 2.0)),
    (52.1, 53.0, fit([752, 358, 480, 400], 1.1, 2.0)),
    (55.2, 55.8, FULL),
    (57.0, 57.8, fit([200, 100, 1040, 330], 1.06, 1.8)),
    (60.2, 60.8, FULL),
    # APP
    (65.6, 66.4, fit([208, 370, 720, 450], 1.12, 1.9)),
    (68.6, 69.2, FULL),
    (69.9, 70.5, fit([1060, 0, 220, 90], 1.0, 1.8)),
    (71.8, 72.6, FULL),
    # DEV
    (78.2, 79.0, fit([30, 290, 1390, 210], 1.05, 2.0)),
    (81.0, 81.6, FULL),
    (82.4, 83.2, fit([208, 300, 720, 250], 1.1, 2.0)),
    (84.4, 85.0, FULL),
    (85.9, 86.7, fit([200, 300, 1040, 560], 1.05, 1.5)),
    (88.8, 89.4, FULL),
]

# Cursor: (start, end, (css_x, css_y)); visible only inside CURSOR_ON intervals
CURSOR_ON = [(3.9, 16.2), (50.6, 53.2), (68.9, 71.7), (84.2, 86.3)]
CURSOR = [
    (3.9, 3.9, (1180, 820)),
    (4.2, 5.0, centre(M["landing"]["input"])),
    (7.15, 7.6, centre(M["landing"]["button"])),
    (10.6, 11.7, centre(M["today"]["toggle"])),
    (13.6, 14.6, (1100, 760)),
    (50.6, 50.6, (900, 760)),
    (51.0, 51.8, centre(M["insights"]["graphs"])),
    (52.3, 52.9, (1150, 820)),
    (68.9, 68.9, (900, 600)),
    (69.3, 70.4, centre(M["today"]["theme"])),
    (70.9, 71.5, (1110, 520)),
    (84.2, 84.2, (900, 600)),
    (84.4, 85.1, centre(M["today"]["tab_rival"])),
    (85.5, 86.1, (1100, 760)),
]
CLICKS = [5.1, 7.7, 11.85, 51.9, 70.6, 85.25]

CAPTIONS = [
    (4.4, 7.8, "Enter any Codeforces handle"),
    (9.0, 11.9, "Five problems a day, at about a 60% chance"),
    (12.6, 15.6, "Each one comes with its reasons"),
    (24.6, 27.4, "Your full history, imported and cleaned automatically"),
    (33.4, 35.9, "A live prediction for every unsolved problem"),
    (36.2, 38.8, "Reasons come from the model's own features"),
    (40.2, 43.4, "Tested on 36,449 attempts it never saw"),
    (49.2, 51.7, "A rating for every topic"),
    (52.4, 55.2, "Each topic's history against your overall rating"),
    (57.2, 60.3, "Contest rating and a year of practice"),
    (65.8, 68.6, "A weekly plan, easier early and harder later"),
    (70.8, 72.8, "Dark or light, and fully keyboard accessible"),
    (78.4, 81.0, "A documented REST API with 21 endpoints"),
    (82.6, 84.4, "Plugins load right inside the app"),
    (86.0, 89.0, "Rival, built by our cross-dev team"),
]

# Chapter cards: (start, end, spec). The window shrinks into a card and grows back out of it.
CARDS = [
    (16.9, 19.8, dict(label="Under the hood", title="Five components", sub="From raw Codeforces data to a coach in your browser.",
                      flow=["ETL", "AI/ML", "VIZ", "APP", "DEV"])),
    (19.8, 23.6, dict(label="1   ETL", title="Clean data, straight from Codeforces",
                      flow=["Codeforces API", "Cleaned into attempts", "SQLite"],
                      stats=[("11,526", "problems"), ("200", "training users"), ("182,242", "training examples")])),
    (28.6, 32.4, dict(label="2   AI/ML", title="Predicting your chance",
                      flow=["Elo rating per topic", "Logistic regression", "Chance of solving"],
                      stats=[("0.947", "AUC, Elo alone 0.907"), ("68%", "solved in the 50–70% zone"), ("11", "features")])),
    (44.8, 48.2, dict(label="3   VIZ", title="Charts drawn by hand", sub="Every chart is our own SVG, with a data table behind it.",
                      chips=["Topic ratings", "Topic history", "Rating graph", "Activity heatmap"])),
    (61.6, 64.8, dict(label="4   APP", title="A web app anyone can use", sub="No sign-up. Live at upsolve.mohitupawar.com.",
                      chips=["Today", "Insights", "Week", "Plugins"])),
    (74.0, 77.4, dict(label="5   DEV", title="Open to other teams", sub="A documented REST API, and plugins that run inside Upsolve.",
                      stats=[("21", "API endpoints"), ("1", "cross-dev plugin"), ("28", "automated tests")])),
]
CARD_IN, CARD_OUT = 0.6, 0.8     # window -> card, card -> window

INTRO_END = 3.4
WINDOW_IN = (3.0, 3.8)
WINDOW_OUT = (89.8, 90.6)
OUTRO_START = 90.4
DURATION = 96.0


# ------------------------------------------------------------------ frame parts

def content_at(t):
    cur = STATES[0]
    prev = None
    for st in STATES:
        if st[0] <= t:
            prev, cur = cur, st
    start, name, kind, dur = cur
    if kind == "cut" or prev is None or dur == 0 or t >= start + dur:
        return content(name)
    p = ease((t - start) / dur)
    a, b = content(prev[1]), content(name)
    if kind == "fade":
        return Image.blend(a, b, p)
    out = Image.new("RGB", (CONT_W, CONT_H), BG)
    off = int(CONT_H * p)
    if kind == "scroll":
        out.paste(a, (0, -off)); out.paste(b, (0, CONT_H - off))
    else:
        out.paste(a, (0, off)); out.paste(b, (0, off - CONT_H))
    return out


def canvas_at(t):
    im = TEMPLATE.copy()
    im.paste(content_at(t), (CX0, CY0), CONTENT_MASK)
    return im


def camera_at(t):
    cam = FULL
    for (s, e, target) in CAM:
        if t >= e:
            cam = target
        elif t >= s:
            p = ease((t - s) / (e - s))
            return tuple(lerp(a, b, p) for a, b in zip(cam, target))
        else:
            break
    return cam


def cursor_at(t):
    pos = CURSOR[0][2]
    for (s, e, target) in CURSOR:
        if t >= e:
            pos = target
        elif t >= s:
            p = ease((t - s) / max(e - s, 1e-6))
            # slight arc for a hand-moved feel
            mx, my = lerp(pos[0], target[0], p), lerp(pos[1], target[1], p)
            arc = math.sin(p * math.pi) * min(60, abs(target[0] - pos[0]) * 0.08)
            return (mx, my - arc)
        else:
            break
    return pos


def project(cam, X, Y):
    """Canvas coords -> output coords under camera."""
    x, y, z = cam
    cx, cy = css(x, y)
    vw, vh = CW / z, CH / z
    return (X - (cx - vw / 2)) * OW / vw, (Y - (cy - vh / 2)) * OH / vh


def render_camera(canvas, cam):
    x, y, z = cam
    cx, cy = css(x, y)
    vw, vh = CW / z, CH / z
    left = min(max(cx - vw / 2, 0), CW - vw)
    top = min(max(cy - vh / 2, 0), CH - vh)
    return canvas.resize((OW, OH), Image.BICUBIC, box=(left, top, left + vw, top + vh))


def clamp_cam(cam):
    x, y, z = cam
    cx, cy = css(x, y)
    vw, vh = CW / z, CH / z
    cx = min(max(cx, vw / 2), CW - vw / 2)
    cy = min(max(cy, vh / 2), CH - vh / 2)
    return ((cx - CX0) / K, (cy - CY0) / K, z)


ARROW = [(0, 0), (0, 23), (5.5, 18), (9.5, 27), (13, 25.5), (9, 17), (16.5, 17)]


def draw_cursor(img, x, y, t):
    pressed = any(0 <= t - c < 0.18 for c in CLICKS)
    s = 1.55 * (0.88 if pressed else 1.0)
    d = ImageDraw.Draw(img, "RGBA")
    for c in CLICKS:
        dt = t - c
        if 0 <= dt < 0.5:
            r = 10 + 46 * ease(dt / 0.5)
            a = int(170 * (1 - dt / 0.5))
            d.ellipse((x - r, y - r, x + r, y + r), outline=BLUE + (a,), width=4)
    pts = [(x + px * s, y + py * s) for px, py in ARROW]
    shadow = [(px + 2, py + 3) for px, py in pts]
    d.polygon(shadow, fill=(0, 0, 0, 90))
    d.polygon(pts, fill=(255, 255, 255, 255), outline=(10, 10, 12, 255))
    d.line(pts + [pts[0]], fill=(10, 10, 12, 255), width=2)


CAP_FONT = font(36, medium=True)


def draw_caption(img, t):
    for (s, e, txt) in CAPTIONS:
        if s <= t <= e:
            a = min(1, (t - s) / 0.3, (e - t) / 0.3)
            d = ImageDraw.Draw(img, "RGBA")
            tw = d.textlength(txt, font=CAP_FONT)
            w, h = tw + 64, 72
            x0, y0 = (OW - w) / 2, OH - 110 + (1 - a) * 12
            d.rounded_rectangle((x0, y0, x0 + w, y0 + h), 36, fill=(14, 14, 16, int(225 * a)), outline=LINE + (int(255 * a),), width=2)
            d.text((x0 + 32, y0 + 16), txt, font=CAP_FONT, fill=INK + (int(255 * a),))


def card(t, lines, t0):
    """Centred title card with staggered fade-up entrances, measured from t0."""
    img = Image.new("RGB", (OW, OH), BG)
    total_h = 96 + 40 + sum(l[1] * 1.25 for l in lines)
    y = (OH - total_h) / 2
    def stagger(i):
        return ease((t - t0 - 0.18 * i) / 0.6)
    p = stagger(0)
    if p > 0:
        ch = CHEVRON.resize((96, 96), Image.LANCZOS)
        ch.putalpha(ch.getchannel("A").point(lambda v: int(v * p)))
        img.paste(ch, (int((OW - 96) / 2), int(y + (1 - p) * 20)), ch)
    y += 96 + 40
    d = ImageDraw.Draw(img, "RGBA")
    for i, (txt, size, medium, color) in enumerate(lines, start=1):
        p = stagger(i)
        f = font(size, medium)
        tw = d.textlength(txt, font=f)
        if p > 0:
            d.text(((OW - tw) / 2, y + (1 - p) * 18), txt, font=f, fill=color + (int(255 * p),))
        y += size * 1.25
    return img


INTRO = [("Upsolve", 128, True, INK), ("Practice problems that fit you.", 44, False, MUTED)]
OUTRO = [("upsolve.mohitupawar.com", 76, True, INK), ("Try it with any Codeforces handle.", 38, False, MUTED),
         ("The Syndicate, CS698B", 30, False, FAINT)]


def count_text(value, p):
    """Count a stat like '182,242', '0.947' or '68%' up from zero."""
    num = value.replace(",", "").rstrip("%")
    try:
        v = float(num)
    except ValueError:
        return value
    dec = len(num.split(".")[1]) if "." in num else 0
    cur = v * p
    txt = f"{cur:,.{dec}f}" if "," in value else f"{cur:.{dec}f}"
    return txt + ("%" if value.endswith("%") else "")


def chapter_card(t, t0, t1, spec):
    img = Image.new("RGB", (OW, OH), BG)
    d = ImageDraw.Draw(img, "RGBA")
    st = lambda i, dur=0.55: ease((t - t0 - 0.12 - 0.14 * i) / dur)
    f_label, f_title, f_sub = font(34, True), font(84, True), font(38)
    f_node, f_val, f_cap = font(32, True), font(88, True), font(28)
    blocks = 150 + (60 if spec.get("sub") else 0)
    if spec.get("flow") or spec.get("chips"):
        blocks += 150
    if spec.get("stats"):
        blocks += 210
    y = (OH - blocks) / 2 - 10

    def centred(txt, f, yy, color, p):
        if p <= 0:
            return
        tw = d.textlength(txt, font=f)
        d.text(((OW - tw) / 2, yy + (1 - p) * 18), txt, font=f, fill=color + (int(255 * p),))

    centred(spec["label"], f_label, y, BLUE, st(0)); y += 58
    centred(spec["title"], f_title, y, INK, st(1)); y += 112
    i = 2
    if spec.get("sub"):
        centred(spec["sub"], f_sub, y, MUTED, st(i)); y += 66; i += 1
    items = spec.get("flow") or spec.get("chips")
    if items:
        y += 34
        arrows = bool(spec.get("flow"))
        gap = 84 if arrows else 28
        widths = [d.textlength(s, font=f_node) + 72 for s in items]
        total = sum(widths) + gap * (len(items) - 1)
        x = (OW - total) / 2
        boxes = []
        for k, (s, w) in enumerate(zip(items, widths)):
            p = st(i + k * 0.6)
            boxes.append((x, w))
            if p > 0:
                yy = y + (1 - p) * 16
                d.rounded_rectangle((x, yy, x + w, yy + 76), 18, fill=(24, 24, 28, int(255 * p)), outline=LINE + (int(255 * p),), width=3)
                tw = d.textlength(s, font=f_node)
                d.text((x + (w - tw) / 2, yy + 19), s, font=f_node, fill=INK + (int(255 * p),))
            x += w + gap
        if arrows:
            for k in range(len(items) - 1):
                p = st(i + (k + 1) * 0.6)
                if p <= 0:
                    continue
                ax0 = boxes[k][0] + boxes[k][1] + 14
                ax1 = boxes[k + 1][0] - 14
                ym = y + 38
                d.line((ax0, ym, lerp(ax0, ax1, p), ym), fill=FAINT + (255,), width=3)
                if p >= 1:
                    d.polygon([(ax1, ym), (ax1 - 14, ym - 9), (ax1 - 14, ym + 9)], fill=FAINT + (255,))
            # a blue dot travels along the pipeline once everything is drawn
            ready = t0 + 0.12 + 0.14 * (i + len(items) * 0.6) + 0.4
            if t > ready:
                q = ((t - ready) / 1.6) % 1.0
                xs = boxes[0][0] + boxes[0][1] / 2, boxes[-1][0] + boxes[-1][1] / 2
                dx = lerp(xs[0], xs[1], ease(q))
                a = int(255 * math.sin(q * math.pi))
                d.ellipse((dx - 9, y + 38 - 9 + 50, dx + 9, y + 38 + 9 + 50), fill=BLUE + (a,))
        i += len(items) * 0.6 + 0.4
        y += 76 + 40
    if spec.get("stats"):
        y += 30
        n = len(spec["stats"])
        colw = 460
        x0 = (OW - colw * n) / 2
        for k, (val, cap) in enumerate(spec["stats"]):
            p = st(i + k * 0.5)
            if p <= 0:
                continue
            cnt = ease((t - t0 - 0.12 - 0.14 * (i + k * 0.5)) / 1.1)
            txt = count_text(val, cnt)
            cx = x0 + colw * k + colw / 2
            tw = d.textlength(txt, font=f_val)
            col = BLUE if k == 0 else INK
            d.text((cx - tw / 2, y + (1 - p) * 18), txt, font=f_val, fill=col + (int(255 * p),))
            cw = d.textlength(cap, font=f_cap)
            d.text((cx - cw / 2, y + 108 + (1 - p) * 18), cap, font=f_cap, fill=MUTED + (int(255 * p),))
    # slow push-in for the whole card
    z = 1 + 0.035 * ease((t - t0) / max(t1 - t0, 0.1))
    if z > 1.001:
        w, h = OW / z, OH / z
        img = img.resize((OW, OH), Image.BICUBIC, box=((OW - w) / 2, (OH - h) / 2, (OW + w) / 2, (OH + h) / 2))
    return img


def card(t, lines, t0):
    """Centred title card with staggered fade-up entrances, measured from t0."""
    img = Image.new("RGB", (OW, OH), BG)
    total_h = 96 + 40 + sum(l[1] * 1.25 for l in lines)
    y = (OH - total_h) / 2
    def stagger(i):
        return ease((t - t0 - 0.18 * i) / 0.6)
    p = stagger(0)
    if p > 0:
        ch = CHEVRON.resize((96, 96), Image.LANCZOS)
        ch.putalpha(ch.getchannel("A").point(lambda v: int(v * p)))
        img.paste(ch, (int((OW - 96) / 2), int(y + (1 - p) * 20)), ch)
    y += 96 + 40
    d = ImageDraw.Draw(img, "RGBA")
    for i, (txt, size, medium, color) in enumerate(lines, start=1):
        p = stagger(i)
        f = font(size, medium)
        tw = d.textlength(txt, font=f)
        if p > 0:
            d.text(((OW - tw) / 2, y + (1 - p) * 18), txt, font=f, fill=color + (int(255 * p),))
        y += size * 1.25
    return img


def card_at(t):
    """The chapter card image at time t, cross-fading between back-to-back cards."""
    for k, (s, e, spec) in enumerate(CARDS):
        if s <= t < e:
            img = chapter_card(t, s, e, spec)
            if k > 0 and abs(CARDS[k - 1][1] - s) < 1e-6 and t < s + 0.4:
                ps, pe, pspec = CARDS[k - 1]
                img = Image.blend(chapter_card(t, ps, pe, pspec), img, ease((t - s) / 0.4))
            return img
    return None


def scaled(img, sc):
    small = img.resize((int(OW * sc), int(OH * sc)), Image.BICUBIC)
    base = Image.new("RGB", (OW, OH), BG)
    base.paste(small, ((OW - small.width) // 2, (OH - small.height) // 2))
    return base


def app_frame(t):
    cam = clamp_cam(camera_at(t))
    img = render_camera(canvas_at(t), cam)
    if any(a <= t <= b for a, b in CURSOR_ON):
        X, Y = css(*cursor_at(t))
        draw_cursor(img, *project(cam, X, Y), t)
    draw_caption(img, t)
    return img


def frame(t):
    if t < WINDOW_IN[0]:
        return card(t, INTRO, 0.2)
    if t >= OUTRO_START + 0.4:
        return card(t, OUTRO, OUTRO_START)
    c = card_at(t)
    if c is not None:
        return c
    # window shrinking into the next card / growing out of the previous one
    for s, e, spec in CARDS:
        if s - CARD_IN <= t < s:
            p = ease((t - (s - CARD_IN)) / CARD_IN)
            return Image.blend(scaled(app_frame(t), lerp(1.0, 0.9, p)), chapter_card(s, s, e, spec), p)
        if e <= t < e + CARD_OUT and not any(abs(s2 - e) < 1e-6 for s2, _, _ in CARDS):
            p = ease((t - e) / CARD_OUT)
            return Image.blend(chapter_card(e, s, e, spec), scaled(app_frame(t), lerp(0.9, 1.0, p)), p)
    img = app_frame(t)
    if t < WINDOW_IN[1]:
        p = ease((t - WINDOW_IN[0]) / (WINDOW_IN[1] - WINDOW_IN[0]))
        img = Image.blend(card(t, INTRO, 0.2), scaled(img, lerp(0.94, 1.0, p)), p)
    if t >= WINDOW_OUT[0]:
        p = ease((t - WINDOW_OUT[0]) / (WINDOW_OUT[1] - WINDOW_OUT[0]))
        img = Image.blend(scaled(img, lerp(1.0, 0.92, p)), card(t, OUTRO, OUTRO_START) if t >= OUTRO_START else Image.new("RGB", (OW, OH), BG), p)
    return img


def main():
    n = int(DURATION * FPS)
    proc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS),
        "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT),
    ], stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(frame(i / FPS).tobytes())
        if i % 150 == 0:
            print(f"frame {i}/{n}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("wrote", OUT)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "--stills":
        for t in [8.5, 16.6, 18.5, 21.5, 23.3, 23.9, 26.0, 30.5, 34.5, 37.5, 41.5, 46.5, 50.5, 54.0, 58.5, 63.5, 67.0, 71.2, 76.0, 79.5, 83.0, 87.5, 93.0]:
            frame(t).save(HERE / "stills" / f"t{t:05.1f}.png")
        print("stills written")
    else:
        main()
