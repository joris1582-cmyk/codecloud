"""Procedural dinosaur story renderer (Pillow + numpy -> ffmpeg).

Usage: python3 render.py <mode> <part>
  mode = vertical (1080x1920, TikTok/Shorts part with header) | landscape (1920x1080, YouTube chapter)
"""
import json, math, sys, subprocess, re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

FPS = 30
FONT_BLACK = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FONT_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
TIMING = json.load(open("timing.json")) if __import__("os").path.exists("timing.json") else []
HL_COLOR = [(255, 221, 0)]
END_TEXT = ["FOLLOW FOR MORE DINO STORIES"]
HEADER_COLOR = [(220, 30, 30)]
TITLES = ["The Night The Mountain Woke Up", "Alone In The Ash", "The Sky Hunter",
          "The Valley Of Bones", "Small Horns, Big Heart", "The Way Home"]

# ----------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, k): return a + (b - a) * k
def ease(k): k = clamp(k); return k * k * (3 - 2 * k)
def lc(c1, c2, k): return tuple(int(lerp(a, b, clamp(k))) for a, b in zip(c1, c2))
def dark(c, k): return tuple(int(v * k) for v in c[:3])

_grad = {}
def gradient(W, H, top, bot):
    key = (W, H, top, bot)
    if key not in _grad:
        a = np.linspace(0, 1, H)[:, None, None]
        arr = (np.array(top)[None, None, :] * (1 - a) + np.array(bot)[None, None, :] * a)
        arr = np.repeat(arr, W, axis=1).astype(np.uint8)
        if len(_grad) > 40: _grad.clear()
        _grad[key] = Image.fromarray(arr, "RGB")
    return _grad[key]

def ell(cx, cy, rx, ry, n=28, rot=0.0):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        if rot:
            x, y = x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)
        pts.append((cx + x, cy + y))
    return pts

def rot_pts(pts, ox, oy, a):
    c, s = math.cos(a), math.sin(a)
    return [(ox + (x - ox) * c - (y - oy) * s, oy + (x - ox) * s + (y - oy) * c) for x, y in pts]

class Xf:
    """local (u,v) body units -> screen px. facing=+1 faces right."""
    def __init__(self, x, y, s, facing=1, rot=0.0, pivot=(0, 0)):
        self.x, self.y, self.s, self.f, self.rot, self.pv = x, y, s, facing, rot, pivot
    def __call__(self, pts):
        if self.rot:
            pts = rot_pts(pts, self.pv[0], self.pv[1], self.rot)
        return [(self.x + self.f * u * self.s, self.y + v * self.s) for u, v in pts]

def h01(i, salt=0):
    x = math.sin(i * 12.9898 + salt * 78.233) * 43758.5453
    return x - math.floor(x)

