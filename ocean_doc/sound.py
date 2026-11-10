#!/usr/bin/env python3
"""THE OCEAN IS MORE TERRIFYING THAN YOU THINK - sound.

Everything except the narration is synthesised here: surface water, the plunge, a low
underwater bed, a slowly sinking drone, pressure groans, far-off calls, a small glassy tone
for each bioluminescent flash, and a heartbeat with a rising cluster for the last ten seconds.

  python3 sound.py            -> audio/mix.wav (48 kHz stereo, about -14 LUFS)
  python3 sound.py --stems    -> also audio/stem_*.wav for checking the balance
"""
import math
import os
import re
import subprocess
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

import timeline as TL

HERE = TL.HERE
SR = 48000
END = TL.END
N = int(round(END * SR))
TAIL = 9 * SR
NT = N + TAIL
T = np.arange(NT) / SR
rng = np.random.default_rng(2026)

D2, Eb2, F2, Ab2, A2, Bb2 = 73.42, 77.78, 87.31, 103.83, 110.00, 116.54
C3, D3, Eb3, F3, A3, Bb3 = 130.81, 146.83, 155.56, 174.61, 220.00, 233.08
C4, Db4, D5, Eb5, A5 = 261.63, 277.18, 587.33, 622.25, 880.00
GLASS = [1174.66, 1244.51, 1396.91, 1661.22, 1760.00, 2217.46]


# ----------------------------------------------------------------------------- dsp helpers
def lp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "lowpass", fs=SR, output="sos"), x, axis=0)


def hp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "highpass", fs=SR, output="sos"), x, axis=0)


def bp(x, f1, f2, order=2):
    return signal.sosfilt(signal.butter(order, [f1, f2], "bandpass", fs=SR, output="sos"), x, axis=0)


def curve(points, t=T):
    ts, vs = zip(*points)
    return np.interp(t, ts, vs)


def smooth(k):
    k = np.clip(k, 0, 1)
    return k * k * (3 - 2 * k)


def rms_db(x):
    return 20 * math.log10(max(1e-9, float(np.sqrt(np.mean(np.square(x))))))


def norm_rms(x, target=1.0):
    return x * (target / max(1e-9, float(np.sqrt(np.mean(np.square(x))))))


class Mix:
    def __init__(self):
        self.dry = np.zeros((NT, 2))
        self.hall = np.zeros((NT, 2))
        self.deep = np.zeros((NT, 2))

    def add(self, x, t, gain=1.0, pan=0.0, hall=0.0, deep=0.0):
        i = int(round(t * SR))
        if i < 0:
            x = x[-i:]
            i = 0
        n = min(len(x), NT - i)
        if n <= 0:
            return
        if x.ndim == 1:
            a = (pan + 1) * math.pi / 4
            st = np.stack([x[:n] * math.cos(a), x[:n] * math.sin(a)], 1) * 1.4142
        else:
            st = x[:n]
        st = st * gain
        self.dry[i:i + n] += st
        if hall:
            self.hall[i:i + n] += st * hall
        if deep:
            self.deep[i:i + n] += st * deep


def make_ir(tau, fc, dur, seed, predelay=0.02):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    pd = int(predelay * SR)
    ir = np.zeros((n + pd, 2))
    for c in range(2):
        x = r.standard_normal(n) * np.exp(-t / tau)
        ir[pd:, c] = hp(lp(x, fc, 2), 90, 1)
    return ir / np.sqrt(np.square(ir).sum(0)).mean()


def reverb(x, ir):
    return np.stack([signal.fftconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)], 1)


# ----------------------------------------------------------------------------- sources
def boom(dur=3.5, f0=95.0, f1=33.0, tau=0.9, click=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.10)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t / tau)
    x += 0.35 * np.sin(2 * ph) * np.exp(-t / (tau * 0.35))      # an octave up, so small speakers carry it too
    x += lp(rng.standard_normal(n), 220, 2) * np.exp(-t / 0.16) * click * 3.0
    return x * np.minimum(1, t / 0.004)


def riser(dur, f1=300.0, f2=2500.0):
    n = int(dur * SR)
    k = np.arange(n) / n
    return bp(rng.standard_normal(n), f1, f2) * k ** 3 * (1 - np.clip((k - 0.97) / 0.03, 0, 1))


