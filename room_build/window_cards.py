"""The view out of SUB-01's window (#98 G7): the parallax cards that web/room/window_view.js layers behind the glass.

Everything here is drawn from code (Pillow + numpy, one fixed seed, so the output is reproducible to the byte) and is
released under CC0 like the rest of the room: no photographs, no downloaded assets, no brands, no signage, no text.
The cards are horizontally tileable (the shader wraps them), in metres of the small "diorama" behind the window, with
y = 0 on the window's centre line (his eye line when he stands) and the street at y = GROUND.

    python room_build/window_cards.py            # writes web/room/window/*.webp and prints the sizes
    python room_build/window_cards.py --preview  # also a contact sheet, room_build/out/window_cards.png

Cards (name, pixels, metres covered, depth behind the glass in window_view.js):
  near    1024 x 1024   16 x 16 m  14 m   the house across the lane, its balcony with the washing, the utility pole,
                                           the cables, the vending machine, the street lamp, a tree at the edge
  mid     2048 x 1024   48 x 24 m  30 m   a row of 4-5 storey apartment blocks (balconies, AC units, laundry, pipes,
                                           water tanks, antennas), two gaps where the elevated railway shows
  far     2048 x  256  280 x 50 m 100 m   the sea of low roofs, mid-rise blocks and a few towers in the haze
  ground  1024 x 1024   24 x 24 m  the street plane (y = GROUND): asphalt, a coin parking lot with cars, a kerb, a road
  noise    256 x  256                R: tileable fbm (clouds)   G: rain streaks   B, A: raindrop refraction offsets
Each card with windows has a lights mask `<name>_l.webp` (lossless): R = window pane, G = kind (0 a home that switches on
and off in the evening, 50 a red aviation light, 100 always on and warm, 200 always on and cool), B = the window's id.
"""
import argparse
import math
import os
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "room" / "window"
GROUND = -8.2               # the street, metres below the window's centre line (a third-floor room: he looks over the roofs)
SEED = 20261002
QUALITY = 80                # lossy WebP quality for the colour cards
BUDGET = 1.5 * 1024 * 1024  # all files together (the task's asset budget)

# a muted Tokyo palette (sRGB 0..255)
WALLS = {"tile_beige": (196, 182, 160), "concrete": (158, 158, 154), "white": (226, 224, 218), "brown": (118, 86, 70),
         "tile_grey": (142, 146, 150), "cream": (214, 204, 182), "pale_green": (176, 190, 170)}
GLASS_DAY = (118, 136, 156)
FRAME = (62, 64, 68)
CLOTH = [(238, 238, 236), (176, 200, 226), (120, 132, 150), (58, 70, 110), (232, 190, 196), (240, 226, 160), (160, 170, 150)]
FUTON = [(214, 190, 170), (170, 190, 214), (226, 210, 184), (140, 160, 190)]
RAIL = (70, 72, 76)


def lerp(a, b, t):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def shade(c, k):
    return tuple(max(0, min(255, int(round(v * k)))) for v in c)


def tileable_noise(rng, w, h, cells, octaves=4, persistence=0.5):
    """value noise that wraps in both directions: lattice values repeat at the tile's edges"""
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        n = cells * 2 ** o
        lat = rng.random((n, n)).astype(np.float32)
        ys = (np.arange(h) / h * n)[:, None]
        xs = (np.arange(w) / w * n)[None, :]
        y0 = np.floor(ys).astype(int) % n; x0 = np.floor(xs).astype(int) % n
        fy = ys - np.floor(ys); fx = xs - np.floor(xs)
        fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)
        y1 = (y0 + 1) % n; x1 = (x0 + 1) % n
        v = (lat[y0, x0] * (1 - fx) * (1 - fy) + lat[y0, x1] * fx * (1 - fy) + lat[y1, x0] * (1 - fx) * fy + lat[y1, x1] * fx * fy)
        out += amp * v; total += amp; amp *= persistence
    return out / total