# ----------------------------------------------------------------- environment pieces
def mountains(d, W, base_y, amp, color, seed, cam=0.0, step=None):
    step = step or max(8, W // 90)
    pts = [(0, base_y + 400)]
    for x in range(0, W + step, step):
        X = x + cam
        y = base_y - amp * (0.55 * math.sin(X * 0.004 + seed) + 0.3 * math.sin(X * 0.011 + seed * 2.1)
                            + 0.15 * math.sin(X * 0.027 + seed * 3.3) + 0.6)
        pts.append((x, y))
    pts.append((W, base_y + 4000))
    pts.append((0, base_y + 4000))
    d.polygon(pts, fill=color)

def fern(d, x, y, size, color, sway=0.0):
    # trunk
    d.polygon([(x - size * 0.04, y), (x + size * 0.04, y), (x + size * 0.02 + sway * 0.3, y - size * 0.75),
               (x - size * 0.02 + sway * 0.3, y - size * 0.75)], fill=color)
    tx, ty = x + sway * 0.3, y - size * 0.75
    for k in range(7):
        a = -math.pi / 2 + (k - 3) * 0.42 + sway * 0.002
        L = size * (0.55 - abs(k - 3) * 0.04)
        ex, ey = tx + math.cos(a) * L, ty + math.sin(a) * L * 0.75 + abs(k - 3) * size * 0.06
        mx, my = (tx + ex) / 2, (ty + ey) / 2 - size * 0.08
        w = size * 0.07
        d.polygon([(tx, ty), (mx - w * math.sin(a), my + w * math.cos(a) * 0.3), (ex, ey),
                   (mx + w * math.sin(a), my - w * math.cos(a) * 0.3 - w)], fill=color)

def fern_row(d, W, y, size, color, seed, cam=0.0, density=1.0, t=0.0):
    spacing = size * 0.9 / density
    n = int(W / spacing) + 4
    off = cam % spacing
    base_i = int(cam // spacing)
    for k in range(-2, n):
        i = base_i + k
        jitter = (h01(i, seed) - 0.5) * spacing * 0.8
        sc = 0.7 + 0.6 * h01(i, seed + 1)
        x = k * spacing - off + jitter
        fern(d, x, y + h01(i, seed + 2) * size * 0.08, size * sc, color, sway=math.sin(t * 1.3 + i) * size * 0.05)

def volcano(d, cx, base_y, w, h, color, crater_glow=None):
    d.polygon([(cx - w, base_y), (cx - w * 0.14, base_y - h), (cx + w * 0.14, base_y - h), (cx + w, base_y)], fill=color)
    if crater_glow:
        d.polygon([(cx - w * 0.14, base_y - h), (cx + w * 0.14, base_y - h), (cx + w * 0.08, base_y - h * 0.9),
                   (cx - w * 0.06, base_y - h * 0.86)], fill=crater_glow)

def glow_layer(W, H, blobs, blur=18):
    """blobs: list of (x,y,r,(r,g,b),alpha). Rendered at 1/4 res then blurred + upscaled."""
    q = 4
    im = Image.new("RGB", (W // q, H // q), (0, 0, 0))
    gd = ImageDraw.Draw(im)
    for x, y, r, c, a in blobs:
        cc = tuple(int(v * a) for v in c)
        gd.ellipse([x / q - r / q, y / q - r / q, x / q + r / q, y / q + r / q], fill=cc)
    im = im.filter(ImageFilter.GaussianBlur(blur))
    return im.resize((W, H), Image.BILINEAR)

def particles(d, W, H, t, n, seed, color, size, vx, vy, y0=0.0, y1=1.0, flicker=False, alpha_layer=None):
    for i in range(n):
        x = (h01(i, seed) * W * 1.3 + vx * t * (0.6 + 0.8 * h01(i, seed + 3))) % (W * 1.3) - W * 0.15
        span = (y1 - y0) * H
        y = y0 * H + (h01(i, seed + 1) * span + vy * t * (0.6 + 0.8 * h01(i, seed + 4))) % span
        r = size * (0.5 + h01(i, seed + 2))
        if flicker and math.sin(t * 9 + i) < -0.6:
            continue
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)

def stars(d, W, H, t, n=120, seed=7, ymax=0.55):
    for i in range(n):
        x = h01(i, seed) * W; y = h01(i, seed + 1) * H * ymax
        b = 150 + int(100 * (0.5 + 0.5 * math.sin(t * 2 + i * 1.7)))
        r = 1.2 + 2.0 * h01(i, seed + 2)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(b, b, min(255, b + 20)))

def ribs(d, cx, gy, s, color):
    for k in range(6):
        x = cx + (k - 2.5) * s * 0.22
        hgt = s * (0.95 - abs(k - 2.5) * 0.1)
        wdt = s * 0.32
        d.arc([x - wdt, gy - hgt, x + wdt, gy + hgt * 0.9], 200, 330, fill=color, width=max(6, int(s * 0.05)))
    d.rounded_rectangle([cx - s * 0.75, gy - s * 0.12, cx + s * 0.75, gy - s * 0.05], radius=int(s * 0.03), fill=color)

def skull(d, cx, gy, s, color, hole):
    d.ellipse([cx - s * 0.3, gy - s * 0.32, cx + s * 0.25, gy], fill=color)
    d.polygon([(cx + s * 0.15, gy - s * 0.25), (cx + s * 0.55, gy - s * 0.12), (cx + s * 0.18, gy - s * 0.02)], fill=color)
    d.ellipse([cx - s * 0.08, gy - s * 0.24, cx + s * 0.06, gy - s * 0.12], fill=hole)

# ----------------------------------------------------------------- characters
def triceratops(d, x, y, s, col, phase=0.0, facing=1, horn=1.0, frill=None, lying=False, head_down=0.0,
                eye=True, rot=0.0, blink=False):
    X = Xf(x, y + (s * 0.2 if lying else 0), s, facing, rot, (0, -0.4))
    frill = frill or lc(col, (255, 220, 150), 0.35)
    legc = dark(col, 0.8)
    if not lying:
        for i, (u, off) in enumerate([(-0.24, 0.0), (0.2, math.pi), (-0.12, math.pi), (0.3, 0.0)]):
            c = dark(legc, 0.8) if i < 2 else legc
            a = math.sin(phase + off) * 0.38
            top = (u, -0.32)
            quad = [(u - 0.05, -0.32), (u + 0.05, -0.32), (u + 0.05, -0.02), (u - 0.05, -0.02)]
            q = rot_pts(quad, top[0], top[1], a)
            d.polygon(X(q), fill=c)
    # tail
    d.polygon(X([(-0.36, -0.52), (-0.36, -0.34), (-0.74, -0.33)]), fill=col)
    # body
    d.polygon(X(ell(0, -0.44, 0.42, 0.22)), fill=col)
    d.polygon(X(ell(0.02, -0.38, 0.34, 0.1)), fill=lc(col, (255, 230, 200), 0.12))
    # head group (rotatable)
    hp = (0.4, -0.48)
    hr = head_down * 0.45
    def H_(pts): return X(rot_pts(pts, hp[0], hp[1], hr))
    d.polygon(H_(ell(0.42, -0.62, 0.15, 0.2)), fill=frill)
    for k in range(5):  # frill spikes
        a = -math.pi * 0.95 + k * 0.42
        bx, by = 0.42 + math.cos(a) * 0.15, -0.62 + math.sin(a) * 0.2
        d.polygon(H_([(bx - 0.02, by), (bx + 0.02, by), (0.42 + math.cos(a) * 0.2, -0.62 + math.sin(a) * 0.26)]), fill=frill)
    d.polygon(H_(ell(0.52, -0.5, 0.16, 0.12)), fill=col)
    d.polygon(H_([(0.6, -0.56), (0.74, -0.46), (0.62, -0.42)]), fill=dark(col, 0.85))  # beak
    hl = 0.05 + 0.2 * horn
    d.polygon(H_([(0.52, -0.6), (0.57, -0.6), (0.56 + hl, -0.6 - hl * 0.55)]), fill=(240, 230, 205))
    d.polygon(H_([(0.64, -0.55), (0.68, -0.55), (0.69, -0.55 - 0.04 - 0.05 * horn)]), fill=(240, 230, 205))
    if eye:
        ex, ey = H_([(0.53, -0.53)])[0]
        r = max(2, s * 0.025)
        if blink:
            d.line([ex - r, ey, ex + r, ey], fill=(20, 15, 10), width=max(2, int(r * 0.6)))
        else:
            d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(250, 245, 230))
            d.ellipse([ex - r * 0.55 + facing * r * 0.25, ey - r * 0.55, ex + r * 0.55 + facing * r * 0.25, ey + r * 0.55], fill=(20, 15, 10))

TREX_K = [0.6]
def trex(d, x, y, s, col, phase=0.0, facing=1, jaw=0.0, rot=0.0, head_low=0.0, eye_glow=True):
    s = s * TREX_K[0]
    X = Xf(x, y, s, facing, rot, (0, -0.1))
    back = dark(col, 0.72)
    def leg(ph, c):
        a = math.sin(ph) * 0.42
        knee = rot_pts([(0.04, -0.36)], 0, -0.55, a)[0]
        foot = (knee[0] - 0.06 + math.sin(ph) * 0.05, min(0, -0.0 + (0.04 if math.cos(ph) > 0.4 else 0)))
        d.polygon(X(ell(0.0, -0.52, 0.13, 0.17, rot=a)), fill=c)
        d.polygon(X([(knee[0] - 0.05, knee[1]), (knee[0] + 0.05, knee[1]), (foot[0] + 0.03, foot[1] - 0.03),
                     (foot[0] - 0.03, foot[1] - 0.03)]), fill=c)
        d.polygon(X([(foot[0] - 0.06, foot[1] - 0.04), (foot[0] + 0.12, foot[1] - 0.03), (foot[0] + 0.12, foot[1]),
                     (foot[0] - 0.06, foot[1])]), fill=c)
    leg(phase + math.pi, back)
    # tail
    d.polygon(X([(-0.15, -0.72), (-0.12, -0.5), (-0.55, -0.55), (-0.95, -0.5), (-0.6, -0.6)]), fill=col)
    d.polygon(X(ell(0.05, -0.64, 0.33, 0.17, rot=-0.22)), fill=col)
    d.polygon(X(ell(0.08, -0.58, 0.25, 0.08, rot=-0.22)), fill=lc(col, (220, 210, 170), 0.18))
    # arm
    d.line(X([(0.28, -0.66), (0.36, -0.58), (0.4, -0.6)]), fill=back, width=max(3, int(s * 0.025)))
    leg(phase, col)
    # head
    hp = (0.3, -0.78)
    hr = head_low * 0.5
    def H_(pts): return X(rot_pts(pts, hp[0], hp[1], hr))
    d.polygon(H_([(0.2, -0.86), (0.3, -0.78), (0.28, -0.7), (0.18, -0.68)]), fill=col)  # neck
    jp = (0.32, -0.79)
    jawpts = rot_pts([(0.32, -0.79), (0.64, -0.8), (0.62, -0.75), (0.34, -0.72)], jp[0], jp[1], jaw * 0.55)
    d.polygon(H_(jawpts), fill=back)
    if jaw > 0.15:
        for k in range(5):
            tx = 0.4 + k * 0.045
            d.polygon(H_(rot_pts([(tx, -0.79), (tx + 0.02, -0.79), (tx + 0.01, -0.765)], jp[0], jp[1], jaw * 0.55)), fill=(245, 240, 220))
            d.polygon(H_([(tx, -0.805), (tx + 0.02, -0.805), (tx + 0.01, -0.78)]), fill=(245, 240, 220))
    d.polygon(H_([(0.24, -0.92), (0.5, -0.95), (0.66, -0.88), (0.66, -0.82), (0.32, -0.79), (0.22, -0.82)]), fill=col)
    d.polygon(H_([(0.4, -0.95), (0.5, -0.95), (0.47, -0.92)]), fill=back)  # brow ridge
    # scar
    d.line(H_([(0.4, -0.95), (0.47, -0.86), (0.53, -0.8)]), fill=lc(col, (230, 190, 170), 0.6), width=max(2, int(s * 0.012)))
    ex, ey = H_([(0.43, -0.885)])[0]
    r = max(3, s * 0.022)
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(235, 240, 235) if eye_glow else (200, 60, 30))