def groan(dur, f0):
    """Slow metallic creak, like a hull taking load."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    wob = lp(rng.standard_normal(n), 3.0, 2)
    wob /= np.abs(wob).max() + 1e-9
    f = f0 * (1 + 0.10 * wob + 0.03 * np.sin(2 * np.pi * 1.7 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.6 * np.sin(1.47 * ph + 1) + 0.4 * np.sin(2.09 * ph + 2) + 0.25 * np.sin(2.83 * ph)
    st = lp(np.abs(rng.standard_normal(n)), 14.0, 2)
    st /= st.max()
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5 * (0.35 + 0.65 * st)
    return bp(np.tanh(2.2 * x * env), 140, 1100)


def moan(dur, fa, fb):
    """Long falling call from far away."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = t / dur
    f = (fa + (fb - fa) * smooth(k) + 5 * np.sin(2 * np.pi * 4.5 * t) * k) * (1 + 0.04 * np.exp(-k / 0.08))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.42 * np.sin(2 * ph + 0.5) + 0.16 * np.sin(3 * ph + 1.1) + 0.06 * np.sin(4 * ph)
    return lp(x * np.sin(np.pi * k) ** 1.3, 1100)


def ping(f=1180.0):
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.09) * np.minimum(1, t / 0.003)
    out = np.zeros((n + int(2.0 * SR), 2))
    for i, (dl, g) in enumerate([(0.0, 1.0), (0.41, 0.42), (0.82, 0.20), (1.23, 0.10), (1.64, 0.05)]):
        y = lp(x, 6000 / (1 + i * 1.3)) if i else x
        a = ((0.0 if i == 0 else (0.6 if i % 2 else -0.6)) + 1) * math.pi / 4
        j = int(dl * SR)
        out[j:j + n, 0] += y * g * math.cos(a) * 1.4142
        out[j:j + n, 1] += y * g * math.sin(a) * 1.4142
    return out


def sparkle(f, dur=1.3):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.08)) \
        * np.exp(-t / 0.28) * np.minimum(1, t / 0.004)


def swell_tone(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * f * t + 0.6 * np.sin(2 * np.pi * 3.1 * t)) * np.sin(np.pi * t / dur) ** 2


def thump(f0=64.0, f1=42.0, dur=0.24):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / 0.03)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t / 0.07) + 0.5 * np.sin(2 * ph) * np.exp(-t / 0.04) + 0.25 * np.sin(3 * ph) * np.exp(-t / 0.03)
    x += 0.38 * np.sin(5 * ph) * np.exp(-t / 0.028) + 0.22 * np.sin(8 * ph + 0.5) * np.exp(-t / 0.020)   # the knock a phone can play
    return x * np.minimum(1, t / 0.003)


def bubble(f0, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f0 * (1 + 1.8 * (t / dur) ** 1.5)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / dur) ** 2