class Card:
    """an RGBA canvas in metres (x wraps at `xm`; y from y0 up to y1) plus its lights mask and a shade multiplier"""

    def __init__(self, name, W, H, xm, y0, y1, rng, ss=2):
        self.out_size = (W, H); W *= ss; H *= ss                    # drawn at `ss` times the size, then downsampled
        self.name, self.W, self.H, self.xm, self.y0, self.y1, self.rng = name, W, H, xm, y0, y1, rng
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.lit = Image.new("RGB", (W, H), (0, 0, 0))
        self.ld = ImageDraw.Draw(self.lit)
        self.shade = np.ones((H, W), np.float32)
        self.ids = 0
        self.sx = W / xm; self.sy = H / (y1 - y0)

    # metres -> pixels (y up)
    def px(self, x):
        return x * self.sx

    def py(self, y):
        return (self.y1 - y) * self.sy

    def box(self, x0, y0, x1, y1):
        return [self.px(x0), self.py(y1), self.px(x1), self.py(y0)]

    @staticmethod
    def _ib(b):
        """pixel box, at least one pixel wide and tall (thin lines drawn in metres must still show)"""
        X0, Y0 = int(round(b[0])), int(round(b[1])); X1, Y1 = max(X0, int(round(b[2])) - 1), max(Y0, int(round(b[3])) - 1)
        return [X0, Y0, X1, Y1]

    def rect(self, x0, y0, x1, y1, c, a=255):
        for dx in (0, -self.xm, self.xm):                        # wrap: draw the copies that cross the seam
            b = self.box(x0 + dx, y0, x1 + dx, y1)
            if b[2] < 0 or b[0] > self.W: continue
            self.d.rectangle(self._ib(b), fill=(*c, a))

    def poly(self, pts, c, a=255):
        for dx in (0, -self.xm, self.xm):
            p = [(self.px(x + dx), self.py(y)) for x, y in pts]
            if max(q[0] for q in p) < 0 or min(q[0] for q in p) > self.W: continue
            self.d.polygon(p, fill=(*c, a))

    def line(self, pts, c, w_m, a=255):
        wpx = max(1, int(round(w_m * self.sx)))
        for dx in (0, -self.xm, self.xm):
            p = [(self.px(x + dx), self.py(y)) for x, y in pts]
            if max(q[0] for q in p) < 0 or min(q[0] for q in p) > self.W: continue
            self.d.line(p, fill=(*c, a), width=wpx)

    def ellipse(self, cx, cy, rx, ry, c, a=255):
        for dx in (0, -self.xm, self.xm):
            b = [self.px(cx + dx - rx), self.py(cy + ry), self.px(cx + dx + rx), self.py(cy - ry)]
            if b[2] < 0 or b[0] > self.W: continue
            self.d.ellipse(b, fill=(*c, a))

    def light(self, x0, y0, x1, y1, kind=0):
        """a pane in the lights mask: R = 255, G = kind, B = id (cycles through 1..250)"""
        self.ids = self.ids % 250 + 1
        for dx in (0, -self.xm, self.xm):
            b = self.box(x0 + dx, y0, x1 + dx, y1)
            if b[2] < 0 or b[0] > self.W: continue
            self.ld.rectangle(self._ib(b), fill=(255, kind, self.ids))

    def darken(self, x0, y0, x1, y1, k0, k1=None, vertical=True):
        """multiply the shade in a box: k0 at the top (or left) fading to k1 at the bottom (or right)"""
        k1 = k0 if k1 is None else k1
        for dx in (0, -self.xm, self.xm):
            b = self.box(x0 + dx, y0, x1 + dx, y1)
            X0, Y0, X1, Y1 = int(max(0, b[0])), int(max(0, b[1])), int(min(self.W, b[2])), int(min(self.H, b[3]))
            if X1 <= X0 or Y1 <= Y0: continue
            n = (Y1 - Y0) if vertical else (X1 - X0)
            ramp = np.linspace(k0, k1, n, dtype=np.float32)
            self.shade[Y0:Y1, X0:X1] *= ramp[:, None] if vertical else ramp[None, :]

    def finish(self, grime=0.10, cells=6):
        """apply the shade and a tileable grime noise to the colour; returns (rgba, lights) PIL images"""
        a = np.asarray(self.img).astype(np.float32)
        g = np.random.default_rng(self.rng.randrange(1 << 30))
        n = tileable_noise(g, self.W, self.H, cells, 5)
        fine = tileable_noise(g, self.W, self.H, 64, 2)                       # surface grain
        k = self.shade * (1 - grime + 2 * grime * n) * (0.94 + 0.12 * fine)
        a[..., :3] *= k[..., None]
        rgba = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
        if self.out_size != (self.W, self.H):
            # colour premultiplied before the resize (no dark fringes), the lights mask scaled with its id and kind
            # premultiplied by the pane coverage (the shader reads id = B / R, so blended edges keep their window's id)
            arr = np.asarray(rgba).astype(np.float32); al = arr[..., 3:4] / 255
            pre = Image.fromarray(np.concatenate([arr[..., :3] * al, arr[..., 3:4]], -1).astype(np.uint8), "RGBA").resize(self.out_size, Image.LANCZOS)
            q = np.asarray(pre).astype(np.float32); a2 = np.maximum(q[..., 3:4], 1) / 255
            rgba = Image.fromarray(np.concatenate([np.clip(q[..., :3] / a2, 0, 255), q[..., 3:4]], -1).astype(np.uint8), "RGBA")
            self.lit = self.lit.resize(self.out_size, Image.BOX)
        return rgba, self.lit


# ------------------------------------------------------------------ parts
def window(c, x, y, w, h, lit_kind=0, curtain=None, frame=FRAME, glass=GLASS_DAY, sliding=True):
    c.rect(x, y, x + w, y + h, frame)
    f = 0.05
    c.rect(x + f, y + f, x + w - f, y + h - f, glass)
    c.rect(x + f, y + h * 0.55, x + w - f, y + h - f, lerp(glass, (200, 212, 224), 0.35))   # the sky in the upper pane
    if curtain:
        c.rect(x + f, y + f, x + w * 0.5 - f, y + h - f, curtain, 215)
        c.rect(x + w * 0.5 + f, y + f, x + w - f, y + h - f, curtain, 215)
    if sliding:
        c.rect(x + w * 0.5 - 0.02, y + f, x + w * 0.5 + 0.02, y + h - f, frame)
    c.darken(x + f, y + h - 0.3, x + w - f, y + h - f, 0.72, 1.0)                 # the reveal's shadow on the glass
    c.rect(x - 0.04, y - 0.06, x + w + 0.04, y, (206, 204, 198))                    # the sill
    for i in range(2):                                                              # weathering streaks below the sill
        sx = x + 0.1 + (w - 0.2) * (0.15 + 0.7 * ((i * 7 + int(x * 13)) % 5) / 4)
        c.darken(sx, y - 0.9 - 0.3 * i, sx + 0.06, y - 0.06, 1.0, 0.86)
    c.light(x + f, y + f, x + w - f, y + h - f, lit_kind)


def ac_unit(c, x, y, w=0.78, h=0.56):
    c.rect(x, y, x + w, y + h, (222, 222, 218))
    c.rect(x + w * 0.62, y + h * 0.1, x + w - 0.05, y + h * 0.9, (196, 196, 192))
    for i in range(5):                                           # the grille
        yy = y + h * (0.2 + 0.14 * i)
        c.rect(x + 0.06, yy, x + w * 0.58, yy + 0.02, (170, 170, 168))
    c.rect(x, y - 0.03, x + w, y, (120, 120, 118))               # its bracket


def laundry(c, x, y, w, rng, pole=True):
    """items hanging from a pole at height y, spread over w metres"""
    if pole:
        c.rect(x - 0.1, y - 0.02, x + w + 0.1, y + 0.02, (150, 150, 146))
    n = rng.randint(2, 5)
    cx = x + 0.15
    for _ in range(n):
        iw = rng.uniform(0.28, 0.55); ih = rng.uniform(0.45, 0.95)
        if cx + iw > x + w: break
        col = rng.choice(CLOTH)
        sag = rng.uniform(0.0, 0.06)
        c.poly([(cx, y - 0.04), (cx + iw, y - 0.04), (cx + iw - sag, y - ih), (cx + sag, y - ih)], col)
        c.rect(cx + 0.02, y - 0.02, cx + iw - 0.02, y + 0.03, (90, 90, 90))          # pegs
        cx += iw + rng.uniform(0.08, 0.22)