def ptero(d, x, y, s, col, flap=0.0, facing=1, perched=False):
    X = Xf(x, y, s, facing)
    wing = dark(col, 0.8)
    if perched:
        d.polygon(X([(-0.05, -0.05), (0.15, -0.35), (0.25, -0.05)]), fill=wing)
        d.line(X([(0.05, 0.0), (0.05, 0.12)]), fill=wing, width=max(2, int(s * 0.03)))
        d.line(X([(0.15, 0.0), (0.15, 0.12)]), fill=wing, width=max(2, int(s * 0.03)))
        d.polygon(X(ell(0.1, -0.05, 0.16, 0.08)), fill=col)
        hx, hy = 0.24, -0.24
    else:
        tip = math.sin(flap) * 0.45
        d.polygon(X([(-0.05, 0.0), (0.12, 0.0), (0.05 - 0.15, -0.1 - tip), (-0.55, -0.15 - tip * 1.4)]), fill=wing)
        d.polygon(X(ell(0.05, 0.0, 0.2, 0.06)), fill=col)
        d.polygon(X([(-0.03, 0.0), (0.12, 0.0), (0.2, 0.1 + tip * 0.6), (0.62, 0.05 + tip * 1.4)]), fill=col)
        hx, hy = 0.26, -0.04
    d.polygon(X([(hx - 0.04, hy - 0.04), (hx + 0.06, hy - 0.05), (hx + 0.38, hy + 0.01), (hx + 0.05, hy + 0.04)]), fill=col)
    d.polygon(X([(hx - 0.02, hy - 0.04), (hx + 0.04, hy - 0.04), (hx - 0.22, hy - 0.16)]), fill=lc(col, (240, 140, 70), 0.5))
    ex, ey = X([(hx + 0.04, hy - 0.01)])[0]
    r = max(2, s * 0.02)
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(20, 15, 10))

def egg(d, x, y, s, crack=0.0, wob=0.0, col=(235, 225, 195)):
    pts = rot_pts(ell(0, -0.55, 0.38, 0.52), 0, 0, wob)
    d.polygon([(x + u * s, y + v * s) for u, v in pts], fill=col)
    for k in range(5):
        u = (h01(k, 4) - 0.5) * 0.5; v = -0.3 - h01(k, 5) * 0.5
        d.ellipse([x + (u - 0.04) * s, y + (v - 0.03) * s, x + (u + 0.04) * s, y + (v + 0.03) * s], fill=(200, 170, 120))
    if crack > 0:
        L = crack
        pts = [(-0.3, -0.6), (-0.15, -0.68), (-0.05, -0.58), (0.08, -0.7), (0.2, -0.6), (0.32, -0.66)]
        n = max(2, int(len(pts) * L))
        d.line([(x + u * s, y + v * s) for u, v in pts[:n]], fill=(60, 40, 30), width=max(2, int(s * 0.03)))

def nest(d, x, y, s, col=(110, 80, 50)):
    d.ellipse([x - s * 0.9, y - s * 0.25, x + s * 0.9, y + s * 0.15], fill=col)
    for k in range(14):
        a = k / 14 * math.pi
        d.line([x - s * 0.9 + k * s * 0.13, y - s * 0.2, x - s * 0.8 + k * s * 0.13 + 10, y + s * 0.05],
               fill=dark(col, 0.7), width=max(2, int(s * 0.03)))

# ----------------------------------------------------------------- scene system
class Ctx:
    pass

def base(c, top, bot):
    c.img.paste(gradient(c.W, c.H, top, bot))

def add_glow(c, blobs, blur=18):
    g = glow_layer(c.W, c.H, blobs, blur)
    c.img = ImageChops.add(c.img, g)
    c.d = ImageDraw.Draw(c.img)

# ---- individual scenes. Each: f(c) where c.t local time, c.k local progress 0..1
def sc_valley_day(c, closeup=False):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    base(c, (110, 175, 230), (250, 222, 170))
    cam = c.t * 18
    sun = (W * 0.78, gy - U * 0.75)
    add_glow(c, [(sun[0], sun[1], U * 0.18, (255, 230, 160), 0.9)], 20)
    c.d.ellipse([sun[0] - U * 0.06, sun[1] - U * 0.06, sun[0] + U * 0.06, sun[1] + U * 0.06], fill=(255, 245, 210))
    volcano(c.d, W * 0.25 - cam * 0.05, gy - U * 0.1, U * 0.45, U * 0.5, (120, 120, 140))
    mountains(c.d, W, gy - U * 0.12, U * 0.18, (120, 150, 160), 1, cam * 0.2)
    if c.birds:
        for i in range(7):
            bx = W * 0.2 + i * U * 0.08 + c.t * U * 0.12
            by = gy - U * 0.6 - math.sin(i * 1.3) * U * 0.05 - c.t * U * 0.05
            w = U * 0.02; f = math.sin(c.t * 10 + i) * w * 0.6
            c.d.line([bx - w, by - f, bx, by, bx + w, by - f], fill=(40, 40, 50), width=3)
    mountains(c.d, W, gy - U * 0.02, U * 0.08, (80, 120, 90), 4, cam * 0.45)
    fern_row(c.d, W, gy + U * 0.02, U * 0.35, (50, 100, 60), 11, cam * 0.6, 0.6, c.t)
    c.d.rectangle([0, gy, W, H], fill=(95, 130, 70))
    c.d.rectangle([0, gy + U * 0.06, W, H], fill=(80, 112, 60))
    if c.river:
        c.d.polygon([(0, gy + U * 0.1), (W, gy + U * 0.07), (W, gy + U * 0.16), (0, gy + U * 0.2)], fill=(90, 150, 180))
        for i in range(8):
            xx = (i * W / 8 + c.t * 40) % W
            c.d.line([xx, gy + U * 0.13, xx + U * 0.05, gy + U * 0.13], fill=(170, 210, 230), width=3)
    if closeup:
        triceratops(c.cd, W * 0.5 - U * 0.25, gy + U * 0.05, U * 0.8, (205, 125, 70), c.t * 3, 1, horn=0.15,
                    blink=(int(c.t * 10) % 37 == 0))
    else:
        herd = [(-0.55, 0.55, (140, 95, 70)), (-0.1, 0.62, (125, 88, 66)), (0.35, 0.5, (150, 105, 75))]
        for u, sc, col in herd:
            x = W / 2 + u * U + c.t * U * 0.03
            triceratops(c.cd, x, gy + U * 0.02, U * sc, col, c.t * 4 + u * 5, 1, horn=1.0)
        triceratops(c.cd, W / 2 - U * 0.75 + c.t * U * 0.035, gy + U * 0.06, U * 0.28, (205, 125, 70), c.t * 6, 1, horn=0.15)
    c.zoom = 1.0 + 0.04 * c.k

def sc_night(c):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    base(c, (12, 10, 32), (70, 25, 40))
    stars(c.d, W, H, c.t, 90, ymax=0.45 if c.vert else 0.5)
    vx = W * 0.5
    fl = 0.7 + 0.3 * math.sin(c.t * 3)
    add_glow(c, [(vx, gy - U * 0.55, U * 0.35, (255, 70, 30), 0.6 * fl)], 22)
    volcano(c.d, vx, gy - U * 0.05, U * 0.55, U * 0.55, (30, 20, 30), (255, 110, 40))
    mountains(c.d, W, gy - U * 0.02, U * 0.07, (20, 18, 28), 3)
    fern_row(c.d, W, gy + U * 0.02, U * 0.32, (15, 22, 22), 13, 0, 0.6, c.t)
    c.d.rectangle([0, gy, W, H], fill=(18, 20, 22))
    for u, sc, col in [(-0.45, 0.5, (55, 40, 45)), (0.25, 0.55, (50, 38, 42))]:
        triceratops(c.cd, W / 2 + u * U, gy + U * 0.04, U * sc, col, 0, 1, lying=True, eye=False)
    triceratops(c.cd, W / 2 - U * 0.05, gy + U * 0.09, U * 0.3, (120, 75, 50), 0, 1, horn=0.15, lying=True,
                head_down=-0.2 * math.sin(c.t))
    c.zoom = 1.0 + 0.08 * c.k

