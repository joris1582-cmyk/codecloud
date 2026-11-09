"""Prepend a 2.5 s cold-open hook to a rendered vertical part.

Run from the project directory (dino_video or sea_video):
  python3 ../dino_video/hook.py <project:dino|sea> <part> "<cue phrase>" <offset_s> "<HOOK TEXT>" <in.mp4> <out.mp4>

The hook re-renders the scene at the cue (without captions), overlays big hook text,
uses the part's music bed plus a low impact hit, then concatenates the original part.
"""
import sys, os, math, subprocess, wave, re
import numpy as np
from PIL import Image, ImageDraw

project, part, phrase, offset, text, src, dst = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4]), sys.argv[5], sys.argv[6], sys.argv[7]
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
if project == "sea":
    sys.path.insert(0, os.getcwd())
    import sea_render  # noqa: F401  (installs sea scenes into render)
import render as R

HOOK = 2.5
FPS = R.FPS
W, H = 1080, 1920
SR = 44100

words = R.TIMING[part - 1]["words"]
norm = [R.norm(w["w"]) for w in words]
ph = [R.norm(x) for x in phrase.split()]
idx = next(i for i in range(len(norm)) if norm[i:i + len(ph)] == ph)
t0 = max(0.4, words[idx]["t0"] + offset)
sched = R.scene_schedule(part)


def overlay(img, k, tt):
    d = ImageDraw.Draw(img)
    lines = text.split("|")
    size = int(W * 0.105)
    f = R.font(R.FONT_BLACK, size)
    while max(d.textlength(l, font=f) for l in lines) > W * 0.9:
        size -= 4; f = R.font(R.FONT_BLACK, size)
    y = H * 0.62 - len(lines) * size * 0.6
    pop = min(1.0, k / 0.12)
    for i, l in enumerate(lines):
        col = R.HL_COLOR[0] if i == len(lines) - 1 else (255, 255, 255)
        tw = d.textlength(l, font=f)
        jitter = math.sin(tt * 40 + i) * 3
        d.text(((W - tw) / 2 + jitter, y + i * size * 1.15 + (1 - pop) * 40), l, font=f, fill=col,
               stroke_width=max(6, size // 8), stroke_fill=(0, 0, 0))


tmp_v = dst + ".hook_v.mp4"
p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                      "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", tmp_v],
                     stdin=subprocess.PIPE)
n = int(HOOK * FPS)
for i in range(n):
    tt = t0 + i / FPS
    img = R.render_frame(part, tt, W, H, "vertical", sched, [])
    k = i / FPS
    # punch-in zoom + flash at start
    z = 1.08 + 0.06 * (k / HOOK)
    cw, ch = W / z, H / z
    img = img.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))
    if k < 0.12:
        img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), 0.6 * (1 - k / 0.12))
    overlay(img, k, tt)
    p.stdin.write(img.tobytes())
p.stdin.close(); p.wait()

# audio: music bed at the same moment + low impact hit
music = f"audio/music_p{part}.wav"
tmp_a = dst + ".hook_a.wav"
mb = np.zeros(int(HOOK * SR))
if os.path.exists(music):
    with wave.open(music) as w:
        sr = w.getframerate(); w.setpos(min(int(t0 * sr), w.getnframes() - 1))
        raw = np.frombuffer(w.readframes(int(HOOK * sr)), dtype=np.int16).astype(float) / 32767
        if w.getnchannels() == 2: raw = raw[::2]
    mb[:len(raw)] = raw[:len(mb)] * 0.5
kt = np.arange(int(1.2 * SR)) / SR
hit = (np.sin(2 * np.pi * (70 * np.exp(-kt * 3)) * kt * 4) * np.exp(-kt * 3.5) * 0.9 +
       np.random.default_rng(1).standard_normal(len(kt)) * np.exp(-kt * 18) * 0.25)
mb[:len(hit)] += hit
mb = mb / (np.abs(mb).max() + 1e-9) * 0.9
with wave.open(tmp_a, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mb * 32767).astype(np.int16).tobytes())

subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp_v, "-i", tmp_a, "-i", src, "-filter_complex",
                "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,loudnorm=I=-14:TP=-1.5[ha];"
                "[2:a]aformat=sample_rates=44100:channel_layouts=stereo[ma];"
                "[0:v][ha][2:v][ma]concat=n=2:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst], check=True)
os.remove(tmp_v); os.remove(tmp_a)
print("hooked", dst, "t0=%.2f" % t0)