def futon(c, x, y, w, rng):
    """a duvet aired over the railing (very Tokyo): a thick pastel rectangle folded over the rail"""
    col = rng.choice(FUTON)
    c.rect(x, y - 0.75, x + w, y + 0.12, col)
    c.rect(x, y + 0.08, x + w, y + 0.12, shade(col, 0.82))
    for i in range(3):
        c.rect(x, y - 0.75 + 0.22 * i, x + w, y - 0.73 + 0.22 * i, shade(col, 0.9))


def plant(c, x, y, rng):
    c.rect(x, y, x + 0.28, y + 0.24, (150, 92, 70))
    for _ in range(5):
        c.ellipse(x + 0.14 + rng.uniform(-0.18, 0.18), y + 0.36 + rng.uniform(-0.1, 0.18), 0.14, 0.11, rng.choice([(60, 110, 52), (76, 130, 60), (50, 96, 48)]))


def balcony(c, x0, x1, y, kind, rng, under_shadow=0.7):
    """slab at y (the floor of the balcony), a railing above it, a soft shadow on the wall below"""
    c.darken(x0, y - 0.9, x1, y, under_shadow, 1.0)
    c.rect(x0, y - 0.18, x1, y, (176, 174, 170))                 # the slab
    c.rect(x0, y - 0.21, x1, y - 0.18, (120, 118, 116))
    if kind == "bars":
        c.rect(x0, y + 1.06, x1, y + 1.12, RAIL)
        n = int((x1 - x0) / 0.13)
        for i in range(n + 1):
            xx = x0 + (x1 - x0) * i / n
            c.rect(xx - 0.012, y, xx + 0.012, y + 1.08, RAIL)
    elif kind == "panel":
        c.rect(x0, y, x1, y + 1.0, (190, 198, 196), 235)
        c.rect(x0, y + 1.0, x1, y + 1.08, RAIL)
        c.rect(x0, y + 0.02, x1, y + 0.05, shade((190, 198, 196), 0.85))
    else:                                                       # concrete parapet
        c.rect(x0, y, x1, y + 1.1, (182, 178, 170))
        c.rect(x0, y + 1.1, x1, y + 1.16, (150, 146, 140))
        c.darken(x0, y, x1, y + 0.3, 0.88, 1.0)


def pipe(c, x, y0, y1, col=(128, 126, 122)):
    c.rect(x, y0, x + 0.09, y1, col)
    c.rect(x + 0.09, y0, x + 0.12, y1, shade(col, 0.7))


def water_tank(c, x, y):
    c.rect(x + 0.1, y, x + 1.3, y + 0.35, (110, 110, 110))        # frame legs
    c.rect(x, y + 0.35, x + 1.4, y + 1.5, (206, 206, 200))
    c.rect(x + 1.1, y + 0.35, x + 1.4, y + 1.5, (170, 170, 166))
    c.rect(x, y + 1.5, x + 1.4, y + 1.6, (150, 150, 148))


def antenna(c, x, y, h=1.6):
    c.rect(x - 0.02, y, x + 0.02, y + h, (90, 90, 92))
    for i in range(4):
        yy = y + h * (0.55 + 0.12 * i); w = 0.5 - 0.09 * i
        c.rect(x - w, yy, x + w, yy + 0.03, (90, 90, 92))


def stair_tower(c, x0, x1, y_base, floors, fh, rng):
    """an open exterior staircase: concrete, with the diagonal flights and small landing windows"""
    wall = (150, 150, 146)
    c.rect(x0, y_base, x1, y_base + floors * fh + 0.4, wall)
    for f in range(floors):
        y = y_base + f * fh
        c.poly([(x0 + 0.1, y + 0.1), (x1 - 0.1, y + fh - 0.3), (x1 - 0.1, y + fh - 0.05), (x0 + 0.1, y + 0.35)], (96, 96, 94))
        c.rect(x0 + 0.1, y + fh - 0.2, x1 - 0.1, y + fh - 0.12, (90, 90, 90))
        c.light(x0 + 0.25, y + fh - 1.0, x1 - 0.25, y + fh - 0.45, 200)        # a landing light, always on at night
        c.rect(x0 + 0.25, y + fh - 1.0, x1 - 0.25, y + fh - 0.45, (120, 124, 130))