def sc_eruption(c, run=False, alone=False):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    base(c, (40, 8, 12), (150, 45, 20))
    vx = W * 0.5 if not run else W * 0.62
    fl = 0.8 + 0.2 * math.sin(c.t * 13)
    add_glow(c, [(vx, gy - U * 0.6, U * 0.55, (255, 120, 30), 0.85 * fl), (vx, gy - U * 0.9, U * 0.3, (255, 200, 80), 0.6)], 24)
    # lava fountain
    for i in range(26):
        a = -math.pi / 2 + (h01(i, 2) - 0.5) * 1.1
        sp = U * (0.4 + 0.5 * h01(i, 3))
        tt = (c.t * 0.8 + h01(i, 4)) % 1.0
        px = vx + math.cos(a) * sp * tt
        py = gy - U * 0.6 + math.sin(a) * sp * tt + U * 0.9 * tt * tt
        r = U * 0.012 * (1.5 - tt)
        c.d.ellipse([px - r, py - r, px + r, py + r], fill=(255, 190, 60))
    volcano(c.d, vx, gy - U * 0.05, U * 0.6, U * 0.58, (25, 12, 15), (255, 160, 50))
    # lava streams
    c.d.line([vx - U * 0.04, gy - U * 0.6, vx - U * 0.2, gy - U * 0.3, vx - U * 0.32, gy - U * 0.05], fill=(255, 120, 30), width=int(U * 0.012))
    c.d.line([vx + U * 0.05, gy - U * 0.6, vx + U * 0.15, gy - U * 0.35, vx + U * 0.36, gy - U * 0.05], fill=(255, 100, 20), width=int(U * 0.01))
    # falling rocks
    for i in range(10):
        tt = (c.t * 0.6 + h01(i, 9)) % 1.0
        rx = W * h01(i, 10) + tt * U * 0.2
        ry = -U * 0.1 + tt * (gy + U * 0.1)
        r = U * (0.015 + 0.02 * h01(i, 11))
        c.d.line([rx, ry, rx - U * 0.05, ry - U * 0.12], fill=(255, 140, 40), width=int(r))
        c.d.ellipse([rx - r, ry - r, rx + r, ry + r], fill=(60, 30, 20))
    fern_row(c.d, W, gy + U * 0.02, U * 0.3, (20, 10, 12), 17, c.t * (120 if run else 0), 0.6, c.t)
    c.d.rectangle([0, gy, W, H], fill=(25, 12, 12))
    particles(c.d, W, H, c.t, 60, 21, (255, 170, 60), U * 0.004, 30, -90, flicker=True)
    if run and not alone:
        for i, (u, sc) in enumerate([(-0.2, 0.5), (0.15, 0.55), (0.45, 0.48), (-0.5, 0.52)]):
            x = W / 2 + u * U - c.t * U * 0.25
            triceratops(c.cd, x, gy + U * 0.03, U * sc, (40, 22, 22), c.t * 14 + i, -1, horn=1.0)
        triceratops(c.cd, W / 2 + U * 0.8 - c.t * U * 0.12, gy + U * 0.07, U * 0.26, (90, 50, 35), c.t * 16, -1, horn=0.15)
    if alone:
        triceratops(c.cd, W / 2 - U * 0.1, gy + U * 0.06, U * 0.32, (95, 55, 38), 0, 1, horn=0.15, head_down=0.15 * math.sin(c.t * 2))
    c.shake = U * 0.012 * (1.0 if not alone else 0.4)
    c.zoom = 1.05 + 0.05 * c.k

def sc_ash(c, footprints=True):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    base(c, (120, 118, 122), (190, 182, 175))
    add_glow(c, [(W * 0.7, gy - U * 0.7, U * 0.2, (255, 235, 210), 0.35)], 24)
    mountains(c.d, W, gy - U * 0.1, U * 0.15, (140, 136, 138), 5, c.t * 4)
    for i in range(9):  # dead trees
        x = (i + 0.5) * W / 9 + (h01(i, 31) - 0.5) * U * 0.1
        h = U * (0.25 + 0.2 * h01(i, 32))
        c.d.line([x, gy, x, gy - h], fill=(80, 76, 76), width=int(U * 0.012))
        c.d.line([x, gy - h * 0.6, x + U * 0.06, gy - h * 0.85], fill=(80, 76, 76), width=int(U * 0.007))
        c.d.line([x, gy - h * 0.45, x - U * 0.05, gy - h * 0.65], fill=(80, 76, 76), width=int(U * 0.007))
    c.d.rectangle([0, gy, W, H], fill=(170, 166, 162))
    if footprints:
        for i in range(10):
            fx = W * 0.05 + i * U * 0.12
            fy = gy + U * (0.1 if i % 2 else 0.14)
            c.d.ellipse([fx - U * 0.03, fy - U * 0.012, fx + U * 0.03, fy + U * 0.012], fill=(140, 136, 132))
    x = W / 2 + math.sin(c.t * 0.4) * U * 0.1
    triceratops(c.cd, x, gy + U * 0.08, U * 0.34, (180, 120, 85), c.t * 3, -1 if (c.t % 8) < 4 else 1, horn=0.15,
                head_down=0.2 + 0.1 * math.sin(c.t * 1.5))
    particles(c.cd, W, H, c.t, 110, 41, (225, 222, 218, 255), U * 0.005, 15, 60)
    c.zoom = 1.0 + 0.06 * c.k

def sc_smoke_forest(c, reveal=0.0, closeup=False):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    base(c, (60, 58, 62), (120, 110, 105))
    for i in range(12):
        x = (i + 0.5) * W / 12 + (h01(i, 51) - 0.5) * U * 0.1
        hh = U * (0.6 + 0.4 * h01(i, 52))
        c.d.polygon([(x - U * 0.03, gy), (x + U * 0.03, gy), (x + U * 0.01, gy - hh), (x - U * 0.01, gy - hh)], fill=(35, 33, 36))
    c.d.rectangle([0, gy, W, H], fill=(70, 66, 64))
    if closeup:
        s = U * 1.6
        trex(c.cd, W / 2 - s * 0.38 + U * 0.05, gy + U * 0.75, s, (70, 82, 60), 0, 1, jaw=0.15 + 0.15 * math.sin(c.t * 1.5),
             head_low=0.15 + 0.08 * math.sin(c.t))
        triceratops(c.cd, W / 2 + U * 0.3, gy + U * 0.1, U * 0.28, (180, 120, 85), 0, -1, horn=0.15)
    else:
        s = U * lerp(0.9, 1.15, reveal)
        x = W / 2 + lerp(-U * 0.25, -U * 0.1, reveal)
        trex(c.cd, x, gy + U * 0.04, s, (70, 82, 60), reveal * c.t * 1.5, 1, jaw=0.3 * reveal * (0.5 + 0.5 * math.sin(c.t * 2)))
        triceratops(c.cd, W / 2 + U * 0.38, gy + U * 0.1, U * 0.27, (180, 120, 85), 0, -1, horn=0.15)
    # fog
    fog = (110, 104, 100, int(lerp(200, 70, reveal)))
    for i in range(6):
        fx = (i * W / 4 + c.t * U * 0.05 * (1 + i % 2)) % (W * 1.5) - W * 0.25
        c.fog.append((fx, gy - U * 0.2 - i * U * 0.08, U * 0.45, fog))
    c.zoom = 1.0 + 0.06 * c.k

