#!/usr/bin/env python3
"""THE OCEAN IS MORE TERRIFYING THAN YOU THINK - picture.

Still plates (plates/*.jpg) are animated in code: camera moves, light that travels over the
subject, local warps (water, lure, arms, fins), drifting marine snow with depth of field,
light shafts, bloom and sensor noise. Compositing is done in linear light, frames go to ffmpeg.

  python3 render.py --scale 1.0                    # 2160x3840 master  -> build/picture_2160.mp4
  python3 render.py --scale 0.5                    # 1080x1920 draft   -> build/picture_1080.mp4
  python3 render.py --scale 0.25 --stills 1 5 9.5  # preview frames    -> preview/
  python3 render.py --scale 0.125 --sheet 0 62 48  # contact sheet     -> preview/sheet.jpg
"""
import argparse
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import timeline as TL

HERE = TL.HERE
FPS = TL.FPS
FONT_DIR = "/usr/share/fonts/opentype/inter/"
OPT = {"hud": True, "title": True, "subs": True}

W = H = LW = LH = QW = QH = 0
S = PS = 1.0
GX = GY = VIG = None
NOISE = []
GRAIN = []
SNOW_COL = np.array([0.80, 0.90, 1.00], np.float32)
BLUE, CYAN = TL.BLUE, TL.CYAN


# ----------------------------------------------------------------------------- helpers
def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def smoother(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)


def ramp(t, a, b):
    return smooth((t - a) / (b - a))


def lerp(a, b, k):
    return a + (b - a) * k


def sstep(x, a, b):
    y = np.clip((x - a) / (b - a), 0, 1)
    return y * y * (3 - 2 * y)


def n1(t, seed):
    a = seed * 1.731
    return 0.5 * math.sin(t * 1.9 + a) + 0.3 * math.sin(t * 4.3 + 2.1 * a) + 0.2 * math.sin(t * 7.7 + 0.7 * a)


def drift(t, seed):
    """Slow float of a hovering vehicle: (dx, dy, roll), each roughly -1..1."""
    a = seed * 1.731
    dx = 0.5 * math.sin(t * 0.61 + a) + 0.3 * math.sin(t * 1.13 + 2.1 * a) + 0.2 * math.sin(t * 0.29 + 0.7 * a)
    dy = 0.5 * math.sin(t * 0.53 + 1.3 * a + 1) + 0.3 * math.sin(t * 0.97 + 0.4 * a + 2) + 0.2 * math.sin(t * 0.23 + a + 4)
    r = 0.6 * math.sin(t * 0.41 + 0.9 * a + 3) + 0.4 * math.sin(t * 0.83 + 1.7 * a)
    return dx, dy, r