def apartment_block(c, x0, w, floors, style, rng, fh=2.9, base=GROUND):
    """a Japanese low-rise apartment block ("manshon"): a street-side facade with a balcony per unit"""
    wall = WALLS[style]
    top = base + floors * fh + 0.55
    c.rect(x0, base, x0 + w, top, wall)
    if style.startswith("tile"):                                 # tile courses as faint lines
        for i in range(int((top - base) / 0.3)):
            c.rect(x0, base + 0.3 * i, x0 + w, base + 0.3 * i + 0.012, shade(wall, 0.88))
    if style == "brown":
        for i in range(int((top - base) / 0.22)):
            c.rect(x0, base + 0.22 * i, x0 + w, base + 0.22 * i + 0.012, shade(wall, 0.84))
    # one side a little darker: the facade has a slight return
    c.darken(x0, base, x0 + 0.5, top, 0.86, 1.0, vertical=False)
    # ground floor: pilotis parking (dark bays), an entrance, the meters
    gf = base + fh
    c.rect(x0, base, x0 + w, gf, shade(wall, 0.92))
    c.darken(x0, base, x0 + w, gf, 1.0, 0.75)
    nb = max(1, int(w / 3.0))
    for i in range(nb):
        bx = x0 + 0.35 + i * (w - 0.7) / nb
        bw = (w - 0.7) / nb - 0.35
        if i == nb // 2:                                         # the entrance: a glass door, lit all night
            c.rect(bx, base, bx + bw, gf - 0.5, (168, 176, 182))
            c.rect(bx + 0.1, base, bx + bw - 0.1, gf - 0.65, (96, 110, 124))
            c.light(bx + 0.15, base + 0.05, bx + bw - 0.15, gf - 0.7, 200)
        else:
            c.rect(bx, base, bx + bw, gf - 0.35, (40, 40, 44))     # a dark parking bay
            if rng.random() < 0.7:                               # a parked car, seen from behind
                cc = rng.choice([(150, 154, 160), (210, 212, 214), (60, 64, 72), (90, 100, 130)])
                c.rect(bx + bw * 0.2, base + 0.25, bx + bw * 0.8, base + 1.0, cc)
                c.poly([(bx + bw * 0.24, base + 1.0), (bx + bw * 0.76, base + 1.0), (bx + bw * 0.7, base + 1.45), (bx + bw * 0.3, base + 1.45)], shade(cc, 0.9))
                c.poly([(bx + bw * 0.27, base + 1.0), (bx + bw * 0.73, base + 1.0), (bx + bw * 0.68, base + 1.38), (bx + bw * 0.32, base + 1.38)], (44, 52, 66))
                c.rect(bx + bw * 0.22, base + 0.6, bx + bw * 0.3, base + 0.72, (120, 40, 40))
                c.rect(bx + bw * 0.7, base + 0.6, bx + bw * 0.78, base + 0.72, (120, 40, 40))
                c.rect(bx + bw * 0.22, base, bx + bw * 0.34, base + 0.3, (20, 20, 22))
                c.rect(bx + bw * 0.66, base, bx + bw * 0.78, base + 0.3, (20, 20, 22))
    # the stair tower on one side
    sw = 1.9
    stair_x = x0 if rng.random() < 0.5 else x0 + w - sw
    stair_tower(c, stair_x, stair_x + sw, gf, floors - 1, fh, rng)
    fx0, fx1 = (stair_x + sw, x0 + w) if stair_x == x0 else (x0, stair_x)
    # units: balconies with a sliding door and a small kitchen window
    units = max(1, int(round((fx1 - fx0) / 4.0)))
    uw = (fx1 - fx0) / units
    rail = rng.choice(["bars", "panel", "panel", "concrete"])
    for f in range(1, floors):
        y = gf + (f - 1) * fh
        for u in range(units):
            ux = fx0 + u * uw
            window(c, ux + 0.35, y + 0.25, min(1.8, uw * 0.48), 2.0, curtain=rng.choice([None, None, (236, 232, 222), (210, 214, 220)]))
            if uw > 3.2:
                window(c, ux + uw - 1.15, y + 1.2, 0.8, 0.9, sliding=False)
        balcony(c, fx0, fx1, y, rail, rng)
        for u in range(units):                                   # what sits on the balcony
            ux = fx0 + u * uw
            r = rng.random()
            if r < 0.45: ac_unit(c, ux + uw - 1.0, y + 0.05)
            if rng.random() < 0.38: laundry(c, ux + 0.3, y + 1.75, min(2.2, uw - 1.3), rng)
            elif rng.random() < 0.18: futon(c, ux + 0.35, y + 1.0, 1.5, rng)
            if rng.random() < 0.22: plant(c, ux + 0.35 + rng.uniform(0, 0.4), y + 0.02, rng)
    for i in range(units + 1):                                   # the balcony dividers
        xx = fx0 + i * uw
        if 0 < i < units:
            for f in range(1, floors):
                y = gf + (f - 1) * fh
                c.rect(xx - 0.03, y, xx + 0.03, y + 1.9, (160, 160, 156))
    pipe(c, x0 + w - 0.25 if stair_x == x0 else x0 + 0.15, base, top - 0.2)
    c.darken(x0, top - 0.5, x0 + w, top, 0.8, 1.0)                            # the parapet's shadow
    c.darken(x0 + w - 0.12, base, x0 + w, top, 1.0, 0.8, vertical=False)       # the far corner
    # roof: parapet, water tank, an antenna, a railing
    c.rect(x0, top, x0 + w, top + 0.12, shade(wall, 0.8))
    if rng.random() < 0.6: water_tank(c, x0 + rng.uniform(0.6, max(0.7, w - 2.2)), top + 0.1)
    if rng.random() < 0.7: antenna(c, x0 + rng.uniform(0.6, w - 0.6), top + 0.1)
    if rng.random() < 0.5:
        for i in range(int(w / 0.5)):
            xx = x0 + 0.25 + i * 0.5
            c.rect(xx - 0.012, top + 0.1, xx + 0.012, top + 1.0, RAIL)
        c.rect(x0, top + 1.0, x0 + w, top + 1.05, RAIL)
    return top


def tree(c, x, y_base, r, rng, trunk=True, h_scale=1.0):
    if trunk:
        c.rect(x - 0.12, y_base, x + 0.12, y_base + r * 1.3, (78, 60, 46))
    cy = y_base + r * 1.3 + r * 0.7 * h_scale
    greens = [(38, 62, 36), (50, 84, 42), (66, 104, 48), (84, 122, 56), (106, 140, 62), (128, 156, 70)]
    for i in range(30):                                          # the crown: big clusters, darker low down
        ang = rng.uniform(0, 2 * math.pi); rad = rng.uniform(0, r * 0.85)
        px, py = x + math.cos(ang) * rad, cy + math.sin(ang) * rad * 0.8 * h_scale
        k = min(4, int((py - (cy - r)) / (2 * r) * 5))
        c.ellipse(px, py, r * rng.uniform(0.25, 0.42), r * rng.uniform(0.22, 0.36), greens[max(0, k)])
    for i in range(220):                                         # leaf speckle: small lighter and darker tufts
        ang = rng.uniform(0, 2 * math.pi); rad = rng.uniform(0, r * 0.95) ** 0.8 * r ** 0.2
        px, py = x + math.cos(ang) * rad, cy + math.sin(ang) * rad * 0.8 * h_scale
        k = min(5, max(0, int((py - (cy - r)) / (2 * r) * 6) + rng.choice([-1, 0, 0, 1])))
        c.ellipse(px, py, r * rng.uniform(0.05, 0.11), r * rng.uniform(0.04, 0.09), greens[k])
    c.darken(x - r, cy - r * h_scale, x + r, cy - r * 0.3 * h_scale, 0.78, 1.0)   # the shaded underside


def utility_pole(c, x, y_base, top):
    c.rect(x - 0.17, y_base, x + 0.17, top, (150, 148, 144))
    c.rect(x + 0.08, y_base, x + 0.17, top, (118, 116, 112))
    for yy in (top - 0.5, top - 1.4):                            # cross-arms with insulators
        c.rect(x - 1.1, yy, x + 1.1, yy + 0.1, (110, 108, 104))
        for i in range(5):
            xx = x - 1.0 + 0.5 * i
            c.rect(xx - 0.06, yy + 0.1, xx + 0.06, yy + 0.32, (190, 190, 190))
    c.rect(x + 0.2, top - 2.8, x + 1.05, top - 1.9, (124, 124, 122))                 # the transformer
    c.rect(x + 0.25, top - 1.9, x + 1.0, top - 1.75, (96, 96, 94))
    c.rect(x - 0.9, top - 2.5, x - 0.2, top - 1.6, (124, 124, 122))                   # a second one
    c.rect(x + 0.17, y_base + 2.2, x + 0.3, y_base + 2.26, (90, 90, 90))              # the stay band