def sc_chase(c, lava_cliff=False):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    base(c, (70, 40, 40), (200, 110, 60))
    add_glow(c, [(W * 0.2, gy - U * 0.4, U * 0.4, (255, 120, 50), 0.4)], 22)
    cam = c.t * U * (1.2 if not lava_cliff else 0.1)
    mountains(c.d, W, gy - U * 0.1, U * 0.15, (80, 45, 45), 6, cam * 0.15)
    fern_row(c.d, W, gy + U * 0.02, U * 0.4, (35, 25, 25), 61, cam * 0.5, 0.7, c.t)
    c.d.rectangle([0, gy, W, H], fill=(45, 28, 25))
    if lava_cliff:
        edge = W / 2 + U * 0.35
        c.d.rectangle([edge, gy, W, H], fill=(20, 8, 8))
        c.d.polygon([(edge, gy + U * 0.35), (W, gy + U * 0.3), (W, H), (edge, H)], fill=(255, 90, 20))
        add_glow(c, [(edge + U * 0.3, gy + U * 0.35, U * 0.35, (255, 120, 30), 0.7)], 18)
        kx = edge - U * 0.12
        triceratops(c.cd, kx, gy + U * 0.05, U * 0.3, (180, 120, 85), math.sin(c.t * 5) * 0.4, -1, horn=0.15)
        tx = lerp(W / 2 - U * 1.0, W / 2 - U * 0.45, ease(c.k * 1.4))
        trex(c.cd, tx, gy + U * 0.03, U * 1.05, (70, 82, 60), c.t * 3, 1, jaw=0.4 + 0.3 * math.sin(c.t * 3))
    else:
        triceratops(c.cd, W / 2 + U * 0.28, gy + U * 0.07, U * 0.3, (180, 120, 85), c.t * 18, 1, horn=0.15)
        trex(c.cd, W / 2 - U * 0.42 + math.sin(c.t * 0.7) * U * 0.05, gy + U * 0.03, U * 1.0, (70, 82, 60), c.t * 9, 1,
             jaw=0.5 + 0.4 * math.sin(c.t * 4))
        c.shake = U * 0.006
    c.zoom = 1.02

def sc_ptero_attack(c):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    sc_chase(c, lava_cliff=True)
    k = ease(c.k * 1.6)
    px = lerp(W + U * 0.3, W / 2 - U * 0.15, k)
    py = lerp(gy - U * 1.0, gy - U * 0.88, k)
    ptero(c.cd, px, py, U * 0.55, (180, 90, 60), c.t * 14, -1)
    if c.k > 0.55:
        c.shake = U * 0.015

def sc_friend(c, fly=False):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    if fly:
        base(c, (90, 140, 200), (255, 200, 150))
        add_glow(c, [(W * 0.5, gy - U * 0.2, U * 0.4, (255, 220, 160), 0.8)], 22)
    else:
        base(c, (60, 40, 80), (250, 140, 90))
        add_glow(c, [(W * 0.3, gy - U * 0.15, U * 0.35, (255, 160, 90), 0.8)], 22)
    cam = c.t * U * (0.25 if fly else 0.02)
    mountains(c.d, W, gy - U * 0.15, U * 0.2, (110, 90, 120) if not fly else (110, 150, 140), 8, cam * 0.2)
    mountains(c.d, W, gy - U * 0.02, U * 0.1, (60, 50, 70) if not fly else (70, 130, 80), 9, cam * 0.4)
    c.d.rectangle([0, gy, W, H], fill=(50, 40, 55) if not fly else (70, 120, 70))
    if fly:
        fern_row(c.d, W, gy + U * 0.03, U * 0.3, (40, 90, 50), 71, cam * 0.7, 0.5, c.t)
        triceratops(c.cd, W / 2 - U * 0.1, gy + U * 0.08, U * 0.3, (205, 125, 70), c.t * 6, 1, horn=0.15)
        ptero(c.cd, W / 2 + U * 0.2 + math.sin(c.t) * U * 0.1, gy - U * 0.65 + math.sin(c.t * 1.3) * U * 0.05, U * 0.45,
              (180, 90, 60), c.t * 7, 1)
    else:
        c.d.polygon([(W / 2 + U * 0.05, gy), (W / 2 + U * 0.12, gy - U * 0.16), (W / 2 + U * 0.38, gy - U * 0.18),
                     (W / 2 + U * 0.45, gy)], fill=(40, 32, 45))
        ptero(c.cd, W / 2 + U * 0.22, gy - U * 0.22, U * 0.55, (180, 90, 60), 0, -1, perched=True)
        triceratops(c.cd, W / 2 - U * 0.22, gy + U * 0.08, U * 0.33, (205, 125, 70), 0, 1, horn=0.15,
                    head_down=-0.15 + 0.1 * math.sin(c.t * 1.2), blink=(int(c.t * 10) % 31 == 0))
    c.zoom = 1.0 + 0.05 * c.k

def sc_travel(c):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    day = 0.5 + 0.5 * math.cos(c.t * 0.9)
    base(c, lc((15, 15, 40), (110, 170, 220), day), lc((60, 40, 70), (250, 215, 170), day))
    if day < 0.5: stars(c.d, W, H, c.t, 70)
    cam = c.t * U * 0.3
    mountains(c.d, W, gy - U * 0.12, U * 0.18, lc((30, 30, 50), (130, 140, 150), day), 12, cam * 0.2)
    c.d.rectangle([0, gy, W, H], fill=lc((30, 28, 35), (180, 140, 95), day))
    fern_row(c.d, W, gy + U * 0.02, U * 0.25, lc((20, 25, 25), (90, 110, 60), day), 81, cam * 0.6, 0.3, c.t)
    triceratops(c.cd, W / 2 - U * 0.05, gy + U * 0.08, U * 0.3, lc((90, 60, 45), (205, 125, 70), day), c.t * 6, 1, horn=0.15)
    ptero(c.cd, W / 2 + U * 0.3, gy - U * 0.7 + math.sin(c.t) * U * 0.05, U * 0.38, lc((70, 40, 30), (180, 90, 60), day), c.t * 8, 1)
    c.zoom = 1.0

def sc_bones(c, nest_close=False, trex_far=0.0, brace=False):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    base(c, (190, 130, 90), (245, 205, 150))
    add_glow(c, [(W * 0.5, gy - U * 0.5, U * 0.3, (255, 230, 180), 0.6)], 22)
    mountains(c.d, W, gy - U * 0.08, U * 0.12, (190, 140, 100), 14, c.t * 3)
    c.d.rectangle([0, gy, W, H], fill=(200, 160, 115))
    bone = (245, 238, 220)
    if nest_close:
        ribs(c.d, W / 2 - U * 0.55, gy, U * 0.6, bone)
        ribs(c.d, W / 2 + U * 0.6, gy, U * 0.5, bone)
        nest(c.d, W / 2 + U * 0.05, gy + U * 0.12, U * 0.3)
        egg(c.cd, W / 2 + U * 0.05, gy + U * 0.08, U * 0.28, 0, math.sin(c.t * 3) * 0.04 * c.k)
        if not brace:
            triceratops(c.cd, W / 2 - U * 0.42, gy + U * 0.1, U * 0.33, (205, 125, 70), 0, 1, horn=0.15, head_down=0.35)
    else:
        ribs(c.d, W / 2 - U * 0.15, gy, U * 0.8, bone)
        ribs(c.d, W / 2 + U * 0.75, gy, U * 0.55, bone)
        skull(c.d, W / 2 - U * 0.75, gy, U * 0.45, bone, (170, 130, 95))
        triceratops(c.cd, W / 2 + U * 0.05 + c.t * U * 0.02, gy + U * 0.1, U * 0.3, (205, 125, 70), c.t * 4, 1, horn=0.15)
        ptero(c.cd, W / 2 + math.cos(c.t * 0.7) * U * 0.35, gy - U * 0.8 + math.sin(c.t * 0.7) * U * 0.08, U * 0.32,
              (180, 90, 60), c.t * 6, 1 if math.sin(c.t * 0.7) < 0 else -1)
    if trex_far > 0:
        s = U * lerp(0.5, 1.0, trex_far)
        trex(c.cd, lerp(W / 2 - U * 1.1, W / 2 - U * 0.75, trex_far), gy + U * 0.02, s, (70, 82, 60), c.t * 2.5, 1,
             jaw=0.25, head_low=0.1)
        c.shake = U * 0.004 * trex_far
    if brace:
        triceratops(c.cd, W / 2 - U * 0.25, gy + U * 0.1, U * 0.36, (205, 125, 70), math.sin(c.t * 8) * 0.15, -1,
                    horn=0.15, head_down=0.3)
    particles(c.d, W, H, c.t, 30, 91, (235, 210, 170), U * 0.004, 40, 5, 0.3, 0.75)
    c.zoom = 1.0 + 0.07 * c.k

