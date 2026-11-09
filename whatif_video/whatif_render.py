"""'What if' shorts: two standalone ~61 s vertical videos. Reuses the dino renderer engine.

  python3 whatif_render.py vertical <1|2> [preview times...]
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dino_video"))
import render as R
from render import (clamp, lerp, ease, lc, dark, ell, rot_pts, h01, mountains, particles, stars, base, add_glow, Xf,
                    fern_row, triceratops, trex, ptero)
from PIL import Image, ImageDraw

G = {"t": 0.0, "part": 1, "stamps": [], "dk": None}
THEME = {1: dict(badge=(232, 84, 20), hl=(255, 221, 0), title=["THE ASTEROID", "MISSED?"]),
         2: dict(badge=(14, 104, 186), hl=(90, 228, 255), title=["YOU FELL INTO THE", "DEEPEST OCEAN?"])}
R.TITLES = ["What if the asteroid missed?", "What if you fell into the deepest ocean?"]
YEL, WHITE, RED = (255, 221, 0), (255, 255, 255), (255, 80, 70)

# ----------------------------------------------------------------- cues / overlays
_cue = {}
def cue(part, phrase):
    key = (part, phrase)
    if key not in _cue:
        words = R.TIMING[part - 1]["words"]
        nw = [R.norm(w["w"]) for w in words]; ph = [R.norm(x) for x in phrase.split()]
        _cue[key] = next(words[i]["t0"] for i in range(len(nw) - len(ph) + 1) if nw[i:i + len(ph)] == ph)
    return _cue[key]

def since(phrase): return G["t"] - cue(G["part"], phrase)

def stamp(text, x, y, size, color=WHITE, k=1.0):
    G["stamps"].append((text, x, y, size, color, clamp(k)))

def pop(phrase, text, x, y, size, color=WHITE, hold=None):
    s = since(phrase)
    if s >= 0 and (hold is None or s < hold):
        stamp(text, x, y, size, color, s / 0.14)

def draw_stamps(img, W, H):
    d = ImageDraw.Draw(img)
    for text, x, y, size, color, k in G["stamps"]:
        sc = 0.55 + 0.45 * ease(k) + 0.12 * math.sin(min(1.0, k) * math.pi)
        f = R.font(R.FONT_BLACK, max(10, int(W * size * sc)))
        lines = text.split("\n")
        lh = f.size * 1.08
        y0 = y * H - lh * len(lines) / 2
        for i, l in enumerate(lines):
            tw = d.textlength(l, font=f)
            d.text((x * W - tw / 2, y0 + i * lh), l, font=f, fill=color, stroke_width=max(4, f.size // 8), stroke_fill=(0, 0, 0))

def draw_header(img, part, t, W, H):
    th = THEME[part]; d = ImageDraw.Draw(img)
    big = 1.0 + 0.28 * (1 - ease((t - 2.4) / 0.5))
    f1 = R.font(R.FONT_BLACK, int(W * 0.066 * big))
    txt = "WHAT IF…"
    tw = d.textlength(txt, font=f1)
    y = H * 0.085
    d.rounded_rectangle([(W - tw) / 2 - W * 0.035, y - W * 0.008, (W + tw) / 2 + W * 0.035, y + f1.size * 1.2],
                        radius=int(W * 0.025), fill=th["badge"])
    d.text(((W - tw) / 2, y), txt, font=f1, fill=WHITE)
    y += f1.size * 1.42
    for i, line in enumerate(th["title"]):
        sz = int(W * 0.078 * big)
        f2 = R.font(R.FONT_BLACK, sz)
        while d.textlength(line, font=f2) > W * 0.92:
            sz -= 2; f2 = R.font(R.FONT_BLACK, sz)
        tw2 = d.textlength(line, font=f2)
        d.text(((W - tw2) / 2, y), line, font=f2, fill=th["hl"] if i == len(th["title"]) - 1 else WHITE,
               stroke_width=max(5, sz // 8), stroke_fill=(0, 0, 0))
        y += sz * 1.12

def draw_endcard(img, part, k, W, H, vert):
    if k <= 0: return
    ov = Image.new("RGBA", (W, H), (0, 0, 0, int(175 * k)))
    img.paste(ov, (0, 0), ov)
    d = ImageDraw.Draw(img)
    f1 = R.font(R.FONT_BLACK, int(W * 0.17)); f2 = R.font(R.FONT_BLACK, int(W * 0.062))
    y = H * 0.40 + (1 - k) * 40
    for txt, f, col, dy in [("FOLLOW", f1, THEME[part]["hl"], 0), ("FOR MORE WHAT IFS", f2, WHITE, f1.size * 1.2)]:
        tw = d.textlength(txt, font=f)
        d.text(((W - tw) / 2, y + dy), txt, font=f, fill=col, stroke_width=max(5, f.size // 10), stroke_fill=(0, 0, 0))

R.draw_header = draw_header
R.draw_endcard = draw_endcard

# ================================================================= VIDEO 1: asteroid
_earth = {}
def earth(c, cx, cy, r, glow=0.5):
    r = int(r)
    if r not in _earth:
        S = 2 * r; L = Image.new("RGB", (S, S), (26, 86, 168)); d = ImageDraw.Draw(L)
        for i in range(11):
            x = h01(i, 301) * S; y = h01(i, 302) * S; rx = S * (0.07 + 0.11 * h01(i, 303)); ry = S * (0.05 + 0.07 * h01(i, 304))
            d.polygon(ell(x, y, rx, ry, 16, rot=h01(i, 305) * 3), fill=(58, 138, 78))
            d.polygon(ell(x + rx * 0.6, y + ry * 0.5, rx * 0.6, ry * 0.75, 12, rot=h01(i, 306) * 3), fill=(92, 150, 84))
        for i in range(16):
            x = h01(i, 311) * S; y = h01(i, 312) * S
            d.polygon(ell(x, y, S * (0.05 + 0.07 * h01(i, 313)), S * 0.014, 12, rot=0.2), fill=(236, 242, 248))
        sh = Image.new("RGB", (S, S), (4, 8, 24)); m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).ellipse([-S * 0.35, -S * 0.15, S * 0.9, S * 1.1], fill=255)
        from PIL import ImageFilter
        m = m.filter(ImageFilter.GaussianBlur(S * 0.06))
        L = Image.composite(L, Image.blend(L, sh, 0.72), m)
        mask = Image.new("L", (S, S), 0); ImageDraw.Draw(mask).ellipse([1, 1, S - 2, S - 2], fill=255)
        L.putalpha(mask)
        _earth[r] = L
    add_glow(c, [(cx, cy, r * 1.07, (70, 150, 255), glow)], 12)
    c.img.paste(_earth[r], (int(cx - r), int(cy - r)), _earth[r])
    c.d = ImageDraw.Draw(c.img)

def asteroid(c, x, y, r, ang, fire=1.0):
    bx, by = -math.cos(ang), -math.sin(ang); px, py = -by, bx
    if fire > 0:
        add_glow(c, [(x + bx * r * k * 1.5, y + by * r * k * 1.5, r * (1.9 - 0.14 * k), (255, 150 - 10 * k, 40), 0.55 * fire * (1 - k / 9))
                     for k in range(8)], 10)
        fl = 1 + 0.12 * math.sin(G["t"] * 40)
        c.d.polygon([(x + px * r, y + py * r), (x - px * r, y - py * r), (x + bx * r * 9 * fl, y + by * r * 9 * fl)], fill=(255, 150, 50))
        c.d.polygon([(x + px * r * 0.6, y + py * r * 0.6), (x - px * r * 0.6, y - py * r * 0.6), (x + bx * r * 5.5 * fl, y + by * r * 5.5 * fl)],
                    fill=(255, 226, 150))
    pts = [(x + math.cos(i / 12 * 6.283) * r * (0.82 + 0.3 * h01(i, 77)), y + math.sin(i / 12 * 6.283) * r * (0.82 + 0.3 * h01(i, 78)))
           for i in range(12)]
    c.cd.polygon(pts, fill=(104, 88, 76))
    for i in range(3):
        ax = x + (h01(i, 81) - 0.5) * r * 0.9; ay = y + (h01(i, 82) - 0.5) * r * 0.9; rr = r * (0.14 + 0.1 * h01(i, 83))
        c.cd.ellipse([ax - rr, ay - rr, ax + rr, ay + rr], fill=(70, 58, 52))

def space(c):
    base(c, (3, 4, 14), (12, 10, 34))
    stars(c.d, c.W, c.H, G["t"], 150, ymax=1.0)

def a_approach(c):
    W, H, U = c.W, c.H, c.U
    space(c)
    earth(c, W * 0.42, H * 0.83, U * 0.62)
    k = c.k
    x = lerp(W * 1.02, W * 0.66, k); y = lerp(H * 0.25, H * 0.47, k)
    asteroid(c, x, y, U * lerp(0.035, 0.085, k), math.atan2(H * 0.22, -W * 0.36))
    pop("a rock", "66,000,000 YEARS AGO", 0.5, 0.29, 0.05, YEL, hold=4.5)
    c.zoom = 1.0 + 0.1 * k; c.shake = U * 0.004 * k

def a_miss(c):
    W, H, U = c.W, c.H, c.U
    space(c)
    earth(c, W * 0.42, H * 0.83, U * 0.62, glow=0.5 + 0.3 * ease(c.k))
    k = clamp(c.tl / 2.2)
    if k < 1:
        x = lerp(W * 0.66, -W * 0.35, ease(k) * 0.4 + k * 0.6); y = lerp(H * 0.47, H * 0.40, k)
        asteroid(c, x, y, U * 0.085, math.atan2(-H * 0.07, -W))
        c.shake = U * 0.014 * math.sin(k * math.pi)
        if 0.3 < k < 0.42: c.flash = 0.35
    pop("it passes", "MISSED!", 0.5, 0.30, 0.13, YEL, hold=1.5)
    for i, (ph, tx) in enumerate([("No explosion", "NO EXPLOSION"), ("No fire", "NO FIRE"), ("No endless", "NO WINTER")]):
        pop(ph, tx, 0.5, 0.285 + i * 0.045, 0.062, RED if i < 2 else (150, 215, 255))
    c.zoom = 1.04

def a_morning(c):
    c.birds = True
    R.sc_valley_day(c)
    W, H, U = c.W, c.H, c.U
    ptero(c.cd, W * 0.2 + c.t * U * 0.12, c.gy - U * 0.72 + math.sin(c.t * 1.4) * U * 0.03, U * 0.3, (180, 90, 60), c.t * 7, 1)
    pop("nothing has", "JUST ANOTHER DAY", 0.5, 0.29, 0.055, WHITE)

def a_king(c):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (235, 150, 70), (255, 220, 150))
    add_glow(c, [(W * 0.5, gy - U * 0.45, U * 0.5, (255, 230, 170), 0.7)], 24)
    mountains(c.d, W, gy - U * 0.08, U * 0.16, (170, 100, 70), 31, c.t * 4)
    fern_row(c.d, W, gy + U * 0.02, U * 0.36, (70, 60, 40), 33, c.t * 6, 0.6, c.t)
    c.d.rectangle([0, gy, W, H], fill=(96, 78, 46))
    s = U * 0.9; x = W * 0.5 - U * 0.17
    roar = 0.55 + 0.4 * math.sin(c.t * 5)
    trex(c.cd, x, gy + U * 0.05, s, (70, 92, 60), math.sin(c.t * 2) * 0.3, 1, jaw=roar, head_low=-0.05)
    K = R.TREX_K[0] * s
    hx, hy = x + 0.37 * K, gy + U * 0.05 - 0.985 * K
    w = K * 0.13; bob = math.sin(c.t * 5) * K * 0.006
    c.cd.polygon([(hx - w, hy + bob), (hx - w * 1.1, hy - w * 0.9 + bob), (hx - w * 0.5, hy - w * 0.35 + bob), (hx, hy - w * 1.15 + bob),
                  (hx + w * 0.5, hy - w * 0.35 + bob), (hx + w * 1.1, hy - w * 0.9 + bob), (hx + w, hy + bob)], fill=(255, 205, 40))
    c.cd.rectangle([hx - w, hy - w * 0.18 + bob, hx + w, hy + w * 0.12 + bob], fill=(235, 170, 20))
    n = 1 + int(64 * ease(c.k))
    stamp(f"+{n},000,000 YEARS", 0.5, 0.295, 0.062, YEL, c.tl / 0.14)
    c.shake = U * 0.006
    c.zoom = 1.0 + 0.06 * c.k

def mammal(d, x, y, s, facing=1, blink=False):
    X = Xf(x, y, s, facing)
    fur = (120, 92, 70)
    d.line(X([(-0.3, -0.12), (-0.62, -0.2), (-0.8, -0.05)]), fill=(150, 118, 100), width=max(2, int(s * 0.04)))
    d.polygon(X(ell(0, -0.2, 0.34, 0.2)), fill=fur)
    d.polygon(X(ell(0.3, -0.26, 0.19, 0.15)), fill=fur)
    d.polygon(X([(0.42, -0.3), (0.6, -0.2), (0.42, -0.14)]), fill=fur)
    d.polygon(X(ell(0.22, -0.42, 0.07, 0.09)), fill=(160, 120, 100))
    nx, ny = X([(0.6, -0.2)])[0]; r = s * 0.03
    d.ellipse([nx - r, ny - r, nx + r, ny + r], fill=(230, 140, 140))
    ex, ey = X([(0.38, -0.3)])[0]; r = s * 0.045
    if blink: d.line([ex - r, ey, ex + r, ey], fill=(20, 15, 10), width=3)
    else:
        d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(255, 250, 220))
        d.ellipse([ex - r * 0.5, ey - r * 0.5, ex + r * 0.5, ey + r * 0.5], fill=(10, 10, 10))

def a_burrow(c):
    W, H, U = c.W, c.H, c.U
    gy = H * 0.44
    base(c, (8, 10, 30), (30, 26, 60))
    stars(c.d, W, H, c.t, 60, ymax=0.4)
    c.d.ellipse([W * 0.74, H * 0.27, W * 0.74 + U * 0.11, H * 0.27 + U * 0.11], fill=(235, 235, 215))
    fern_row(c.d, W, gy + U * 0.02, U * 0.26, (14, 20, 26), 41, 0, 0.5, c.t)
    c.d.rectangle([0, gy, W, H], fill=(58, 42, 30))
    c.d.rectangle([0, gy, W, gy + U * 0.03], fill=(38, 54, 34))
    bx, by = W * 0.5, gy + U * 0.2
    c.d.polygon(ell(bx, by, U * 0.3, U * 0.12, 30), fill=(22, 15, 11))
    c.d.polygon([(bx + U * 0.2, by - U * 0.05), (bx + U * 0.34, gy), (bx + U * 0.46, gy), (bx + U * 0.3, by + U * 0.05)], fill=(22, 15, 11))
    tx = lerp(-U * 0.3, W + U * 0.3, clamp(c.tl / 5.5))
    trex(c.cd, tx, gy + U * 0.02, U * 0.62, (20, 30, 28), c.t * 5, 1, jaw=0.2)
    step = abs(math.sin(c.t * 5))
    c.shake = U * 0.008 * (step > 0.93) * (0 < tx < W)
    out = ease((since("only coming") + 0.2) / 0.8)
    mx = lerp(bx - U * 0.04, bx + U * 0.36, out); my = lerp(by + U * 0.1, gy + U * 0.01, out)
    add_glow(c, [(mx, my - U * 0.04, U * 0.16, (255, 220, 150), 0.25)], 12)
    mammal(c.cd, mx, my, U * 0.2, 1, blink=int(c.t * 10) % 23 == 0)
    mammal(c.cd, bx - U * 0.14, by + U * 0.09, U * 0.13, -1, blink=int(c.t * 10) % 17 == 0)
    pop("Tiny", "YOUR ANCESTOR ↓", 0.5, 0.455, 0.05, YEL, hold=4.0)
    c.zoom = 1.0 + 0.1 * c.k

def raptor(d, x, y, s, col, phase=0.0, facing=1, up=0.0, eye=1.0, tool=0.0, tie=False, case=False, accent=(232, 120, 56)):
    X = Xf(x, y, s, facing)
    th = lerp(0.12, 1.2, up)
    bd = (math.cos(th), -math.sin(th))
    hip = (0.0, -0.46)
    lw = lambda f: max(3, int(s * f))
    back = dark(col, 0.74)
    def leg(ph, cc):
        sw = math.sin(ph) * 0.14
        knee = (hip[0] + 0.10 + sw, hip[1] + 0.2)
        ank = (knee[0] - 0.11 + sw * 0.5, knee[1] + 0.17)
        d.line(X([hip, knee, ank]), fill=cc, width=lw(0.075), joint="curve")
        d.line(X([ank, (ank[0] + 0.02, -0.025), (ank[0] + 0.15, -0.012)]), fill=cc, width=lw(0.045), joint="curve")
        kx, ky = X([knee])[0]; r = lw(0.075) / 2
        d.ellipse([kx - r, ky - r, kx + r, ky + r], fill=cc)
    leg(phase + math.pi, back)
    tl = lerp(0.72, 0.46, up)
    d.polygon(X([(hip[0] + 0.02, hip[1] - 0.08), (hip[0] + 0.02, hip[1] + 0.07), (hip[0] - tl, hip[1] + lerp(-0.06, 0.24, up))]), fill=col)
    bc = (hip[0] + bd[0] * 0.2, hip[1] + bd[1] * 0.2)
    d.polygon(X(ell(bc[0], bc[1], 0.28, 0.14, 24, rot=-th)), fill=col)
    d.polygon(X(ell(bc[0] + 0.03, bc[1] + 0.03, 0.2, 0.07, 20, rot=-th)), fill=lc(col, (255, 240, 210), 0.22))
    sh = (hip[0] + bd[0] * 0.4, hip[1] + bd[1] * 0.4)
    nt = (sh[0] + 0.1, sh[1] - 0.2)
    d.line(X([sh, nt]), fill=col, width=lw(0.095))
    hs = 1 + 0.28 * up
    hc = (nt[0] + 0.06, nt[1] - 0.03)
    for k in range(3):
        d.polygon(X([(hc[0] - 0.07, hc[1] - 0.06 + 0.04 * k), (hc[0] - 0.05, hc[1] + 0.0 + 0.04 * k),
                     (hc[0] - 0.25 - 0.03 * k, hc[1] - 0.14 + 0.07 * k)]), fill=accent)
    d.polygon(X(ell(hc[0], hc[1], 0.12 * hs, 0.088 * hs, 20)), fill=col)
    sn = lerp(0.22, 0.13, up)
    d.polygon(X([(hc[0] + 0.04, hc[1] - 0.065 * hs), (hc[0] + 0.1 + sn, hc[1] - 0.005), (hc[0] + 0.1 + sn, hc[1] + 0.035),
                 (hc[0] + 0.04, hc[1] + 0.075 * hs)]), fill=col)
    ex, ey = X([(hc[0] + 0.05, hc[1] - 0.02)])[0]; r = s * 0.024 * eye
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(255, 245, 190))
    d.ellipse([ex - r * 0.5 + facing * r * 0.2, ey - r * 0.55, ex + r * 0.5 + facing * r * 0.2, ey + r * 0.55], fill=(15, 12, 10))
    if tie:
        d.polygon(X([(sh[0] + 0.06, sh[1] + 0.0), (sh[0] + 0.12, sh[1] + 0.02), (sh[0] + 0.14, sh[1] + 0.26), (sh[0] + 0.08, sh[1] + 0.3),
                     (sh[0] + 0.05, sh[1] + 0.24)]), fill=(210, 40, 40))
    elbow = (sh[0] + 0.07, sh[1] + 0.13)
    hand = (sh[0] + 0.21, sh[1] + 0.13 + 0.03 * math.sin(phase) - 0.1 * tool)
    d.polygon(X([elbow, (elbow[0] - 0.12, elbow[1] + 0.17), (elbow[0] + 0.05, elbow[1] + 0.06)]), fill=accent)
    d.line(X([(sh[0] + 0.02, sh[1] + 0.03), elbow, hand]), fill=back, width=lw(0.05), joint="curve")
    if tool > 0:
        top = (hand[0] + 0.02, hand[1] - 0.3 * tool)
        d.line(X([(hand[0], hand[1] + 0.05), top]), fill=(150, 110, 70), width=lw(0.03))
        d.polygon(X([(top[0] - 0.09, top[1] - 0.05), (top[0] + 0.09, top[1] - 0.05), (top[0] + 0.09, top[1] + 0.04), (top[0] - 0.09, top[1] + 0.04)]),
                  fill=(170, 175, 185))
    if case:
        d.polygon(X([(hand[0] - 0.09, hand[1] + 0.03), (hand[0] + 0.11, hand[1] + 0.03), (hand[0] + 0.11, hand[1] + 0.19), (hand[0] - 0.09, hand[1] + 0.19)]),
                  fill=(96, 62, 36))
    leg(phase, col)

def a_troodon(c):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (30, 60, 80), (120, 160, 130))
    mountains(c.d, W, gy - U * 0.1, U * 0.16, (40, 80, 80), 51, c.t * 3)
    fern_row(c.d, W, gy + U * 0.0, U * 0.42, (24, 60, 50), 52, c.t * 5, 0.7, c.t)
    c.d.rectangle([0, gy, W, H], fill=(46, 80, 52))
    s = U * 0.62; x = W * 0.5 - s * 0.12; y = gy + U * 0.05
    b = ease(since("Troodon already") / 2.5)
    hx, hy = x + 0.3 * s, y - 0.86 * s
    add_glow(c, [(hx, hy, s * (0.12 + 0.3 * b), (255, 230, 120), 0.35 + 0.5 * b)], 14)
    raptor(c.cd, x, y, s, (60, 120, 110), math.sin(c.t * 1.5) * 0.3, 1, up=0.12, eye=1.1)
    pop("Troodon already", "TROODON", 0.5, 0.30, 0.085, YEL)
    pop("biggest brains", "BIG BRAIN ENERGY", 0.5, 0.348, 0.045, WHITE)
    c.zoom = 1.0 + 0.1 * c.k

def a_dinosauroid(c):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (10, 32, 62), (16, 50, 90))
    g = int(U * 0.09)
    for xx in range(0, W, g): c.d.line([xx, 0, xx, H], fill=(22, 60, 104), width=2)
    for yy in range(0, H, g): c.d.line([0, yy, W, yy], fill=(22, 60, 104), width=2)
    c.d.line([W * 0.12, gy + U * 0.06, W * 0.88, gy + U * 0.06], fill=(120, 170, 220), width=4)
    up = ease(since("Standing upright") / 1.0)
    eye = 1.0 + 1.3 * ease(since("Big eyes") / 0.6)
    tool = ease(since("Hands that") / 0.7)
    s = U * 0.56
    add_glow(c, [(W * 0.5, gy - s * 0.5, s * 0.7, (60, 140, 220), 0.3)], 22)
    raptor(c.cd, W * 0.5 - s * 0.08, gy + U * 0.06, s, (70, 140, 120), 0.0, 1, up=up, eye=eye, tool=tool)
    stamp("THE “DINOSAUROID” · 1982", 0.5, 0.287, 0.044, (150, 205, 255), c.tl / 0.14)
    pop("Standing upright", "UPRIGHT", 0.2, 0.40, 0.05, YEL)
    pop("Big eyes", "BIG EYES", 0.8, 0.36, 0.05, YEL)
    pop("Hands that", "TOOLS", 0.8, 0.50, 0.05, YEL)
    c.zoom = 1.0 + 0.06 * c.k

def skyline(c, base_y, cam, seed, col, lit, hmin, hmax, wfrac=1.0):
    W, U = c.W, c.U
    x = -U * 0.1 - (cam % (U * 0.2))
    i = int(cam // (U * 0.2))
    while x < W:
        bw = U * (0.13 + 0.1 * h01(i, seed)); bh = U * (hmin + (hmax - hmin) * h01(i, seed + 1))
        c.d.rectangle([x, base_y - bh, x + bw - U * 0.012, base_y], fill=col)
        if h01(i, seed + 2) > 0.6:
            c.d.polygon([(x + bw * 0.3, base_y - bh), (x + bw * 0.45, base_y - bh - U * 0.07), (x + bw * 0.6, base_y - bh)], fill=col)
        if lit:
            cols = max(2, int(bw / (U * 0.045))); rows = int(bh / (U * 0.055))
            for r in range(rows):
                for q in range(cols):
                    if h01(i * 131 + r * 17 + q, seed + 5) < 0.5 * wfrac:
                        wx = x + (q + 0.3) * bw / cols; wy = base_y - bh + (r + 0.35) * U * 0.055
                        c.d.rectangle([wx, wy, wx + bw / cols * 0.42, wy + U * 0.026], fill=lit)
        x += bw; i += 1

def a_city(c):
    W, H, U = c.W, c.H, c.U
    gy = H * 0.62
    base(c, (40, 30, 90), (250, 150, 110))
    add_glow(c, [(W * 0.3, gy - U * 0.1, U * 0.45, (255, 170, 110), 0.7)], 24)
    skyline(c, gy, c.t * 6, 600, (70, 60, 120), None, 0.2, 0.5)
    # sauropod "crane" between the towers
    sx, sy = W * 0.68 - c.t * U * 0.01, gy
    col = (38, 34, 70)
    c.d.polygon(ell(sx, sy - U * 0.2, U * 0.2, U * 0.1, 20), fill=col)
    c.d.line([sx + U * 0.12, sy - U * 0.24, sx + U * 0.26, sy - U * 0.5, sx + U * 0.3 + math.sin(c.t) * U * 0.01, sy - U * 0.66], fill=col, width=int(U * 0.05),
             joint="curve")
    c.d.polygon(ell(sx + U * 0.33 + math.sin(c.t) * U * 0.01, sy - U * 0.67, U * 0.05, U * 0.028, 12), fill=col)
    c.d.line([sx - U * 0.15, sy - U * 0.2, sx - U * 0.42, sy - U * 0.1], fill=col, width=int(U * 0.04))
    for lx in (-0.1, 0.1): c.d.rectangle([sx + lx * U - U * 0.03, sy - U * 0.14, sx + lx * U + U * 0.03, sy], fill=col)
    skyline(c, gy, c.t * 14, 700, (22, 20, 50), (255, 214, 130), 0.3, 0.72)
    c.d.rectangle([0, gy, W, H], fill=(16, 14, 34))
    for i in range(3):
        ptero(c.cd, (W * (0.2 + 0.3 * i) + c.t * U * (0.1 + 0.03 * i)) % (W * 1.3) - W * 0.15, H * (0.30 + 0.035 * i) + math.sin(c.t * 1.3 + i) * U * 0.02,
              U * 0.2, (30, 24, 54), c.t * 7 + i, 1)
    pop("built by", "DINO CITY", 0.5, 0.30, 0.085, YEL)
    c.zoom = 1.0 + 0.08 * c.k

def car(d, x, y, s, col, facing, head_col, t):
    X = Xf(x, y, s, facing)
    bob = math.sin(t * 9 + x) * 0.01
    d.polygon(X([(-0.5, -0.1 + bob), (-0.5, -0.3 + bob), (-0.28, -0.32 + bob), (-0.16, -0.52 + bob), (0.2, -0.52 + bob), (0.32, -0.32 + bob),
                 (0.5, -0.28 + bob), (0.5, -0.1 + bob)]), fill=col)
    d.polygon(X([(-0.12, -0.47 + bob), (0.17, -0.47 + bob), (0.25, -0.33 + bob), (-0.2, -0.33 + bob)]), fill=(160, 205, 235))
    for wx in (-0.3, 0.3):
        cx, cy = X([(wx, -0.09)])[0]; r = s * 0.1
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(20, 20, 24)); d.ellipse([cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45], fill=(150, 150, 160))
    # raptor driver sticking out of the roof
    hx, hy = 0.02, -0.62 + bob
    d.line(X([(hx - 0.02, -0.45 + bob), (hx, hy)]), fill=head_col, width=max(3, int(s * 0.07)))
    d.polygon(X(ell(hx + 0.03, hy - 0.03, 0.1, 0.07, 14)), fill=head_col)
    d.polygon(X([(hx + 0.08, hy - 0.08), (hx + 0.3, hy - 0.03), (hx + 0.3, hy + 0.0), (hx + 0.08, hy + 0.03)]), fill=head_col)
    for k in range(2):
        d.polygon(X([(hx - 0.03, hy - 0.08 + 0.04 * k), (hx - 0.02, hy - 0.02 + 0.04 * k), (hx - 0.18, hy - 0.14 + 0.06 * k)]), fill=(232, 120, 56))
    ex, ey = X([(hx + 0.07, hy - 0.04)])[0]; r = s * 0.02
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(255, 245, 190))

def a_rush(c):
    W, H, U = c.W, c.H, c.U
    gy = H * 0.5
    base(c, (60, 40, 110), (250, 160, 110))
    skyline(c, gy, c.t * 10, 700, (26, 22, 56), (255, 214, 130), 0.3, 0.6)
    c.d.rectangle([0, gy, W, H], fill=(52, 50, 62))
    c.d.rectangle([0, gy + U * 0.07, W, H * 0.64], fill=(30, 30, 36))
    for i in range(8):
        lx = (i * W / 6 - c.t * U * 0.1) % (W * 1.3) - W * 0.15
        c.d.rectangle([lx, H * 0.565, lx + U * 0.1, H * 0.565 + U * 0.012], fill=(230, 220, 160))
    # pedestrians on the far sidewalk
    for i, (col, case, tie) in enumerate([((70, 140, 120), True, True), ((150, 110, 70), False, True), ((110, 100, 150), True, False)]):
        px = (W * (0.15 + 0.4 * i) + c.t * U * (0.12 + 0.02 * i)) % (W * 1.3) - W * 0.15
        raptor(c.cd, px, gy + U * 0.06, U * 0.2, col, c.t * 8 + i * 2, 1, up=1.0, eye=1.6, tie=tie, case=case)
    cols = [(210, 60, 50), (240, 190, 40), (60, 130, 210), (240, 240, 240)]
    heads = [(70, 140, 120), (150, 110, 70), (110, 100, 150), (90, 150, 80)]
    for i in range(4):
        cx = (W * (0.05 + 0.33 * i) + c.t * U * 0.045) % (W * 1.35) - W * 0.17
        car(c.cd, cx, H * 0.548, U * 0.3, cols[i], 1, heads[i], c.t)
    for i in range(3):
        cx = (W * (0.2 + 0.45 * i) - c.t * U * 0.07) % (W * 1.35) - W * 0.17
        car(c.cd, cx, H * 0.63, U * 0.36, cols[(i + 2) % 4], -1, heads[(i + 1) % 4], c.t + 1)
    ph = int(c.tl / 0.55)
    if c.tl > 0.5 and (c.tl / 0.55) % 1 < 0.6:
        stamp("HONK!", 0.2 + 0.6 * h01(ph, 901), 0.30 + 0.12 * h01(ph, 902), 0.06, YEL, ((c.tl / 0.55) % 1) / 0.25)
    c.zoom = 1.03

def human(d, x, y, s, col, wave=0.0):
    lw = max(3, int(s * 0.11))
    d.ellipse([x - s * 0.11, y - s * 1.0, x + s * 0.11, y - s * 0.78], fill=col)
    d.rounded_rectangle([x - s * 0.13, y - s * 0.75, x + s * 0.13, y - s * 0.36], radius=int(s * 0.06), fill=col)
    d.line([x - s * 0.06, y - s * 0.38, x - s * 0.08, y], fill=col, width=lw)
    d.line([x + s * 0.06, y - s * 0.38, x + s * 0.08, y], fill=col, width=lw)
    d.line([x - s * 0.13, y - s * 0.72, x - s * 0.22, y - s * 0.4], fill=col, width=int(lw * 0.8))
    if wave:
        a = -1.1 + math.sin(wave) * 0.35
        d.line([x + s * 0.13, y - s * 0.72, x + s * 0.13 + math.cos(a) * s * 0.36, y - s * 0.72 + math.sin(a) * s * 0.36], fill=col, width=int(lw * 0.8))
    else:
        d.line([x + s * 0.13, y - s * 0.72, x + s * 0.22, y - s * 0.4], fill=col, width=int(lw * 0.8))

def a_humans(c):
    W, H, U = c.W, c.H, c.U
    gy = H * 0.6
    base(c, (6, 6, 14), (16, 14, 26))
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(L)
    ld.polygon([(W * 0.5 - U * 0.05, H * 0.22), (W * 0.5 + U * 0.05, H * 0.22), (W * 0.5 + U * 0.3, gy), (W * 0.5 - U * 0.3, gy)], fill=(255, 245, 210, 34))
    c.img.paste(L, (0, 0), L); c.d = ImageDraw.Draw(c.img)
    c.d.polygon(ell(W * 0.5, gy, U * 0.3, U * 0.05, 30), fill=(60, 56, 70))
    gone = since("We never")
    if gone < 0:
        fl = 0.55 + 0.25 * math.sin(c.t * 11) * math.sin(c.t * 3.7)
        human(c.cd, W * 0.5, gy, U * 0.42, (150, 200, 255, int(255 * fl)))
        stamp("?", 0.5, 0.31, 0.16, WHITE, c.tl / 0.14)
    else:
        k = clamp(gone / 0.9)
        if k < 1: human(c.cd, W * 0.5, gy, U * 0.42, (150, 200, 255, int(140 * (1 - k))))
        for i in range(60):
            px = W * 0.5 + (h01(i, 71) - 0.5) * U * 0.3 * (1 + k * 2); py = gy - h01(i, 72) * U * 0.42 - k * U * 0.25 * h01(i, 73)
            r = U * 0.006 * (1 - k * 0.5)
            c.cd.ellipse([px - r, py - r, px + r, py + r], fill=(150, 200, 255, int(220 * (1 - k * 0.8))))
        stamp("0 HUMANS", 0.5, 0.30, 0.1, RED, gone / 0.14)
    c.zoom = 1.0 + 0.08 * c.k

def a_paths(c):
    W, H, U = c.W, c.H, c.U
    space(c)
    ex, ey, er = W * 0.34, H * 0.47, U * 0.17
    earth(c, ex, ey, er, glow=0.6)
    sx, sy = W * 1.0, H * 0.275
    div = ease(since("One tiny") / 1.2)
    hit = (ex + er * 0.5, ey - er * 0.4)
    miss = (lerp(hit[0], -W * 0.05, div), lerp(hit[1], H * 0.30, div))
    def dotted(p0, p1, col, n=22):
        for i in range(n):
            k = i / (n - 1); x = lerp(p0[0], p1[0], k); y = lerp(p0[1], p1[1], k); r = U * 0.008
            c.cd.ellipse([x - r, y - r, x + r, y + r], fill=col)
    dotted((sx, sy), hit, (255, 90, 80))
    if div > 0.02: dotted((sx, sy), miss, (255, 221, 0))
    k = clamp(c.tl / 4.5)
    ax = lerp(sx, miss[0], k); ay = lerp(sy, miss[1], k)
    asteroid(c, ax, ay, U * 0.03, math.atan2(miss[1] - sy, miss[0] - sx), fire=0.7)
    if div > 0.5:
        stamp("HIT", 0.5, 0.42, 0.045, RED, (div - 0.5) / 0.14)
        stamp("MISS", 0.16, 0.262, 0.045, YEL, (div - 0.5) / 0.14)
    c.zoom = 1.0 + 0.05 * c.k

def a_you(c):
    W, H, U = c.W, c.H, c.U
    space(c)
    cx, cy, r = W * 0.5, H * 0.86, U * 0.62
    earth(c, cx, cy, r, glow=0.8)
    human(c.cd, cx, cy - r + U * 0.01, U * 0.2, (250, 245, 235), wave=c.t * 6)
    stamp("YOU ↓", 0.5, 0.385, 0.075, YEL, c.tl / 0.14)
    c.zoom = 1.0 + 0.12 * c.k

# ================================================================= VIDEO 2: deepest ocean
BOTTOM = 10935
def depth_at(t):
    if G["dk"] is None:
        G["dk"] = [(cue(2, "You hit") + 0.9, 0), (cue(2, "Two hundred"), 200), (cue(2, "One thousand"), 1000),
                   (cue(2, "Three thousand"), 3000), (cue(2, "Eight thousand"), 8000), (cue(2, "The bottom"), BOTTOM)]
    ks = G["dk"]
    if t <= ks[0][0]: return 0.0
    for (ta, da), (tb, db) in zip(ks, ks[1:]):
        if t < tb: return da + (db - da) * (t - ta) / (tb - ta)
    return float(BOTTOM)

def zone(d):
    return ("SUNLIGHT ZONE" if d < 200 else "TWILIGHT ZONE" if d < 1000 else "MIDNIGHT ZONE" if d < 4000 else
            "THE ABYSS" if d < 6000 else "HADAL ZONE")

def draw_hud(img, depth, W, H):
    d = ImageDraw.Draw(img)
    hl = THEME[2]["hl"]
    f0 = R.font(R.FONT_BLACK, int(W * 0.036)); f1 = R.font(R.FONT_BLACK, int(W * 0.1))
    x, y = W * 0.06, H * 0.238
    d.text((x, y), "DEPTH", font=f0, fill=WHITE, stroke_width=4, stroke_fill=(0, 0, 0))
    d.text((x, y + f0.size * 1.15), f"{int(depth):,} m", font=f1, fill=hl, stroke_width=max(5, f1.size // 9), stroke_fill=(0, 0, 0))
    d.text((x, y + f0.size * 1.3 + f1.size * 1.12), zone(depth), font=f0, fill=(190, 215, 235), stroke_width=4, stroke_fill=(0, 0, 0))
    gx, y0, y1 = W * 0.945, H * 0.30, H * 0.615
    d.line([gx, y0, gx, y1], fill=(0, 0, 0), width=12); d.line([gx, y0, gx, y1], fill=(210, 225, 240), width=5)
    for k in range(12):
        yy = lerp(y0, y1, k * 1000 / 11000)
        d.line([gx - (16 if k % 5 == 0 else 9), yy, gx, yy], fill=(210, 225, 240), width=4)
    my = lerp(y0, y1, min(depth, 11000) / 11000)
    d.polygon([(gx - 40, my), (gx - 8, my - 16), (gx - 8, my + 16)], fill=hl, outline=(0, 0, 0))
    d.ellipse([gx - 11, my - 11, gx + 11, my + 11], fill=hl, outline=(0, 0, 0), width=3)

def water_cols(depth):
    if depth < 200:
        k = depth / 200; return lc((44, 156, 220), (14, 84, 156), k), lc((16, 100, 176), (6, 46, 104), k)
    if depth < 1000:
        k = (depth - 200) / 800; return lc((14, 84, 156), (3, 12, 30), k), lc((6, 46, 104), (1, 5, 14), k)
    return (3, 12, 30), (1, 4, 11)

def ocean(c, speed=1.0):
    W, H, U = c.W, c.H, c.U
    t = G["t"]; depth = depth_at(t)
    top, bot = water_cols(depth)
    base(c, top, bot)
    a = clamp(1 - depth / 320)
    if a > 0:
        for i in range(6):
            x = W * (-0.05 + 0.2 * i) + math.sin(t * 0.5 + i) * U * 0.03
            c.d.polygon([(x, 0), (x + W * 0.07, 0), (x + W * 0.22, H * 0.8), (x + W * 0.1, H * 0.8)], fill=lc(top, (170, 225, 250), 0.16 * a))
    particles(c.d, W, H, t, 70, 5, lc(top, (200, 225, 240), 0.55), U * 0.0038, 5, -U * 0.42 * speed)
    return depth

DX, DY = 0.5, 0.47
def diver(c, depth, land=0.0, look=0.0):
    W, H, U = c.W, c.H, c.U
    t = G["t"]; x, y, s = W * DX, H * DY, U * 0.2
    dk = clamp((depth - 150) / 700)
    if dk > 0:
        add_glow(c, [(x, y, s * 2.4, (90, 140, 205), 0.36 * dk)], 20)
    d = c.cd
    sway = math.sin(t * 1.2) * 0.22 * (1 - land)
    fl = math.sin(t * 3.1) * (1 - land)
    def P(pts): return [(x + a_, y + b_) for a_, b_ in rot_pts([(u * s, v * s) for u, v in pts], 0, 0, sway)]
    suit = (245, 135, 30); suit2 = (205, 100, 20); skin = (245, 205, 175)
    lw = max(5, int(s * 0.13))
    def limb(pts, col):
        q = P(pts); d.line(q, fill=col, width=lw, joint="curve")
        for qx, qy in (q[0], q[-1]): d.ellipse([qx - lw / 2, qy - lw / 2, qx + lw / 2, qy + lw / 2], fill=col)
    for sg in (-1, 1):
        limb([(sg * 0.09, 0.2), (sg * lerp(0.2, 0.1, land), 0.42 - 0.03 * fl * sg), (sg * lerp(0.24, 0.1, land), 0.62)], suit2)
        limb([(sg * 0.15, -0.2), (sg * lerp(0.33, 0.24, land), lerp(-0.32, -0.02, land) + 0.03 * fl), (sg * lerp(0.4, 0.27, land), lerp(-0.56, 0.16, land) + 0.05 * fl * sg)], suit2)
    d.rounded_rectangle([x - s * 0.17, y - s * 0.29, x + s * 0.17, y + s * 0.27], radius=int(s * 0.08), fill=suit) if abs(sway) < 0.02 else \
        d.polygon(P([(-0.17, -0.27), (-0.12, -0.3), (0.12, -0.3), (0.17, -0.27), (0.17, 0.24), (0.12, 0.28), (-0.12, 0.28), (-0.17, 0.24)]), fill=suit)
    hx, hy = P([(0, -0.46)])[0]; r = s * 0.16
    d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=skin)
    d.pieslice([hx - r, hy - r, hx + r, hy + r], 180, 360, fill=(70, 45, 30))
    gx = hx + look * r * 0.3
    d.rounded_rectangle([gx - r * 0.8, hy - r * 0.15, gx + r * 0.8, hy + r * 0.42], radius=int(r * 0.2), fill=(30, 40, 60))
    d.rounded_rectangle([gx - r * 0.62, hy - r * 0.03, gx + r * 0.62, hy + r * 0.3], radius=int(r * 0.15), fill=(150, 215, 240))
    nb = int(lerp(9, 2, clamp(depth / 2500)))
    for i in range(nb):
        by = hy - s * 0.3 - ((t * U * 0.28 + i * U * 0.17) % (U * 1.1)); bx = hx + math.sin(t * 2 + i * 1.7) * s * 0.22 + (h01(i, 15) - 0.5) * s * 0.3
        br = U * (0.006 + 0.008 * h01(i, 16))
        if by > H * 0.3: d.ellipse([bx - br, by - br, bx + br, by + br], outline=(215, 240, 255), width=3)

def fish(d, x, y, s, col, facing, ph=0.0):
    X = Xf(x, y, s, facing)
    d.polygon(X(ell(0, 0, 0.5, 0.2, 16)), fill=col)
    w = math.sin(ph) * 0.08
    d.polygon(X([(-0.42, 0), (-0.78, -0.22 + w), (-0.78, 0.22 + w)]), fill=col)
    ex, ey = X([(0.3, -0.04)])[0]; r = max(2, s * 0.05)
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(15, 20, 30))

def shark(d, x, y, s, col, facing, ph=0.0):
    X = Xf(x, y, s, facing)
    w = math.sin(ph) * 0.05
    d.polygon(X([(0.55, 0.0), (0.3, -0.11), (-0.1, -0.13), (-0.42, -0.04), (-0.42, 0.04), (-0.1, 0.11), (0.3, 0.09)]), fill=col)
    d.polygon(X([(-0.38, 0), (-0.66, -0.26 + w), (-0.55, 0.0 + w), (-0.62, 0.16 + w)]), fill=col)
    d.polygon(X([(0.02, -0.12), (-0.12, -0.34), (-0.18, -0.12)]), fill=col)
    d.polygon(X([(0.12, 0.08), (-0.02, 0.28), (-0.08, 0.09)]), fill=dark(col, 0.85))
    ex, ey = X([(0.4, -0.03)])[0]; r = max(2, s * 0.014)
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(5, 8, 12))

def jelly(c, x, y, s, col, t, a=1.0):
    add_glow(c, [(x, y, s * 1.5, col, 0.55 * a)], 12)
    cc = lc((2, 8, 20), lc(col, (255, 255, 255), 0.35), a)
    pulse = 1 + 0.08 * math.sin(t * 3 + x)
    c.cd.pieslice([x - s * 0.5 * pulse, y - s * 0.45, x + s * 0.5 * pulse, y + s * 0.45], 180, 360, fill=cc)
    for k in range(5):
        tx = x + (k - 2) * s * 0.2 * pulse
        pts = [(tx + math.sin(t * 2.5 + k + j * 0.9) * s * 0.07, y + j * s * 0.2) for j in range(6)]
        c.cd.line(pts, fill=cc, width=max(2, int(s * 0.05)), joint="curve")

def jellies(c, a=1.0):
    W, H, U = c.W, c.H, c.U
    t = G["t"]; t0 = cue(2, "The only")
    cols = [(60, 220, 255), (255, 90, 200), (120, 255, 170), (160, 130, 255), (60, 220, 255)]
    for i, (xf, yo) in enumerate([(0.2, 0.0), (0.82, 0.16), (0.3, 0.42), (0.74, 0.5), (0.12, 0.7)]):
        y = H * 0.62 + yo * U - (t - t0) * U * 0.075
        fade = clamp((t - t0 - i * 0.25) / 0.7) * a
        if H * 0.27 < y < H * 0.68 and fade > 0:
            jelly(c, W * xf + math.sin(t * 0.8 + i) * U * 0.03, y, U * (0.11 + 0.03 * (i % 2)), cols[i], t, fade)

def angler(c, x, y, s, t, facing=-1):
    X = Xf(x, y, s, facing)
    lx, ly = X([(0.62, -0.5 + math.sin(t * 2) * 0.03)])[0]
    add_glow(c, [(lx, ly, s * 0.75, (255, 232, 150), 0.95), (x + facing * s * 0.3, y, s * 0.6, (255, 220, 150), 0.25)], 14)
    d = c.cd; body = (58, 44, 52); rim = (96, 74, 84)
    d.polygon(X([(-0.4, 0), (-0.72, -0.2 + math.sin(t * 4) * 0.04), (-0.72, 0.2 + math.sin(t * 4) * 0.04)]), fill=body)
    d.polygon(X(ell(0, 0, 0.5, 0.4, 24)), fill=rim)
    d.polygon(X(ell(-0.02, 0.02, 0.47, 0.37, 24)), fill=body)
    jaw = 0.1 + 0.05 * math.sin(t * 3)
    d.polygon(X([(0.1, -0.02), (0.56, -0.12 - jaw), (0.6, 0.02), (0.5, 0.26 + jaw), (0.1, 0.2)]), fill=(20, 10, 14))
    for k in range(6):
        tx = 0.18 + k * 0.065
        d.polygon(X([(tx, -0.05 - jaw * k / 6), (tx + 0.045, -0.06 - jaw * (k + 1) / 6), (tx + 0.03, 0.07 - jaw * k / 6)]), fill=(245, 240, 225))
        d.polygon(X([(tx, 0.22 + jaw * k / 6), (tx + 0.045, 0.23 + jaw * (k + 1) / 6), (tx + 0.02, 0.1 + jaw * k / 6)]), fill=(245, 240, 225))
    ex, ey = X([(0.12, -0.18)])[0]; r = s * 0.05
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(235, 240, 235)); d.ellipse([ex - r * 0.4, ey - r * 0.4, ex + r * 0.4, ey + r * 0.4], fill=(10, 10, 10))
    d.line(X([(0.05, -0.36), (0.2, -0.66), (0.48, -0.66), (0.62, -0.52)]), fill=rim, width=max(3, int(s * 0.03)), joint="curve")
    r = s * 0.07
    d.ellipse([lx - r, ly - r, lx + r, ly + r], fill=(255, 250, 215))

def snailfish(c, x, y, s, t, facing):
    add_glow(c, [(x, y, s * 0.9, (220, 215, 235), 0.35)], 12)
    X = Xf(x, y, s, facing); d = c.cd; col = (246, 228, 234)
    tail = [(-0.1 - j * 0.14, math.sin(t * 5 - j * 0.9) * 0.04 * j) for j in range(6)]
    up = [(u, v - 0.17 * (1 - j / 5.5)) for j, (u, v) in enumerate(tail)]; dn = [(u, v + 0.17 * (1 - j / 5.5)) for j, (u, v) in enumerate(tail)]
    d.polygon(X(up + dn[::-1]), fill=col)
    d.polygon(X(ell(0.08, 0, 0.26, 0.2, 18)), fill=col)
    d.polygon(X(ell(0.02, 0.06, 0.16, 0.1, 14)), fill=(255, 205, 215))
    ex, ey = X([(0.2, -0.05)])[0]; r = max(2, s * 0.035)
    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=(15, 15, 25))

def seafloor(c, fy):
    W, H, U = c.W, c.H, c.U
    pts = [(0, H)]
    for x in range(0, W + 30, 30):
        pts.append((x, fy + math.sin(x * 0.011) * U * 0.012 + math.sin(x * 0.037 + 1) * U * 0.006))
    pts.append((W, H))
    c.d.polygon(pts, fill=(64, 58, 52))
    for i in range(14):
        rx = h01(i, 121) * W; ry = fy + U * (0.03 + 0.2 * h01(i, 122)); rr = U * (0.012 + 0.02 * h01(i, 123))
        c.d.polygon(ell(rx, ry, rr * 1.5, rr * 0.7, 10), fill=(46, 42, 40))
    add_glow(c, [(W * DX, fy + U * 0.04, U * 0.42, (120, 135, 150), 0.3)], 18)

def plastic_bag(c, x, y, s, t):
    add_glow(c, [(x, y, s * 1.2, (200, 225, 255), 0.5)], 12)
    d = c.cd; col = (238, 243, 248, 235)
    w = math.sin(t * 2.2) * 0.06
    pts = [(-0.3, -0.25), (-0.36, 0.2 + w), (-0.2, 0.45), (0.0, 0.38 - w), (0.2, 0.47 + w), (0.36, 0.2 - w), (0.3, -0.25)]
    rot = math.sin(t * 0.9) * 0.2
    P = lambda q: [(x + a_, y + b_) for a_, b_ in rot_pts([(u * s, v * s) for u, v in q], 0, 0, rot)]
    d.polygon(P(pts), fill=col)
    for sg in (-1, 1):
        d.line(P([(sg * 0.28, -0.24), (sg * 0.3, -0.52), (sg * 0.1, -0.52), (sg * 0.1, -0.24)]), fill=col, width=max(4, int(s * 0.07)), joint="curve")
    for k in range(3):
        d.line(P([(-0.2 + k * 0.18, -0.15), (-0.14 + k * 0.16, 0.3)]), fill=(200, 210, 222, 235), width=3)

def o_hook(c):
    W, H, U = c.W, c.H, c.U
    ys, yb = H * 0.345, H * 0.635
    base(c, (10, 70, 140), (2, 12, 34))
    c.d.rectangle([0, 0, W, ys], fill=(150, 205, 245))
    add_glow(c, [(W * 0.8, H * 0.29, U * 0.2, (255, 240, 190), 0.6)], 18)
    for x in range(0, W, 40):
        yy = ys + math.sin(x * 0.03 + c.t * 3) * 5
        c.d.rectangle([x, yy - 6, x + 40, yy + 2], fill=(215, 240, 255))
    floor = [(0, H), (0, H * 0.42), (W * 0.2, H * 0.425), (W * 0.34, H * 0.5), (W * 0.42, yb), (W * 0.58, yb), (W * 0.66, H * 0.5),
             (W * 0.8, H * 0.425), (W, H * 0.42), (W, H)]
    c.d.polygon(floor, fill=(42, 40, 52))
    scale = (yb - ys) / BOTTOM
    ek = ease((c.tl - 0.7) / 0.8)
    if ek > 0:
        pk = yb - 8849 * scale
        L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(L)
        a = int(170 * ek)
        ld.polygon([(W * 0.5, pk), (W * 0.385, yb), (W * 0.615, yb)], fill=(205, 215, 230, a))
        ld.polygon([(W * 0.5, pk), (W * 0.468, pk + (yb - pk) * 0.28), (W * 0.49, pk + (yb - pk) * 0.23), (W * 0.512, pk + (yb - pk) * 0.3),
                    (W * 0.532, pk + (yb - pk) * 0.28)], fill=(255, 255, 255, int(235 * ek)))
        c.img.paste(L, (0, 0), L); c.d = ImageDraw.Draw(c.img)
        stamp("MT. EVEREST\nFITS INSIDE", 0.22, 0.515, 0.036, WHITE, (c.tl - 0.7) / 0.14)
    ak = ease((c.tl - 0.2) / 1.0)
    ax = W * 0.8
    c.d.line([ax, ys, ax, lerp(ys, yb, ak)], fill=THEME[2]["hl"], width=7)
    ay = lerp(ys, yb, ak)
    c.d.polygon([(ax - 16, ay - 20), (ax + 16, ay - 20), (ax, ay + 4)], fill=THEME[2]["hl"])
    if ak > 0.6: stamp("11 KM", 0.895, 0.49, 0.05, THEME[2]["hl"], (ak - 0.6) / 0.2)
    py = lerp(H * 0.262, ys - U * 0.01, clamp(c.tl / max(0.5, cue(2, "You hit") - 0.1)) ** 2)
    human(c.cd, W * 0.5, py, U * 0.06, (245, 135, 30))
    c.zoom = 1.0 + 0.07 * c.k

def o_splash(c):
    W, H, U = c.W, c.H, c.U
    depth = ocean(c)
    sy = H * 0.31 - c.tl * U * 0.55
    if sy > -U * 0.1:
        if sy > 1: c.d.rectangle([0, 0, W, sy], fill=(196, 232, 250))
        for x in range(0, W, 36):
            yy = sy + math.sin(x * 0.03 + c.t * 4) * 8
            c.d.ellipse([x - 22, yy - 14, x + 40, yy + 14], fill=(225, 244, 255))
    for i in range(26):
        k = clamp(c.tl / 1.6)
        a = h01(i, 61) * 6.283; rr = U * (0.05 + 0.3 * h01(i, 62)) * (0.3 + k)
        bx = W * DX + math.cos(a) * rr; by = H * DY + math.sin(a) * rr * 0.7 - c.tl * U * 0.2 * h01(i, 63)
        br = U * (0.008 + 0.014 * h01(i, 64)) * (1 - k * 0.6)
        if k < 1 and by > H * 0.26: c.cd.ellipse([bx - br, by - br, bx + br, by + br], outline=(235, 250, 255), width=3)
    for i in range(14):
        fx = (W * 1.25 - (c.t * U * 0.3 + i * U * 0.1)) % (W * 1.5) - W * 0.25
        fy = H * (0.35 + 0.22 * h01(i, 71)) + math.sin(c.t * 2 + i) * U * 0.012
        fish(c.cd, fx, fy, U * (0.05 + 0.02 * h01(i, 72)), (225, 190, 70) if i % 3 else (240, 120, 70), -1, c.t * 10 + i)
    diver(c, depth)
    if c.tl < 0.25: c.flash = 0.5 * (1 - c.tl / 0.25)
    c.shake = U * 0.012 * clamp(1 - c.tl / 0.6)

def o_twilight(c):
    W, H, U = c.W, c.H, c.U
    depth = ocean(c)
    sx = lerp(-U * 0.4, W + U * 0.5, clamp(c.tl / 4.2))
    top, _ = water_cols(depth)
    shark(c.cd, sx, H * 0.385 + math.sin(c.t * 0.8) * U * 0.02, U * 0.62, lc(top, (150, 170, 190), 0.45), 1, c.t * 4)
    diver(c, depth)

def o_dark(c):
    depth = ocean(c)
    W, H, U = c.W, c.H, c.U
    for i in range(10):
        if math.sin(G["t"] * 1.5 + i * 2.1) > 0.75:
            x = W * h01(i, 91); y = H * (0.3 + 0.35 * h01(i, 92)); r = U * 0.005
            c.d.ellipse([x - r, y - r, x + r, y + r], fill=(120, 220, 255))
    diver(c, depth)

def o_alive(c):
    depth = ocean(c)
    jellies(c)
    diver(c, depth)

def o_angler(c):
    W, H, U = c.W, c.H, c.U
    depth = ocean(c)
    jellies(c, a=clamp(1 - c.tl / 2.5) * 0.9 + 0.1)
    x = lerp(W * 1.3, W * 0.77, ease(c.tl / 1.3)) + math.sin(c.t * 0.9) * U * 0.02
    angler(c, x, H * 0.5 + math.sin(c.t * 1.3) * U * 0.02, U * 0.3, c.t)
    diver(c, depth, look=1.0)

def o_pressure(c):
    W, H, U = c.W, c.H, c.U
    depth = ocean(c)
    for i in range(8):
        if math.sin(G["t"] * 1.2 + i * 1.9) > 0.6:
            x = W * h01(i, 95); y = H * (0.3 + 0.35 * h01(i, 96)); r = U * 0.005
            c.d.ellipse([x - r, y - r, x + r, y + r], fill=(140, 255, 200))
    diver(c, depth)
    pop("almost freezing", "2°C", 0.2, 0.42, 0.085, (160, 220, 255), hold=3.2)
    s = since("three hundred times")
    if s >= 0:
        stamp("×300\nPRESSURE", 0.74, 0.43, 0.052, YEL, s / 0.14)
        c.shake = U * 0.008 * clamp(1 - s / 0.5)

def o_sink(c):
    W, H, U = c.W, c.H, c.U
    depth = ocean(c, speed=3.5)
    for i in range(26):
        x = W * h01(i, 101); y = (h01(i, 102) * H - G["t"] * U * 3.2 * (0.7 + 0.6 * h01(i, 103))) % H
        c.d.line([x, y, x, y + U * (0.08 + 0.1 * h01(i, 104))], fill=(40, 70, 110), width=4)
    diver(c, depth)
    c.shake = U * 0.006

def o_snailfish(c):
    W, H, U = c.W, c.H, c.U
    depth = ocean(c)
    a = c.tl * 0.85 + 2.6
    snailfish(c, W * 0.5 + math.cos(a) * U * 0.36, H * 0.47 + math.sin(a) * U * 0.11, U * 0.2, c.t, -1 if math.sin(a) > 0 else 1)
    snailfish(c, W * 0.5 + math.cos(a + 2.4) * U * 0.42, H * 0.44 + math.sin(a + 2.4) * U * 0.14, U * 0.14, c.t + 1, -1 if math.sin(a + 2.4) > 0 else 1)
    diver(c, depth, look=math.cos(a))
    pop("deepest fish", "RECORD: 8,336 m", 0.56, 0.352, 0.046, YEL, hold=cue(2, "Below this") - cue(2, "deepest fish"))
    pop("Below this", "NO FISH BELOW", 0.56, 0.352, 0.05, RED)

FLOOR = 0.53
def o_bottom(c):
    W, H, U = c.W, c.H, c.U
    tb = cue(2, "The bottom")
    k = ease((G["t"] - (tb - 2.2)) / 2.2)
    depth = ocean(c, speed=1 - k)
    fy = lerp(H * 1.05, H * FLOOR, k)
    seafloor(c, fy)
    landed = G["t"] - tb
    if 0 <= landed < 1.4:
        for i in range(12):
            a = h01(i, 111) * math.pi; r = U * 0.3 * landed / 1.4 * (0.4 + h01(i, 112))
            c.fog.append((W * DX + math.cos(a) * r * 1.4, H * FLOOR - math.sin(a) * r * 0.3, U * 0.12, (120, 112, 104, int(130 * (1 - landed / 1.4)))))
        c.shake = U * 0.014 * clamp(1 - landed / 0.5)
    diver(c, depth, land=ease(landed / 0.5 + 0.3) if landed > -0.3 else 0.0)
    s = since("eight tons")
    if s >= 0:
        stamp("8 TONS\nPER SQUARE INCH", 0.5, 0.36, 0.058, YEL, s / 0.14)
        c.shake = max(c.shake, U * 0.006 * (0.5 + 0.5 * math.sin(G["t"] * 9)))

def beam(c, ang, a=1.0):
    W, H, U = c.W, c.H, c.U
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(L)
    x, y = W * DX + U * 0.03, H * DY - U * 0.09
    ln = U * 0.95
    p1 = (x + math.cos(ang - 0.2) * ln, y + math.sin(ang - 0.2) * ln); p2 = (x + math.cos(ang + 0.2) * ln, y + math.sin(ang + 0.2) * ln)
    ld.polygon([(x, y), p1, p2], fill=(220, 235, 255, int(46 * a)))
    c.img.paste(L, (0, 0), L); c.d = ImageDraw.Draw(c.img)

def o_strange(c):
    W, H, U = c.W, c.H, c.U
    depth = ocean(c, speed=0)
    seafloor(c, H * FLOOR)
    ang = lerp(2.6, 0.15, ease(c.k * 1.2)) if c.k < 0.85 else 0.15
    beam(c, ang)
    diver(c, depth, land=1.0, look=math.cos(ang))
    if c.tl > 1.2: stamp("???", 0.8, 0.40, 0.09, WHITE, (c.tl - 1.2) / 0.14)
    c.zoom = 1.0 + 0.08 * c.k

def o_bag(c):
    W, H, U = c.W, c.H, c.U
    depth = ocean(c, speed=0)
    seafloor(c, H * FLOOR)
    beam(c, 0.15)
    bx = lerp(W * 1.15, W * 0.78, ease(c.tl / 0.9)); by = H * 0.43 + math.sin(c.t * 1.4) * U * 0.02
    plastic_bag(c, bx, by, U * 0.2, c.t)
    diver(c, depth, land=1.0, look=1.0)
    if c.tl > 1.0: stamp("FOUND AT 10,898 m", 0.5, 0.612, 0.05, YEL, (c.tl - 1.0) / 0.14)
    c.zoom = 1.08 + 0.06 * c.k

R.SCENES = {
    1: [("What", a_approach), ("But this time", a_miss), ("The dinosaurs wake", a_morning), ("T-rex stays", a_king),
        ("And our ancestors", a_burrow), ("Meanwhile", a_troodon), ("A scientist once", a_dinosauroid), ("Now picture", a_city),
        ("Rush hour", a_rush), ("And humans", a_humans), ("One rock", a_paths), ("That is the", a_you)],
    2: [("What", o_hook), ("You hit", o_splash), ("Two hundred", o_twilight), ("One thousand", o_dark), ("The only", o_alive),
        ("An anglerfish", o_angler), ("Three thousand", o_pressure), ("Keep sinking", o_sink), ("Eight thousand", o_snailfish),
        ("Nearly eleven", o_bottom), ("And the strangest", o_strange), ("A plastic", o_bag)],
}

_orig = R.render_frame
def render_frame(part, t, W, H, mode, sched, groups):
    G["t"] = t; G["part"] = part; G["stamps"] = []
    R.HL_COLOR[0] = THEME[part]["hl"]
    img = _orig(part, t, W, H, mode, sched, groups)
    if t < R.TIMING[part - 1]["duration"] - 1.7:
        draw_stamps(img, W, H)
        if part == 2 and t >= cue(2, "You hit"):
            draw_hud(img, depth_at(t), W, H)
    return img
R.render_frame = render_frame

if __name__ == "__main__":
    R.main()