def cables(c, ys, sag, n_per_tile=1, width=0.035, col=(28, 28, 30), x0=0.0, x1=None):
    """catenaries from x0 to x1 (default: across the whole tile, meeting themselves at the seam)"""
    x1 = c.xm if x1 is None else x1
    for y in ys:
        pts = []
        for i in range(97):
            t = i / 96
            s = math.sin(math.pi * t * n_per_tile) ** 2
            pts.append((x0 + (x1 - x0) * t, y - sag * s))
        c.line(pts, col, width)


def street_lamp(c, x, y_base, h):
    c.rect(x - 0.06, y_base, x + 0.06, y_base + h, (120, 122, 126))
    c.poly([(x - 0.06, y_base + h - 0.05), (x + 0.7, y_base + h + 0.3), (x + 0.7, y_base + h + 0.4), (x - 0.06, y_base + h + 0.08)], (120, 122, 126))
    c.rect(x + 0.45, y_base + h + 0.2, x + 0.95, y_base + h + 0.42, (200, 200, 196))
    c.light(x + 0.47, y_base + h + 0.18, x + 0.93, y_base + h + 0.3, 100)             # always on, warm


def vending_machine(c, x, y_base, lit_kind=200):
    c.rect(x, y_base, x + 1.0, y_base + 1.85, (200, 36, 42))
    c.rect(x + 0.05, y_base + 1.05, x + 0.95, y_base + 1.75, (236, 240, 244))          # the lit display
    c.light(x + 0.07, y_base + 1.07, x + 0.93, y_base + 1.73, lit_kind)
    for i in range(3):                                           # cans, no labels
        for j in range(5):
            cx = x + 0.14 + 0.18 * j; cy = y_base + 1.14 + 0.22 * i
            c.rect(cx, cy, cx + 0.1, cy + 0.16, [(60, 120, 180), (220, 220, 220), (60, 160, 90), (240, 180, 60), (120, 80, 60)][(i + j) % 5])
    c.rect(x + 0.08, y_base + 0.25, x + 0.6, y_base + 0.55, (40, 40, 44))              # the flap
    c.rect(x + 0.7, y_base + 0.6, x + 0.9, y_base + 0.9, (40, 40, 44))


# ------------------------------------------------------------------ the cards
def house(c, hx0, hw, rng, eave_h=5.6, ridge_h=1.65, detail=True):
    """a two-storey Japanese house: siding, a pitched tile roof with its ridge, a balcony across the first floor"""
    eave = GROUND + eave_h
    wall = (222, 218, 206)
    c.rect(hx0, GROUND - 0.2, hx0 + hw, eave, wall)
    for i in range(int((eave - GROUND) / 0.2)):                  # siding lines
        c.rect(hx0, GROUND + 0.2 * i, hx0 + hw, GROUND + 0.2 * i + 0.014, shade(wall, 0.86))
    c.darken(hx0, GROUND, hx0 + 0.6, eave, 0.84, 1.0, vertical=False)
    ridge = eave + ridge_h
    roof = (74, 76, 82)
    c.poly([(hx0 - 0.45, eave - 0.05), (hx0 + hw + 0.45, eave - 0.05), (hx0 + hw / 2 + 0.6, ridge), (hx0 + hw / 2 - 0.6, ridge)], roof)
    for i in range(1, 9):                                        # the tile courses
        t = i / 9
        y = eave + (ridge - eave) * t
        x0 = hx0 - 0.45 + (hw / 2 - 0.15) * t; x1 = hx0 + hw + 0.45 - (hw / 2 - 0.15) * t
        c.rect(x0, y, x1, y + 0.03, shade(roof, 0.72))
    c.rect(hx0 + hw / 2 - 0.65, ridge, hx0 + hw / 2 + 0.65, ridge + 0.1, (56, 58, 62))
    c.rect(hx0 - 0.45, eave - 0.18, hx0 + hw + 0.45, eave - 0.05, (236, 236, 232))     # the gutter / fascia
    c.darken(hx0, eave - 0.7, hx0 + hw, eave - 0.05, 0.72, 1.0)
    f1 = GROUND + 2.9                                            # the first floor
    k = hw / 8.2
    window(c, hx0 + 0.9 * k, f1 + 0.3, 1.7, 1.9, curtain=(240, 236, 226))
    window(c, hx0 + 4.4 * k, f1 + 0.3, 1.7, 1.9, curtain=(214, 220, 228))
    if hw > 7: window(c, hx0 + 6.7 * k, f1 + 1.1, 0.8, 0.9, sliding=False)
    balcony(c, hx0 + 0.5 * k, hx0 + 6.5 * k, f1, "bars", rng, under_shadow=0.6)
    ac_unit(c, hx0 + 5.4 * k, f1 + 0.05)
    laundry(c, hx0 + 0.8 * k, f1 + 1.85, 2.9 * k, rng)
    if detail:
        futon(c, hx0 + 4.1 * k, f1 + 1.08, 1.6, rng)
        plant(c, hx0 + 0.75 * k, f1 + 0.04, rng)
    window(c, hx0 + 1.2 * k, GROUND + 0.9, 1.5, 1.4, curtain=(228, 226, 220))
    c.rect(hx0 + 4.0 * k, GROUND, hx0 + 5.0 * k, GROUND + 2.1, (96, 78, 64))           # the door
    c.rect(hx0 + 4.1 * k, GROUND + 1.2, hx0 + 4.9 * k, GROUND + 2.0, (160, 170, 180))
    c.light(hx0 + 4.12 * k, GROUND + 1.22, hx0 + 4.88 * k, GROUND + 1.98, 0)
    c.rect(hx0 + 6.2 * k, GROUND + 1.3, hx0 + 6.55 * k, GROUND + 1.75, (200, 200, 196))   # meter box
    pipe(c, hx0 + hw - 0.35, GROUND, eave - 0.2, (190, 188, 182))
    c.darken(hx0, GROUND, hx0 + hw, GROUND + 0.6, 1.0, 0.7)
    return ridge