def sc_fight(c, stage):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    base(c, (170, 100, 70), (240, 190, 140))
    mountains(c.d, W, gy - U * 0.08, U * 0.12, (180, 125, 90), 14)
    c.d.rectangle([0, gy, W, H], fill=(190, 145, 100))
    bone = (245, 238, 220)
    k = c.k
    if stage == "charge":
        ribs(c.d, W / 2 + U * 0.55, gy, U * 0.6, bone)
        tx = lerp(W / 2 - U * 1.0, W / 2 + U * 0.25, ease(k * 1.3))
        kx = W / 2 + (U * 0.05 if k < 0.45 else U * 0.05 - U * 0.45 * ease((k - 0.45) * 4))
        triceratops(c.cd, kx, gy + U * 0.1, U * 0.33, (205, 125, 70), c.t * 10, -1, horn=0.15, head_down=0.3)
        if k < 0.75:
            trex(c.cd, tx, gy + U * 0.03, U * 1.0, (70, 82, 60), c.t * 9, 1, jaw=0.6)
            c.shake = U * 0.01
        else:
            trex(c.cd, W / 2 + U * 0.25, gy + U * 0.03, U * 1.0, (70, 82, 60), 0, 1, jaw=0.2, rot=0.35)
            for i in range(30):
                a = h01(i, 5) * math.pi; r = U * 0.5 * (k - 0.75) * 4 * h01(i, 6)
                c.fog.append((W / 2 + U * 0.5 + math.cos(a) * r * 1.5, gy - math.sin(a) * r * 0.6, U * 0.12, (230, 205, 170, 140)))
            c.shake = U * 0.02 * (1 - (k - 0.75) * 4)
    elif stage == "rise":
        trex(c.cd, W / 2 + U * 0.05, gy + U * 0.03, U * 1.05, (70, 82, 60), 0, 1, jaw=0.6 + 0.3 * math.sin(c.t * 5),
             rot=lerp(0.3, 0.0, ease(k * 2)))
        px = lerp(W + U * 0.2, W / 2 + U * 0.55, ease(k * 1.5))
        ptero(c.cd, px + math.sin(c.t * 8) * U * 0.03, gy - U * 0.95 + math.cos(c.t * 8) * U * 0.03, U * 0.5, (180, 90, 60), c.t * 16, -1)
        triceratops(c.cd, W / 2 - U * 0.55, gy + U * 0.1, U * 0.33, (205, 125, 70), 0, 1, horn=0.15, head_down=0.3)
        c.shake = U * 0.006
    elif stage == "fall":
        kx = lerp(W / 2 - U * 0.75, W / 2 - U * 0.15, ease(k * 2.5))
        rot = 0.0 if k < 0.4 else -1.3 * ease((k - 0.4) * 2)
        trex(c.cd, W / 2 + U * 0.15, gy + U * 0.03, U * 1.05, (70, 82, 60), 0, 1, jaw=0.7, rot=rot)
        triceratops(c.cd, kx, gy + U * 0.1, U * 0.33, (205, 125, 70), c.t * 14 if k < 0.4 else 0, 1, horn=0.15, head_down=0.35)
        ptero(c.cd, W / 2 + U * 0.45, gy - U * 0.95, U * 0.45, (180, 90, 60), c.t * 9, -1)
        if 0.38 < k < 0.6: c.shake = U * 0.025
    elif stage == "leave":
        kk = ease(k)
        trex(c.cd, lerp(W / 2 + U * 0.1, W / 2 + U * 0.9, kk), gy - U * 0.05 * kk, U * lerp(1.0, 0.45, kk), (70, 82, 60),
             c.t * 2.5, 1, jaw=0.0)
        triceratops(c.cd, W / 2 - U * 0.45, gy + U * 0.1, U * 0.33, (205, 125, 70), 0, 1, horn=0.15)
        ptero(c.cd, W / 2 - U * 0.15, gy - U * 0.15, U * 0.4, (180, 90, 60), 0, 1, perched=True)
    elif stage == "hatch":
        nest(c.d, W / 2, gy + U * 0.12, U * 0.32)
        crack = clamp(k * 2.2)
        if k < 0.55:
            egg(c.cd, W / 2, gy + U * 0.08, U * 0.3, crack, math.sin(c.t * 14) * 0.08)
        else:
            egg(c.cd, W / 2 + U * 0.12, gy + U * 0.1, U * 0.15, 1, 0.6)
            triceratops(c.cd, W / 2 - U * 0.08, gy + U * 0.08, U * 0.16, (225, 150, 95), 0, -1, horn=0.05,
                        blink=(int(c.t * 10) % 23 == 0))
        triceratops(c.cd, W / 2 - U * 0.42, gy + U * 0.1, U * 0.36, (205, 125, 70), 0, 1, horn=0.15, head_down=0.25)
        c.zoom = 1.0 + 0.1 * k