def make_noise(n, beta, seed):
    """Tileable 1/f^beta noise, ~N(0,1)."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((n, n)))
    fx = np.fft.fftfreq(n)[:, None]
    fy = np.fft.fftfreq(n)[None, :]
    k = np.sqrt(fx * fx + fy * fy)
    k[0, 0] = 1
    f /= k ** beta
    f[0, 0] = 0
    x = np.real(np.fft.ifft2(f))
    return ((x - x.mean()) / x.std()).astype(np.float32)


def noise2(i, u, v):
    """Sample noise texture i at (u, v) given in texture periods."""
    n = NOISE[i]
    N = n.shape[0]
    mx = (np.mod(u, 1.0) * N).astype(np.float32)
    my = (np.mod(v, 1.0) * N).astype(np.float32)
    return cv2.remap(n, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def rad2(x0, y0):
    """Squared distance to (x0, y0) on the low-res screen grid, in units of W."""
    return np.square(GX - x0) + np.square((GY - y0) * (H / W))


def up(a, interp=cv2.INTER_CUBIC):
    return cv2.resize(a, (W, H), interpolation=interp)


def setup(scale):
    global W, H, S, LW, LH, QW, QH, GX, GY, PS, NOISE, GRAIN, VIG
    W = int(round(2160 * scale / 2)) * 2
    H = int(round(3840 * scale / 2)) * 2
    S = W / 2160.0
    LW, LH = max(16, W // 8), max(16, H // 8)
    QW, QH = max(16, W // 4), max(16, H // 4)
    gx = (np.arange(LW, dtype=np.float32) + 0.5) / LW
    gy = (np.arange(LH, dtype=np.float32) + 0.5) / LH
    GX, GY = np.meshgrid(gx, gy)
    PS = 1.0 if scale >= 0.45 else (0.5 if scale >= 0.2 else 0.25)
    NOISE = [make_noise(512, 1.7, 100 + i) for i in range(6)]
    rng = np.random.default_rng(7)
    GRAIN = [np.clip(rng.standard_normal((H, W), dtype=np.float32) * 32, -127, 127).astype(np.int8) for _ in range(5)]
    VIG = (1 - 0.36 * np.clip(rad2(0.5, 0.5) / (0.25 + (0.5 * H / W) ** 2), 0, 1) ** 1.3).astype(np.float32)
    PLATES.clear()
    SNOWS.clear()
    SPRITES.clear()


# ----------------------------------------------------------------------------- plates
def grade_twilight(x):
    l = x.mean(2, keepdims=True)
    x = l + (x - l) * 0.72
    return x * np.array([0.50, 0.56, 0.62], np.float32)


def grade_trench_wall(x):
    h, w = x.shape[:2]
    gx = np.meshgrid((np.arange(w, dtype=np.float32) + 0.5) / w, np.arange(h, dtype=np.float32))[0]
    r, b = x[:, :, 0], x[:, :, 2]
    wm = sstep((b - r) / (b + 0.05), 0.50, 0.75) * sstep(gx, 0.36, 0.46)   # open water: blue, right of the wall
    wm = cv2.GaussianBlur(wm, (0, 0), max(1.5, 5.0 * w / 1152.0))
    return x * (1 - 0.66 * wm[:, :, None])


def grade_abyss(x):
    return np.clip((x - 0.02) * 1.02, 0, 1) * np.array([0.94, 0.98, 1.04], np.float32)


PLATE_OPTS = {
    "surface": dict(sharpen=0.55),
    "twilight": dict(sharpen=0.5, grade=grade_twilight),
    "trench_wall": dict(sharpen=0.6, grade=grade_trench_wall),
    "trench_deep": dict(sharpen=0.6, grade=lambda x: x * (1.0 - 0.28 * x)),
    "abyss": dict(sharpen=0.6, grade=grade_abyss),
    "angler_wide": dict(sharpen=0.35),
    "angler_close": dict(sharpen=0.35),
    "squid_wide": dict(sharpen=0.35),
    "squid_eye": dict(sharpen=0.35, grade=lambda x: x * 0.92),
}
PLATES = {}


class Plate:
    def __init__(self, name):
        o = PLATE_OPTS.get(name, {})
        bgr = cv2.imread(os.path.join(HERE, "plates", name + ".jpg"), cv2.IMREAD_COLOR)
        if bgr is None:
            raise FileNotFoundError(name)
        if PS != 1.0:
            bgr = cv2.resize(bgr, None, fx=PS, fy=PS, interpolation=cv2.INTER_AREA)
        x = np.ascontiguousarray(bgr[:, :, ::-1]).astype(np.float32) / 255.0
        sh = o.get("sharpen", 0.4)
        if sh:
            x = np.clip(x + sh * (x - cv2.GaussianBlur(x, (0, 0), 1.3 * max(PS, 0.5))), 0, 1)
        if o.get("grade"):
            x = np.clip(o["grade"](x), 0, 1).astype(np.float32)
        self.h, self.w = x.shape[:2]
        self.lin = np.square(x)                       # gamma 2.0 working space
        self.px = self.w / 1536.0                     # warp amplitudes are given for a 1536 px wide plate
        lw, lh = max(8, self.w // 8), max(8, self.h // 8)
        self.lgx, self.lgy = np.meshgrid((np.arange(lw, dtype=np.float32) + 0.5) / lw,
                                         (np.arange(lh, dtype=np.float32) + 0.5) / lh)
        self.gx, self.gy = np.meshgrid(np.arange(self.w, dtype=np.float32), np.arange(self.h, dtype=np.float32))
        self.aux = {}

    def warp(self, dx, dy, src=None, border=cv2.BORDER_REPLICATE):
        """out(x, y) = src(x + dx, y + dy); dx, dy are low-res fields in plate px."""
        dx = cv2.resize(dx.astype(np.float32), (self.w, self.h), interpolation=cv2.INTER_CUBIC)
        dy = cv2.resize(dy.astype(np.float32), (self.w, self.h), interpolation=cv2.INTER_CUBIC)
        return cv2.remap(self.lin if src is None else src, self.gx + dx, self.gy + dy, cv2.INTER_LINEAR,
                         borderMode=border)

    def bumps(self, items):
        """Sum of soft local shifts: (cx, cy, rx, ry, ax, ay); a positive ax moves the feature right."""
        dx = np.zeros_like(self.lgx)
        dy = np.zeros_like(self.lgx)
        for cx, cy, rx, ry, ax, ay in items:
            w = np.exp(-(np.square((self.lgx - cx) / rx) + np.square((self.lgy - cy) / ry)))
            dx -= w * ax * self.px
            dy -= w * ay * self.px
        return dx, dy


def plate(name):
    if name not in PLATES:
        PLATES[name] = Plate(name)
    return PLATES[name]


def view(img, cx, cy, zoom, rot=0.0, border=cv2.BORDER_REPLICATE):
    """Camera: plate point (cx, cy) (normalised) lands on the frame centre."""
    ph, pw = img.shape[:2]
    s = max(W / pw, H / ph) * zoom
    cr, sr = math.cos(rot), math.sin(rot)
    a, b = cr / s, sr / s
    M = np.array([[a, b, cx * pw - a * W / 2 - b * H / 2],
                  [-b, a, cy * ph + b * W / 2 - a * H / 2]], np.float64)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP, borderMode=border)


def to_screen(px, py, cx, cy, zoom, rot, pl):
    """Plate point (normalised) -> screen position (normalised)."""
    s = max(W / pl.w, H / pl.h) * zoom
    dx, dy = (px - cx) * pl.w, (py - cy) * pl.h
    cr, sr = math.cos(rot), math.sin(rot)
    return (W / 2 + s * (cr * dx - sr * dy)) / W, (H / 2 + s * (sr * dx + cr * dy)) / H


# ----------------------------------------------------------------------------- particles and glows
def splat(buf, x, y, v):
    h, w = buf.shape
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = x - x0
    fy = y - y0
    for ox, oy, wgt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xi = x0 + ox
        yi = y0 + oy
        m = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
        np.add.at(buf, (yi[m], xi[m]), (v * wgt)[m].astype(np.float32))


class Snow:
    """Marine snow in three depth layers plus a few out-of-focus flakes close to the lens."""
    LAYERS = [  # n, buffer divisor, sigma (buffer px at 4K), brightness range, parallax range
        (1100, 1, 1.25, (0.03, 0.20), (0.25, 0.60)),
        (320, 2, 1.70, (0.06, 0.36), (0.70, 1.30)),
        (60, 4, 3.20, (0.05, 0.22), (1.60, 2.40)),
    ]

    def __init__(self, seed, density=1.0):
        rng = np.random.default_rng(seed)
        self.layers = []
        for n, div, sig, br, zr in self.LAYERS:
            n = max(4, int(n * density))
            self.layers.append(dict(
                div=div, sig=sig,
                p=rng.random((n, 2)).astype(np.float32),
                z=rng.uniform(zr[0], zr[1], n).astype(np.float32),
                b=(rng.random(n) ** 2.2 * (br[1] - br[0]) + br[0]).astype(np.float32),
                ph=rng.uniform(0, 6.283, n).astype(np.float32),
                tw=rng.uniform(0.3, 1.6, n).astype(np.float32),
                dr=(rng.normal(0, 1, (n, 2)) * np.array([0.004, 0.003])).astype(np.float32),
                wa=rng.uniform(0.001, 0.004, n).astype(np.float32),
                wf=rng.uniform(0.15, 0.5, n).astype(np.float32)))
        nb = max(3, int(8 * density))
        self.bok = dict(p=rng.random((nb, 2)), z=rng.uniform(3.0, 4.5, nb), r=rng.uniform(0.012, 0.03, nb),
                        b=rng.uniform(0.010, 0.032, nb), dr=rng.normal(0, 1, (nb, 2)) * 0.006)

    @staticmethod
    def _place(p, z, pan, zoom):
        q = p + z[:, None] * np.asarray(pan, np.float32)[None, :]
        q = np.mod(q, 1.0) * 1.5 - 0.25
        return 0.5 + (q - 0.5) * (1.0 + (zoom - 1.0) * np.minimum(z, 2.0)[:, None])

    def render(self, t, pan=(0.0, 0.0), zoom=1.0, mb=(0.0, 0.0), bokeh=True):
        out = np.zeros((H, W), np.float32)
        for L in self.layers:
            w, h = W // L["div"], H // L["div"]
            p = L["p"] + L["dr"] * t
            p[:, 0] += L["wa"] * np.sin(L["ph"] + t * L["wf"] * 6.283)
            p[:, 1] += L["wa"] * np.cos(L["ph"] * 1.7 + t * L["wf"] * 5.1)
            q = self._place(p, L["z"], pan, zoom)
            b = L["b"] * (0.72 + 0.28 * np.sin(L["ph"] * 3.1 + t * L["tw"] * 2.0))
            sig = L["sig"] * S
            zm = float(L["z"].mean())
            sx = math.hypot(sig, abs(mb[0]) * zm * w * 0.45)
            sy = math.hypot(sig, abs(mb[1]) * zm * h * 0.45)
            buf = np.zeros((h, w), np.float32)
            splat(buf, q[:, 0] * w - 0.5, q[:, 1] * h - 0.5, b * (2 * math.pi * sig * sig))
            if max(sx, sy) >= 0.5:
                buf = cv2.GaussianBlur(buf, (0, 0), sigmaX=max(sx, 0.3), sigmaY=max(sy, 0.3))
            if L["div"] > 1:
                buf = cv2.resize(buf, (W, H), interpolation=cv2.INTER_LINEAR)
            out += buf
        if bokeh:
            B = self.bok
            q = self._place(B["p"] + B["dr"] * t, B["z"], pan, zoom)
            lo = np.zeros((LH, LW), np.float32)
            for i in range(len(q)):
                d = np.sqrt(rad2(float(q[i, 0]), float(q[i, 1])))
                lo += np.clip((B["r"][i] - d) / 0.004 + 0.5, 0, 1) * B["b"][i]
            lo = cv2.GaussianBlur(lo, (0, 0), 1.2)
            out += up(lo, cv2.INTER_LINEAR)
        return out


SNOWS = {}


def snow(name, seed, density=1.0):
    if name not in SNOWS:
        SNOWS[name] = Snow(seed, density)
    return SNOWS[name]


def glows(points):
    """Soft light points: (x, y, sigma in W, amplitude, rgb), screen-normalised. Quarter-res RGB."""
    buf = np.zeros((QH, QW, 3), np.float32)
    for x, y, sg, amp, col in points:
        if amp <= 1e-5:
            continue
        s = max(0.55, sg * QW)
        r = int(3.2 * s) + 1
        cx, cy = x * QW, y * QH
        x0, x1 = max(0, int(cx) - r), min(QW, int(cx) + r + 1)
        y0, y1 = max(0, int(cy) - r), min(QH, int(cy) + r + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        xs = np.arange(x0, x1, dtype=np.float32) + 0.5 - cx
        ys = np.arange(y0, y1, dtype=np.float32) + 0.5 - cy
        g = np.exp(-(ys[:, None] ** 2 + xs[None, :] ** 2) / (2 * s * s)) * amp
        buf[y0:y1, x0:x1] += g[:, :, None] * np.asarray(col, np.float32)
    return buf


def flash(tau, attack=0.07, decay=0.5):
    if tau < 0:
        return 0.0
    return min(tau / attack, 1.0) * math.exp(-max(tau - attack, 0.0) / decay)


def pulse(tau, dur):
    if tau < 0 or tau > dur:
        return 0.0
    return math.sin(math.pi * tau / dur) ** 2


def rays(t, sx, sy):
    """Light shafts fanning out from a point above the frame. Low-res scalar field."""
    ax = (GX - sx) * (W / H)
    ay = np.maximum(GY - sy, 1e-3)
    th = np.arctan2(ax, ay)
    r = np.sqrt(ax * ax + ay * ay)
    a = (0.55 * np.sin(th * 23.0 + 0.31 * t + 1.0) + 0.45 * np.sin(th * 41.0 - 0.23 * t + 2.3)
         + 0.50 * np.sin(th * 9.0 + 0.11 * t) + 0.30 * np.sin(th * 67.0 + 0.4 * t + 0.7))
    a = np.clip(0.35 + 0.42 * a, 0, None) ** 1.6
    return (a * np.exp(-r / 0.75) * sstep(r, 0.25, 0.5)).astype(np.float32)


def bloom(img, thr=0.42, amt=0.55):
    q = cv2.resize(img, (QW, QH), interpolation=cv2.INTER_AREA)
    q = np.maximum(q - thr, 0)
    if float(q.max()) <= 0:
        return img
    b1 = cv2.GaussianBlur(q, (0, 0), max(0.6, 4 * S))
    b2 = cv2.GaussianBlur(q, (0, 0), max(1.0, 14 * S))
    s16 = cv2.resize(q, (max(8, QW // 4), max(8, QH // 4)), interpolation=cv2.INTER_AREA)
    b3 = cv2.resize(cv2.GaussianBlur(s16, (0, 0), max(1.0, 11 * S)), (QW, QH), interpolation=cv2.INTER_LINEAR)
    img += up(0.50 * b1 + 0.32 * b2 + 0.30 * b3, cv2.INTER_LINEAR) * amt
    return img


# ----------------------------------------------------------------------------- descent profile
_VT = np.array([4.6, 8.0, 10.0, 11.5, 12.4, 18.0])
_VV = np.array([0.05, 0.18, 0.38, 0.26, 0.06, 0.03])      # screen heights per second (mid layer)
_TT = np.arange(4.6, 18.02, 1 / 120.0)
_PP = np.concatenate([[0.0], np.cumsum(np.interp(_TT[:-1] + 1 / 240.0, _VT, _VV)) / 120.0])


def travel(t):
    return float(np.interp(t, _TT, _PP))


P1000 = travel(12.4)


def depth_at(t):
    if t < 4.6:
        return 0.0
    if t < 18.0:
        return 1000.0 * travel(t) / P1000
    return 10885.0 + 4.0 * (t - 18.0)


def ytop(t):
    """Screen y (in frame heights) of the water surface seen from below."""
    if t < TL.T_WIPE1:
        return lerp(1.06, -0.035, smoother((t - TL.T_WIPE0) / (TL.T_WIPE1 - TL.T_WIPE0)))
    u = t - TL.T_WIPE1
    return -0.035 - (0.035 * u + 0.0105 * u * u)


# ----------------------------------------------------------------------------- shots
def shot_surface(t):
    pl = plate("surface")
    yh = 0.389
    gx, gy = pl.lgx, pl.lgy
    v = np.clip((gy - yh) / (1 - yh), 0, 1)
    below = (gy > yh).astype(np.float32)
    z = 1.0 / (v + 0.05)
    X = (gx - 0.5) * z
    na = noise2(0, X * 0.55 + t * 0.012, z * 0.11 + t * 0.045)
    nb = noise2(1, X * 1.7 - t * 0.02, z * 0.31 + t * 0.10)
    nc = noise2(2, X * 0.6 + 0.37 - t * 0.01, z * 0.12 + 0.61 + t * 0.04)
    amp = (v ** 1.15) * 15 * pl.px * below
    dx = amp * (0.7 * na + 0.3 * nb)
    dy = amp * 0.55 * (0.7 * nc + 0.3 * nb)
    k = 1 - 0.30 * ramp(t, 2.2, 4.6)                      # the camera sinks towards the water
    dy = dy + below * (gy - yh) * pl.h * (1 / k - 1)
    img = pl.warp(dx, dy, border=cv2.BORDER_REFLECT_101)
    g = noise2(3, X * 4.2 + t * 0.06, z * 0.9 + t * 0.12)  # glitter comes and goes
    gain = 1 + below * (np.clip(1 + 0.95 * g, 0.2, 2.8) - 1)
    gain = cv2.resize(gain, (pl.w, pl.h), interpolation=cv2.INTER_LINEAR)
    lum = img[:, :, 0] * 0.25 + img[:, :, 1] * 0.6 + img[:, :, 2] * 0.15
    hl = np.clip((np.sqrt(lum) - 0.16) / 0.4, 0, 1)
    img = img * (1 + hl * (gain - 1))[:, :, None]
    dxc, dyc, r = drift(t, 1)
    zoom = 1.035 + 0.05 * ramp(t, 0, 4.6)
    return view(img, 0.5 + 0.003 * dxc, 0.5 + 0.004 * dyc + 0.004 * math.sin(t * 1.7), zoom, 0.005 * r)


S2_SPARKS = TL.S2_SPARKS


def shot_descent(t):
    pl = plate("twilight")
    yt = ytop(t)
    zoom = 1.12
    dxc, dyc, r = drift(t, 2)
    d = depth_at(t)
    e = max(0.0, 1 - d / 1000.0) ** 1.7                    # daylight left at this depth
    out = None
    if e > 1e-4:
        if yt > -0.3:                                      # the surface is still in frame: let it shimmer
            gx, gy = pl.lgx, pl.lgy
            band = np.clip(1 - gy / 0.16, 0, 1)
            na = noise2(0, gx * 0.9 + t * 0.05, gy * 1.6 + t * 0.03)
            nb = noise2(1, gx * 1.1 - t * 0.04 + 0.3, gy * 1.4 - t * 0.05)
            img = pl.warp(band * 10 * pl.px * na, band * 6 * pl.px * nb)
            g = noise2(3, gx * 3.1 + t * 0.11, gy * 2.3 - t * 0.13)
            gain = 1 + band * np.clip(0.6 * g, -0.6, 1.2)
            img = img * cv2.resize(gain, (pl.w, pl.h), interpolation=cv2.INTER_LINEAR)[:, :, None]
        else:
            img = pl.lin
        out = view(img, 0.5 + 0.004 * dxc, (0.5 - yt) / zoom, zoom, 0.004 * r)
        out *= np.array([e ** 1.5, e ** 1.15, e], np.float32)
        if e > 0.004:
            rr = rays(t, 0.56, yt - 0.30) * (e * ramp(t, 3.9, 5.0))
            out += up(rr)[:, :, None] * np.array([0.030, 0.070, 0.115], np.float32)
    else:
        out = np.zeros((H, W, 3), np.float32)
    c = ramp(t, 9.8, 12.2) * (1 - ramp(t, 14.4, 15.9))     # our own lamp once daylight is gone
    if e > 1e-4 or c > 1e-4:
        cone = 0.25 + 0.75 * np.exp(-rad2(0.5 + 0.02 * dxc, 0.46) / (2 * 0.42 ** 2))
        lightm = 0.22 * e + c * cone * 0.9
        P = travel(t)
        sn = snow("descent", 11, 1.3).render(t, pan=(0.0, -P), mb=(0.0, travel(t + 1.0 / FPS) - P))
        out += (sn * up(lightm.astype(np.float32)))[:, :, None] * SNOW_COL
    pts = []
    for t0, x, y, amp, sg, col in S2_SPARKS:
        env = flash(t - t0, 0.07, 0.55)
        if env > 1e-3:
            y2 = y - (travel(t) - travel(t0)) * 0.5
            pts += [(x, y2, sg, amp * env, col), (x, y2, sg * 5, amp * env * 0.12, col)]
    if pts:
        out += up(glows(pts))
    return out


def wipe(t):
    """The lens goes through the surface: night sea above the waterline, open water below."""
    a = shot_surface(t)
    b = shot_descent(t)
    xs = np.arange(W, dtype=np.float32) / W
    yw = ytop(t) * H + H * (0.010 * np.sin(6.283 * (xs * 1.3 + t * 0.9)) + 0.005 * np.sin(6.283 * (xs * 3.1 - t * 1.6))
                            + 0.003 * np.sin(6.283 * (xs * 7.3 + t * 2.3)))
    d = np.arange(H, dtype=np.float32)[:, None] - yw[None, :]        # > 0 under water
    m = np.clip(d / (3.0 * S) + 0.5, 0, 1)
    out = a + (b - a) * m[:, :, None]
    rim = np.exp(-np.square((d + 5 * S) / (5 * S))) * 0.16            # meniscus catching the moonlight
    shade = 1 - 0.55 * np.exp(-np.square((d - 10 * S) / (9 * S)))     # and the dark line under it
    dn = d / H
    u = (np.arange(W, dtype=np.float32) / W)[None, :] * np.ones((H, 1), np.float32)
    vv = (np.arange(H, dtype=np.float32) / H)[:, None] * np.ones((1, W), np.float32)
    fr = noise2(4, u * 3.0, vv * 5.0 + t * 0.9) + 0.6 * noise2(5, u * 7.0 + 0.2, vv * 11.0 + t * 1.7)
    froth = np.clip(fr - 0.9, 0, 1.5) * np.exp(-np.clip(dn, 0, None) / 0.07) * (d > 0) * 0.10
    out *= shade[:, :, None]
    out += (rim + froth)[:, :, None] * np.array([0.62, 0.74, 0.90], np.float32)
    return out


def shot_trench_wall(t):
    pl = plate("trench_wall")
    k = (t - 18.0) / (TL.T_TRENCH_CUT - 18.0)
    dxc, dyc, r = drift(t, 3)
    cx = lerp(0.480, 0.500, k) + 0.003 * dxc
    cy = lerp(0.465, 0.535, k) + 0.003 * dyc
    zoom = lerp(1.12, 1.19, smooth(k))
    rot = 0.004 * r
    out = view(pl.lin, cx, cy, zoom, rot)
    lx, ly = to_screen(0.30, 0.48, cx, cy, zoom, rot, pl)
    lightm = 0.22 + 0.95 * np.exp(-(np.square((GX - lx - 0.03 * math.sin(0.5 * t)) / 0.62)
                                    + np.square((GY - ly) / 0.44)))
    out *= up(lightm.astype(np.float32))[:, :, None]
    vx, vy = to_screen(0.2352, 0.4689, cx, cy, zoom, rot, pl)        # the small vehicle on the wall
    fl = 1 + 0.10 * n1(t * 2.0, 5)
    out += up(glows([(vx + 0.012, vy - 0.004, 0.006 * zoom, 0.55 * fl, (0.80, 0.92, 1.0)),
                     (vx + 0.03, vy - 0.006, 0.035 * zoom, 0.05 * fl, (0.55, 0.78, 1.0))]))
    tt = t - 18.0
    sn = snow("trench", 23, 1.0).render(t, pan=(0.01 * tt, -0.055 * tt), zoom=zoom / 1.12, mb=(0.0, 0.055 / FPS))
    out += (sn * up((lightm * 0.9).astype(np.float32)))[:, :, None] * SNOW_COL
    return out * ramp(t, 18.0, 18.3)


def shot_trench_deep(t):
    pl = plate("trench_deep")
    if "beam" not in pl.aux:
        lo = cv2.resize(np.sqrt(pl.lin.mean(2)), (pl.lgx.shape[1], pl.lgx.shape[0]), interpolation=cv2.INTER_AREA)
        pl.aux["beam"] = sstep(lo, 0.2, 0.55) * sstep(pl.lgx, 0.22, 0.30) * (1 - sstep(pl.lgx, 0.66, 0.74))
    k = (t - TL.T_TRENCH_CUT) / (28.0 - TL.T_TRENCH_CUT)
    ke = smooth(k)
    dxc, dyc, r = drift(t, 4)
    cx = lerp(0.50, 0.545, ke) + 0.003 * dxc
    cy = lerp(0.47, 0.585, ke) + 0.003 * dyc
    zoom = lerp(1.06, 1.25, ke)
    rot = 0.004 * r
    n = noise2(4, pl.lgx * 2.2 + pl.lgy * 0.35, pl.lgy * 1.3 + t * 0.10)
    gain = 1 + pl.aux["beam"] * np.clip(0.5 * n, -0.45, 0.9)       # backscatter drifting through the beam
    img = pl.lin * cv2.resize(gain.astype(np.float32), (pl.w, pl.h), interpolation=cv2.INTER_LINEAR)[:, :, None]
    out = view(img, cx, cy, zoom, rot)
    vx, vy = to_screen(0.602, 0.815, cx, cy, zoom, rot, pl)          # the tiny light far below
    fl = 1 + 0.12 * n1(t * 2.3, 9)
    out += up(glows([(vx, vy, 0.004 * zoom, 0.6 * fl, (0.85, 0.94, 1.0)), (vx, vy, 0.022 * zoom, 0.045 * fl, (0.6, 0.8, 1.0))]))
    tt = t - TL.T_TRENCH_CUT
    lightm = 0.25 + 0.6 * np.exp(-rad2(0.42, 0.40) / (2 * 0.40 ** 2))
    sn = snow("trench2", 29, 0.9).render(t, pan=(0.0, -0.04 * tt), zoom=zoom / 1.06, mb=(0.0, 0.04 / FPS))
    out += (sn * up(lightm.astype(np.float32)))[:, :, None] * SNOW_COL
    return out * (1 - ramp(t, 27.45, 28.0))


ANGLER_FAR, CLOSE_FAR = TL.ANGLER_FAR, TL.CLOSE_FAR


def emitter_points(ems, t, zoom=1.0):
    pts = []
    for e in ems:
        tau = t - e["t0"]
        if e["kind"] == "flash":
            env = max(flash(tau - i * 0.42, 0.06, 0.38) for i in range(e["rep"]))
        else:
            env = pulse(tau, e["dur"])
        if env < 1e-3:
            continue
        x = 0.5 + (e["x"] - 0.5) * (1 + 0.25 * (zoom - 1))
        y = 0.5 + (e["y"] - 0.5) * (1 + 0.25 * (zoom - 1))
        pts += [(x, y, e["sg"], e["amp"] * env, e["col"]), (x, y, e["sg"] * 4.5, e["amp"] * env * 0.10, e["col"])]
    return pts


def lure_light(t, lx, ly, zoom, b_l, b_f, amb, r_face, r_lure):
    """Light map (low-res RGB) for a fish lit by its own lure."""
    fl = 1 + 0.10 * math.sin(6.283 * 0.9 * t) + 0.06 * math.sin(6.283 * 2.3 * t + 1.0) + 0.05 * n1(t * 3.0, 3)
    d2 = rad2(lx, ly)
    F = 1.0 / (1.0 + d2 / (r_face * zoom) ** 2)
    G = np.exp(-d2 / (2 * (r_lure * zoom) ** 2))
    lum = amb + fl * (1.25 * b_f * F + 1.4 * b_l * G)
    rgb = amb + (fl * (1.25 * b_f * F + 1.4 * b_l * G))[:, :, None] * np.array([0.80, 0.93, 1.0], np.float32)
    return lum.astype(np.float32), rgb.astype(np.float32), fl


def shot_angler_wide(t):
    pl = plate("angler_wide")
    s1, s2 = math.sin(6.283 * 0.31 * t), math.sin(6.283 * 0.83 * t + 1.0)
    sx, sy = 5 * s1 + 2 * s2, 3 * math.sin(6.283 * 0.27 * t + 2.0)
    fin = 6.283 * 1.3 * t
    img = pl.warp(*pl.bumps([
        (0.216, 0.369, 0.075, 0.055, sx, sy), (0.29, 0.40, 0.07, 0.05, 0.5 * sx, 0.5 * sy),
        (0.715, 0.44, 0.05, 0.05, 2.5 * math.sin(fin), 3.0 * math.sin(fin + 1.2)),
        (0.86, 0.455, 0.05, 0.06, 3.0 * math.sin(6.283 * 0.9 * t + 0.5), 1.5 * math.sin(6.283 * 0.9 * t)),
        (0.37, 0.60, 0.15, 0.05, 0.0, 2.2 * math.sin(6.283 * 0.22 * t))]))
    k = smooth((t - 28.0) / (TL.T_ANGLER_CUT - 28.0))
    dxc, dyc, r = drift(t, 5)
    cx = lerp(0.50, 0.43, k) + 0.004 * dxc
    cy = lerp(0.50, 0.49, k) + 0.005 * dyc
    zoom = lerp(1.0, 1.30, k)
    rot = 0.006 * r
    out = view(img, cx, cy, zoom, rot)
    lx, ly = to_screen(0.216 + sx * pl.px / pl.w, 0.369 + sy * pl.px / pl.h, cx, cy, zoom, rot, pl)
    b_l = ramp(t, 29.2, 30.9)
    b_f = ramp(t, 30.3, 33.1)
    amb = 0.10 * ramp(t, 31.0, 33.8)
    lum, rgb, fl = lure_light(t, lx, ly, zoom, b_l, b_f, amb, 0.30, 0.036)
    out *= up(rgb)
    pts = emitter_points(ANGLER_FAR, t, zoom)
    pts += [(lx, ly, 0.030 * zoom, 0.10 * b_l * fl, (0.35, 0.62, 1.0)), (lx, ly, 0.10 * zoom, 0.028 * b_l * fl, (0.30, 0.55, 1.0))]
    out += up(glows(pts))
    sn = snow("angler", 31, 0.8).render(t, pan=(-(cx - 0.5) * zoom, -(cy - 0.5) * zoom - 0.004 * (t - 28)), zoom=zoom)
    out += (sn * up(0.03 * b_l + lum * 0.9))[:, :, None] * SNOW_COL
    return out


def shot_angler_close(t):
    pl = plate("angler_close")
    s1, s2 = math.sin(6.283 * 0.29 * t + 0.4), math.sin(6.283 * 0.77 * t + 1.3)
    sx, sy = 7 * s1 + 3 * s2, 4 * math.sin(6.283 * 0.24 * t + 2.0)
    img = pl.warp(*pl.bumps([
        (0.141, 0.2565, 0.10, 0.075, sx, sy), (0.26, 0.31, 0.09, 0.06, 0.45 * sx, 0.45 * sy),
        (0.50, 0.72, 0.34, 0.07, 0.0, 3.2 * math.sin(6.283 * 0.25 * t)),
        (0.52, 0.46, 0.30, 0.05, 0.0, -1.2 * math.sin(6.283 * 0.25 * t))]))
    k = (t - TL.T_ANGLER_CUT) / (39.0 - TL.T_ANGLER_CUT)
    ke = 1 - (1 - min(1.0, max(0.0, k))) ** 1.6
    dxc, dyc, r = drift(t, 6)
    cx = lerp(0.49, 0.47, ke) + 0.003 * dxc
    cy = lerp(0.46, 0.54, ke) + 0.004 * dyc
    zoom = lerp(1.02, 1.25, ke)
    rot = 0.005 * r
    out = view(img, cx, cy, zoom, rot)
    lx, ly = to_screen(0.141 + sx * pl.px / pl.w, 0.2565 + sy * pl.px / pl.h, cx, cy, zoom, rot, pl)
    die = 1 - ramp(t, 38.45, 38.85)                         # the lure goes out
    lum, rgb, fl = lure_light(t, lx, ly, zoom, 0.9 * die, 1.0 * die, 0.15 * die, 0.50, 0.075)
    out *= up(rgb)
    pts = emitter_points(CLOSE_FAR, t, zoom)
    pts += [(lx, ly, 0.05 * zoom, 0.09 * die * fl, (0.35, 0.62, 1.0)), (lx, ly, 0.16 * zoom, 0.022 * die * fl, (0.30, 0.55, 1.0))]
    out += up(glows(pts))
    sn = snow("angler2", 37, 0.5).render(t, pan=(-(cx - 0.5) * zoom, -(cy - 0.5) * zoom), zoom=zoom)
    out += (sn * up(lum * 0.8))[:, :, None] * SNOW_COL
    return out


def shot_squid_wide(t):
    pl = plate("squid_wide")
    Hp = np.array([0.50 * pl.w, 0.55 * pl.h])
    Tp = np.array([0.06 * pl.w, 0.93 * pl.h])
    u = Tp - Hp
    smax = float(np.linalg.norm(u))
    u /= smax
    nrm = np.array([-u[1], u[0]])
    px, py = pl.lgx * pl.w, pl.lgy * pl.h
    s = (px - Hp[0]) * u[0] + (py - Hp[1]) * u[1]
    wd = (px - Hp[0]) * nrm[0] + (py - Hp[1]) * nrm[1]
    amp = 13 * pl.px * (np.clip(s / smax, 0, 1.2) ** 1.4) * np.exp(-np.square(wd / (0.17 * pl.w)))
    ph = 6.283 * (s / (0.42 * smax) - 0.20 * t)
    wave = amp * np.sin(ph) + 0.4 * amp * np.sin(1.9 * ph + 1.0 + 0.5 * t)       # arms and tentacles trailing
    fw = np.exp(-(np.square((pl.lgx - 0.84) / 0.13) + np.square((pl.lgy - 0.205) / 0.09)))
    fwave = 5 * pl.px * fw * np.sin(6.283 * 0.8 * t + pl.lgx * 30 - pl.lgy * 18)  # fins rippling
    img = pl.warp(nrm[0] * wave + 0.7 * fwave, nrm[1] * wave + 0.7 * fwave)
    k = smooth((t - 39.0) / (TL.T_SQUID_CUT - 39.0))
    dxc, dyc, r = drift(t, 7)
    cx = lerp(0.39, 0.54, k) + 0.003 * dxc
    cy = lerp(0.62, 0.47, k) + 0.003 * dyc
    zoom = lerp(1.34, 1.11, k)
    rot = 0.005 * r
    out = view(img, cx, cy, zoom, rot)
    q = smooth((t - 39.3) / 3.2)                             # the lamp travels up the body
    spx, spy = to_screen(lerp(0.14, 0.58, q), lerp(0.86, 0.44, q), cx, cy, zoom, rot, pl)
    rs = lerp(0.20, 0.50, q) * zoom
    spot = ramp(t, 39.25, 40.3)
    amb = 0.30 * ramp(t, 40.2, 43.2)
    lum = amb + 1.15 * spot * np.exp(-rad2(spx, spy) / (2 * rs * rs))
    out *= up((lum[:, :, None] * np.array([0.92, 0.97, 1.0], np.float32)).astype(np.float32))
    sn = snow("squid", 43, 0.8).render(t, pan=(-(cx - 0.39) * zoom * 0.8 - 0.006 * (t - 39), -(cy - 0.62) * zoom * 0.8 + 0.005 * (t - 39)), zoom=1.0)
    out += (sn * up((0.02 * spot + lum * 0.8).astype(np.float32)))[:, :, None] * SNOW_COL
    return out


def shot_squid_eye(t):
    pl = plate("squid_eye")
    br = 6.283 * 0.2 * t
    img = pl.warp(*pl.bumps([(0.78, 0.18, 0.35, 0.20, 2.5 * math.sin(br), 2.0 * math.sin(br + 0.7)),
                             (0.22, 0.86, 0.30, 0.22, 3.5 * math.sin(br + 1.4), 2.5 * math.sin(br + 2.2))]))
    k = (t - TL.T_SQUID_CUT) / (49.0 - TL.T_SQUID_CUT)
    dxc, dyc, r = drift(t, 8)
    cx = 0.532 + 0.003 * dxc
    cy = 0.471 + 0.003 * dyc
    zoom = lerp(1.03, 1.17, smooth(k))
    rot = 0.004 * r
    out = view(img, cx, cy, zoom, rot)
    spx, spy = lerp(0.30, 0.62, k), lerp(0.62, 0.40, k)
    lum = 0.30 + 0.80 * np.exp(-rad2(spx, spy) / (2 * 0.42 ** 2))
    out *= up((lum[:, :, None] * np.array([0.92, 0.97, 1.0], np.float32)).astype(np.float32))
    sn = snow("eye", 47, 0.5).render(t, pan=(-0.006 * (t - 45), 0.004 * (t - 45)), zoom=zoom / 1.03)
    out += (sn * up((lum * 0.6).astype(np.float32)))[:, :, None] * SNOW_COL
    return out * (1 - ramp(t, 48.45, 49.0))


_grng = np.random.default_rng(55)
GLOW_PTS = [(float(_grng.normal(0, 0.034)), float(_grng.normal(0, 0.024)), float(_grng.uniform(0.0024, 0.0060)),
             float(_grng.uniform(0.16, 0.50)), float(_grng.uniform(0, 6.283)), float(_grng.uniform(0.5, 1.4)),
             BLUE if _grng.random() < 0.6 else CYAN, float(_grng.uniform(0.0, 1.0))) for _ in range(11)]


def glow_env(t):
    return ramp(t, TL.T_GLOW0, TL.T_GLOW0 + 1.3) * (1 - ramp(t, TL.T_GLOW1 - 1.1, TL.T_GLOW1))


def shot_abyss(t):
    pl = plate("abyss")
    k = smooth((t - 49.0) / 10.2)
    dxc, dyc, r = drift(t, 9)
    cx = lerp(0.488, 0.600, k) + 0.003 * dxc
    cy = lerp(0.515, 0.440, k) + 0.003 * dyc
    zoom = lerp(1.05, 1.38, k)
    rot = 0.005 * r
    out = view(pl.lin, cx, cy, zoom, rot)
    lx, ly = to_screen(0.20, 0.72, cx, cy, zoom, rot, pl)
    dim = 1 - 0.55 * ramp(t, 52.5, 58.0)                    # the void swallows our light
    lightm = dim * (0.10 + 0.95 * np.exp(-rad2(lx, ly) / (2 * (0.50 * zoom) ** 2)))
    out *= up(lightm.astype(np.float32))[:, :, None]
    tt = t - 49.0
    sn = snow("abyss", 53, 0.7).render(t, pan=(-(cx - 0.488) * zoom - 0.004 * tt, -(cy - 0.515) * zoom - 0.006 * tt), zoom=zoom / 1.05)
    out += (sn * up((lightm * 0.9 + 0.02).astype(np.float32)))[:, :, None] * SNOW_COL
    g = glow_env(t)
    if g > 1e-3:                                            # something far out lights up, then goes dark
        tg = t - TL.T_GLOW0
        gx0 = 0.655 - 0.012 * tg + 0.006 * math.sin(0.9 * tg)          # it is moving
        gy0 = 0.375 + 0.006 * tg + 0.004 * math.sin(0.7 * tg + 1.0)
        breathe = 0.75 + 0.25 * math.sin(6.283 * 0.55 * tg)
        rise = ramp(t, TL.T_GLOW0, TL.T_GLOW0 + 1.3)
        pts = [(gx0, gy0, 0.060, 0.070 * g * breathe, (0.10, 0.50, 0.95)), (gx0, gy0, 0.024, 0.085 * g * breathe, (0.10, 0.62, 0.90)),
               (gx0 + 0.040, gy0 - 0.014, 0.038, 0.045 * g * (1.5 - breathe), (0.10, 0.52, 0.95)),      # not one round blob
               (gx0 - 0.034, gy0 + 0.022, 0.030, 0.040 * g * breathe, (0.11, 0.58, 0.90))]
        for ox, oy, sg, amp, ph, fr, col, off in GLOW_PTS:
            t_off = TL.T_GLOW1 - 1.15 + 1.0 * off                       # the lights go out one by one
            a = amp * rise * (1 - ramp(t, t_off - 0.10, t_off)) * (0.55 + 0.45 * math.sin(6.283 * fr * t + ph)) ** 2
            pts.append((gx0 + ox, gy0 + oy, sg, a, col))
        out += up(glows(pts))
    return out * ramp(t, 49.0, 49.9) * (1 - ramp(t, TL.T_GLOW1 - 0.1, TL.T_BLACK))


def picture(t):
    if t < TL.T_WIPE0:
        return shot_surface(t)
    if t < TL.T_WIPE1:
        return wipe(t)
    if t < 18.0:
        return shot_descent(t)
    if t < TL.T_TRENCH_CUT:
        return shot_trench_wall(t)
    if t < 28.0:
        return shot_trench_deep(t)
    if t < TL.T_ANGLER_CUT:
        return shot_angler_wide(t)
    if t < 39.0:
        return shot_angler_close(t)
    if t < TL.T_SQUID_CUT:
        return shot_squid_wide(t)
    if t < 49.0:
        return shot_squid_eye(t)
    if t < TL.T_BLACK:
        return shot_abyss(t)
    return np.zeros((H, W, 3), np.float32)


# ----------------------------------------------------------------------------- text
SPRITES = {}


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name + ".otf"), max(4, int(round(size))))


def line_width(text, f, tracking):
    return sum(f.getlength(ch) for ch in text) + tracking * max(0, len(text) - 1)


def text_sprite(lines, gap=0.25, shadow=1.0, fixed_digits=False):
    """lines: [(text, font, size_px, tracking_px)], centred. Returns alpha and shadow maps."""
    fonts = [font(fn, sz) for _, fn, sz, _ in lines]
    widths, heights = [], []
    for (text, _, sz, tr), f in zip(lines, fonts):
        if fixed_digits:
            dw = max(f.getlength(c) for c in "0123456789")
            widths.append(sum(dw if ch.isdigit() else f.getlength(ch) for ch in text) + tr * max(0, len(text) - 1))
        else:
            widths.append(line_width(text, f, tr))
        heights.append(sz)
    pad = int(max(h for h in heights) * 0.9) + int(24 * S)
    cw = int(max(widths)) + 2 * pad
    ch_ = int(sum(heights) + gap * sum(heights[:-1])) + 2 * pad
    im = Image.new("L", (cw, ch_), 0)
    d = ImageDraw.Draw(im)
    y = pad
    for (text, _, sz, tr), f, wline in zip(lines, fonts, widths):
        asc, desc = f.getmetrics()
        x = (cw - wline) / 2
        dw = max(f.getlength(c) for c in "0123456789") if fixed_digits else 0
        for chx in text:
            adv = dw if (fixed_digits and chx.isdigit()) else f.getlength(chx)
            off = (adv - f.getlength(chx)) / 2 if (fixed_digits and chx.isdigit()) else 0
            d.text((x + off, y + (sz - asc) * 0.5 - desc * 0.1), chx, font=f, fill=255)
            x += adv + tr
        y += sz * (1 + gap)
    a = np.asarray(im, np.float32) / 255.0
    big = np.asarray(im.filter(ImageFilter.GaussianBlur(max(1.0, 13 * S))), np.float32) / 255.0
    tight = np.asarray(im.filter(ImageFilter.GaussianBlur(max(0.6, 3.0 * S))), np.float32) / 255.0
    sh = np.clip(big * 1.5 + tight * 0.9, 0, 1) * shadow
    return dict(a=a, sh=sh)


def put(disp, spr, cx, cy, alpha=1.0, scale=1.0, anchor="c"):
    if alpha <= 0.003:
        return
    a, sh = spr["a"], spr["sh"]
    if abs(scale - 1.0) > 1e-3:
        a = cv2.resize(a, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        sh = cv2.resize(sh, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    h, w = a.shape
    x0 = int(round(cx - w / 2)) if anchor == "c" else int(round(cx))
    y0 = int(round(cy - h / 2))
    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(W, x0 + w), min(H, y0 + h)
    if xa >= xb or ya >= yb:
        return
    a = a[ya - y0:yb - y0, xa - x0:xb - x0] * alpha
    sh = sh[ya - y0:yb - y0, xa - x0:xb - x0] * alpha
    reg = disp[ya:yb, xa:xb]
    reg *= (1 - 0.72 * sh)[:, :, None]
    reg += (1 - reg) * a[:, :, None]


def sprite(key, build):
    if key not in SPRITES:
        SPRITES[key] = build()
    return SPRITES[key]


CARD_LIST = None


def draw_subtitles(disp, t):
    global CARD_LIST
    if CARD_LIST is None:
        CARD_LIST = TL.cards()
    sz = 0.052 * W
    for i, (t0, t1, text) in enumerate(CARD_LIST):
        if t0 <= t < t1:
            follows = i > 0 and abs(CARD_LIST[i - 1][1] - t0) < 1e-6
            leads = i + 1 < len(CARD_LIST) and abs(CARD_LIST[i + 1][0] - t1) < 1e-6
            a_in = 1.0 if follows else min(1.0, 0.34 + (t - t0) / 0.10)
            a_out = 1.0 if leads else min(1.0, (t1 - t) / 0.12)

            def build(text=text):
                f = font("Inter-SemiBold", sz)
                if line_width(text, f, 0) > 0.80 * W and " " in text:
                    ws = text.split(" ")
                    best = min(range(1, len(ws)), key=lambda j: abs(len(" ".join(ws[:j])) - len(" ".join(ws[j:]))))
                    return text_sprite([(" ".join(ws[:best]), "Inter-SemiBold", sz, 0), (" ".join(ws[best:]), "Inter-SemiBold", sz, 0)], gap=0.22)
                return text_sprite([(text, "Inter-SemiBold", sz, 0)])
            put(disp, sprite(("sub", text), build), W / 2, 0.705 * H, min(a_in, a_out))


def draw_title(disp, t):
    a = 1 - ramp(t, 2.55, 3.05)                 # on from the very first frame, so the cover frame carries it
    if a <= 0:
        return

    def build():
        return text_sprite([("THE OCEAN IS MORE", "InterDisplay-SemiBold", 0.054 * W, 0.010 * W),
                            ("TERRIFYING", "InterDisplay-Black", 0.124 * W, 0.004 * W),
                            ("THAN YOU THINK", "InterDisplay-SemiBold", 0.054 * W, 0.010 * W)], gap=0.30, shadow=0.9)
    put(disp, sprite("title", build), W / 2, 0.262 * H, a, scale=1.0 + 0.02 * t / 3.0)


def draw_end(disp, t):
    a = ramp(t, TL.T_TEXT, TL.T_TEXT + 0.6)
    if a <= 0:
        return

    def build():
        return text_sprite([("WHAT ELSE IS", "InterDisplay-Bold", 0.092 * W, 0.006 * W),
                            ("DOWN THERE?", "InterDisplay-Bold", 0.092 * W, 0.006 * W)], gap=0.24, shadow=0.0)
    put(disp, sprite("end", build), W / 2, 0.468 * H, a, scale=1.0 + 0.03 * (t - TL.T_TEXT) / 2.0)


def draw_hud(disp, t):
    if t < 18.0:
        a = ramp(t, 4.8, 5.4) * (1 - ramp(t, 15.1, 15.9))
    else:
        a = ramp(t, 18.35, 18.9) * (1 - ramp(t, 27.2, 27.8))
    if a <= 0:
        return
    d = depth_at(t)
    atm = 1 + 0.09792 * d
    x = 0.074 * W
    lab = lambda s: sprite(("lab", s), lambda: text_sprite([(s, "Inter-SemiBold", 0.0165 * W, 0.0030 * W)], shadow=0.8))
    val = lambda s: sprite(("val", s), lambda: text_sprite([(s, "Inter-Medium", 0.034 * W, 0.0)], shadow=0.8, fixed_digits=True))
    for (label, value, yy) in (("DEPTH", "{:,.0f} m".format(d), 0.098), ("PRESSURE", "{:,.0f} atm".format(atm), 0.142)):
        sl, sv = lab(label), val(value)
        put(disp, sl, x - line_pad(sl) / 2, yy * H, 0.62 * a, anchor="l")
        put(disp, sv, x - line_pad(sv) / 2, (yy + 0.0195) * H, 0.85 * a, anchor="l")
    if len(SPRITES) > 400:
        for kk in [kk for kk in SPRITES if isinstance(kk, tuple) and kk[0] == "val"][:200]:
            del SPRITES[kk]


def line_pad(spr):
    """Horizontal padding (both sides) baked into a sprite, measured from its alpha."""
    if "pad" not in spr:
        cols = np.nonzero(spr["a"].max(0) > 0.02)[0]
        spr["pad"] = (int(cols[0]) * 2) if len(cols) else 0
    return spr["pad"]


# ----------------------------------------------------------------------------- frame
def frame(fi):
    t = fi / FPS
    lin = picture(t)
    if t < TL.T_BLACK:
        lin = bloom(lin)
        lin *= up(VIG)[:, :, None]
    np.maximum(lin, 0, out=lin)
    m = lin > 0.8                                           # soft shoulder for the brightest lights
    if m.any():
        lin[m] = 0.8 + 0.2 * (1 - np.exp(-(lin[m] - 0.8) / 0.2))
    disp = np.sqrt(lin, out=lin)
    rs = np.random.default_rng(1000 + fi)
    g = GRAIN[fi % len(GRAIN)]
    g = np.roll(g, (int(rs.integers(H)), int(rs.integers(W))), axis=(0, 1))
    if rs.random() < 0.5:
        g = g[:, ::-1]
    gk = 0.0115 / 32.0
    disp += (g.astype(np.float32) * gk)[:, :, None] * np.array([0.95, 1.0, 1.12], np.float32)
    np.clip(disp, 0, 1, out=disp)
    if OPT["title"]:
        draw_title(disp, t)
    if OPT["hud"] and 4.7 < t < 28.0:
        draw_hud(disp, t)
    if OPT["subs"]:
        draw_subtitles(disp, t)
    draw_end(disp, t)
    return (disp * 255.0 + 0.5).astype(np.uint8)


# ----------------------------------------------------------------------------- output
def encode_cmd(path, crf, preset):
    return ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS),
            "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264", "-preset", preset,
            "-crf", str(crf), "-pix_fmt", "yuv420p", "-threads", "2", "-g", "60", "-bf", "2",
            "-x264-params", "aq-mode=3:aq-strength=0.8", "-colorspace", "bt709", "-color_primaries", "bt709",
            "-color_trc", "bt709", "-color_range", "tv", path]


def worker(job):
    idx, f0, f1, scale, crf, preset, outdir, opt = job
    OPT.update(opt)
    cv2.setNumThreads(1)
    setup(scale)
    path = os.path.join(outdir, "chunk_%03d.mp4" % idx)
    mark = path + ".%d-%d.done" % (f0, f1)
    if os.path.exists(mark):                      # finished in an earlier, interrupted run
        return idx, path, f1 - f0
    p = subprocess.Popen(encode_cmd(path, crf, preset), stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        p.stdin.write(frame(fi).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg failed on chunk %d" % idx)
    open(mark, "w").close()
    return idx, path, f1 - f0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--stills", type=float, nargs="*")
    ap.add_argument("--sheet", type=float, nargs=3, metavar=("T0", "T1", "N"))
    ap.add_argument("--range", type=float, nargs=2, metavar=("T0", "T1"))
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--chunks", type=int, default=12)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-hud", action="store_true")
    ap.add_argument("--no-title", action="store_true")
    ap.add_argument("--no-subs", action="store_true")
    a = ap.parse_args()
    OPT.update(hud=not a.no_hud, title=not a.no_title, subs=not a.no_subs)
    prev = os.path.join(HERE, "preview")
    if a.stills is not None or a.sheet is not None:
        setup(a.scale)
        os.makedirs(prev, exist_ok=True)
        if a.stills is not None:
            for t in a.stills:
                t0 = time.time()
                im = frame(int(round(t * FPS)))
                p = os.path.join(prev, "still_%06.2f.jpg" % t)
                Image.fromarray(im).save(p, quality=92)
                print(p, "%.2fs" % (time.time() - t0))
        else:
            t0, t1, n = a.sheet[0], a.sheet[1], int(a.sheet[2])
            ts = np.linspace(t0, t1, n, endpoint=False)
            cols = 8 if n >= 8 else n
            rows = int(math.ceil(n / cols))
            sheet = Image.new("RGB", (cols * W, rows * H))
            for i, t in enumerate(ts):
                sheet.paste(Image.fromarray(frame(int(round(t * FPS)))), ((i % cols) * W, (i // cols) * H))
            p = os.path.join(prev, "sheet_%05.1f_%05.1f.jpg" % (t0, t1))
            sheet.save(p, quality=88)
            print(p, " ".join("%.2f" % t for t in ts))
        return
    setup(a.scale)
    f0, f1 = 0, int(round(TL.END * FPS))
    if a.range:
        f0, f1 = int(round(a.range[0] * FPS)), int(round(a.range[1] * FPS))
    build = os.path.join(HERE, "build")
    cdir = os.path.join(build, "chunks_%d" % W)
    os.makedirs(cdir, exist_ok=True)
    edges = np.linspace(f0, f1, a.chunks + 1).round().astype(int)
    jobs = [(i, int(edges[i]), int(edges[i + 1]), a.scale, a.crf, a.preset, cdir,
             dict(OPT)) for i in range(a.chunks) if edges[i + 1] > edges[i]]
    t0 = time.time()
    done = 0
    with mp.Pool(a.jobs, maxtasksperchild=1) as pool:
        for idx, path, n in pool.imap_unordered(worker, jobs):
            done += n
            print("chunk %d done  %d/%d frames  %.0fs" % (idx, done, f1 - f0, time.time() - t0), flush=True)
    lst = os.path.join(cdir, "list.txt")
    with open(lst, "w") as f:
        for j in jobs:
            f.write("file '%s'\n" % os.path.join(cdir, "chunk_%03d.mp4" % j[0]))
    out = a.out or os.path.join(build, "picture_%d.mp4" % W)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    print("wrote", out, "%.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