def card_near(rng):
    c = Card("near", 1024, 1024, 16.0, -9.0, 7.0, rng)
    # the house across the lane (x 1.4..9.6), then the coin parking lot's wall to the tile's end (what the overview sees)
    hx0, hw = 1.4, 8.2
    house(c, hx0, hw, rng, eave_h=6.0)
    # the block wall along the lane (in front of the house's garden), the gate
    c.rect(0.0, GROUND, 1.2, GROUND + 1.25, (172, 170, 162))
    c.rect(0.0, GROUND + 1.25, 1.2, GROUND + 1.33, (150, 148, 142))
    c.rect(hx0 + hw + 0.2, GROUND, 16.0, GROUND + 1.25, (172, 170, 162))               # the lot's wall, to the seam
    c.rect(hx0 + hw + 0.2, GROUND + 1.25, 16.0, GROUND + 1.33, (150, 148, 142))
    c.rect(10.2, GROUND, 11.2, GROUND + 1.2, (110, 112, 116))                           # a gate
    # the lot's corner: a vending machine against the house, a street lamp, the utility pole with its cables
    vending_machine(c, hx0 + hw + 0.35, GROUND)
    street_lamp(c, 10.6, GROUND, 5.6)
    utility_pole(c, 12.3, GROUND - 0.2, GROUND + 10.4)
    cables(c, [GROUND + 9.0, GROUND + 9.35, GROUND + 9.7], 0.45, 1, width=0.03)
    cables(c, [GROUND + 8.3], 0.3, 2, width=0.022)
    # a tree in the garden on the far side of the house (behind its left end, where no default camera looks)
    tree(c, 0.6, GROUND, 2.3, rng)
    rgba, lit = c.finish(grime=0.08)
    return rgba, lit


def card_mid(rng):
    c = Card("mid", 2048, 1024, 48.0, -10.0, 14.0, rng)
    # blocks from x = 1 to 20 and 28 to 47; the gap 20..28 shows the elevated railway and the far card
    # (what the page's overview camera sees is around x 39..42: a low house there, the far skyline and the sky above it)
    layout = [(1.0, 10.2, 5, "tile_grey"), (12.4, 7.6, 3, "tile_beige"), (28.4, 5.8, 3, "brown")]
    for x0, w, floors, style in layout:
        apartment_block(c, x0, w, floors, style, rng)
    apartment_block(c, 41.2, 6.4, 4, "white", rng)                 # its roof is the skyline the overview camera sees
    c.rect(34.3, GROUND, 41.0, GROUND + 1.1, (168, 166, 160)); c.rect(34.3, GROUND + 1.1, 41.0, GROUND + 1.16, (140, 138, 132))
    # the alleys between blocks: small trees at street level (their crowns stay below his eye line), a wall
    tree(c, 20.7, GROUND, 1.5, rng)
    tree(c, 27.6, GROUND, 1.3, rng)
    tree(c, 47.9, GROUND, 1.5, rng)
    tree(c, 35.2, GROUND, 1.2, rng)
    c.rect(19.9, GROUND, 28.7, GROUND + 1.0, (168, 166, 160))
    c.rect(19.9, GROUND + 1.0, 28.7, GROUND + 1.06, (140, 138, 132))
    # the viaduct of the elevated railway, seen in the two gaps: concrete piers and the deck; the trains are drawn by the shader
    deck = GROUND + 7.6
    for ga, gb in ((20.0, 28.4), (34.2, 41.0)):
        c.rect(ga, deck, gb, deck + 0.9, (164, 160, 152))
        c.rect(ga, deck + 0.9, gb, deck + 1.7, (150, 148, 142), 110)                 # the sound barrier (translucent above)
        c.rect(ga, deck + 0.9, gb, deck + 1.0, (120, 118, 112))
        c.darken(ga, deck, gb, deck + 0.9, 0.7, 0.9)
        for px_ in (ga + 1.8, gb - 1.6):
            c.rect(px_, GROUND, px_ + 0.9, deck, (158, 154, 146))
            c.darken(px_, GROUND, px_ + 0.9, deck, 0.8, 1.0, vertical=False)
        for xx in (ga + 0.6, gb - 0.7):                           # two catenary masts per gap
            c.rect(xx, deck + 1.7, xx + 0.08, deck + 5.2, (70, 70, 72))
    # a lit shop front on the ground floor of the beige block (a generic konbini-like glass front, no signs)
    sx = 13.4
    c.rect(sx, GROUND, sx + 5.6, GROUND + 2.6, (234, 236, 238))
    c.rect(sx + 0.15, GROUND + 0.1, sx + 5.45, GROUND + 2.45, (196, 206, 214))
    c.light(sx + 0.2, GROUND + 0.15, sx + 5.4, GROUND + 2.4, 200)
    c.rect(sx, GROUND + 2.6, sx + 5.6, GROUND + 3.0, (56, 100, 160))                   # a plain colour band, no text
    rgba, lit = c.finish(grime=0.10, cells=8)
    return rgba, lit