def sc_green_valley(c, reunion=False, night=False, asteroid=0.0):
    W, H, gy, U = c.W, c.H, c.gy, c.U
    if night:
        base(c, (8, 10, 30), (40, 30, 70))
        stars(c.d, W, H, c.t, 130)
    else:
        base(c, (100, 175, 240), (240, 240, 200))
        add_glow(c, [(W * 0.75, gy - U * 0.7, U * 0.25, (255, 240, 190), 0.8)], 22)
    if asteroid > 0:
        ax, ay = W * 0.7, gy - U * (0.62 if c.vert else 0.6)
        r = U * (0.012 + 0.05 * asteroid)
        add_glow(c, [(ax, ay, r * 4, (255, 170, 90), 0.5 + 0.4 * asteroid)], 16)
        c.d.line([ax, ay, ax + r * 6, ay - r * 5], fill=(255, 160, 80), width=max(2, int(r * 0.6)))
        c.d.ellipse([ax - r, ay - r, ax + r, ay + r], fill=(255, 235, 200))
    mc = (35, 35, 60) if night else (110, 160, 150)
    mountains(c.d, W, gy - U * 0.12, U * 0.16, mc, 21, c.t * 5)
    mountains(c.d, W, gy - U * 0.02, U * 0.08, (25, 35, 40) if night else (80, 150, 80), 22, c.t * 9)
    fern_row(c.d, W, gy + U * 0.02, U * 0.3, (15, 30, 25) if night else (50, 120, 60), 23, c.t * 10, 0.5, c.t)
    c.d.rectangle([0, gy, W, H], fill=(25, 35, 30) if night else (100, 160, 80))
    if reunion:
        mx = lerp(W / 2 + U * 0.6, W / 2 + U * 0.25, ease(c.k * 2))
        triceratops(c.cd, mx, gy + U * 0.06, U * 0.6, (130, 90, 70), c.t * 8 if c.k < 0.5 else 0, -1, horn=1.0,
                    head_down=0.2 if c.k > 0.5 else 0)
        triceratops(c.cd, W / 2 - U * 0.25, gy + U * 0.1, U * 0.32, (205, 125, 70), 0, 1, horn=0.15)
        triceratops(c.cd, W / 2 - U * 0.5, gy + U * 0.11, U * 0.16, (225, 150, 95), c.t * 2, 1, horn=0.05)
        ptero(c.cd, W / 2 - U * 0.1, gy - U * 0.75, U * 0.35, (180, 90, 60), c.t * 7, 1)
    elif night:
        for u, sc, col in [(-0.5, 0.5, (40, 32, 40)), (0.35, 0.55, (38, 30, 38))]:
            triceratops(c.cd, W / 2 + u * U, gy + U * 0.04, U * sc, col, 0, 1, lying=True, eye=False)
        triceratops(c.cd, W / 2 - U * 0.4, gy + U * 0.09, U * 0.13, (80, 60, 50), 0, 1, horn=0.05, lying=True, eye=False)
        triceratops(c.cd, W / 2 - U * 0.08, gy + U * 0.09, U * 0.3, (110, 75, 55), 0, 1, horn=0.15, lying=True,
                    head_down=-0.35 if asteroid > 0 else -0.1)
        ptero(c.cd, W / 2 + U * 0.12, gy - U * 0.08, U * 0.32, (90, 50, 40), 0, 1, perched=True)
    else:
        herd = [(-0.7, 0.5, (140, 95, 70)), (0.45, 0.55, (125, 88, 66)), (0.05, 0.6, (130, 90, 70))]
        for u, sc, col in herd:
            triceratops(c.cd, W / 2 + u * U + c.t * U * 0.02, gy + U * 0.03, U * sc, col, c.t * 3 + u * 4, 1, horn=1.0)
        triceratops(c.cd, W / 2 - U * 0.25 + c.t * U * 0.02, gy + U * 0.08, U * 0.32, (205, 125, 70), c.t * 3.5, 1, horn=0.15)
        triceratops(c.cd, W / 2 - U * 0.45 + c.t * U * 0.02, gy + U * 0.1, U * 0.16, (225, 150, 95), c.t * 6, 1, horn=0.05)
    c.zoom = 1.0 + (0.12 * c.k if asteroid > 0 else 0.04 * c.k)

# cue phrase -> scene lambda
SCENES = {
    1: [("Part", lambda c: sc_valley_day(c)),
        ("But Kira had", lambda c: (setattr(c, 'birds', True), setattr(c, 'river', True), sc_valley_day(c, closeup=True))),
        ("One night", sc_night),
        ("Then the mountain", lambda c: sc_eruption(c)),
        ("The herd panicked", lambda c: sc_eruption(c, run=True)),
        ("And in all", lambda c: sc_eruption(c, alone=True))],
    2: [("Part", lambda c: sc_ash(c)),
        ("Then she heard", lambda c: sc_smoke_forest(c, 0.0)),
        ("From the smoke", lambda c: sc_smoke_forest(c, ease(c.k * 2))),
        ("He lowered", lambda c: sc_smoke_forest(c, 1.0, closeup=True)),
        ("She ran", lambda c: sc_chase(c))],
    3: [("Part", lambda c: sc_chase(c)),
        ("The ground ended", lambda c: sc_chase(c, lava_cliff=True)),
        ("Then a shadow", sc_ptero_attack),
        ("The flying", lambda c: sc_friend(c)),
        ("But when Zephyr", lambda c: sc_friend(c, fly=True))],
    4: [("Part", sc_travel),
        ("On the fourth", lambda c: sc_bones(c)),
        ("In the middle", lambda c: sc_bones(c, nest_close=True)),
        ("Then the ground", lambda c: sc_bones(c, nest_close=True, trex_far=ease(c.k * 1.5))),
        ("Kira lowered", lambda c: sc_bones(c, nest_close=True, trex_far=1.0, brace=True))],
    5: [("Part", lambda c: sc_fight(c, "charge")),
        ("He rose again", lambda c: sc_fight(c, "rise")),
        ("Kira charged", lambda c: sc_fight(c, "fall")),
        ("Then the tyrant", lambda c: sc_fight(c, "leave")),
        ("Behind Kira", lambda c: sc_fight(c, "hatch"))],
    6: [("Part", lambda c: sc_green_valley(c)),
        ("Her mother", lambda c: sc_green_valley(c, reunion=True)),
        ("Nobody called", lambda c: sc_green_valley(c)),
        ("That night", lambda c: sc_green_valley(c, night=True)),
        ("And high above", lambda c: sc_green_valley(c, night=True, asteroid=ease(c.k))),
        ("Some stories", lambda c: sc_green_valley(c, night=True, asteroid=1.0))],
}

def norm(w): return re.sub(r"[^a-z]", "", w.lower())

def scene_schedule(part):
    words = TIMING[part - 1]["words"]
    total = TIMING[part - 1]["duration"]
    nw = [norm(w["w"]) for w in words]
    starts = []
    for phrase, fn in SCENES[part]:
        ph = [norm(x) for x in phrase.split()]
        idx = None
        for i in range(len(nw) - len(ph) + 1):
            if nw[i:i + len(ph)] == ph and (not starts or i >= starts[-1][2]):
                idx = i; break
        assert idx is not None, (part, phrase)
        t0 = 0.0 if not starts else words[idx]["t0"] - 0.15
        starts.append([t0, fn, idx])
    out = []
    for i, (t0, fn, _) in enumerate(starts):
        t1 = starts[i + 1][0] if i + 1 < len(starts) else total
        out.append((t0, t1, fn))
    return out

# ----------------------------------------------------------------- captions & overlays
_fonts = {}
def font(path, size):
    k = (path, size)
    if k not in _fonts: _fonts[k] = ImageFont.truetype(path, size)
    return _fonts[k]

def caption_groups(words):
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 or re.search(r"[.,?!]$", w["w"]):
            groups.append(cur); cur = []
    if cur: groups.append(cur)
    return groups

