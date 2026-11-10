#!/usr/bin/env python3
"""Cover image: the anglerfish with the title above it. Writes final/cover.jpg (1080x1920)."""
import os

from PIL import Image

import render as R

R.OPT.update(hud=False, title=False, subs=False)
R.setup(0.5)
T_COVER = 33.6
img = R.frame(int(round(T_COVER * R.FPS))).astype("float32") / 255.0
spr = R.text_sprite([("THE OCEAN IS MORE", "InterDisplay-SemiBold", 0.054 * R.W, 0.010 * R.W),
                     ("TERRIFYING", "InterDisplay-Black", 0.124 * R.W, 0.004 * R.W),
                     ("THAN YOU THINK", "InterDisplay-SemiBold", 0.054 * R.W, 0.010 * R.W)], gap=0.30, shadow=0.9)
R.put(img, spr, R.W / 2, 0.155 * R.H, 1.0)
os.makedirs(os.path.join(R.HERE, "final"), exist_ok=True)
out = os.path.join(R.HERE, "final", "cover.jpg")
Image.fromarray((img * 255 + 0.5).astype("uint8")).save(out, quality=93)
print(out)
