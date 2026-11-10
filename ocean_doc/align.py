"""Word-level timing for the six narration clips (forced alignment, local).

Usage: python3 align.py   -> writes timing.json
Needs: pip install pocketsphinx ; ffmpeg
"""
import json, os, re, subprocess, wave, sys
import numpy as np
from pocketsphinx import Decoder

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = json.load(open(os.path.join(HERE, "script.json")))
TMP = os.environ.get("TMPDIR", "/tmp")


def spoken(text):
    t = text.replace("1,000", "one thousand")
    return re.findall(r"[a-z']+", t.lower())


def align(path, words):
    wav = os.path.join(TMP, "align_%d.wav" % os.getpid())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav], check=True)
    with wave.open(wav) as w:
        data = w.readframes(w.getnframes())
    os.remove(wav)
    dec = Decoder(samprate=16000, loglevel="ERROR")
    for w_, ph in (("seafloor", "S IY F L AO R"),):
        if dec.lookup_word(w_) is None:
            dec.add_word(w_, ph, True)
    dec.set_align_text(" ".join(words))
    dec.start_utt(); dec.process_raw(data, full_utt=True); dec.end_utt()
    out = []
    for seg in dec.seg():
        if seg.word.startswith("<") or seg.word == "(NULL)":
            continue
        out.append((re.sub(r"\(\d+\)$", "", seg.word), seg.start_frame / 100.0, (seg.end_frame + 1) / 100.0))
    return out, len(data) / 2 / 16000.0


res = []
for sc in SCRIPT["scenes"]:
    path = os.path.join(HERE, "audio", "vo", "s%d.mp3" % sc["id"])
    disp = sc["narration"].split()
    sp = spoken(sc["narration"])
    segs, dur = align(path, sp)
    assert [s[0] for s in segs] == sp, (sc["id"], [s[0] for s in segs], sp)
    # map spoken tokens back onto display words ("1,000" = "one thousand")
    words, i = [], 0
    for dw in disp:
        n = len(spoken(dw))
        t0, t1 = segs[i][1], segs[i + n - 1][2]
        words.append({"w": dw, "t0": round(t0, 3), "t1": round(t1, 3)})
        i += n
    res.append({"id": sc["id"], "dur": round(dur, 3), "words": words})
    print(sc["id"], "%.2fs" % dur, " ".join("%s[%.2f-%.2f]" % (w["w"], w["t0"], w["t1"]) for w in words))
json.dump(res, open(os.path.join(HERE, "timing.json"), "w"), indent=1)