def draw_caption(img, groups, t, W, H, vert):
    g = None
    for i, gr in enumerate(groups):
        end = groups[i + 1][0]["t0"] if i + 1 < len(groups) else gr[-1]["t1"] + 0.6
        end = min(end, gr[-1]["t1"] + 0.8)
        if gr[0]["t0"] - 0.05 <= t < end:
            g = gr; break
    if not g: return
    d = ImageDraw.Draw(img)
    size = int(W * (0.088 if vert else 0.048))
    f = font(FONT_BLACK, size)
    words = [w["w"].upper() for w in g]
    space = size * 0.28
    widths = [d.textlength(w, font=f) for w in words]
    total = sum(widths) + space * (len(words) - 1)
    maxw = W * 0.9
    if total > maxw:
        size = int(size * maxw / total); f = font(FONT_BLACK, size)
        widths = [d.textlength(w, font=f) for w in words]; space = size * 0.28
        total = sum(widths) + space * (len(words) - 1)
    pop = clamp((t - g[0]["t0"]) / 0.12)
    y = H * (0.665 if vert else 0.80)
    x = (W - total) / 2
    for w, wd, wo in zip(words, widths, g):
        active = wo["t0"] <= t < wo["t1"] + 0.05
        col = HL_COLOR[0] if active else (255, 255, 255)
        yy = y - (size * 0.06 if active else 0) + (1 - pop) * size * 0.25
        d.text((x, yy), w, font=f, fill=col, stroke_width=max(4, size // 9), stroke_fill=(0, 0, 0))
        x += wd + space

def draw_header(img, part, t, W, H):
    d = ImageDraw.Draw(img)
    f1 = font(FONT_BLACK, int(W * 0.11))
    f2 = font(FONT_BLACK, int(W * 0.06))
    txt = f"PART {part}"
    tw = d.textlength(txt, font=f1)
    y = H * 0.115
    d.rounded_rectangle([(W - tw) / 2 - W * 0.04, y - W * 0.012, (W + tw) / 2 + W * 0.04, y + W * 0.125],
                        radius=int(W * 0.03), fill=HEADER_COLOR[0])
    d.text(((W - tw) / 2, y), txt, font=f1, fill=(255, 255, 255))
    title = TITLES[part - 1].upper()
    sz = int(W * 0.06)
    while d.textlength(title, font=f2) > W * 0.88:
        sz -= 2; f2 = font(FONT_BLACK, sz)
    tw2 = d.textlength(title, font=f2)
    d.text(((W - tw2) / 2, y + W * 0.15), title, font=f2, fill=(255, 255, 255), stroke_width=max(4, sz // 9), stroke_fill=(0, 0, 0))

def draw_endcard(img, part, k, W, H, vert):
    if k <= 0: return
    ov = Image.new("RGBA", (W, H), (0, 0, 0, int(150 * k)))
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)
    if part < 6:
        a, b = f"PART {part + 1}", "FOLLOW SO YOU DON'T MISS IT"
    else:
        a, b = "THE END...?", END_TEXT[0]
    f1 = font(FONT_BLACK, int(W * (0.13 if vert else 0.08)))
    f2 = font(FONT_BLACK, int(W * (0.05 if vert else 0.03)))
    y = H * (0.40 if vert else 0.38)
    for txt, f, col, dy in [(a, f1, HL_COLOR[0], 0), (b, f2, (255, 255, 255), f1.size * 1.25)]:
        tw = d.textlength(txt, font=f)
        d.text(((W - tw) / 2, y + dy), txt, font=f, fill=col, stroke_width=max(4, f.size // 10), stroke_fill=(0, 0, 0))

def draw_chapter(img, part, t, W, H):
    k = clamp(t / 0.4) * clamp((4.0 - t) / 0.5)
    if k <= 0: return
    d = ImageDraw.Draw(img)
    f1 = font(FONT_BLACK, int(H * 0.05)); f2 = font(FONT_BLACK, int(H * 0.075))
    x = W * 0.05; y = H * 0.07
    a = int(255 * k)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
    ld.text((x, y), f"PART {part}", font=f1, fill=HL_COLOR[0] + (a,), stroke_width=4, stroke_fill=(0, 0, 0, a))
    ld.text((x, y + H * 0.065), TITLES[part - 1].upper(), font=f2, fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, a))
    img.paste(layer, (0, 0), layer)

# ----------------------------------------------------------------- frame
VIGNETTE = {}
def vignette(W, H):
    if (W, H) not in VIGNETTE:
        y, x = np.ogrid[0:H, 0:W]
        r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
        m = np.clip(1.0 - 0.35 * np.clip(r - 0.6, 0, 1) ** 1.5, 0, 1)
        VIGNETTE[(W, H)] = Image.fromarray((m * 255).astype(np.uint8), "L")
    return VIGNETTE[(W, H)]

BF = {}
def bottom_fade(W, H, vert):
    if (W, H) not in BF:
        y = np.linspace(0, 1, H)[:, None]
        start = 0.66 if vert else 0.78
        m = 1.0 - 0.6 * np.clip((y - start) / (1 - start), 0, 1)
        BF[(W, H)] = Image.fromarray(np.repeat((m * 255).astype(np.uint8), W, axis=1), "L")
    return BF[(W, H)]

def render_frame(part, t, W, H, mode, sched, groups):
    vert = mode == "vertical"
    c = Ctx(); c.W, c.H = W, H; c.U = min(W, H) if not vert else W * 0.82
    c.vert = vert
    TREX_K[0] = 0.62 if vert else 0.6
    c.gy = H * (0.58 if vert else 0.74)
    c.img = Image.new("RGB", (W, H)); c.d = ImageDraw.Draw(c.img)
    chars = Image.new("RGBA", (W, H), (0, 0, 0, 0)); c.cd = ImageDraw.Draw(chars)
    c.zoom, c.shake, c.fog, c.birds, c.river, c.flash = 1.0, 0.0, [], False, False, 0.0
    for i, (t0, t1, fn) in enumerate(sched):
        if t0 <= t < t1 or (i == len(sched) - 1 and t >= t0):
            c.t = t - t0; c.tl = t - t0; c.k = clamp((t - t0) / max(0.1, t1 - t0))
            fn(c); trans = (t - t0); break
    # shadow pass for characters: soften edges
    chars = chars.filter(ImageFilter.GaussianBlur(0.9))
    c.img.paste(chars, (0, 0), chars)
    if c.fog:
        fl = Image.new("RGBA", (W // 4, H // 4), (0, 0, 0, 0)); fd = ImageDraw.Draw(fl)
        for x, y, r, col in c.fog:
            fd.ellipse([(x - r) / 4, (y - r * 0.4) / 4, (x + r) / 4, (y + r * 0.4) / 4], fill=col)
        fl = fl.filter(ImageFilter.GaussianBlur(8)).resize((W, H), Image.BILINEAR)
        c.img.paste(fl, (0, 0), fl)
    img = c.img
    if c.flash:
        img = Image.blend(img, Image.new("RGB", (W, H), (200, 210, 230)), c.flash)
    z = c.zoom
    sx = sy = 0
    if c.shake:
        sx = math.sin(t * 47) * c.shake; sy = math.cos(t * 39) * c.shake; z = max(z, 1.0 + 2.2 * c.shake / min(W, H))
    if z > 1.001 or c.shake:
        cw, ch = W / z, H / z
        x0 = clamp((W - cw) / 2 + sx, 0, W - cw); y0 = clamp((H - ch) / 2 + sy, 0, H - ch)
        img = img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    # crossfade from black on scene changes
    if trans < 0.25 and t > 0.3:
        img = Image.blend(Image.new("RGB", (W, H)), img, 0.35 + 0.65 * trans / 0.25)
    black = Image.new("RGB", (W, H))
    img = Image.composite(img, black, vignette(W, H))
    img = Image.composite(img, black, bottom_fade(W, H, vert))
    total = TIMING[part - 1]["duration"]
    if t < 0.35 and (part == 1 or vert):
        img = Image.blend(black, img, t / 0.35)
    if vert:
        draw_header(img, part, t, W, H)
    else:
        draw_chapter(img, part, t, W, H)
    end_start = total - (1.7 if part < 6 else 3.5)
    if t < end_start:
        draw_caption(img, groups, t, W, H, vert)
    if vert or part == 6:
        draw_endcard(img, part, clamp((t - end_start) / 0.3), W, H, vert)
    return img

def main():
    mode, part = sys.argv[1], int(sys.argv[2])
    W, H = (1080, 1920) if mode == "vertical" else (1920, 1080)
    sched = scene_schedule(part)
    groups = caption_groups(TIMING[part - 1]["words"])
    total = TIMING[part - 1]["duration"]
    n = int(math.ceil(total * FPS))
    if len(sys.argv) > 3:  # preview stills
        for ts in sys.argv[3:]:
            render_frame(part, float(ts), W, H, mode, sched, groups).save(f"preview2/{mode}_p{part}_{ts}.jpg", quality=85)
        return
    out = f"build/{mode}_p{part}.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-i", f"audio/mix_p{part}.wav", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out],
                         stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(render_frame(part, i / FPS, W, H, mode, sched, groups).tobytes())
    p.stdin.close(); p.wait()
    print("done", out)

if __name__ == "__main__":
    main()
