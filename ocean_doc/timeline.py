"""Shared timeline for picture (render.py) and sound (sound.py)."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30
END = 62.6

# scene starts (s) as in the brief; the last scene runs to END so the closing line can hold
SC = [0.0, 8.0, 18.0, 28.0, 39.0, 49.0]
# narration clip starts (s)
VO = [0.9, 8.5, 19.2, 29.0, 40.2, 49.4]

# shot boundaries
T_WIPE0, T_WIPE1 = 3.5, 4.6      # camera slips under the surface
T_TRENCH_CUT = 23.6              # cliff wall -> looking down the wall
T_ANGLER_CUT = 34.0              # wide -> close-up
T_SQUID_CUT = 45.0               # wide -> eye
T_GLOW0, T_GLOW1 = 55.3, 58.9    # distant glow appears / is gone
T_BLACK = 59.7                   # picture is black
T_TEXT = 59.95                   # closing line starts to appear

# subtitle cards: number of narration words per card, per scene
CARDS = [
    [4, 2, 4, 3, 3],
    [5, 3, 2, 2, 3],
    [3, 2, 2, 3, 3, 3],
    [2, 4, 5, 4, 3],
    [4, 4, 4, 3],
    [2, 2, 4, 4, 3, 5, 3],
]


# ---- small lights in the dark (shared so that every flash can have its own sound)
BLUE = (0.10, 0.50, 1.00)
CYAN = (0.12, 0.85, 0.80)
# (t0, x, y, amplitude, size, colour): sparks seen during the descent
S2_SPARKS = [(13.25, 0.71, 0.36, 0.30, 0.0050, BLUE), (14.35, 0.24, 0.55, 0.22, 0.0040, CYAN),
             (14.95, 0.60, 0.21, 0.16, 0.0035, BLUE), (15.35, 0.42, 0.44, 0.12, 0.0030, BLUE)]


def rng_emitters(seed, n, t0, t1, boxes, max_dur=2.4, max_rep=3):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        bx = boxes[rng.integers(len(boxes))]
        out.append(dict(x=rng.uniform(bx[0], bx[2]), y=rng.uniform(bx[1], bx[3]), t0=rng.uniform(t0, t1),
                        dur=rng.uniform(0.8, max_dur), kind=("flash" if rng.random() < 0.55 else "pulse"),
                        amp=rng.uniform(0.07, 0.34), sg=rng.uniform(0.0025, 0.008),
                        col=(BLUE if rng.random() < 0.7 else CYAN), rep=int(rng.integers(1, max_rep + 1))))
    return out


# distant animals around the anglerfish: anywhere while the fish is still unseen, then only above and below it
ANGLER_FAR = (rng_emitters(41, 8, 28.2, 29.5, [(0.30, 0.12, 0.92, 0.62)], max_dur=1.1, max_rep=2)
              + rng_emitters(42, 12, 28.4, 34.2, [(0.06, 0.06, 0.94, 0.24), (0.06, 0.78, 0.94, 0.95)]))
CLOSE_FAR = rng_emitters(43, 5, 34.0, 37.8, [(0.55, 0.05, 0.95, 0.20), (0.10, 0.84, 0.90, 0.96)])


def load_script():
    return json.load(open(os.path.join(HERE, "script.json")))


def load_timing():
    return json.load(open(os.path.join(HERE, "timing.json")))


def cards():
    """[(t0, t1, text)] in master time."""
    out = []
    tm = load_timing()
    for si, sc in enumerate(tm):
        words = sc["words"]
        i = 0
        for n in CARDS[si]:
            grp = words[i:i + n]
            i += n
            text = " ".join(w["w"] for w in grp).rstrip(".,")
            out.append([VO[si] + grp[0]["t0"] - 0.04, VO[si] + grp[-1]["t1"] + 0.28, text])
        assert i == len(words), (si, i, len(words))
    for a, b in zip(out, out[1:]):
        if b[0] - a[1] < 0.22:      # no blank flash between back-to-back cards
            a[1] = b[0]
    return [tuple(c) for c in out]


def word_time(scene, word_index, end=False):
    w = load_timing()[scene - 1]["words"][word_index]
    return VO[scene - 1] + (w["t1"] if end else w["t0"])


if __name__ == "__main__":
    for c in cards():
        print("%6.2f %6.2f  %s" % c)