def card_far(rng):
    c = Card("far", 2048, 256, 280.0, -9.0, 41.0, rng)
    c.rect(0, -9.0, 280, GROUND + 1.2, (150, 158, 172))              # the far ground, opaque: nothing shows through the roofs
    # the sea of small roofs: hundreds of little houses, each a wall and a roof, lighter and bluer with distance
    for row in range(6):
        y = GROUND + 0.4 + row * 0.95
        k = row / 5
        x = rng.uniform(0, 2.0)
        while x < 280:
            w = rng.uniform(4.0, 9.0); h = rng.uniform(2.2, 3.6)
            wall = lerp(rng.choice([(214, 208, 196), (196, 194, 190), (226, 222, 214), (170, 160, 150)]), (160, 172, 190), k * 0.5)
            roof = lerp(rng.choice([(80, 82, 88), (96, 74, 64), (70, 76, 84), (120, 112, 104)]), (150, 162, 182), k * 0.5)
            c.rect(x, y, x + w, y + h * 0.65, wall)
            c.poly([(x - 0.2, y + h * 0.6), (x + w + 0.2, y + h * 0.6), (x + w * 0.5, y + h)], roof)
            if rng.random() < 0.6:
                c.light(x + w * 0.3, y + h * 0.2, x + w * 0.5, y + h * 0.45, 0)
            x += w + rng.uniform(0.3, 2.5)
    # mid-rise blocks behind the roofs
    x = 3.0
    while x < 276:
        w = rng.uniform(14, 30); fl = rng.randint(3, 7)
        if x + w > 168 and x < 216:                              # kept low where the overview camera looks (sky and one tower)
            x = 216.0; continue
        top = GROUND + 4.5 + fl * 1.7
        col = lerp(rng.choice(list(WALLS.values())), (170, 182, 200), 0.45)
        c.rect(x, GROUND + 3.0, x + w, top, col)
        c.darken(x, GROUND + 3.0, x + 0.3 * w, top, 0.9, 1.0, vertical=False)
        for f in range(fl):                                      # rows of windows, as a lights grid
            y = GROUND + 5.0 + f * 1.7
            n = int(w / 2.2)
            for i in range(n):
                xx = x + 0.6 + i * 2.2
                c.rect(xx, y, xx + 1.2, y + 0.9, (120, 134, 150))
                if rng.random() < 0.7: c.light(xx, y, xx + 1.2, y + 0.9, 0)
        x += w + rng.uniform(4, 22)
    # a few towers, far away (generic office towers and one slender mast; no landmark is copied)
    for tx, tw, th, kind in ((38, 9, 36, "office"), (96, 12, 28, "office"), (142, 3, 44, "mast"), (190, 14, 40, "office"), (236, 10, 33, "office")):
        top = GROUND + th
        col = (176, 188, 206)
        if kind == "office":
            c.rect(tx, GROUND + 2, tx + tw, top, col)
            c.darken(tx, GROUND + 2, tx + tw * 0.4, top, 0.9, 1.0, vertical=False)
            for f in range(int((th - 4) / 1.5)):
                y = GROUND + 4 + f * 1.5
                c.rect(tx + 0.4, y, tx + tw - 0.4, y + 0.7, (132, 148, 168))
                if rng.random() < 0.75: c.light(tx + 0.4, y, tx + tw - 0.4, y + 0.7, 0)
            c.rect(tx + tw * 0.5 - 0.15, top, tx + tw * 0.5 + 0.15, top + 2.2, (120, 126, 136))
            c.light(tx + tw * 0.5 - 0.3, top + 1.9, tx + tw * 0.5 + 0.3, top + 2.3, 50)   # red aviation light
        else:
            c.poly([(tx - 0.6, GROUND + 2), (tx + tw + 0.6, GROUND + 2), (tx + tw * 0.5 + 0.35, top), (tx + tw * 0.5 - 0.35, top)], col)
            c.rect(tx + tw * 0.5 - 2.2, GROUND + 24, tx + tw * 0.5 + 2.2, GROUND + 25.6, lerp(col, (120, 130, 150), 0.4))
            c.rect(tx + tw * 0.5 - 0.1, top, tx + tw * 0.5 + 0.1, top + 3.5, (120, 126, 136))
            c.light(tx + tw * 0.5 - 0.4, top + 3.0, tx + tw * 0.5 + 0.4, top + 3.6, 50)
            c.light(tx + tw * 0.5 - 2.0, GROUND + 24.2, tx + tw * 0.5 + 2.0, GROUND + 25.4, 200)
    rgba, lit = c.finish(grime=0.05, cells=10)
    return rgba, lit


def card_ground(rng):
    """the street plane seen from above: u along the window, v = depth from the glass. 24 x 24 m, tileable."""
    W = 1024
    c = Card("ground", W, W, 24.0, 0.0, 24.0, rng)              # y here is the depth
    c.rect(0, 0, 24, 24, (72, 72, 74))                            # asphalt
    # the lane right under the window (depth 0..7): asphalt with a gutter and a kerb at the lot's edge
    c.rect(0, 6.6, 24, 6.9, (150, 150, 146))                      # the kerb
    c.rect(0, 6.9, 24, 7.6, (120, 120, 118))                      # the wall's footing / sidewalk
    c.rect(0, 0.0, 24, 0.5, (58, 58, 60))                         # the gutter
    # the coin parking lot (depth 7.6 .. 14.5): bays 2.5 m wide, white lines, a few cars seen from above
    lot0, lot1 = 7.6, 14.5
    c.rect(0, lot0, 24, lot1, (84, 84, 86))
    for i in range(10):
        x = 0.3 + i * 2.5
        c.rect(x - 0.06, lot0 + 0.4, x + 0.06, lot1 - 0.6, (214, 214, 206))
    c.rect(0.24, lot1 - 0.72, 22.86, lot1 - 0.6, (214, 214, 206))
    cars = [(1, (236, 236, 232)), (3, (40, 42, 48)), (4, (150, 154, 160)), (7, (46, 58, 96)), (8, (226, 228, 230))]
    for bay, col in cars:
        x = 0.3 + bay * 2.5 + 0.4
        y = lot0 + 0.9
        c.rect(x + 0.08, y + 0.08, x + 1.78, y + 4.48, (30, 30, 32), 120)    # the shadow
        c.rect(x, y, x + 1.7, y + 4.4, col)
        c.rect(x + 0.12, y + 1.0, x + 1.58, y + 1.7, (40, 48, 60))          # rear glass
        c.rect(x + 0.12, y + 1.7, x + 1.58, y + 3.0, shade(col, 0.92))       # roof
        c.rect(x + 0.12, y + 3.0, x + 1.58, y + 3.9, (50, 60, 76))          # windscreen
        c.rect(x + 0.2, y + 3.95, x + 1.5, y + 4.3, shade(col, 0.85))        # bonnet
    # the pay machine and the sign post (a blank post, no text), a bicycle
    c.rect(22.0, lot0 + 0.3, 22.6, lot0 + 0.9, (220, 160, 40))
    c.rect(20.9, lot0 + 5.2, 21.0, lot0 + 6.9, (120, 120, 120))            # a bike, from above
    c.ellipse(20.95, lot0 + 5.3, 0.2, 0.3, (40, 40, 40)); c.ellipse(20.95, lot0 + 6.8, 0.2, 0.3, (40, 40, 40))
    # the road beyond the lot (depth 14.5 .. 18): a sidewalk, the road, a crosswalk
    c.rect(0, lot1, 24, lot1 + 1.2, (156, 152, 146))               # sidewalk (tiles)
    for i in range(48):
        c.rect(i * 0.5, lot1, i * 0.5 + 0.02, lot1 + 1.2, (130, 126, 120))
    c.rect(0, lot1 + 1.2, 24, 24, (64, 64, 66))                    # the road
    c.rect(0, lot1 + 2.7, 24, 2.75 + lot1, (200, 200, 190))        # centre line
    for i in range(0, 24, 2):                                     # dashed
        c.rect(i, lot1 + 2.6, i + 1.0, lot1 + 2.85, (64, 64, 66))
    for i in range(6):                                            # a crosswalk
        c.rect(14.0 + i * 0.9, lot1 + 1.3, 14.45 + i * 0.9, lot1 + 3.9, (206, 206, 198))
    c.rect(0, lot1 + 4.0, 24, lot1 + 5.2, (156, 152, 146))         # the far sidewalk
    # manholes, drains, a parked car on the road
    c.ellipse(5.0, 3.5, 0.35, 0.35, (52, 52, 54)); c.ellipse(5.0, 3.5, 0.3, 0.3, (82, 82, 84))
    c.rect(11.4, lot1 + 1.3, 13.1, lot1 + 5.6, (30, 30, 32), 100)
    c.rect(11.3, lot1 + 1.25, 13.0, lot1 + 5.55, (200, 60, 50))
    c.rect(11.42, lot1 + 2.3, 12.88, lot1 + 3.0, (40, 48, 60)); c.rect(11.42, lot1 + 3.0, 12.88, lot1 + 4.3, (182, 54, 46))
    c.rect(11.42, lot1 + 4.3, 12.88, lot1 + 5.1, (50, 60, 76))
    rgba, lit = c.finish(grime=0.12, cells=12)
    return rgba, lit