def pad(notes, dur, cut0, cut1=None, detune=0.006, voices=3):
    """Dark detuned chord. Returns stereo, roughly unit RMS before filtering."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for f in notes:
        for v in range(voices):
            d = (v - (voices - 1) / 2) * detune
            s = 2 * ((f * (1 + d) * t + rng.random()) % 1.0) - 1
            a = (np.clip((v - (voices - 1) / 2) * 0.7 + rng.uniform(-0.15, 0.15), -1, 1) + 1) * math.pi / 4
            out[:, 0] += s * math.cos(a)
            out[:, 1] += s * math.sin(a)
    out /= math.sqrt(len(notes) * voices) * 0.4
    a = lp(out, cut0, 2)
    if cut1 and cut1 != cut0:
        k = (np.arange(n) / n)[:, None]
        a = a * (1 - k) + lp(out, cut1, 2) * k
    return a


def load_vo(i):
    p = os.path.join(HERE, "audio", "vo", "s%d.mp3" % i)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def block_env(x, win=0.03, hop=0.01):
    """RMS envelope sampled every hop, interpolated back to audio rate."""
    h, w = int(hop * SR), int(win * SR)
    c = np.concatenate([[0.0], np.cumsum(np.square(x))])
    idx = np.arange(0, len(x), h)
    lo = np.maximum(idx - w // 2, 0)
    hi = np.minimum(idx + w // 2, len(x))
    e = np.sqrt((c[hi] - c[lo]) / np.maximum(hi - lo, 1))
    return np.interp(np.arange(len(x)), idx, e)


def voice_chain(x):
    x = hp(x, 65, 2)
    e = block_env(x)
    act = e > 0.02 * e.max()
    x = x * (0.10 / max(1e-9, float(np.sqrt(np.mean(np.square(x[act]))))))     # speech at about -20 dBFS RMS
    e = block_env(x)
    thr, ratio = 0.11, 2.2                                                      # gentle levelling
    g = np.where(e > thr, (thr + (e - thr) / ratio) / np.maximum(e, 1e-9), 1.0)
    g = lp(g, 12.0, 1)
    x = x * g * 1.12
    x = 0.46 * np.tanh(x / 0.46)                                                 # round off the tallest peaks
    return x * 1.2


# ----------------------------------------------------------------------------- build
def build(stems=False):
    m = Mix()          # effects and music
    v = Mix()          # narration

    # --- surface: quiet water under the moon, muffled as the lens goes under
    n = int(6.2 * SR)
    tl = np.arange(n) / SR
    w = bp(rng.standard_normal((n, 2)), 180, 2600, 2)
    w[:, 0] *= 0.55 + 0.45 * np.sin(2 * np.pi * 0.21 * tl + 0.6)
    w[:, 1] *= 0.60 + 0.40 * np.sin(2 * np.pi * 0.33 * tl + 2.0)
    lap = lp(np.abs(rng.standard_normal((n, 2))), 2.2, 2)
    lap = (lap / lap.max(0)) ** 2
    w = w + bp(rng.standard_normal((n, 2)), 500, 4200, 2) * lap * 0.9
    w = norm_rms(w, 1.0)
    k = smooth((tl - 3.85) / 0.5)[:, None]
    amb = w * (1 - k) + lp(w, 320, 2) * k * 2.2
    amb *= (np.minimum(1, tl / 0.25) * (1 - smooth((tl - 4.5) / 1.6)))[:, None]
    m.add(amb, 0.0, gain=0.024)

    # --- the plunge and the bubbles that follow
    pl = boom(1.6, 80, 38, 0.35, 0.9)
    m.add(pl, 4.02, gain=0.10, deep=0.4)
    wl = int(1.0 * SR)
    whoosh = bp(rng.standard_normal(wl), 150, 1800) * np.sin(np.pi * np.arange(wl) / wl) ** 2
    m.add(whoosh, 3.70, gain=0.07, hall=0.4)
    for i in range(30):
        tb = 4.12 + rng.exponential(0.55)
        if tb > 6.6:
            continue
        m.add(lp(bubble(rng.uniform(280, 900), rng.uniform(0.04, 0.11)), 2600), tb,
              gain=rng.uniform(0.012, 0.035) * math.exp(-(tb - 4.12) / 1.2), pan=rng.uniform(-0.8, 0.8), hall=0.7)

    # --- underwater bed: rumble plus a little mid-band "water" that small speakers can carry
    rum = norm_rms(lp(rng.standard_normal((NT, 2)), 110, 2), 1.0)
    body = norm_rms(bp(rng.standard_normal((NT, 2)), 220, 800, 2), 1.0)
    lfo = 1 + 0.30 * np.sin(2 * np.pi * 0.07 * T + 1.0) + 0.20 * np.sin(2 * np.pi * 0.13 * T)
    bed = (rum * 0.9 + body * 0.22 * (1 + 0.4 * np.sin(2 * np.pi * 0.05 * T))[:, None]) * lfo[:, None]
    g_bed = curve([(0, 0), (3.9, 0), (4.6, 0.5), (8, 0.6), (16, 0.45), (17.6, 0.3), (18, 0.8), (28, 0.7), (38.5, 0.6),
                   (38.9, 0.25), (39.5, 0.6), (49, 0.6), (58.5, 0.9), (59.3, 0.9), (59.4, 0.15), (59.95, 0.5),
                   (61.3, 0.4), (END, 0.0), (END + 1, 0.0)])
    m.dry += bed * g_bed[:, None] * 0.022

    # --- drone: sinks with the camera, creeps upward again at the very end
    f_root = curve([(0, F2), (5, F2), (12.5, D2), (53, D2), (59.3, Eb2), (60, D2), (END + 9, D2)])
    g_dr = curve([(0, 0), (2.4, 0), (4.5, 0.12), (6, 0.35), (12, 0.55), (16, 0.35), (17.6, 0.2), (18, 0.75), (27, 0.8),
                  (28, 0.55), (33, 0.7), (38.4, 0.7), (38.9, 0.2), (39.5, 0.55), (45, 0.7), (49, 0.55), (53, 0.7),
                  (59.25, 1.0), (59.33, 0.0), (END + 9, 0.0)])
    dr = np.zeros((NT, 2))
    for c, dc in enumerate((-0.0012, 0.0012)):
        ph = 2 * np.pi * np.cumsum(f_root * (1 + dc)) / SR
        x = 0.55 * np.sin(ph / 2) + 0.40 * np.sin(ph) + 0.16 * np.sin(1.5 * ph + 1.0 + c)
        for h in range(2, 7):
            x += (0.22 / h ** 1.5) * np.sin(h * ph + 0.7 * h + c)
        dr[:, c] = x * (1 + 0.12 * np.sin(2 * np.pi * 0.09 * T + c))
    m.dry += dr * g_dr[:, None] * 0.050

    # --- chords
    def pad_ev(t0, t1, notes, c0, c1, env, level, hall=0.25, trem=None):
        x = pad(notes, t1 - t0, c0, c1)
        tl = t0 + np.arange(len(x)) / SR
        e = curve(env, tl)
        if trem:
            d = curve(trem, tl)
            e = e * (1 - d * 0.5 * (1 + np.sin(2 * np.pi * 6.5 * tl)))
        m.add(x * e[:, None], t0, gain=level, hall=hall)

    pad_ev(2.4, 8.6, [D3, A3], 420, 420, [(2.4, 0), (5.2, 0.7), (8.6, 0)], 0.050)
    pad_ev(7.5, 16.6, [D2, A2, F3], 520, 300, [(7.5, 0), (9.5, 0.8), (12.5, 0.8), (16.6, 0)], 0.070)
    pad_ev(18.0, 28.2, [D2, A2, D3, F3], 380, 600,
           [(18.0, 0), (18.3, 0.8), (21, 0.55), (27.2, 1.0), (28.15, 0)], 0.085)
    pad_ev(28.6, 38.9, [D2, Ab2, D3, Eb3], 340, 760,
           [(28.6, 0), (31.5, 0.6), (33.8, 1.0), (35, 0.8), (38.4, 1.0), (38.87, 0)], 0.085)
    pad_ev(39.3, 49.0, [D2, A2, F3, C4], 420, 640,
           [(39.3, 0), (41.8, 0.8), (43, 0.9), (44.9, 0.7), (46, 0.95), (48.95, 0)], 0.080)
    pad_ev(45.0, 49.0, [Db4], 900, 900, [(45.0, 0), (45.6, 1.0), (48.0, 0.8), (48.95, 0)], 0.022, hall=0.6)
    pad_ev(50.5, 59.34, [D2, A2, Eb3, Bb3], 330, 1700,
           [(50.5, 0), (53, 0.25), (56, 0.5), (59.2, 1.0), (59.32, 0)], 0.170,
           trem=[(50.5, 0), (55, 0.1), (59.2, 0.55)])
    pad_ev(60.0, END, [D2, A2], 300, 300, [(60.0, 0), (60.8, 1.0), (61.3, 0.8), (END, 0)], 0.040)

    # --- last ten seconds: a thin cluster that keeps climbing
    nh = int((59.32 - 53.0) * SR)
    th = np.arange(nh) / SR
    glide = 2 ** (th / (59.32 - 53.0) * 1.0 / 12.0)
    hi = np.zeros(nh)
    for f, a0 in ((D5, 1.0), (Eb5, 0.8), (A5, 0.5)):
        hi += a0 * np.sin(2 * np.pi * np.cumsum(f * glide) / SR + rng.random() * 6.28) * (1 + 0.3 * np.sin(2 * np.pi * rng.uniform(4, 7) * th))
    e = curve([(0, 0), (2.0, 0.25), (6.2, 1.0), (6.31, 0)], th)
    m.add(hi * e, 53.0, gain=0.010, hall=1.5)

    # --- hits on the cuts, with a short intake of breath before the big ones
    m.add(boom(3.0, 85, 34, 0.8, 0.3), 0.05, gain=0.065, deep=0.5)
    m.add(riser(0.55), 17.45, gain=0.030, hall=0.6)
    m.add(boom(4.0, 100, 31, 1.1, 0.6), 18.0, gain=0.15, deep=0.5)
    m.add(boom(3.0, 80, 33, 0.8, 0.35), TL.T_TRENCH_CUT, gain=0.07, deep=0.5)
    m.add(riser(0.7), TL.T_ANGLER_CUT - 0.7, gain=0.035, hall=0.6)
    m.add(boom(3.0, 90, 34, 0.8, 0.5), TL.T_ANGLER_CUT, gain=0.09, deep=0.5)
    m.add(riser(0.6), TL.T_SQUID_CUT - 0.6, gain=0.030, hall=0.6)
    m.add(boom(3.0, 78, 33, 0.9, 0.35), TL.T_SQUID_CUT, gain=0.08, deep=0.5)
    m.add(boom(5.0, 110, 30, 1.4, 0.7), TL.T_TEXT, gain=0.17, deep=0.5)

    def stab(t0, notes, level, decay, c0=1400, c1=450, dur=3.2):
        x = pad(notes, dur, c0, c1)
        tl = np.arange(len(x)) / SR
        m.add(x * (np.minimum(1, tl / 0.012) * np.exp(-tl / decay))[:, None], t0, gain=level, hall=0.8, deep=0.3)

    stab(0.05, [D3, A3], 0.030, 0.9, 900, 400)
    stab(18.0, [D2, A2, D3], 0.085, 1.0)
    stab(TL.T_ANGLER_CUT, [D2, Ab2, Eb3], 0.045, 0.8, 1100, 400)
    stab(TL.T_SQUID_CUT, [D2, A2, Db4], 0.040, 0.9, 1100, 400)
    stab(TL.T_TEXT, [D2, A2, D3, A3], 0.110, 1.3, 1600, 420, dur=3.6)

    # --- the trench: the hull complains, and the pressure keeps building
    for tg, dur, f0, g, pan in ((20.5, 1.3, 110, 0.050, -0.5), (22.9, 1.6, 82, 0.060, 0.4),
                                (25.3, 1.1, 131, 0.045, -0.2), (26.7, 1.5, 98, 0.055, 0.6)):
        m.add(groan(dur, f0), tg, gain=g, pan=pan, deep=1.0, hall=0.3)
    ns = int(4.3 * SR)
    ts = np.arange(ns) / SR
    sw = (np.sin(2 * np.pi * 46 * ts) + 0.3 * np.sin(2 * np.pi * 92 * ts)) * (ts / 4.3) ** 2 * (1 - smooth((ts - 4.0) / 0.3))
    m.add(sw, 23.6, gain=0.07)

    # --- calls from far away
    for tm, dur, fa, fb, g, pan in ((13.7, 2.6, 235, 165, 0.016, 0.5), (39.75, 2.6, 185, 118, 0.036, -0.5),
                                    (43.6, 2.2, 150, 104, 0.030, 0.6), (51.2, 2.8, 128, 92, 0.026, -0.3)):
        m.add(moan(dur, fa, fb), tm, gain=g, pan=pan, deep=1.6, hall=0.4)
    for tp, g in ((6.3, 0.022), (15.0, 0.016), (50.2, 0.022), (53.7, 0.020)):
        m.add(ping(), tp, gain=g, hall=0.9)

    # --- one small glassy tone for every light that flashes in the dark
    for i, (t0, x, y, amp, sg, col) in enumerate(TL.S2_SPARKS):
        m.add(sparkle(GLASS[(i * 2 + 1) % len(GLASS)]), t0, gain=0.030 * amp / 0.3, pan=(x - 0.5) * 1.6, hall=1.4)
    for j, e in enumerate(TL.ANGLER_FAR + TL.CLOSE_FAR):
        f = GLASS[(j * 5 + 2) % len(GLASS)]
        pan = (e["x"] - 0.5) * 1.6
        if e["kind"] == "flash":
            for r in range(e["rep"]):
                m.add(sparkle(f), e["t0"] + r * 0.42, gain=0.020 * e["amp"] / 0.3 * (0.8 ** r), pan=pan, hall=1.4)
        else:
            m.add(swell_tone(f, e["dur"]), e["t0"], gain=0.008 * e["amp"] / 0.3, pan=pan, hall=1.4)

    # --- the lure: a thin ringing that grows as the light does and stops when it goes out
    n0 = int((38.9 - 29.2) * SR)
    tl = 29.2 + np.arange(n0) / SR
    ring = np.sin(2 * np.pi * 1661.22 * tl) + np.sin(2 * np.pi * 1668.0 * tl)
    e = curve([(29.2, 0), (31.0, 0.5), (33.5, 0.8), (38.45, 1.0), (38.85, 0)], tl) * (1 + 0.2 * np.sin(2 * np.pi * 0.9 * tl))
    m.add(ring * e, 29.2, gain=0.0045, pan=-0.3, hall=1.2)

    # --- the far glow: it sings faintly, then the voices drop out
    n0 = int((TL.T_GLOW1 - TL.T_GLOW0) * SR)
    tl = TL.T_GLOW0 + np.arange(n0) / SR
    sh = np.zeros(n0)
    for f, off in ((1244.51, 0.35), (1760.0, 0.7), (2217.46, 1.0)):
        t_off = TL.T_GLOW1 - 1.15 + off
        env = smooth((tl - TL.T_GLOW0) / 1.3) * (1 - smooth((tl - (t_off - 0.12)) / 0.12))
        sh += np.sin(2 * np.pi * f * tl + rng.random() * 6.28) * env * (1 + 0.35 * np.sin(2 * np.pi * rng.uniform(2.5, 5.0) * tl))
    m.add(sh, TL.T_GLOW0, gain=0.0085, pan=0.35, hall=1.6)

    # --- heartbeat, speeding up
    tb, i = 52.6, 0
    while tb < 59.15:
        k = (tb - 52.6) / (59.15 - 52.6)
        g = 0.11 + 0.24 * k
        m.add(thump(), tb, gain=g, deep=0.15)
        m.add(thump(58, 40), tb + 0.27, gain=g * 0.6, deep=0.15)
        tb += 1.10 - 0.30 * k
        i += 1

    # --- narration
    vo_len = []
    for si in range(6):
        x = voice_chain(load_vo(si + 1))
        vo_len.append(len(x) / SR)
        v.add(x, TL.VO[si], gain=1.0, hall=0.085)
    vo = v.dry + reverb(v.hall, make_ir(0.30, 3800, 2.4, 5, 0.025))

    # --- space
    fx = m.dry + reverb(m.hall, make_ir(0.42, 5000, 3.5, 3)) * 0.9 + reverb(m.deep, make_ir(1.0, 1400, 7.5, 4, 0.04)) * 0.9

    # --- music and effects step back a little while the voice speaks
    ve = block_env(vo[:, 0], 0.05, 0.01)
    duck = lp(np.clip(ve / 0.03, 0, 1), 3.0, 1)
    duck = np.clip(duck, 0, 1)
    fx *= (1 - 0.42 * duck)[:, None]

    mix = (fx + vo)[:N]
    f_out = int(0.5 * SR)
    mix[-f_out:] *= np.cos(np.linspace(0, np.pi / 2, f_out))[:, None] ** 2
    for name, st in (("fx", fx[:N]), ("vo", vo[:N])):
        print("%-3s rms %.1f dBFS  peak %.1f dBFS" % (name, rms_db(st), 20 * math.log10(np.abs(st).max() + 1e-9)))
        if stems:
            wavfile.write(os.path.join(HERE, "audio", "stem_%s.wav" % name), SR, st.astype(np.float32))
    print("per 4 s (fx / vo, dBFS):")
    for a in range(0, int(END), 4):
        s = slice(a * SR, min(N, (a + 4) * SR))
        print("  %2d-%2d  %6.1f  %6.1f" % (a, a + 4, rms_db(fx[s]), rms_db(vo[s])))
    return mix


def lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    summ = r[r.rindex("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1))
    return i, tp


def limit(x, ceil=0.89):
    """Look-ahead peak limiter (5 ms), stereo-linked."""
    pk = np.abs(x).max(1)
    la = int(0.005 * SR)
    need = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    from scipy.ndimage import minimum_filter1d
    g = minimum_filter1d(need, 2 * la + 1)
    g = np.minimum(g, lp(g, 1.3, 1))
    g = minimum_filter1d(g, la)
    return x * g[:, None]


def main():
    os.makedirs(os.path.join(HERE, "audio"), exist_ok=True)
    mix = build("--stems" in sys.argv)
    tmp = os.path.join(HERE, "audio", "premaster.wav")
    out = os.path.join(HERE, "audio", "mix.wav")
    wavfile.write(tmp, SR, mix.astype(np.float32))
    i0, tp0 = lufs(tmp)
    gain = 10 ** ((-14.0 - i0) / 20)
    mix = limit(mix * gain)
    wavfile.write(out, SR, mix.astype(np.float32))
    i1, tp1 = lufs(out)
    if abs(i1 + 14.0) > 0.4:                 # the limiter took a little loudness back: one correction pass
        mix = limit(mix * 10 ** ((-14.0 - i1) / 20))
        wavfile.write(out, SR, mix.astype(np.float32))
        i1, tp1 = lufs(out)
    os.remove(tmp)
    print("premaster %.1f LUFS (peak %.1f) -> gain %.1f dB -> %.1f LUFS, true peak %.1f dBFS, %.2f s"
          % (i0, tp0, 20 * math.log10(gain), i1, tp1, len(mix) / SR))


if __name__ == "__main__":
    main()
