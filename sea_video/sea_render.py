"""Spooky sea story renderer. Reuses the dino renderer's engine (captions, header, camera, encode)."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dino_video"))
import render as R
from render import (clamp, lerp, ease, lc, dark, ell, rot_pts, h01, mountains, particles, stars, base, add_glow, Xf)
from PIL import ImageDraw

R.TITLES = ["The Light That Went Out", "The Ship In The Fog", "The Captain's Log",
            "Something Below", "Light The Lamp", "The Keeper"]
R.HL_COLOR[0] = (120, 255, 170)
R.HEADER_COLOR[0] = (25, 90, 70)
R.END_TEXT[0] = "FOLLOW FOR MORE SCARY STORIES"

GHOST = (120, 255, 170)

# ----------------------------------------------------------------- props
def sea(c, y, top, bot, t, amp=1.0, seed=1, foam=True):
    W, H, U = c.W, c.H, c.U
    if y >= H - 2:
        return
    c.d.rectangle([0, y, W, H], fill=bot)
    for layer in range(4):
        yy = y + layer * U * 0.05
        col = lc(top, bot, layer / 4)
        pts = [(0, H)]
        step = max(8, W // 80)
        for x in range(0, W + step, step):
            v = (math.sin(x * 0.012 + t * (1.2 + layer * 0.3) + seed + layer) * 0.6 +
                 math.sin(x * 0.031 - t * 1.7 + layer * 2) * 0.4)
            pts.append((x, yy + v * U * 0.025 * amp * (1 + layer * 0.4)))
        pts.append((W, H))
        c.d.polygon(pts, fill=col)
        if False:
            for x in range(0, W, step * 3):
                v = math.sin(x * 0.012 + t * 1.2 + seed)
                if v > 0.6:
                    c.d.ellipse([x - 6, yy - v * U * 0.025 * amp - 4, x + 6, yy - v * U * 0.025 * amp + 4], fill=(200, 215, 220))

def rock(d, cx, y, w, h, col):
    d.polygon([(cx - w, y + h * 0.3), (cx - w * 0.7, y - h * 0.4), (cx - w * 0.2, y - h * 0.7), (cx + w * 0.35, y - h * 0.6),
               (cx + w * 0.8, y - h * 0.2), (cx + w, y + h * 0.3)], fill=col)

def lighthouse(c, cx, base_y, h, lit=1.0, beam=0.0, col=(200, 200, 205), stripe=(150, 30, 35), dark_k=1.0):
    d = c.d
    w0, w1 = h * 0.13, h * 0.08
    body = dark(col, dark_k); st = dark(stripe, dark_k)
    d.polygon([(cx - w0, base_y), (cx + w0, base_y), (cx + w1, base_y - h), (cx - w1, base_y - h)], fill=body)
    for k in range(3):
        y0 = base_y - h * (0.18 + k * 0.28); y1 = y0 - h * 0.12
        f0 = 1 - (base_y - y0) / h; f1 = 1 - (base_y - y1) / h
        a0 = lerp(w1, w0, f0); a1 = lerp(w1, w0, f1)
        d.polygon([(cx - a0, y0), (cx + a0, y0), (cx + a1, y1), (cx - a1, y1)], fill=st)
    top = base_y - h
    d.rectangle([cx - w1 * 1.4, top - h * 0.02, cx + w1 * 1.4, top], fill=dark((40, 40, 45), dark_k))
    lamp_col = lc((30, 35, 40), (255, 245, 200), lit)
    d.rectangle([cx - w1 * 0.9, top - h * 0.13, cx + w1 * 0.9, top - h * 0.02], fill=lamp_col)
    d.polygon([(cx - w1 * 1.2, top - h * 0.13), (cx + w1 * 1.2, top - h * 0.13), (cx, top - h * 0.21)], fill=dark((40, 40, 45), dark_k))
    lx, ly = cx, top - h * 0.075
    if lit > 0.05:
        add_glow(c, [(lx, ly, h * 0.16, (255, 240, 190), 0.9 * lit)], 14)
        # rotating beam (drawn as a translucent wedge layer)
        from PIL import Image
        L = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0)); ld = ImageDraw.Draw(L)
        side = math.cos(beam)
        length = c.W * 1.2 * abs(side)
        if abs(side) > 0.05:
            sgn = 1 if side > 0 else -1
            spread = c.U * 0.06 + c.U * 0.1 * (1 - abs(side))
            ld.polygon([(lx, ly), (lx + sgn * length, ly - spread * 0.4), (lx + sgn * length, ly + spread)],
                       fill=(255, 245, 210, int(70 * lit)))
            c.img.paste(L, (0, 0), L)
            c.d = ImageDraw.Draw(c.img)

def person(d, x, y, s, col, kind="boy", facing=1, phase=0.0, arm_up=0.0, run=False):
    """simple silhouette person; y = feet, s = height."""
    X = Xf(x, y, s, facing)
    leg = 0.18 * math.sin(phase) if run else 0
    d.polygon(X([(-0.06, 0), (-0.02 + leg * 0.5, -0.45), (0.02, -0.45), (0.0 + leg, 0)]), fill=col)
    d.polygon(X([(0.06, 0), (0.02 - leg * 0.5, -0.45), (-0.02, -0.45), (0.0 - leg, 0)]), fill=col)
    coat_w = 0.15 if kind == "old" else 0.12
    d.polygon(X([(-coat_w, -0.38), (coat_w, -0.38), (0.1, -0.8), (-0.1, -0.8)]), fill=col)
    hy = -0.9
    d.ellipse(X([(-0.08, hy - 0.08)])[0] + X([(0.08, hy + 0.08)])[0], fill=col) if facing > 0 else \
        d.ellipse(X([(0.08, hy - 0.08)])[0] + X([(-0.08, hy + 0.08)])[0], fill=col)
    if kind == "old":
        d.polygon(X([(-0.12, hy - 0.05), (0.14, hy - 0.05), (0.08, hy - 0.13), (-0.08, hy - 0.13)]), fill=col)  # cap
        d.polygon(X([(0.0, hy + 0.03), (0.09, hy + 0.02), (0.05, hy + 0.17)]), fill=col)  # beard
    arm_a = -arm_up * 2.4
    sh = (0.06, -0.75)
    hand = rot_pts([(0.06, -0.42)], sh[0], sh[1], arm_a * facing if False else arm_a)[0]
    d.line(X([sh, hand]), fill=col, width=max(3, int(s * 0.05)))

def ghost_ship(c, cx, wl, s, alpha=1.0, lantern=1.0, figures=0.0, point=0.0, tilt=0.0, t=0.0):
    from PIL import Image
    L = Image.new("RGBA", (c.W, c.H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    a = int(255 * alpha)
    hull = (35, 45, 45, a); sail = (110, 125, 120, int(a * 0.8))
    def P(pts): return rot_pts([(cx + u * s, wl + v * s) for u, v in pts], cx, wl, tilt)
    d.polygon(P([(-0.6, -0.15), (0.6, -0.15), (0.5, 0.05), (-0.45, 0.05)]), fill=hull)
    d.polygon(P([(0.45, -0.15), (0.7, -0.3), (0.62, -0.13)]), fill=hull)
    for mx, mh in [(-0.25, 0.85), (0.15, 1.0)]:
        d.line(P([(mx, -0.15), (mx, -0.15 - mh)]), fill=hull, width=max(3, int(s * 0.02)))
        for k in range(2):
            y0 = -0.25 - k * mh * 0.42
            pts = [(mx - 0.22, y0 - 0.3), (mx + 0.22, y0 - 0.3), (mx + 0.18, y0), (mx + 0.05, y0 - 0.06),
                   (mx - 0.02, y0 + 0.01), (mx - 0.2, y0)]
            d.polygon(P(pts), fill=sail)
            for r in range(3):  # tears
                tx = mx - 0.15 + r * 0.12
                d.line(P([(tx, y0 - 0.25), (tx + 0.03, y0 - 0.05)]), fill=(0, 0, 0, 0), width=max(2, int(s * 0.012)))
    if figures > 0:
        fa = int(a * figures)
        for k in range(9):
            fx = -0.45 + k * 0.11
            fh = 0.13 + 0.02 * h01(k, 3)
            d.polygon(P([(fx - 0.025, -0.15), (fx + 0.025, -0.15), (fx + 0.02, -0.15 - fh), (fx - 0.02, -0.15 - fh)]),
                      fill=(150, 255, 190, int(fa * 0.6)))
            hx, hy = P([(fx, -0.17 - fh)])[0]; r = s * 0.022
            d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=(170, 255, 200, int(fa * 0.7)))
            if point > 0:
                d.line(P([(fx, -0.15 - fh * 0.75), (fx - 0.07 * point, -0.15 - fh * (0.75 + 0.3 * point))]),
                       fill=(150, 255, 190, int(fa * 0.6)), width=max(2, int(s * 0.012)))
    c.img.paste(L, (0, 0), L); c.d = ImageDraw.Draw(c.img)
    if lantern > 0:
        lx, ly = P([(0.15, -1.05)])[0]
        sw = math.sin(t * 1.3) * s * 0.02
        add_glow(c, [(lx + sw, ly, s * 0.25, GHOST, 0.75 * lantern * alpha)], 14)
        c.d.ellipse([lx + sw - s * 0.025, ly - s * 0.03, lx + sw + s * 0.025, ly + s * 0.03], fill=(200, 255, 215))

def fog(c, t, density=1.0, y0=0.3, y1=0.8, col=(160, 170, 175)):
    for i in range(int(10 * density)):
        fx = (h01(i, 71) * c.W * 1.6 + t * c.U * 0.04 * (0.5 + h01(i, 72))) % (c.W * 1.6) - c.W * 0.3
        fy = c.H * lerp(y0, y1, h01(i, 73))
        c.fog.append((fx, fy, c.U * (0.35 + 0.3 * h01(i, 74)), col + (int(110 * density),)))

def rain(c, t, n=140, col=(170, 185, 200)):
    W, H, U = c.W, c.H, c.U
    for i in range(n):
        x = (h01(i, 81) * W * 1.2 + t * U * 0.3) % (W * 1.2) - W * 0.1
        y = (h01(i, 82) * H + t * U * 2.2 * (0.8 + 0.4 * h01(i, 83))) % H
        c.d.line([x, y, x - U * 0.012, y + U * 0.045], fill=col, width=2)

def lightning(c, t, every=4.0, seed=0):
    ph = (t + seed) % every
    if ph < 0.12 or 0.2 < ph < 0.26:
        c.flash = 0.55
        return True
    return False

def giant_eye(c, x, y, r, openk=1.0, look=(0.0, 0.0), col=(170, 230, 120)):
    d = c.cd
    if openk <= 0.02:
        d.line([x - r, y, x + r, y], fill=(10, 20, 15), width=max(3, int(r * 0.05)))
        return
    add_glow(c, [(x, y, r * 1.6, (80, 255, 140), 0.5 * openk)], 18)
    pts_top = [(x + r * math.cos(a), y - r * 0.55 * openk * math.sin(a)) for a in [i / 20 * math.pi for i in range(21)]]
    pts_bot = [(x + r * math.cos(a), y + r * 0.55 * openk * math.sin(a)) for a in [math.pi - i / 20 * math.pi for i in range(21)]]
    d.polygon(pts_top + pts_bot, fill=col)
    ix, iy = x + look[0] * r * 0.4, y + look[1] * r * 0.2
    rr = r * 0.42 * min(1, openk * 1.4)
    d.ellipse([ix - rr, iy - rr, ix + rr, iy + rr], fill=(200, 160, 30))
    d.ellipse([ix - rr * 0.18, iy - rr * 0.9, ix + rr * 0.18, iy + rr * 0.9], fill=(5, 5, 5))

def tentacle(d, x0, y0, length, t, col, width, phase=0.0, dirx=0.0):
    pts = []
    n = 16
    for i in range(n + 1):
        k = i / n
        x = x0 + dirx * length * k + math.sin(t * 1.5 + k * 4 + phase) * length * 0.12 * k
        y = y0 - length * k
        pts.append((x, y, width * (1 - k * 0.85)))
    for (xa, ya, wa), (xb, yb, wb) in zip(pts, pts[1:]):
        d.polygon([(xa - wa, ya), (xa + wa, ya), (xb + wb, yb), (xb - wb, yb)], fill=col)
        d.ellipse([xb - wb, yb - wb, xb + wb, yb + wb], fill=col)

def bell(d, x, y, s, col):
    d.polygon([(x - s * 0.35, y), (x + s * 0.35, y), (x + s * 0.22, y - s * 0.5), (x, y - s * 0.62), (x - s * 0.22, y - s * 0.5)], fill=col)
    d.ellipse([x - s * 0.08, y - s * 0.05, x + s * 0.08, y + s * 0.1], fill=col)
    d.rectangle([x - s * 0.05, y - s * 0.75, x + s * 0.05, y - s * 0.6], fill=col)

# ----------------------------------------------------------------- scenes
NIGHT_TOP, NIGHT_BOT = (6, 10, 18), (25, 38, 48)

def sc_lighthouse(c, lit=1.0, storm=0.0, beam_speed=0.8, abel=True):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, NIGHT_TOP, lc(NIGHT_BOT, (40, 45, 55), storm))
    if storm < 0.5: stars(c.d, W, H, c.t, 60, ymax=0.4)
    if storm > 0 and lightning(c, c.t, 5.0, 1.3):
        c.d.line([W * 0.2, 0, W * 0.25, gy * 0.3, W * 0.18, gy * 0.5, W * 0.24, gy * 0.75], fill=(230, 235, 255), width=4)
    rock(c.d, W / 2, gy + U * 0.02, U * 0.42, U * 0.22, (20, 22, 26))
    lighthouse(c, W / 2, gy - U * 0.05, U * (0.85 if not c.vert else 0.62), lit, c.t * beam_speed, dark_k=0.55)
    if abel:
        person(c.cd, W / 2 + U * 0.2, gy - U * 0.05, U * 0.14, (10, 12, 14), "old", -1)
        person(c.cd, W / 2 + U * 0.3, gy - U * 0.05, U * 0.1, (10, 12, 14), "boy", -1)
    sea(c, gy, (25, 40, 50), (8, 14, 20), c.t, amp=1 + storm * 3)
    if storm > 0: rain(c, c.t, int(160 * storm))
    c.zoom = 1.0 + 0.05 * c.k

def sc_stairs_lamp(c, cold=True):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (8, 10, 14), (20, 24, 30))
    cx, cy = W / 2, gy - U * 0.35
    c.d.polygon([(cx - U * 0.35, cy + U * 0.35), (cx + U * 0.35, cy + U * 0.35), (cx + U * 0.25, cy - U * 0.2), (cx - U * 0.25, cy - U * 0.2)], fill=(28, 32, 38))
    lamp = (45, 50, 55) if cold else (255, 240, 190)
    c.d.ellipse([cx - U * 0.17, cy - U * 0.15, cx + U * 0.17, cy + U * 0.2], fill=lamp)
    for k in range(5):
        c.d.line([cx - U * 0.17 + k * U * 0.085, cy - U * 0.15, cx - U * 0.17 + k * U * 0.085, cy + U * 0.2], fill=(20, 22, 26), width=4)
    # wet streaks / handprint
    for i in range(14):
        x = cx - U * 0.3 + h01(i, 5) * U * 0.6
        y0 = cy - U * 0.3 + h01(i, 6) * U * 0.2
        L = U * (0.1 + 0.25 * h01(i, 7)) * clamp(c.k * 2)
        c.d.line([x, y0, x, y0 + L], fill=(70, 110, 120), width=3)
    hx, hy = cx + U * 0.05, cy - U * 0.05
    a = clamp(c.k * 1.5)
    c.d.ellipse([hx - U * 0.05, hy - U * 0.03, hx + U * 0.05, hy + U * 0.07], fill=lc((28, 32, 38), (60, 100, 95), a))
    for k in range(5):
        fx = hx - U * 0.05 + k * U * 0.025
        c.d.line([fx, hy - U * 0.02, fx + (k - 2) * U * 0.008, hy - U * 0.11], fill=lc((28, 32, 38), (60, 100, 95), a), width=int(U * 0.016))
    person(c.cd, W / 2 - U * 0.45, gy + U * 0.1, U * 0.3, (6, 8, 10), "boy", 1)
    c.zoom = 1.0 + 0.1 * c.k

def sc_underwater(c, bell_ring=True, eye=0.0, glow=0.3):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (8, 30, 30), (2, 6, 8))
    add_glow(c, [(W / 2, H * 0.15, U * 0.6, (60, 140, 120), glow)], 22)
    for i in range(8):  # light rays
        x = W * (0.1 + i * 0.11) + math.sin(c.t * 0.3 + i) * U * 0.03
        c.d.polygon([(x, 0), (x + U * 0.03, 0), (x + U * 0.12, H * 0.6), (x + U * 0.06, H * 0.6)], fill=(14, 40, 40))
    bx, by = W / 2 + math.sin(c.t * 0.8) * U * 0.04, gy - U * 0.15
    if bell_ring:
        bell(c.cd, bx, by, U * 0.3, (55, 60, 50))
        ring = (c.t % 2.2) / 2.2
        r = U * 0.2 + ring * U * 0.5
        c.d.ellipse([bx - r, by - U * 0.2 - r * 0.6, bx + r, by - U * 0.2 + r * 0.6], outline=(40, 90, 85), width=3)
    if eye > 0:
        giant_eye(c, W / 2, gy - (U * 0.2 if c.vert else -U * 0.1), U * 0.38, eye, (math.sin(c.t * 0.5) * 0.3, 0))
    particles(c.d, W, H, c.t, 70, 91, (60, 110, 100), U * 0.003, 5, -25)
    c.zoom = 1.0 + 0.06 * c.k

def sc_boots(c):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (40, 45, 52), (85, 92, 98))
    rock(c.d, W / 2 - U * 0.1, gy + U * 0.1, U * 0.7, U * 0.18, (30, 32, 36))
    bx, by = W / 2, gy - U * 0.02
    for k in (-1, 1):
        x = bx + k * U * 0.07
        c.cd.polygon([(x - U * 0.04, by), (x + U * 0.03, by), (x + U * 0.03, by - U * 0.16), (x - U * 0.03, by - U * 0.16)], fill=(25, 20, 18))
        c.cd.polygon([(x - U * 0.04, by), (x + U * 0.09, by), (x + U * 0.09, by - U * 0.04), (x - U * 0.04, by - U * 0.04)], fill=(25, 20, 18))
    sea(c, gy + U * 0.05, (60, 75, 85), (25, 32, 40), c.t, amp=0.8)
    person(c.cd, W / 2 - U * 0.42, gy + U * 0.06, U * 0.3, (12, 14, 16), "boy", 1)
    fog(c, c.t, 0.5, 0.3, 0.6)
    c.zoom = 1.0 + 0.08 * c.k

def sc_fog_ship(c, approach=0.0, figures=0.0, point=0.0):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (50, 58, 62), (110, 118, 120))
    s = U * lerp(0.35, 0.95, approach)
    ghost_ship(c, W / 2 + lerp(U * 0.3, 0, approach), gy + U * 0.02, s, alpha=lerp(0.35, 1.0, approach),
               figures=figures, point=point, t=c.t)
    sea(c, gy, (70, 82, 88), (35, 42, 48), c.t, amp=0.5)
    rock(c.d, W / 2 - U * 0.55, gy + U * 0.25, U * 0.5, U * 0.15, (25, 28, 30))
    person(c.cd, W / 2 - U * 0.55, gy + U * 0.18, U * 0.22, (10, 12, 14), "boy", 1)
    fog(c, c.t, lerp(1.4, 0.7, approach), 0.25, 0.75)
    c.zoom = 1.0 + 0.07 * c.k

def sc_ship_close(c):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (30, 38, 42), (70, 78, 82))
    ghost_ship(c, W / 2 + U * 0.15, gy + U * 0.02, U * 1.05, alpha=1.0, figures=0.0, t=c.t)
    sea(c, gy, (50, 60, 66), (20, 26, 30), c.t, amp=0.4)
    px = lerp(W / 2 - U * 0.5, W / 2 - U * 0.15, ease(c.k))
    person(c.cd, px, gy - U * 0.12 * ease(c.k), U * 0.2, (8, 10, 12), "boy", 1, c.t * 6, run=c.k < 0.95)
    fog(c, c.t, 0.6, 0.35, 0.7)
    c.zoom = 1.02 + 0.06 * c.k

def sc_cabin(c, words=0.0, msg=""):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (30, 22, 16), (12, 9, 7))
    for k in range(8):  # planks
        y = gy - U * 0.9 + k * U * 0.13
        c.d.line([0, y, W, y + U * 0.01], fill=(22, 16, 12), width=3)
    fl = 0.8 + 0.2 * math.sin(c.t * 9) * math.sin(c.t * 3.3)
    cx, cy = W / 2 + U * 0.3, gy - U * 0.15
    add_glow(c, [(cx, cy - U * 0.15, U * 0.5, (255, 170, 80), 0.6 * fl)], 20)
    c.d.rectangle([0, gy, W, H], fill=(40, 28, 18))  # table
    c.d.rectangle([cx - U * 0.025, cy - U * 0.1, cx + U * 0.025, gy], fill=(220, 210, 180))
    c.d.polygon([(cx - U * 0.015, cy - U * 0.1), (cx + U * 0.015, cy - U * 0.1), (cx, cy - U * 0.17 - fl * U * 0.02)], fill=(255, 210, 120))
    # book
    bx, by = W / 2 - U * 0.1, gy - (U * 0.3 if c.vert else U * 0.05)
    bw, bh = U * 0.62, U * 0.36
    c.d.polygon([(bx - bw / 2, by), (bx, by - U * 0.02), (bx, by + bh), (bx - bw / 2, by + bh)], fill=(210, 195, 160))
    c.d.polygon([(bx, by - U * 0.02), (bx + bw / 2, by), (bx + bw / 2, by + bh), (bx, by + bh)], fill=(222, 208, 172))
    for k in range(9):
        y = by + U * 0.04 + k * U * 0.033
        L = bw * 0.4 * (0.6 + 0.4 * h01(k, 3))
        c.d.line([bx - bw / 2 + U * 0.03, y, bx - bw / 2 + U * 0.03 + L, y], fill=(80, 60, 45), width=2)
    if msg:
        f = R.font(R.FONT_BLACK, int(U * 0.06))
        n = int(len(msg) * clamp(words))
        c.d.text((bx + U * 0.03, by + U * 0.08), msg[:n], font=f, fill=(110, 20, 15))
    c.zoom = 1.0 + 0.12 * c.k

def sc_floorboards(c, eye=0.0, flood=0.0):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (6, 30, 22), (2, 12, 10))
    if eye > 0:
        giant_eye(c, W / 2, gy - U * 0.05, U * 0.55, eye, (math.sin(c.t * 0.6) * 0.5, 0.2))
    for k in range(7):  # floorboards over the glow
        x = k * W / 6 - U * 0.02
        c.cd.rectangle([x, 0, x + W / 6 * 0.62, H], fill=(28, 20, 14, 255))
    if flood > 0:
        wy = lerp(H, gy - U * 0.3, flood)
        sea(c, wy, (30, 70, 70), (10, 30, 30), c.t * 2, amp=0.6, foam=False)
    c.zoom = 1.0 + 0.05 * c.k

def sc_rising(c, rise=0.0, lit=0.0):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (5, 8, 12), (18, 30, 30))
    if lightning(c, c.t, 3.5, 0.7): pass
    rock(c.d, W / 2 + U * 0.25, gy + U * 0.02, U * 0.35, U * 0.2, (16, 18, 22))
    lighthouse(c, W / 2 + U * 0.25, gy - U * 0.05, U * (0.75 if not c.vert else 0.58), lit, c.t, dark_k=0.4)
    cr = ease(rise)
    body_y = gy + U * 0.6 - cr * U * 0.9
    c.d.ellipse([W / 2 - U * 0.95, body_y - U * 0.55, W / 2 + U * 0.15, body_y + U * 0.6], fill=(10, 22, 20))
    if cr > 0.3:
        giant_eye(c, W / 2 - U * 0.45, body_y - U * 0.15, U * 0.12, clamp((cr - 0.3) * 3), (1, -0.3))
    for k in range(4):
        tentacle(c.d, W / 2 - U * (0.9 - k * 0.3), gy + U * 0.1, U * (0.3 + 0.6 * cr) * (0.8 + 0.2 * k), c.t, (12, 26, 24),
                 U * 0.045, k * 1.7, dirx=0.25)
    sea(c, gy, (20, 35, 38), (5, 10, 12), c.t, amp=2.2)
    rain(c, c.t, 120)
    c.shake = U * 0.006 * cr
    c.zoom = 1.0 + 0.06 * c.k

def sc_stairs_run(c):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (12, 14, 18), (30, 34, 40))
    off = (c.t * U * 0.5) % (U * 0.16)
    for k in range(-2, 16):
        y = gy + U * 0.5 - k * U * 0.16 + off
        x = W / 2 + math.sin(k * 0.9 + c.t * 0.5) * U * 0.25
        c.d.polygon([(x - U * 0.3, y), (x + U * 0.3, y), (x + U * 0.25, y - U * 0.04), (x - U * 0.25, y - U * 0.04)], fill=(45, 48, 55))
    c.d.rectangle([W / 2 - U * 0.04, 0, W / 2 + U * 0.04, H], fill=(20, 22, 26))
    person(c.cd, W / 2 + U * 0.08, gy + U * 0.05, U * 0.32, (5, 6, 8), "boy", 1, c.t * 12, run=True)
    if c.k > 0.4:
        wy = lerp(H, min(gy + U * 0.3, H * 0.85), (c.k - 0.4) / 0.6)
        sea(c, wy, (30, 60, 60), (10, 25, 25), c.t * 2, amp=0.8, foam=False)
    c.shake = U * 0.008
    c.zoom = 1.04

def sc_eye_window(c, match=0.0):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (4, 6, 8), (10, 14, 16))
    giant_eye(c, W / 2, gy - U * 0.35, U * 0.5, 1.0, (math.sin(c.t * 0.9) * 0.4, 0.3))
    # window frame
    fx0, fx1 = W / 2 - U * 0.6, W / 2 + U * 0.6
    for k in range(4):
        x = lerp(fx0, fx1, k / 3)
        c.cd.rectangle([x - U * 0.02, gy - U * 1.0, x + U * 0.02, gy + U * 0.2], fill=(18, 18, 20, 255))
    c.cd.rectangle([fx0, gy - U * 0.4, fx1, gy - U * 0.36], fill=(18, 18, 20, 255))
    person(c.cd, W / 2 - U * 0.3, gy + U * 0.45, U * 0.5, (3, 3, 4), "boy", 1, arm_up=0.6 if match else 0.0)
    if match > 0:
        mx, my = W / 2 - U * 0.15, gy + U * 0.12
        fl = 0.8 + 0.2 * math.sin(c.t * 20)
        add_glow(c, [(mx, my, U * 0.25 * match, (255, 170, 70), 0.9 * fl * match)], 14)
        c.d.polygon([(mx - U * 0.015, my), (mx + U * 0.015, my), (mx, my - U * 0.06 * fl)], fill=(255, 220, 140))
    c.zoom = 1.0 + 0.08 * c.k

def sc_beam_on(c):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (10, 16, 26), (30, 45, 55))
    rock(c.d, W / 2, gy + U * 0.02, U * 0.42, U * 0.22, (20, 22, 26))
    lighthouse(c, W / 2, gy - U * 0.05, U * (0.85 if not c.vert else 0.62), 1.0, c.t * 1.5, dark_k=0.6)
    sink = ease(c.k * 1.3)
    by = gy + U * 0.1 + sink * U * 0.6
    c.d.ellipse([W / 2 - U * 1.0, by - U * 0.4, W / 2 - U * 0.3, by + U * 0.5], fill=(10, 22, 20))
    for k in range(3):
        tentacle(c.d, W / 2 - U * (0.9 - k * 0.25), gy + U * 0.1, U * 0.6 * (1 - sink), c.t * 2, (12, 26, 24), U * 0.04, k)
    sea(c, gy, (30, 45, 55), (8, 14, 20), c.t, amp=lerp(2.5, 0.8, sink))
    c.shake = U * 0.012 * (1 - sink)
    c.zoom = 1.03

def sc_dawn(c, abel=False, lamp=False, hands=False):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    if lamp:
        base(c, (20, 22, 40), (110, 70, 80))
    else:
        base(c, (110, 115, 120), (175, 170, 160))
    rock(c.d, W / 2, gy + U * 0.02, U * 0.42, U * 0.22, (45, 46, 50) if not lamp else (25, 25, 30))
    lighthouse(c, W / 2, gy - U * 0.05, U * (0.85 if not c.vert else 0.62), 1.0 if lamp else 0.0, c.t * 0.8, dark_k=0.9 if not lamp else 0.6)
    sea(c, gy, (110, 115, 118) if not lamp else (60, 50, 70), (60, 65, 70) if not lamp else (20, 18, 30), c.t * 0.5, amp=0.3)
    if abel:
        person(c.cd, W / 2 + U * 0.2, gy - U * 0.05, U * 0.15, (15, 16, 18), "old", -1)
    person(c.cd, W / 2 + U * (0.32 if abel else 0.2), gy - U * 0.05, U * 0.11, (15, 16, 18), "boy", -1, arm_up=0.3 if hands else 0)
    c.zoom = 1.0 + 0.05 * c.k

def sc_hands(c):
    W, H, U, gy = c.W, c.H, c.U, c.gy
    base(c, (20, 24, 28), (45, 52, 58))
    for k in (-1, 1):
        cx = W / 2 + k * U * 0.2
        c.cd.ellipse([cx - U * 0.17, gy - U * 0.2, cx + U * 0.17, gy + U * 0.15], fill=(190, 160, 140))
        for f in range(4):
            fx = cx - U * 0.12 + f * U * 0.08
            c.cd.rounded_rectangle([fx - U * 0.03, gy - U * 0.45 + abs(f - 1.5) * U * 0.04, fx + U * 0.03, gy - U * 0.1],
                                   radius=int(U * 0.03), fill=(190, 160, 140))
        tx = cx + k * U * 0.19
        c.cd.rounded_rectangle([tx - U * 0.03, gy - U * 0.25, tx + U * 0.03, gy], radius=int(U * 0.03), fill=(190, 160, 140))
    for i in range(16):  # drips
        x = W / 2 + (h01(i, 9) - 0.5) * U * 0.7
        y = gy + U * 0.1 + ((c.t * U * 0.4 + h01(i, 10) * U * 0.6) % (U * 0.6))
        c.d.ellipse([x - 4, y - 7, x + 4, y + 7], fill=(90, 140, 140))
    c.zoom = 1.0 + 0.1 * c.k

R.SCENES = {
    1: [("Part", lambda c: sc_lighthouse(c, 1.0, 0.0)),
        ("One November", lambda c: sc_lighthouse(c, 1.0, ease(c.k * 2))),
        ("And at exactly", lambda c: sc_lighthouse(c, 1.0 - ease(c.k * 3), 1.0, abel=False)),
        ("Finn ran", lambda c: sc_stairs_lamp(c)),
        ("Far out", lambda c: sc_underwater(c, True))],
    2: [("Part", sc_boots),
        ("Then the fog", lambda c: sc_fog_ship(c, 0.0)),
        ("It was old", lambda c: sc_fog_ship(c, ease(c.k) * 0.6)),
        ("Finn could see", lambda c: sc_fog_ship(c, 0.6 + 0.2 * ease(c.k), ease(c.k * 2))),
        ("Then the green", lambda c: sc_fog_ship(c, 0.8 + 0.2 * ease(c.k), 1.0, ease(c.k * 1.5))),
        ("Finn knew", lambda c: sc_fog_ship(c, 1.0, 1.0 - 0.6 * c.k, 1.0))],
    3: [("Part", sc_ship_close),
        ("The ship smelled", lambda c: sc_cabin(c)),
        ("The last page", lambda c: sc_cabin(c, 1.0, "")),
        ("Finn turned", lambda c: sc_cabin(c, clamp((c.tl - 3.5) / 5.0), "FINN.\nDO NOT\nLOOK DOWN"))],
    4: [("Part", lambda c: sc_floorboards(c, 0.0)),
        ("Through the gaps", lambda c: sc_floorboards(c, 0.15)),
        ("Then it opened", lambda c: sc_floorboards(c, ease(c.k * 1.5))),
        ("The deck groaned", lambda c: sc_floorboards(c, 1.0, ease(c.k))),
        ("Finn scrambled", lambda c: sc_rising(c, ease(c.k), 0.0)),
        ("At the dark", lambda c: sc_rising(c, 1.0, 0.0))],
    5: [("Part", sc_stairs_run),
        ("Outside the glass", lambda c: sc_eye_window(c, 0.0)),
        ("Finn struck", lambda c: sc_eye_window(c, ease(c.k * 3))),
        ("The wick caught", sc_beam_on),
        ("Somewhere far", lambda c: sc_underwater(c, True, 0.0, 0.15))],
    6: [("Part", lambda c: sc_dawn(c)),
        ("Then Finn heard", lambda c: sc_dawn(c, abel=True)),
        ("That evening", lambda c: sc_dawn(c, abel=True, lamp=True)),
        ("Finn looked down", sc_hands),
        ("Far below", lambda c: sc_underwater(c, False, ease(clamp((c.tl - 2.0) / 3.0)), 0.1))],
}

# --- patch render_frame to support lightning flash + local-time attr
_orig = R.render_frame
def render_frame(part, t, W, H, mode, sched, groups):
    return _orig(part, t, W, H, mode, sched, groups)
R.render_frame = render_frame

if __name__ == "__main__":
    R.main()