def noise_tex(rng):
    """R: fbm for the clouds; G: rain streaks; B, A: the refraction offset of raindrops on the glass (128 = none)"""
    S = 256
    r = tileable_noise(rng, S, S, 4, 5, 0.55)
    r = (r - r.min()) / (r.max() - r.min())
    g = np.zeros((S, S), np.float32)                              # sparse thin streaks, fading in along their length
    for _ in range(46):
        x0 = int(rng.uniform(0, S)); y0 = int(rng.uniform(0, S)); ln = int(rng.uniform(40, 170)); wd = 1 if rng.random() < 0.7 else 2
        for k in range(ln):
            v = (k / ln) ** 0.6 * rng.uniform(0.8, 1.0)
            for j in range(wd):
                g[(y0 + k) % S, (x0 + j) % S] = max(g[(y0 + k) % S, (x0 + j) % S], v)
    ox = np.zeros((S, S), np.float32); oy = np.zeros((S, S), np.float32)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    for _ in range(34):
        cx, cy = rng.uniform(0, S), rng.uniform(0, S); rad = rng.uniform(3, 10)
        for dx in (-S, 0, S):
            for dy in (-S, 0, S):
                px, py = xx - (cx + dx), yy - (cy + dy)
                d = np.sqrt(px * px + py * py) / rad
                m = np.clip(1 - d, 0, 1)
                prof = np.sin(np.pi * np.clip(d, 0, 1)) * (0.4 + 0.6 * m)   # a lens: no bend at the centre, soft at the rim
                ox += np.where(d < 1, px / rad * prof, 0); oy += np.where(d < 1, py / rad * prof, 0)
    ox = np.clip(ox, -1, 1); oy = np.clip(oy, -1, 1)
    tex = np.stack([r, g, 0.5 + 0.5 * ox, 0.5 + 0.5 * oy], -1)
    return Image.fromarray((tex * 255).astype(np.uint8), "RGBA")


def build(preview=False):
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    files = {}
    made = {}
    for name, fn in (("near", card_near), ("mid", card_mid), ("far", card_far), ("ground", card_ground)):
        rgba, lit = fn(random.Random(rng.randrange(1 << 30)))
        rgba.save(OUT / f"{name}.webp", "WEBP", quality=QUALITY, method=6)
        files[f"{name}.webp"] = (OUT / f"{name}.webp").stat().st_size
        made[name] = rgba
        if name != "ground":
            lit.save(OUT / f"{name}_l.webp", "WEBP", lossless=True, method=6)
            files[f"{name}_l.webp"] = (OUT / f"{name}_l.webp").stat().st_size
            made[name + "_l"] = lit
    nz = noise_tex(np.random.default_rng(SEED))
    nz.save(OUT / "noise.webp", "WEBP", lossless=True, method=6)
    files["noise.webp"] = (OUT / "noise.webp").stat().st_size
    made["noise"] = nz
    total = sum(files.values())
    for k, v in files.items():
        print(f"{k:<14} {v / 1024:7.1f} KB")
    print(f"{'total':<14} {total / 1024:7.1f} KB  (budget {BUDGET / 1024:.0f} KB)")
    if preview:
        out = ROOT / "room_build" / "out"; out.mkdir(exist_ok=True)
        sheet = Image.new("RGB", (2048, 1024 + 1024 + 256 + 20 * 3), (30, 30, 34))
        bg = Image.new("RGBA", made["mid"].size, (120, 160, 210, 255)); bg.alpha_composite(made["mid"]); sheet.paste(bg.convert("RGB"), (0, 0))
        y = 1024 + 20
        bg = Image.new("RGBA", made["near"].size, (120, 160, 210, 255)); bg.alpha_composite(made["near"]); sheet.paste(bg.convert("RGB"), (0, y))
        sheet.paste(made["ground"].convert("RGB"), (1024, y))
        y += 1024 + 20
        bg = Image.new("RGBA", made["far"].size, (120, 160, 210, 255)); bg.alpha_composite(made["far"]); sheet.paste(bg.convert("RGB"), (0, y))
        sheet.save(out / "window_cards.png")
        made["mid_l"].save(out / "window_mid_l.png"); made["noise"].save(out / "window_noise.png")
        print(f"preview: {out / 'window_cards.png'}")
    return files


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    f = build(a.preview)
    if sum(f.values()) > BUDGET:
        print("OVER BUDGET", file=sys.stderr); sys.exit(1)
