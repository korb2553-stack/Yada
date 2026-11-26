# -*- coding: utf-8 -*-
"""
art.py — วาดรูปน่ารัก ๆ ให้บอทตู้คีบตุ๊กตาด้วย Pillow
  • ถ้าไม่มีรูปในโฟลเดอร์ assets/ บอทจะเรียกไฟล์นี้สร้างให้เองตอนเปิดบอท
  • อยากใช้รูปของตัวเอง: วางไฟล์ชื่อเดียวกันทับใน assets/ ได้เลย (บอทไม่เขียนทับของเดิม)
  • อยากวาดใหม่ทั้งหมด:  python art.py
"""
import io
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

S = 3  # วาดขยาย 3 เท่าแล้วย่อ เพื่อให้ขอบเนียน
LANCZOS = Image.Resampling.LANCZOS
BICUBIC = Image.Resampling.BICUBIC

PLUSH_IDS = ["bear", "bunny", "cat", "duck", "panda", "pig", "unicorn", "star"]
# body, line, belly, blush, inner, arm, foot
PAL = {
    "bear":    ((214, 160, 112), (140, 92, 62), (244, 214, 178), (255, 150, 150), (244, 214, 178), (214, 160, 112), (214, 160, 112)),
    "bunny":   ((255, 218, 230), (226, 140, 170), (255, 242, 247), (255, 150, 180), (255, 170, 195), (255, 218, 230), (255, 218, 230)),
    "cat":     ((255, 186, 110), (210, 124, 56), (255, 230, 194), (255, 140, 140), (255, 170, 170), (255, 186, 110), (255, 186, 110)),
    "duck":    ((255, 230, 102), (220, 168, 36), (255, 244, 176), (255, 160, 120), (255, 200, 80), (255, 230, 102), (255, 170, 70)),
    "panda":   ((250, 250, 252), (112, 112, 128), (255, 255, 255), (255, 170, 180), (70, 70, 85), (62, 62, 78), (62, 62, 78)),
    "pig":     ((255, 184, 204), (222, 118, 150), (255, 210, 224), (255, 120, 150), (255, 140, 172), (255, 184, 204), (255, 184, 204)),
    "unicorn": ((251, 246, 255), (176, 156, 220), (255, 255, 255), (255, 170, 205), (255, 200, 225), (251, 246, 255), (251, 246, 255)),
    "star":    ((255, 222, 89), (230, 160, 30), (255, 240, 160), (255, 150, 130), (255, 240, 160), (255, 222, 89), (255, 222, 89)),
}
DARK = (52, 36, 48)


# ───────────────────────── เครื่องมือวาด ─────────────────────────
def _c(v):
    return int(round(v * S))


def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf",
              "arialbd.ttf", "Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf"):
        try:
            return ImageFont.truetype(p, int(size))
        except Exception:
            pass
    try:
        return ImageFont.load_default(int(size))
    except Exception:
        return ImageFont.load_default()


def new(w, h):
    return Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))


def fin(img, w, h):
    return img.resize((w, h), LANCZOS)


def E(d, box, fill=None, out=None, w=5):
    d.ellipse([_c(v) for v in box], fill=fill, outline=out, width=_c(w) if out else 1)


def R(d, box, r, fill=None, out=None, w=5):
    d.rounded_rectangle([_c(v) for v in box], radius=_c(r), fill=fill, outline=out, width=_c(w) if out else 1)


def P(d, pts, fill=None, out=None, w=5):
    pp = [(_c(x), _c(y)) for x, y in pts]
    d.polygon(pp, fill=fill)
    if out:
        d.line(pp + [pp[0], pp[1]], fill=out, width=_c(w), joint="curve")


def L(d, pts, fill, w):
    d.line([(_c(x), _c(y)) for x, y in pts], fill=fill, width=_c(w), joint="curve")


def ROT(img, box, ang, fill, out=None, w=5, pivot=None):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    E(ImageDraw.Draw(layer), box, fill, out, w)
    cx, cy = pivot if pivot else ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    img.alpha_composite(layer.rotate(ang, center=(cx * S, cy * S), resample=BICUBIC))


def _mix(c, t, to=(255, 255, 255)):
    return tuple(int(c[i] * (1 - t) + to[i] * t) for i in range(3))


def _sparkle(d, x, y, r, fill):
    q = r * 0.3
    P(d, [(x, y - r), (x + q, y - q), (x + r, y), (x + q, y + q), (x, y + r), (x - q, y + q), (x - r, y), (x - q, y - q)], fill)


def _heart(d, x, y, r, fill):
    E(d, (x - r, y - r * 0.8, x, y + r * 0.2), fill)
    E(d, (x, y - r * 0.8, x + r, y + r * 0.2), fill)
    P(d, [(x - r * 0.95, y - r * 0.12), (x + r * 0.95, y - r * 0.12), (x, y + r)], fill)


def _bg(w, h, top, bot, seed=1, blobs=14):
    g = Image.linear_gradient("L").resize((w * S, h * S))
    img = ImageOps.colorize(g, top, bot).convert("RGBA")
    rnd = random.Random(seed)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(blobs):
        r = rnd.randint(16, 64)
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        E(ld, (x - r, y - r, x + r, y + r), (255, 255, 255, 64))
    img.alpha_composite(layer)
    return img


def _mouth(d, cx, y, w=20, lw=4):
    d.arc([_c(cx - w), _c(y - w / 2), _c(cx), _c(y + w / 2)], 0, 180, fill=DARK, width=_c(lw))
    d.arc([_c(cx), _c(y - w / 2), _c(cx + w), _c(y + w / 2)], 0, 180, fill=DARK, width=_c(lw))


def _face(d, cx, cy, spread, blush, mouth=True, eye=16, eyes=True):
    for sg in (-1, 1):
        bx = cx + sg * (spread + 36)
        E(d, (bx - 25, cy + 14, bx + 25, cy + 42), blush)
    for sg in ((-1, 1) if eyes else ()):
        ex = cx + sg * spread
        E(d, (ex - eye, cy - eye * 1.15, ex + eye, cy + eye * 1.15), DARK)
        E(d, (ex - eye * 0.6, cy - eye * 0.85, ex + eye * 0.1, cy - eye * 0.15), (255, 255, 255))
        E(d, (ex + eye * 0.15, cy + eye * 0.2, ex + eye * 0.5, cy + eye * 0.55), (255, 255, 255))
    if mouth:
        _mouth(d, cx, cy + 34)


# ───────────────────────── ตุ๊กตา ─────────────────────────
def _star():
    img = new(512, 512)
    d = ImageDraw.Draw(img)
    E(d, (96, 462, 416, 508), (70, 50, 70, 55))
    m = Image.new("L", (512 * S, 512 * S), 0)
    md = ImageDraw.Draw(m)
    cx, cy, ro, ri = 256, 262, 250, 116
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        r = ro if k % 2 == 0 else ri
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    md.polygon([(_c(x), _c(y)) for x, y in pts], fill=255)
    bl = m.filter(ImageFilter.GaussianBlur(_c(20)))
    outer = bl.point(lambda v: 255 if v >= 104 else 0)
    inner = bl.point(lambda v: 255 if v >= 152 else 0)
    img.paste((230, 160, 30, 255), (0, 0), outer)
    img.paste((255, 222, 89, 255), (0, 0), inner)
    d = ImageDraw.Draw(img)
    _face(d, 256, 262, 50, PAL["star"][3], eye=15)
    _sparkle(d, 178, 176, 22, (255, 255, 255))
    _sparkle(d, 58, 78, 22, (255, 236, 140))
    _sparkle(d, 458, 420, 20, (255, 236, 140))
    _sparkle(d, 462, 90, 14, (255, 255, 255))
    return fin(img, 512, 512)


def plush(kind):
    if kind in SPECS:
        return _animal(kind)
    body, line, belly, blush, inner, arm, foot = PAL[kind]
    if kind == "star":
        return _star()
    img = new(512, 512)
    d = ImageDraw.Draw(img)
    E(d, (96, 458, 416, 506), (70, 50, 70, 55))  # เงา

    # ── ส่วนที่อยู่หลังหัว
    if kind in ("bear", "panda"):
        for x in (104, 326):
            E(d, (x, 80, x + 82, 162), arm if kind == "panda" else body, line)
        if kind == "bear":
            for x in (125, 347):
                E(d, (x, 101, x + 40, 141), inner)
    elif kind == "bunny":
        ROT(img, (146, 4, 230, 196), -10, body, line)
        ROT(img, (282, 4, 366, 196), 10, body, line)
        ROT(img, (164, 40, 212, 176), -10, inner)
        ROT(img, (300, 40, 348, 176), 10, inner)
    elif kind == "cat":
        P(d, [(110, 176), (122, 58), (226, 114)], body, line)
        P(d, [(402, 176), (390, 58), (286, 114)], body, line)
        P(d, [(134, 152), (140, 92), (196, 122)], inner)
        P(d, [(378, 152), (372, 92), (316, 122)], inner)
    elif kind == "duck":
        ROT(img, (232, 52, 278, 120), 18, body, line)
    elif kind == "pig":
        P(d, [(116, 168), (126, 76), (212, 112)], body, line)
        P(d, [(396, 168), (386, 76), (300, 112)], body, line)
        P(d, [(138, 150), (142, 100), (190, 120)], inner)
        P(d, [(374, 150), (370, 100), (322, 120)], inner)
    elif kind == "unicorn":
        for (x, y), col in zip([(118, 150), (100, 204), (104, 258), (122, 310)],
                               [(255, 150, 190), (196, 164, 255), (150, 204, 255), (150, 236, 204)]):
            E(d, (x - 38, y - 38, x + 38, y + 38), col, _mix(col, 0.0, (120, 90, 140)), 4)
        P(d, [(148, 128), (160, 54), (218, 104)], body, line)
        P(d, [(364, 128), (352, 54), (294, 104)], body, line)
        P(d, [(168, 118), (170, 80), (200, 104)], inner)
        P(d, [(344, 118), (342, 80), (312, 104)], inner)
        P(d, [(256, 0), (226, 118), (286, 118)], (255, 224, 130), (226, 170, 60), 5)
        L(d, [(241, 62), (271, 76)], (230, 176, 70), 5)
        L(d, [(234, 90), (278, 106)], (230, 176, 70), 5)
    d = ImageDraw.Draw(img)

    # ── ตัว
    E(d, (166, 428, 262, 494), foot, line)
    E(d, (250, 428, 346, 494), foot, line)
    E(d, (162, 318, 350, 466), body, line)
    E(d, (208, 346, 304, 446), belly)
    E(d, (116, 338, 198, 428), arm, line)
    E(d, (314, 338, 396, 428), arm, line)
    E(d, (98, 88, 414, 372), body, line)  # หัว

    # ── หน้าตา
    if kind == "bear":
        E(d, (198, 254, 314, 332), belly, line, 4)
        E(d, (236, 260, 276, 288), (92, 62, 52))
        L(d, [(256, 288), (256, 302)], DARK, 4)
        _mouth(d, 256, 312, 18, 4)
        _face(d, 256, 222, 66, blush, mouth=False)
    elif kind == "panda":
        ROT(img, (146, 192, 230, 280), 24, (52, 52, 68))
        ROT(img, (282, 192, 366, 280), -24, (52, 52, 68))
        d = ImageDraw.Draw(img)
        E(d, (234, 262, 278, 286), DARK)
        _face(d, 256, 232, 66, blush)
    elif kind == "cat":
        for x1, x2 in ((234, 230), (256, 256), (278, 282)):
            L(d, [(x1, 100), (x2, 136)], (210, 124, 56), 7)
        P(d, [(244, 262), (268, 262), (256, 276)], (255, 130, 150))
        for sg in (-1, 1):
            L(d, [(256 + sg * 90, 270), (256 + sg * 140, 262)], line, 3)
            L(d, [(256 + sg * 90, 284), (256 + sg * 140, 290)], line, 3)
        _face(d, 256, 226, 66, blush)
    elif kind == "duck":
        E(d, (204, 262, 308, 318), (255, 168, 64), (214, 110, 30), 4)
        L(d, [(214, 290), (298, 290)], (214, 110, 30), 3)
        _face(d, 256, 222, 70, blush, mouth=False)
    elif kind == "pig":
        E(d, (194, 246, 318, 322), (255, 150, 182), line, 4)
        E(d, (224, 272, 242, 300), (200, 88, 122))
        E(d, (270, 272, 288, 300), (200, 88, 122))
        _face(d, 256, 214, 70, blush, mouth=False)
    elif kind == "unicorn":
        P(d, [(248, 262), (264, 262), (256, 272)], (255, 150, 190))
        _face(d, 256, 226, 66, blush)
    else:  # bunny
        P(d, [(246, 258), (266, 258), (256, 270)], (255, 130, 160))
        _face(d, 256, 226, 66, blush)
    if kind == "unicorn":
        _sparkle(d, 404, 372, 16, (255, 255, 255))
    return fin(img, 512, 512)


# ───────────────────────── กรงเล็บ ─────────────────────────
def _claw(d, cx, top_y, spread=135, k=1.0, rail_y=0, opened=False, sad=False, t=None):
    s = lambda v: v * k
    lw = lambda v: max(2, v * k)
    R(d, (cx - s(70), rail_y, cx + s(70), rail_y + s(74)), s(22), (206, 196, 240), (150, 136, 200), lw(5))
    R(d, (cx - s(9), rail_y + s(60), cx + s(9), top_y + s(14)), s(6), (176, 182, 200), (120, 126, 150), lw(3))
    sil, ol = (208, 213, 228), (128, 134, 160)
    for sg in (-1, 1):
        if t is not None:  # t: 1 = กางสุด · 0 = หนีบ
            ro = [(36, 40), (148.75, 98), (188.6, 170), (205, 240)]
            rc = [(36, 40), (161.5, 92), (135, 185), (105.3, 252)]
            rel = [(rc[n][0] + (ro[n][0] - rc[n][0]) * t, rc[n][1] + (ro[n][1] - rc[n][1]) * t) for n in range(4)]
        elif opened:
            rel = [(36, 40), (36 + spread * 0.55, 98), (spread * 0.92, 170), (spread * 1.0, 240)]
        else:
            rel = [(36, 40), (40 + spread * 0.9, 92), (spread, 185), (spread * 0.78, 252)]
        pts = [(cx + sg * s(x), top_y + s(y)) for x, y in rel]
        L(d, pts, ol, s(26))
        for x, y in pts:
            E(d, (x - s(13), y - s(13), x + s(13), y + s(13)), ol)
        L(d, pts, sil, s(17))
        for x, y in pts:
            E(d, (x - s(8.5), y - s(8.5), x + s(8.5), y + s(8.5)), sil)
        tx, ty = pts[-1]
        E(d, (tx - s(14), ty - s(14), tx + s(14), ty + s(14)), (255, 150, 180), (222, 110, 150), lw(4))
    R(d, (cx - s(54), top_y, cx + s(54), top_y + s(54)), s(24), (255, 170, 196), (222, 110, 150), lw(5))
    for sg in (-1, 1):
        ex = cx + sg * s(21)
        E(d, (ex - s(6), top_y + s(19), ex + s(6), top_y + s(33)), DARK)
        E(d, (ex - s(3.5), top_y + s(21), ex + s(0.5), top_y + s(26)), (255, 255, 255))
        bx = cx + sg * s(37)
        E(d, (bx - s(9), top_y + s(33), bx + s(9), top_y + s(43)), (255, 120, 150))
    if sad:
        d.arc([_c(cx - s(8)), _c(top_y + s(38)), _c(cx + s(8)), _c(top_y + s(50))], 200, 340, fill=DARK, width=_c(lw(3)))
        dx, dy = cx + s(70), top_y + s(6)
        P(d, [(dx, dy - s(14)), (dx - s(7), dy + s(2)), (dx + s(7), dy + s(2))], (150, 208, 255))
        E(d, (dx - s(7), dy - s(2), dx + s(7), dy + s(12)), (150, 208, 255))
    else:
        _mouth(d, cx, top_y + s(38), s(10), lw(3))


# ───────────────────────── ฉากรูปตอนคีบ ─────────────────────────
SW, SH, SCX = 800, 520, 400


def _deco(d, pal_body, seed):
    rnd = random.Random(seed)
    spots = [(90, 110), (700, 140), (150, 300), (655, 330), (80, 440), (725, 450), (255, 70), (555, 60), (205, 200), (610, 235)]
    cols = [(255, 255, 255), (255, 236, 140), _mix(pal_body, 0.2, (255, 130, 170)), (255, 255, 255)]
    for i, (x, y) in enumerate(spots):
        c = cols[i % len(cols)]
        if i % 3 == 0:
            _heart(d, x, y, rnd.randint(11, 16), (255, 150, 180))
        else:
            _sparkle(d, x, y, rnd.randint(12, 22), c)


def grab_img(kind):
    body = PAL[kind][0]
    seed = sum(map(ord, kind))
    top = _mix(body, 0.84, (255, 236, 244))
    bot = _mix(body, 0.5, (226, 214, 255))
    back = _bg(SW, SH, top, bot, seed)
    bd = ImageDraw.Draw(back)
    E(bd, (SCX - 190, 150, SCX + 190, 520), (255, 255, 255, 120))  # แสงเรือง ๆ
    R(bd, (-30, -20, SW + 30, 36), 14, (214, 204, 244), (160, 146, 210), 5)
    back = fin(back, SW, SH)
    pl = plush(kind).resize((300, 300), LANCZOS)
    back.paste(pl, (SCX - 150, 186), pl)
    fr = new(SW, SH)
    fd = ImageDraw.Draw(fr)
    _claw(fd, SCX, 112, 135, k=0.92, rail_y=14)
    _deco(fd, body, seed)
    back.alpha_composite(fin(fr, SW, SH))
    return back


def miss_img(kind):
    seed = sum(map(ord, kind)) + 5
    back = _bg(SW, SH, (240, 244, 255), (214, 222, 245), seed)
    bd = ImageDraw.Draw(back)
    R(bd, (-30, -20, SW + 30, 36), 14, (214, 204, 244), (160, 146, 210), 5)
    back = fin(back, SW, SH)
    if kind != "empty":
        pl = plush(kind).resize((180, 180), LANCZOS).rotate(20, resample=BICUBIC, expand=True)
        back.paste(pl, (SCX - pl.width // 2 + 30, SH - pl.height - 6), pl)
    fr = new(SW, SH)
    fd = ImageDraw.Draw(fr)
    _claw(fd, SCX, 100, 205, k=0.78, rail_y=12, opened=True, sad=True)
    for dx, y0 in ((-34, 205), (6, 190), (46, 212)):  # เส้นแสดงการตก
        L(fd, [(SCX + dx + 30, y0), (SCX + dx + 30, y0 + 34)], (190, 200, 230), 6)
    f = _font(64 * S)
    fd.text((_c(SCX + 200), _c(100)), "?!", font=f, fill=(255, 140, 170), stroke_width=_c(5),
            stroke_fill=(255, 255, 255), anchor="mm")
    for x, y in ((120, 130), (700, 330), (90, 400)):
        _sparkle(fd, x, y, 14, (255, 255, 255))
    back.alpha_composite(fin(fr, SW, SH))
    return back


# ───────────────────────── ไอคอน / แบนเนอร์ ─────────────────────────
def claw_icon():
    W = 400
    img = new(W, W)
    d = ImageDraw.Draw(img)
    E(d, (8, 8, W - 8, W - 8), (255, 228, 240), (255, 170, 200), 8)
    _claw(d, 200, 112, 100, k=1.0, rail_y=-6)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse([_c(8), _c(8), _c(W - 8), _c(W - 8)], fill=255)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    d = ImageDraw.Draw(img)
    E(d, (8, 8, W - 8, W - 8), None, (255, 170, 200), 8)
    _sparkle(d, 90, 110, 22, (255, 255, 255))
    _heart(d, 318, 330, 22, (255, 140, 175))
    return fin(img, 256, 256)


def coin():
    img = new(256, 256)
    d = ImageDraw.Draw(img)
    E(d, (14, 14, 242, 242), (255, 214, 70), (222, 150, 20), 8)
    E(d, (38, 38, 218, 218), (255, 234, 130), (240, 180, 40), 5)
    _face(d, 128, 118, 38, (255, 150, 130), eye=11)
    _sparkle(d, 196, 62, 18, (255, 255, 255))
    _sparkle(d, 64, 190, 11, (255, 255, 255))
    return fin(img, 256, 256)


def banner():
    W, H = 1000, 400
    back = _bg(W, H, (255, 226, 238), (222, 214, 255), 7, 18)
    d = ImageDraw.Draw(back)
    # ตู้
    R(d, (46, 28, 336, 392), 38, (255, 170, 200), (224, 110, 150), 6)
    R(d, (92, 6, 290, 58), 20, (255, 236, 140), (240, 180, 40), 5)
    _sparkle(d, 120, 32, 12, (255, 255, 255))
    _sparkle(d, 262, 32, 12, (255, 255, 255))
    E(d, (170, 22, 212, 44), (255, 150, 180))
    R(d, (72, 74, 310, 262), 22, (246, 250, 255), (200, 170, 230), 5)
    R(d, (72, 226, 310, 262), 14, (214, 196, 240), (200, 170, 230), 4)
    _claw(d, 191, 104, 135, k=0.42, rail_y=76)
    R(d, (72, 282, 310, 376), 18, (255, 214, 228), (224, 110, 150), 4)
    L(d, [(140, 334), (140, 312)], (160, 150, 180), 7)
    E(d, (126, 292, 154, 320), (255, 90, 110), (200, 50, 80), 3)
    E(d, (214, 306, 248, 340), (255, 226, 90), (240, 170, 40), 4)
    E(d, (258, 314, 286, 342), (120, 190, 255), (70, 130, 220), 4)
    t = _font(104 * S)
    d.text((_c(384), _c(112)), "CLAW", font=t, fill=(255, 110, 150), stroke_width=_c(6), stroke_fill=(255, 255, 255), anchor="lm")
    t2 = _font(70 * S)
    d.text((_c(388), _c(196)), "MACHINE", font=t2, fill=(150, 120, 235), stroke_width=_c(5), stroke_fill=(255, 255, 255), anchor="lm")
    t3 = _font(30 * S)
    d.text((_c(390), _c(250)), "catch your cute plush!", font=t3, fill=(200, 110, 160), anchor="lm")
    for x, y, r in ((560, 70, 16), (930, 80, 20), (960, 200, 14), (700, 300, 12)):
        _sparkle(d, x, y, r, (255, 255, 255))
    _heart(d, 940, 140, 16, (255, 150, 180))
    _heart(d, 380, 330, 12, (255, 150, 180))
    back = fin(back, W, H)
    for kind, x in zip(["bear", "bunny", "cat", "panda"], (80, 136, 192, 246)):
        p = plush(kind).resize((66, 66), LANCZOS)
        back.paste(p, (x, 164), p)
    for kind, x, sz in zip(["unicorn", "star", "duck", "pig"], (540, 660, 770, 868), (118, 118, 112, 108)):
        p = plush(kind).resize((sz, sz), LANCZOS)
        back.paste(p, (x, 282), p)
    return back


# ═════════════════════ สัตว์เพิ่มเติม (ระบบ spec + ชิ้นส่วน) ═════════════════════
# ชิ้นส่วน: _p_ = อยู่หลังตัว/หัว · _m_ = บนตัว · _f_ = บนหัว (ก่อนวาดหน้า)
def _p_round_ears(img, d, sp, col, inner=None, xl=138, xr=374, y=124, r=44):
    for x in (xl, xr):
        E(d, (x - r, y - r, x + r, y + r), col, sp["line"])
        if inner:
            E(d, (x - r * .55, y - r * .55, x + r * .55, y + r * .55), inner)


def _p_tri_ears(img, d, sp, col, inner, tip=None):
    P(d, [(110, 176), (122, 58), (226, 114)], col, sp["line"])
    P(d, [(402, 176), (390, 58), (286, 114)], col, sp["line"])
    P(d, [(134, 152), (140, 92), (196, 122)], inner)
    P(d, [(378, 152), (372, 92), (316, 122)], inner)
    if tip:
        P(d, [(122, 58), (119, 88), (148, 72)], tip)
        P(d, [(390, 58), (393, 88), (364, 72)], tip)


def _p_floppy_ears(img, d, sp, col, inner=None):
    ROT(img, (64, 104, 170, 300), 18, col, sp["line"])
    ROT(img, (342, 104, 448, 300), -18, col, sp["line"])


def _p_big_ears(img, d, sp, col, inner):
    ROT(img, (24, 100, 196, 320), 15, col, sp["line"])
    ROT(img, (316, 100, 488, 320), -15, col, sp["line"])
    ROT(img, (52, 140, 168, 290), 15, inner)
    ROT(img, (344, 140, 460, 290), -15, inner)


def _p_side_ears(img, d, sp, col, inner=None):
    ROT(img, (52, 140, 166, 206), 22, col, sp["line"])
    ROT(img, (346, 140, 460, 206), -22, col, sp["line"])
    if inner:
        ROT(img, (72, 152, 146, 194), 22, inner)
        ROT(img, (366, 152, 440, 194), -22, inner)


def _p_horns_small(img, d, sp, col):
    ROT(img, (116, 62, 158, 134), -28, col, sp["line"], 4)
    ROT(img, (354, 62, 396, 134), 28, col, sp["line"], 4)


def _p_mane(img, d, sp, col):
    for k in range(14):
        a = k * 2 * math.pi / 14
        x, y = 256 + 158 * math.cos(a), 232 + 158 * math.sin(a)
        E(d, (x - 50, y - 50, x + 50, y + 50), col, sp["line"], 4)
    E(d, (110, 86, 402, 378), col)


def _p_ossicones(img, d, sp, col):
    for x, dx in ((196, -10), (316, 10)):
        L(d, [(x, 116), (x + dx, 50)], sp["line"], 20)
        L(d, [(x, 116), (x + dx, 50)], col, 11)
        E(d, (x + dx - 17, 34, x + dx + 17, 68), col, sp["line"], 4)


def _p_frill(img, d, sp, col, edge):
    E(d, (58, 34, 454, 372), col, sp["line"])
    for k in range(9):
        a = math.radians(-170 + k * 20)
        x, y = 256 + 198 * math.cos(a), 203 + 169 * math.sin(a)
        E(d, (x - 28, y - 28, x + 28, y + 28), edge, sp["line"], 4)


def _p_plates(img, d, sp, col):
    for x, y, s in ((150, 118, 26), (204, 84, 32), (256, 70, 36), (308, 84, 32), (362, 118, 26)):
        P(d, [(x, y - s * 1.2), (x + s * .7, y), (x, y + s * 1.2), (x - s * .7, y)], col, sp["line"], 4)


def _p_wings_bat(img, d, sp, col):
    pts = [(150, 330), (10, 150), (70, 250), (24, 330), (130, 410)]
    P(d, pts, col, sp["line"])
    P(d, [(512 - x, y) for x, y in pts], col, sp["line"])


def _p_crest_back(img, d, sp, col):
    P(d, [(300, 120), (470, 40), (380, 250)], col, sp["line"])


def _p_tail(img, d, sp, col, side=1, ang=-25):
    if side > 0:
        ROT(img, (336, 396, 476, 452), ang, col, sp["line"])
    else:
        ROT(img, (36, 396, 176, 452), -ang, col, sp["line"])


def _p_bushy_tail(img, d, sp, col, tip=None):
    ROT(img, (320, 360, 490, 430), 35, col, sp["line"])
    if tip:
        ROT(img, (442, 364, 496, 426), 35, tip, None, 5, pivot=(405, 395))


def _p_tail_curl(img, d, sp, col):
    ROT(img, (340, 392, 480, 424), 30, col, sp["line"])


def _p_shell(img, d, sp, col, pat):
    E(d, (118, 286, 394, 474), col, sp["line"])


def _p_tentacles(img, d, sp, col):
    for x in (104, 176, 248, 320):
        E(d, (x, 420, x + 88, 498), col, sp["line"])


def _p_dorsal(img, d, sp, col):
    P(d, [(236, 40), (206, 112), (300, 112)], col, sp["line"])


def _flame(d, cx, base_y, h, w, col):
    P(d, [(cx - w, base_y), (cx - w * .4, base_y - h * .5), (cx, base_y - h),
          (cx + w * .5, base_y - h * .45), (cx + w, base_y)], col)


def _p_flame(img, d, sp, c1, c2):
    for cx, h, w in ((190, 76, 26), (322, 76, 26)):
        _flame(d, cx, 130, h, w, c1)
    _flame(d, 256, 126, 104, 40, c1)
    _flame(d, 256, 126, 66, 24, c2)


def _p_wings_small(img, d, sp, col):
    ROT(img, (10, 250, 190, 380), 30, col, sp["line"])
    ROT(img, (322, 250, 502, 380), -30, col, sp["line"])


def _p_fluff(img, d, sp, col):
    for k in range(12):
        a = k * math.pi / 6
        x, y = 256 + 150 * math.cos(a), 232 + 150 * math.sin(a)
        E(d, (x - 56, y - 56, x + 56, y + 56), col, sp["line"], 4)


def _p_wings_butterfly(img, d, sp, c1, c2):
    ROT(img, (6, 90, 200, 290), 28, c1, sp["line"])
    ROT(img, (312, 90, 506, 290), -28, c1, sp["line"])
    ROT(img, (40, 270, 200, 440), -20, c2, sp["line"])
    ROT(img, (312, 270, 472, 440), 20, c2, sp["line"])
    d = ImageDraw.Draw(img)
    for x, y, r in ((70, 170, 18), (442, 170, 18), (96, 350, 14), (416, 350, 14)):
        E(d, (x - r, y - r, x + r, y + r), (255, 255, 255))


def _p_antlers(img, d, sp, col):
    for sg in (-1, 1):
        X = lambda x: 256 + sg * (256 - x)
        branches = [[(X(198), 104), (X(172), 60), (X(150), 24)], [(X(180), 72), (X(140), 66)], [(X(164), 44), (X(130), 30)]]
        for pts in branches:
            L(d, pts, sp["line"], 16)
        for pts in branches:
            L(d, pts, col, 9)
        for pts in branches:
            x, y = pts[-1]
            E(d, (x - 9, y - 9, x + 9, y + 9), (255, 250, 200))


def _m_spots(img, d, sp, col, pts):
    for x, y, r in pts:
        E(d, (x - r, y - r * .85, x + r, y + r * .85), col)


_f_spots = _m_spots


def _m_stripes(img, d, sp, col):
    for y in (350, 386, 422):
        L(d, [(166, y), (196, y + 8)], col, 8)
        L(d, [(346, y), (316, y + 8)], col, 8)


def _m_hex(img, d, sp, col):
    for x, y in ((190, 372), (322, 372), (256, 330)):
        P(d, [(x, y - 24), (x + 21, y - 12), (x + 21, y + 12), (x, y + 24), (x - 21, y + 12), (x - 21, y - 12)], None, col, 4)


def _m_collar(img, d, sp):
    R(d, (188, 352, 324, 380), 12, (230, 70, 76), (160, 40, 50), 4)
    E(d, (236, 364, 276, 404), (255, 214, 80), (214, 150, 20), 4)
    L(d, [(256, 372), (256, 396)], (214, 150, 20), 3)
    E(d, (220, 410, 292, 456), (255, 214, 80), (214, 150, 20), 4)


def _f_muzzle(img, d, sp, col, nose=None):
    E(d, (200, 254, 312, 326), col, sp["line"], 4)
    E(d, (236, 260, 276, 286), nose or (92, 62, 52))
    L(d, [(256, 286), (256, 300)], DARK, 4)
    _mouth(d, 256, 310, 18, 4)


def _f_muzzle_wide(img, d, sp, col, nostril, box):
    E(d, box, col, sp["line"], 4)
    cx = (box[0] + box[2]) / 2
    ny = box[1] + (box[3] - box[1]) * .42
    for sg in (-1, 1):
        E(d, (cx + sg * 41 - 11, ny, cx + sg * 41 + 11, ny + 24), nostril)


def _f_beak(img, d, sp, col, kind="oval"):
    if kind == "oval":
        E(d, (226, 252, 286, 288), col, sp["line"], 4)
    elif kind == "tri":
        P(d, [(236, 254), (276, 254), (256, 292)], col, sp["line"], 4)
    else:
        P(d, [(196, 258), (316, 258), (256, 334)], col, sp["line"], 4)


def _f_penguin_face(img, d, sp):
    for x in (150, 250):
        E(d, (x, 196, x + 112, 316), (255, 255, 255))
    P(d, [(168, 290), (344, 290), (256, 366)], (255, 255, 255))
    E(d, (200, 230, 312, 350), (255, 255, 255))


def _f_trunk(img, d, sp, col):
    R(d, (228, 250, 284, 352), 26, col, sp["line"], 5)
    for y in (300, 320, 338):
        L(d, [(236, y), (276, y)], sp["line"], 3)


def _f_stripes_head(img, d, sp, col):
    for x1, x2 in ((228, 226), (256, 256), (284, 286)):
        L(d, [(x1, 98), (x2, 138)], col, 8)
    for sg in (-1, 1):
        for dy in (0, 22):
            L(d, [(256 + sg * 150, 236 + dy), (256 + sg * 108, 244 + dy)], col, 7)


def _f_mask(img, d, sp, col):
    ROT(img, (138, 190, 238, 278), 18, col)
    ROT(img, (274, 190, 374, 278), -18, col)
    d = ImageDraw.Draw(img)
    P(d, [(236, 120), (276, 120), (266, 176), (246, 176)], (250, 250, 252))


def _f_wide_smile(img, d, sp, teeth=False, y=262, w=60):
    d.arc([_c(256 - w), _c(y - 18), _c(256 + w), _c(y + 34)], 0, 180, fill=DARK, width=_c(5))
    if teeth:
        for x in (226, 286):
            P(d, [(x, y + 30), (x + 16, y + 30), (x + 8, y + 44)], (255, 255, 255), DARK, 2)


def _f_horns3(img, d, sp, col):
    P(d, [(150, 170), (180, 152), (132, 64)], col, sp["line"], 4)
    P(d, [(362, 170), (332, 152), (380, 64)], col, sp["line"], 4)
    P(d, [(242, 290), (270, 290), (256, 250)], col, sp["line"], 4)


def _f_crest_spikes(img, d, sp, col):
    for x in (214, 256, 298):
        P(d, [(x - 16, 110), (x, 64 + abs(x - 256) * .5), (x + 16, 110)], col, sp["line"], 4)


def _f_eggcap(img, d, sp):
    pts = []
    for k in range(19):
        a = math.radians(180 + k * 10)
        pts.append((256 + 146 * math.cos(a), 200 + 118 * math.sin(a)))
    zz = [(402 - 292 * j / 8, 196 if j % 2 == 0 else 232) for j in range(9)]
    P(d, pts + zz, (255, 252, 245), sp["line"], 5)
    for x, y, r in ((190, 120, 12), (300, 110, 10), (250, 150, 9)):
        E(d, (x - r, y - r, x + r, y + r), (200, 230, 190))


def _f_cheeks(img, d, sp, col):
    E(d, (104, 236, 206, 332), col)
    E(d, (306, 236, 408, 332), col)
    E(d, (240, 250, 272, 270), (255, 150, 170))
    R(d, (244, 280, 268, 304), 4, (255, 255, 255), DARK, 3)


def _f_fox_cheeks(img, d, sp, col):
    P(d, [(100, 250), (210, 300), (118, 340)], col)
    P(d, [(412, 250), (302, 300), (394, 340)], col)
    E(d, (206, 262, 306, 336), col)
    E(d, (238, 266, 274, 288), DARK)
    _mouth(d, 256, 312, 18, 4)


def _f_monkey_mask(img, d, sp, col):
    E(d, (150, 188, 262, 300), col)
    E(d, (250, 188, 362, 300), col)
    E(d, (188, 252, 324, 342), col)
    for sg in (-1, 1):
        E(d, (256 + sg * 14 - 5, 282, 256 + sg * 14 + 5, 292), DARK)


def _f_wool_tuft(img, d, sp, col):
    for x, y, r in ((196, 100, 36), (256, 84, 40), (316, 100, 36), (226, 70, 30), (286, 70, 30)):
        E(d, (x - r, y - r, x + r, y + r), col, sp["line"], 4)


def _f_nostril_bump(img, d, sp, col):
    E(d, (222, 64, 290, 120), col, sp["line"], 4)


def _f_big_nose(img, d, sp, col):
    E(d, (226, 248, 286, 306), col)


def _f_nose(img, d, sp, col, y=252, mouth=True):
    P(d, [(244, y), (268, y), (256, y + 14)], col)
    if mouth:
        _mouth(d, 256, y + 28, 18, 4)


def _f_whiskers(img, d, sp, col=None):
    c = col or sp["line"]
    for sg in (-1, 1):
        L(d, [(256 + sg * 88, 272), (256 + sg * 148, 262)], c, 3)
        L(d, [(256 + sg * 88, 286), (256 + sg * 148, 292)], c, 3)


def _f_snout(img, d, sp, col):
    E(d, (196, 256, 316, 322), col, sp["line"], 4)
    d.arc([_c(216), _c(276), _c(296), _c(312)], 10, 170, fill=DARK, width=_c(3))


def _f_frog_eyes(img, d, sp, col):
    for x in (163, 349):
        E(d, (x - 46, 66, x + 46, 158), col, sp["line"])
        E(d, (x - 26, 86, x + 26, 142), (255, 255, 255))
        E(d, (x - 14, 98, x + 14, 128), DARK)
        E(d, (x - 8, 100, x + 2, 110), (255, 255, 255))


def _f_horns_dragon(img, d, sp, col):
    P(d, [(150, 150), (176, 112), (118, 50)], col, sp["line"], 4)
    P(d, [(362, 150), (336, 112), (394, 50)], col, sp["line"], 4)


def _f_spout(img, d, sp):
    for x, y, r in ((256, 60, 12), (228, 40, 9), (284, 40, 9), (256, 20, 8)):
        E(d, (x - r, y - r, x + r, y + r), (166, 220, 255), (110, 180, 235), 3)


def _f_leaf(img, d, sp):
    P(d, [(300, 300), (344, 282), (332, 322)], (130, 210, 110), (70, 150, 70), 3)


def _f_sparkles(img, d, sp, col):
    for x, y, r in ((80, 90, 18), (440, 130, 14), (430, 430, 16), (70, 400, 12)):
        _sparkle(d, x, y, r, col)


def _f_moon(img, d, sp, col):
    E(d, (232, 96, 282, 146), col)
    E(d, (246, 90, 302, 146), sp["body"])


def _f_antennae(img, d, sp, col):
    for sg in (-1, 1):
        pts = [(256 + sg * 28, 96), (256 + sg * 60, 40), (256 + sg * 96, 26)]
        L(d, pts, sp["line"], 9)
        L(d, pts, col, 4)
        x = 256 + sg * 96
        E(d, (x - 11, 15, x + 11, 37), col, sp["line"], 3)


PARTS = {n[3:]: f for n, f in list(globals().items()) if n[:3] in ("_p_", "_m_", "_f_")}


def _S(**k):
    return k


SPECS = {
    "dog": _S(body=(240, 198, 148), line=(170, 118, 70), belly=(255, 238, 210), blush=(255, 150, 150),
              behind=[("floppy_ears", (176, 120, 72))],
              front=[("spots", (176, 120, 72), [(192, 224, 44)]), ("muzzle", (255, 238, 210), None)], eye=(226, 66, False)),
    "hamster": _S(body=(255, 226, 172), line=(214, 162, 92), belly=(255, 246, 226), blush=(255, 150, 150),
                  behind=[("round_ears", (255, 226, 172), (255, 196, 196), 132, 380, 118, 36)],
                  front=[("spots", (232, 176, 120), [(256, 126, 46)]), ("cheeks", (255, 246, 226))], eye=(224, 68, False)),
    "mouse": _S(body=(206, 208, 224), line=(140, 140, 170), belly=(244, 244, 252), blush=(255, 150, 170),
                behind=[("round_ears", (206, 208, 224), (255, 184, 204), 120, 392, 112, 58)],
                front=[("nose", (255, 150, 180)), ("whiskers", None)], eye=(224, 66, False)),
    "sheep": _S(body=(252, 250, 246), line=(196, 186, 176), belly=(255, 255, 255), blush=(255, 170, 180),
                head=(255, 232, 208), foot=(120, 100, 108),
                behind=[("fluff", (252, 250, 246)), ("side_ears", (255, 222, 196), (255, 190, 190))],
                front=[("wool_tuft", (252, 250, 246))], eye=(236, 66, True)),
    "cow": _S(body=(255, 255, 255), line=(150, 150, 166), belly=(255, 230, 236), blush=(255, 160, 170),
              behind=[("horns_small", (255, 238, 200)), ("side_ears", (255, 255, 255), (255, 190, 200))],
              mid=[("spots", (70, 62, 76), [(210, 380, 26), (310, 420, 22), (190, 430, 16)])],
              front=[("spots", (70, 62, 76), [(146, 150, 46), (380, 254, 38)]),
                     ("muzzle_wide", (255, 196, 206), (214, 120, 140), (172, 250, 340, 336))], eye=(214, 70, False)),
    "frog": _S(body=(150, 222, 132), line=(84, 152, 74), belly=(228, 250, 204), blush=(255, 150, 150), eyes=False,
               front=[("frog_eyes", (150, 222, 132))], late=[("wide_smile", False, 262, 56)], eye=(246, 66, False)),
    "turtle": _S(body=(112, 172, 96), line=(70, 120, 64), belly=(196, 228, 156), blush=(255, 150, 140),
                 head=(172, 222, 142), arm=(172, 222, 142), foot=(172, 222, 142),
                 behind=[("shell", (112, 172, 96), (70, 120, 64))], mid=[("hex", (70, 120, 64))], eye=(226, 66, True)),
    "babydino": _S(body=(164, 226, 152), line=(92, 160, 92), belly=(238, 250, 204), blush=(255, 160, 150),
                   behind=[("tail", (164, 226, 152), 1, -25)], front=[("eggcap",)], eye=(258, 64, True)),
    "penguin": _S(body=(70, 82, 124), line=(40, 46, 84), belly=(255, 255, 255), blush=(255, 170, 184), foot=(255, 170, 62),
                  front=[("penguin_face",), ("beak", (255, 170, 62), "oval")], eye=(224, 62, False)),
    "koala": _S(body=(182, 188, 200), line=(110, 116, 134), belly=(226, 230, 238), blush=(255, 150, 162),
                behind=[("round_ears", (182, 188, 200), (246, 216, 226), 112, 400, 122, 62)],
                front=[("big_nose", (66, 66, 82))], eye=(216, 70, False)),
    "fox": _S(body=(255, 162, 84), line=(200, 102, 44), belly=(255, 246, 236), blush=(255, 150, 140),
              behind=[("tri_ears", (255, 162, 84), (70, 50, 56), (60, 40, 44)), ("bushy_tail", (255, 162, 84), (255, 250, 240))],
              front=[("fox_cheeks", (255, 250, 240))], eye=(226, 66, False)),
    "raccoon": _S(body=(164, 166, 182), line=(100, 102, 120), belly=(226, 228, 238), blush=(255, 160, 176),
                  behind=[("round_ears", (164, 166, 182), (70, 70, 86), 140, 372, 122, 40), ("bushy_tail", (164, 166, 182), (70, 70, 86))],
                  front=[("mask", (86, 88, 104)), ("muzzle", (240, 240, 248), None)], eye=(226, 66, False)),
    "monkey": _S(body=(180, 122, 82), line=(112, 72, 44), belly=(240, 212, 172), blush=(255, 150, 150),
                 behind=[("round_ears", (180, 122, 82), (240, 200, 160), 88, 424, 236, 44), ("tail_curl", (180, 122, 82))],
                 front=[("monkey_mask", (240, 212, 172))], eye=(224, 66, True)),
    "elephant": _S(body=(184, 204, 232), line=(110, 130, 172), belly=(228, 238, 252), blush=(255, 160, 182),
                   behind=[("big_ears", (184, 204, 232), (255, 196, 212))], front=[("trunk", (184, 204, 232))], eye=(214, 70, False)),
    "trike": _S(body=(150, 206, 178), line=(80, 150, 120), belly=(238, 250, 208), blush=(255, 160, 150),
                behind=[("frill", (255, 170, 156), (255, 212, 128)), ("tail", (150, 206, 178), 1, -25)],
                front=[("horns3", (252, 244, 214))], eye=(232, 64, False)),
    "stego": _S(body=(176, 216, 132), line=(100, 150, 70), belly=(240, 250, 198), blush=(255, 160, 140),
                behind=[("plates", (255, 176, 86)), ("tail", (176, 216, 132), 1, -25)], eye=(228, 66, True)),
    "brachio": _S(body=(146, 196, 236), line=(80, 128, 184), belly=(230, 244, 255), blush=(255, 160, 170),
                  behind=[("tail", (146, 196, 236), 1, -25)],
                  front=[("spots", (112, 160, 214), [(150, 160, 22), (364, 170, 20), (256, 136, 18)]), ("nostril_bump", (146, 196, 236))],
                  late=[("leaf",)], eye=(232, 66, True)),
    "giraffe": _S(body=(255, 216, 122), line=(198, 148, 62), belly=(255, 242, 204), blush=(255, 150, 142),
                  behind=[("ossicones", (150, 100, 60)), ("side_ears", (255, 216, 122), (150, 100, 60))],
                  mid=[("spots", (190, 120, 60), [(200, 386, 24), (304, 410, 22), (236, 440, 17), (318, 356, 14)])],
                  front=[("spots", (190, 120, 60), [(140, 168, 24), (372, 166, 22), (256, 138, 20)]),
                         ("muzzle_wide", (255, 242, 204), (150, 100, 60), (190, 256, 322, 332))], eye=(216, 66, False)),
    "lion": _S(body=(255, 198, 104), line=(200, 132, 44), belly=(255, 234, 192), blush=(255, 150, 140),
               behind=[("mane", (214, 128, 54)), ("round_ears", (255, 198, 104), (255, 220, 170), 150, 362, 112, 32)],
               front=[("muzzle", (255, 234, 192), None)], eye=(226, 66, False)),
    "tiger": _S(body=(255, 172, 72), line=(200, 102, 32), belly=(255, 240, 220), blush=(255, 150, 140),
                behind=[("round_ears", (255, 172, 72), (255, 240, 220), 138, 374, 124, 40)],
                mid=[("stripes", (96, 52, 40))], front=[("stripes_head", (96, 52, 40)), ("muzzle", (255, 244, 228), None)], eye=(226, 66, False)),
    "polar": _S(body=(246, 250, 255), line=(152, 172, 204), belly=(255, 255, 255), blush=(255, 170, 192),
                behind=[("round_ears", (246, 250, 255), (214, 228, 246), 138, 374, 124, 40)],
                front=[("muzzle", (226, 236, 250), (60, 70, 100))], eye=(222, 66, False)),
    "trex": _S(body=(124, 202, 122), line=(72, 140, 72), belly=(238, 250, 196), blush=(255, 160, 150),
               behind=[("tail", (124, 202, 122), 1, -25)],
               front=[("crest_spikes", (255, 196, 96)), ("wide_smile", True, 262, 60)], eye=(224, 70, False)),
    "ptero": _S(body=(174, 152, 222), line=(112, 92, 172), belly=(238, 228, 252), blush=(255, 160, 190),
                behind=[("wings_bat", (214, 194, 244)), ("crest_back", (174, 152, 222))],
                front=[("beak", (255, 200, 90), "wide")], eye=(226, 66, False)),
    "octopus": _S(body=(255, 142, 182), line=(210, 82, 132), belly=(255, 204, 220), blush=(255, 112, 150), nofeet=True,
                  behind=[("tentacles", (255, 142, 182))],
                  front=[("spots", (255, 196, 214), [(180, 150, 16), (256, 122, 14), (332, 150, 16), (150, 200, 10), (362, 200, 10)])],
                  eye=(232, 66, True)),
    "dolphin": _S(body=(132, 192, 242), line=(72, 132, 192), belly=(236, 248, 255), blush=(255, 160, 184),
                  behind=[("dorsal", (132, 192, 242))], front=[("snout", (236, 248, 255))], eye=(222, 70, False)),
    "dragon": _S(body=(170, 122, 236), line=(110, 72, 182), belly=(255, 226, 150), blush=(255, 150, 190),
                 behind=[("wings_bat", (255, 160, 208)), ("tail", (170, 122, 236), 1, -25)],
                 front=[("horns_dragon", (255, 232, 150)), ("crest_spikes", (255, 226, 150)), ("muzzle", (214, 178, 250), (80, 50, 120))],
                 eye=(226, 66, False)),
    "whale": _S(body=(104, 168, 230), line=(56, 108, 180), belly=(234, 246, 255), blush=(255, 160, 184),
                behind=[("tail", (104, 168, 230), 1, -25)], front=[("spout",)], late=[("wide_smile", False, 268, 52)], eye=(232, 76, False)),
    "phoenix": _S(body=(255, 122, 72), line=(190, 52, 40), belly=(255, 212, 104), blush=(255, 170, 140),
                  behind=[("wings_small", (255, 170, 70)), ("flame", (255, 110, 60), (255, 214, 90))],
                  front=[("beak", (255, 210, 96), "tri")], eye=(230, 66, False)),
    "maneki": _S(body=(255, 251, 240), line=(206, 152, 64), belly=(255, 246, 222), blush=(255, 140, 140), raised=True,
                 behind=[("tri_ears", (255, 251, 240), (255, 120, 120), None)], mid=[("collar",)],
                 front=[("spots", (255, 196, 120), [(150, 150, 34)]), ("nose", (255, 130, 140)), ("whiskers", None)],
                 late=[("sparkles", (255, 214, 80))], eye=(224, 66, False)),
    "moodeng": _S(body=(160, 136, 150), line=(100, 80, 104), belly=(206, 182, 196), blush=(255, 138, 160),
                  behind=[("round_ears", (160, 136, 150), (236, 176, 190), 150, 362, 112, 30)],
                  front=[("muzzle_wide", (222, 166, 182), (112, 80, 104), (140, 238, 372, 352))],
                  late=[("wide_smile", False, 330, 34)], eye=(206, 84, False)),
    # ── มิสติก (มีออร่าเรืองแสงรอบตัว)
    "wolf": _S(body=(170, 182, 214), line=(100, 112, 164), belly=(236, 242, 255), blush=(255, 170, 196), aura=(150, 170, 255),
               behind=[("tri_ears", (170, 182, 214), (255, 190, 214), (90, 100, 150)), ("bushy_tail", (170, 182, 214), (246, 248, 255))],
               front=[("muzzle", (240, 244, 255), None), ("moon", (255, 224, 110))], late=[("sparkles", (200, 214, 255))], eye=(226, 66, False)),
    "fairy": _S(body=(255, 176, 222), line=(200, 92, 162), belly=(255, 226, 242), blush=(255, 130, 172), aura=(255, 170, 230),
                behind=[("wings_butterfly", (196, 160, 255), (255, 190, 232))],
                front=[("antennae", (255, 214, 90))], late=[("sparkles", (255, 240, 170))], eye=(226, 66, True)),
    "deer": _S(body=(250, 236, 214), line=(190, 150, 110), belly=(255, 252, 244), blush=(255, 170, 170), aura=(150, 240, 214),
               behind=[("antlers", (130, 226, 200)), ("side_ears", (250, 236, 214), (255, 200, 200))],
               mid=[("spots", (236, 204, 164), [(200, 386, 12), (300, 404, 10), (240, 430, 9), (322, 364, 8)])],
               front=[("spots", (236, 204, 164), [(148, 168, 10), (370, 172, 9), (256, 132, 9), (126, 222, 7)]),
                      ("muzzle", (255, 252, 244), (120, 80, 70))],
               late=[("sparkles", (160, 240, 220))], eye=(222, 66, False)),
}
for _k, _s in SPECS.items():
    PAL[_k] = (_s["body"], _s["line"], _s["belly"], _s["blush"], _s["belly"],
               _s.get("arm", _s["body"]), _s.get("foot", _s["body"]))
ALL_IDS = PLUSH_IDS + list(SPECS)


def _animal(kind):
    sp = SPECS[kind]
    body, line, belly, blush = sp["body"], sp["line"], sp["belly"], sp["blush"]
    head, arm, foot = sp.get("head", body), sp.get("arm", body), sp.get("foot", body)
    img = new(512, 512)
    d = ImageDraw.Draw(img)
    if sp.get("aura"):
        E(d, (14, 14, 498, 498), tuple(sp["aura"]) + (54,), tuple(sp["aura"]) + (120,), 5)
    E(d, (96, 458, 416, 506), (70, 50, 70, 55))

    def run(parts):
        nonlocal d
        for name, *args in parts:
            PARTS[name](img, d, sp, *args)
            d = ImageDraw.Draw(img)

    run(sp.get("behind", []))
    if not sp.get("nofeet"):
        E(d, (166, 428, 262, 494), foot, line)
        E(d, (250, 428, 346, 494), foot, line)
    E(d, (162, 318, 350, 466), body, line)
    E(d, (208, 346, 304, 446), belly)
    if not sp.get("raised"):
        E(d, (116, 338, 198, 428), arm, line)
    E(d, (314, 338, 396, 428), arm, line)
    run(sp.get("mid", []))
    E(d, (98, 88, 414, 372), head, line)
    run(sp.get("front", []))
    cy, spread, mouth = sp.get("eye", (226, 66, True))
    _face(d, 256, cy, spread, blush, mouth=mouth, eyes=sp.get("eyes", True))
    run(sp.get("late", []))
    if sp.get("raised"):  # แมวกวัก: ยกอุ้งเท้า
        E(d, (84, 190, 172, 296), arm, line)
        E(d, (112, 232, 146, 266), (255, 170, 190))
    return fin(img, 512, 512)


# ═════════════════════ ภาพตู้คีบ + GIF ตอนคีบ ═════════════════════
MW, MH = 560, 340
ASSET_DIR = None
_CACHE = {}


def _machine_bg():
    if "bg" not in _CACHE:
        bg = _bg(MW, MH, (255, 232, 242), (226, 218, 255), 11, 10)
        d = ImageDraw.Draw(bg)
        R(d, (-30, -20, MW + 30, 28), 12, (214, 204, 244), (160, 146, 210), 4)
        R(d, (-30, 300, MW + 30, MH + 30), 14, (236, 222, 255), (190, 170, 235), 4)
        for x, y, r in ((40, 90, 10), (520, 70, 12), (300, 60, 9), (90, 190, 8), (470, 180, 9)):
            _sparkle(d, x, y, r, (255, 255, 255))
        _CACHE["bg"] = fin(bg, MW, MH)
    return _CACHE["bg"]


def _empty_icon(size):
    im = new(120, 120)
    d = ImageDraw.Draw(im)
    for y in (46, 64, 82):
        d.arc([_c(18), _c(y - 14), _c(102), _c(y + 14)], 200, 340, fill=(170, 186, 232, 255), width=_c(5))
    _sparkle(d, 92, 28, 9, (255, 255, 255))
    return fin(im, size, size)


def _icon(kind, size=96):
    key = ("icon", kind, size)
    if key not in _CACHE:
        if kind == "empty":
            im = _empty_icon(size)
        else:
            f = Path(ASSET_DIR) / f"plush_{kind}.png" if ASSET_DIR else None
            im = Image.open(f).convert("RGBA") if f and f.exists() else plush(kind)
            im = im.resize((size, size), LANCZOS)
        _CACHE[key] = im
    return _CACHE[key]


def _burst(fr, cx, cy, step):
    d = ImageDraw.Draw(fr)
    r0 = 22 + step * 12
    cols = [(255, 255, 255), (255, 226, 120), (255, 170, 200), (190, 170, 255)]
    for k in range(8):
        a = k * math.pi / 4 + step * .25
        x, y = cx + r0 * math.cos(a) * 1.3, cy + r0 * math.sin(a)
        s = 7 + (k % 3) * 3
        q = s * .3
        d.polygon([(x, y - s), (x + q, y - q), (x + s, y), (x + q, y + q), (x, y + s), (x - q, y + q), (x - s, y), (x - q, y - q)], fill=cols[k % 4])


def machine_frame(slots, pos, top_y=36, t=1.0, plush_at=None, hide_slot=False, flash=0.0, burst=0, sad=False, hl=True):
    """วาดตู้ 1 เฟรม: slots=[id|'empty'], pos=ช่องที่กรงเล็บอยู่, t=ความกว้างของกรง (1 เปิด·0 ปิด)"""
    fr = _machine_bg().copy()
    n = len(slots)
    cxs = [int(MW / n * (k + .5)) for k in range(n)]
    cx = cxs[pos]
    if hl:
        ov = Image.new("RGBA", (MW, MH), (0, 0, 0, 0))
        ImageDraw.Draw(ov).rounded_rectangle((cx - 54, 188, cx + 54, 306), 20, fill=(255, 255, 255, 96))
        fr.alpha_composite(ov)
    for k, kind in enumerate(slots):
        if k == pos and hide_slot:
            continue
        ic = _icon(kind)
        fr.paste(ic, (cxs[k] - 48, 204), ic)
    if plush_at:
        kind, y = plush_at
        ic = _icon(kind)
        fr.paste(ic, (cx - 48, int(y)), ic)
    layer = new(260, MH)
    _claw(ImageDraw.Draw(layer), 130, top_y, k=0.5, rail_y=0, t=t, sad=sad)
    cl = fin(layer, 260, MH)
    fr.paste(cl, (cx - 130, 0), cl)
    if burst:
        _burst(fr, cx, int(top_y + 74 + 48), burst)
    if flash:
        fr = Image.blend(fr, Image.new("RGBA", fr.size, (255, 255, 255, 255)), flash)
    return fr


def machine_png(slots, pos):
    buf = io.BytesIO()
    machine_frame(slots, pos).convert("RGB").save(buf, "PNG", compress_level=3)
    buf.seek(0)
    return buf


def grab_gif(slots, pos, final_id, win, swap=False):
    """GIF ตอนคีบ (เล่นรอบเดียว) → (BytesIO, วินาทีที่ควรรอก่อนโชว์ผล)"""
    target = slots[pos]
    empty = target == "empty"
    ease = lambda x: x * x * (3 - 2 * x)
    base, low = 36, 130
    frames, durs = [], []

    def add(ms, **kw):
        frames.append(machine_frame(slots, pos, **kw).convert("RGB"))
        durs.append(ms)

    for j in range(9):                                   # กรงเล็บลง
        add(60, top_y=base + (low - base) * ease(j / 8), t=1)
    for j in range(5):                                   # หนีบ
        add(70, top_y=low, t=1 - j / 4)
    carry = None if empty else target
    if swap and not empty:                               # ซีเคร็ท! แสงวาบ แล้วตุ๊กตาเปลี่ยน
        for fl in (.35, .75, .35):
            add(70, top_y=low, t=0, plush_at=(target if fl < .6 else final_id, low + 74), hide_slot=True, flash=fl)
        carry = final_id
    hold = 1500
    if empty:
        for j in range(9):
            add(70, top_y=low - (low - base) * ease(j / 8), t=0)
        add(hold, top_y=base, t=0, sad=True)
    elif win:
        for j in range(9):
            top = low - (low - base) * ease(j / 8)
            add(70, top_y=top, t=0, plush_at=(carry, top + 74), hide_slot=True)
        for b in range(1, 5):
            add(100, top_y=base, t=0, plush_at=(carry, base + 74), hide_slot=True, burst=b)
        add(hold, top_y=base, t=0, plush_at=(carry, base + 74), hide_slot=True, burst=4)
    else:
        top = low
        for j in range(4):
            top = low - (low - base) * ease((j + 1) / 8)
            add(70, top_y=top, t=0, plush_at=(carry, top + 74), hide_slot=True)
        y0 = top + 74
        for j in range(1, 6):                            # ตุ๊กตาหลุดตกลงมา
            f = j / 5
            add(60, top_y=top - (top - base) * ease(f), t=min(1, f * 1.6), plush_at=(target, y0 + (204 - y0) * f * f), hide_slot=True)
        for dy in (-12, 0, -5, 0):                       # เด้ง
            add(60, top_y=base, t=1, plush_at=(target, 204 + dy), hide_slot=True)
        add(hold, top_y=base, t=1, sad=True)
    pal = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    buf = io.BytesIO()
    pal[0].save(buf, "GIF", save_all=True, append_images=pal[1:], duration=durs, disposal=1)
    buf.seek(0)
    return buf, max(1.0, (sum(durs) - hold) / 1000 + 0.6)


# ═════════════════════ ไอคอนเพิ่มเติม ═════════════════════
def potion(m):
    col = {2: (120, 222, 150), 3: (116, 186, 255), 5: (206, 138, 255)}[m]
    glass = (170, 182, 210)
    img = new(256, 256)
    d = ImageDraw.Draw(img)
    E(d, (36, 214, 220, 248), (70, 50, 70, 50))
    R(d, (104, 40, 152, 100), 10, (246, 250, 255), glass, 5)
    E(d, (44, 84, 212, 226), (246, 250, 255), glass, 6)
    E(d, (54, 120, 202, 222), col)
    E(d, (54, 112, 202, 138), _mix(col, .45))
    E(d, (44, 84, 212, 226), None, glass, 6)
    R(d, (96, 18, 160, 52), 10, (214, 160, 110), (160, 110, 70), 5)
    for sg in (-1, 1):
        ex = 128 + sg * 28
        E(d, (ex - 8, 160, ex + 8, 180), DARK)
        E(d, (ex - 5, 162, ex + 0, 168), (255, 255, 255))
        E(d, (128 + sg * 50 - 13, 180, 128 + sg * 50 + 13, 194), (255, 130, 160))
    _mouth(d, 128, 192, 12, 3)
    E(d, (158, 20, 246, 104), (255, 224, 100), (214, 150, 20), 5)
    d.text((_c(202), _c(62)), f"x{m}", font=_font(36 * S), fill=(150, 84, 16), anchor="mm")
    _sparkle(d, 52, 70, 16, (255, 255, 255))
    _sparkle(d, 224, 190, 12, _mix(col, .3))
    return fin(img, 256, 256)


def trophy():
    gold, ol = (255, 214, 70), (214, 150, 20)
    img = new(256, 256)
    d = ImageDraw.Draw(img)
    E(d, (40, 220, 216, 248), (70, 50, 70, 50))
    E(d, (30, 60, 96, 132), None, ol, 11)
    E(d, (160, 60, 226, 132), None, ol, 11)
    R(d, (112, 150, 144, 200), 6, gold, ol, 5)
    R(d, (72, 192, 184, 228), 10, (255, 170, 200), (214, 100, 150), 5)
    R(d, (68, 38, 188, 166), 46, gold, ol, 6)
    _face(d, 128, 96, 28, (255, 160, 120), eye=10)
    _sparkle(d, 206, 40, 16, (255, 255, 255))
    _sparkle(d, 46, 170, 11, (255, 236, 140))
    return fin(img, 256, 256)


def trade_icon():
    img = new(256, 256)
    d = ImageDraw.Draw(img)
    E(d, (10, 10, 246, 246), (226, 244, 255), (150, 200, 240), 8)
    a1 = [(56, 70), (136, 70), (136, 50), (196, 88), (136, 126), (136, 106), (56, 106)]
    P(d, a1, (255, 170, 196), (222, 110, 150), 5)
    P(d, [(256 - x, 256 - y) for x, y in a1], (140, 200, 255), (80, 140, 220), 5)
    _sparkle(d, 60, 190, 14, (255, 255, 255))
    _sparkle(d, 200, 60, 12, (255, 236, 140))
    _heart(d, 196, 206, 14, (255, 150, 180))
    return fin(img, 256, 256)


# ═════════════════════ รูปกระเป๋า (สร้างสดตามของที่มี) ═════════════════════
def bag_image(items, assets_dir=None):
    """items = [(plush_id, จำนวน), ...] → BytesIO (PNG)"""
    n = max(1, len(items))
    cols = min(n, 4 if n <= 8 else 6)
    rows = math.ceil(n / cols)
    cell = 176 if cols <= 4 else 140
    pad, ic = 16, cell - 44
    W, H = pad * 2 + cols * cell, pad * 2 + rows * cell
    back = new(W, H)
    d = ImageDraw.Draw(back)
    R(d, (0, 0, W, H), 30, (255, 240, 247), (255, 190, 214), 6)
    for i, (kind, _) in enumerate(items):
        x, y = pad + (i % cols) * cell, pad + (i // cols) * cell
        R(d, (x + 6, y + 6, x + cell - 6, y + cell - 6), 24, (255, 255, 255), PAL[kind][1], 4)
    back = fin(back, W, H)
    for i, (kind, _) in enumerate(items):
        x, y = pad + (i % cols) * cell, pad + (i // cols) * cell
        f = Path(assets_dir) / f"plush_{kind}.png" if assets_dir else None
        p = Image.open(f).convert("RGBA") if f and f.exists() else plush(kind)
        p = p.resize((ic, ic), LANCZOS)
        back.paste(p, (x + (cell - ic) // 2, y + 8), p)
    fr = new(W, H)
    fd = ImageDraw.Draw(fr)
    font = _font(24 * S)
    for i, (kind, cnt) in enumerate(items):
        x, y = pad + (i % cols) * cell, pad + (i // cols) * cell
        R(fd, (x + cell - 78, y + cell - 44, x + cell - 12, y + cell - 12), 14, (255, 118, 160), (255, 255, 255), 3)
        fd.text((_c(x + cell - 45), _c(y + cell - 28)), f"x{cnt}", font=font, fill=(255, 255, 255), anchor="mm")
    back.alpha_composite(fin(fr, W, H))
    buf = io.BytesIO()
    back.save(buf, "PNG")
    buf.seek(0)
    return buf


# ═════════════════════ สร้างไฟล์ทั้งหมด ═════════════════════
def ensure_scene(folder, kind, mode):
    """รูปตอนคีบได้ (grab) / ตอนหลุด (miss) — สร้างครั้งแรกที่ใช้แล้วเก็บไว้ใน assets/"""
    p = Path(folder) / f"claw_{mode}_{kind}.png"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        (grab_img if mode == "grab" else miss_img)(kind).save(p)
    return p


def ensure_assets(folder, force=False):
    global ASSET_DIR
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    ASSET_DIR = folder
    jobs = [("menu_banner.png", banner), ("claw_icon.png", claw_icon), ("token.png", coin),
            ("trophy.png", trophy), ("trade.png", trade_icon)]
    jobs += [(f"potion_{m}.png", lambda m=m: potion(m)) for m in (2, 3, 5)]
    jobs += [(f"plush_{k}.png", lambda k=k: plush(k)) for k in ALL_IDS]
    made = 0
    for name, fn in jobs:
        p = folder / name
        if force or not p.exists():
            fn().save(p)
            made += 1
    return made


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "assets"
    print("สร้างรูปแล้ว", ensure_assets(out, force=True), "ไฟล์ →", out)
