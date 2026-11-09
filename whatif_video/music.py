"""Synthesize music beds + sound effects for the two what-if videos and mix with the narration."""
import json, re, subprocess, wave
import numpy as np
SR = 44100
T = json.load(open('timing.json'))
rng = np.random.default_rng(11)
norm = lambda w: re.sub(r"[^a-z]", "", w.lower())
def cue(p, phrase):
    ws = T[p-1]['words']; nw = [norm(w['w']) for w in ws]; ph = [norm(x) for x in phrase.split()]
    return next(ws[i]['t0'] for i in range(len(nw)-len(ph)+1) if nw[i:i+len(ph)] == ph)
def add(out, t, sig, g=1.0):
    a = int(t*SR)
    if a < len(out): out[a:a+len(sig)] += sig[:len(out)-a]*g
def smooth(x, n): return np.convolve(x, np.ones(n)/n, 'same')
def note(f, d, amp=1.0, att=0.6):
    t = np.arange(int(d*SR))/SR
    w = np.sin(2*np.pi*f*t)+0.35*np.sin(2*np.pi*f*2.003*t)+0.15*np.sin(2*np.pi*f*3.01*t)
    return w*np.minimum(1, t/att)*np.minimum(1, (d-t)/att)*amp
def pluck(f, d=0.5):
    t = np.arange(int(d*SR))/SR
    return (np.sin(2*np.pi*f*t)+0.4*np.sin(2*np.pi*2*f*t))*np.exp(-t*7)
def whoosh(d=1.6):
    t = np.arange(int(d*SR))/SR
    n = smooth(rng.standard_normal(len(t)), 30)*np.sin(np.pi*t/d)**2
    return n/np.abs(n).max()
def boom(d=1.4, f0=60):
    t = np.arange(int(d*SR))/SR
    return np.sin(2*np.pi*f0*np.exp(-t*2.2)*t*3.5)*np.exp(-t*3)
def ping(f=1150, d=2.2):
    t = np.arange(int(d*SR))/SR
    s = np.sin(2*np.pi*f*t)*np.exp(-t*4.5)
    e = int(0.33*SR); s[e:] += 0.4*s[:-e]; s[2*e:] += 0.16*s[:-2*e]
    return s
def honk(d=0.28):
    t = np.arange(int(d*SR))/SR
    return (np.sign(np.sin(2*np.pi*440*t))+np.sign(np.sin(2*np.pi*554*t)))*0.5*np.minimum(1, (d-t)/0.03)
def write(p, out):
    n = len(out); f = int(0.8*SR); out[:f] *= np.linspace(0, 1, f); out[-f:] *= np.linspace(1, 0, f)
    out = out/(np.abs(out).max()+1e-9)*0.9
    with wave.open(f'audio/music_p{p}.wav', 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out*32767).astype(np.int16).tobytes())
    subprocess.run(['ffmpeg','-y','-v','error','-i',f'audio/voice_p{p}.wav','-i',f'audio/music_p{p}.wav','-filter_complex',
        '[1]volume=0.24[m];[0]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=3:attack=20:release=450[md];'
        '[v][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[o]','-map','[o]','-ar','44100','-ac','2',f'audio/mix_p{p}.wav'],check=True)
    print('mixed', p)

# ---------- video 1: asteroid ----------
dur = T[0]['duration']; out = np.zeros(int(dur*SR))
Am=[220.0,261.63,329.63]; F=[174.61,220.0,261.63]; C=[196.0,261.63,329.63]; G=[196.0,246.94,293.66]; Dm=[146.83,174.61,220.0]; E=[164.81,207.65,246.94]
t_city = cue(1, "Now picture"); t_hum = cue(1, "And humans")
i = 0; t = 0.0
while t < dur:
    prog = [Dm, F, Am, E] if t < cue(1, "The dinosaurs wake") or t >= t_hum else ([C, G, Am, F] if t >= t_city else [Am, F, C, G])
    ch = prog[i % 4]
    add(out, t, sum(note(f, 4.6, 0.22) for f in ch)+note(ch[0]/2, 4.6, 0.3))
    for k in range(8):  # arpeggio pulse
        add(out, t+k*0.5, pluck(ch[k % 3]*2), 0.16)
    t += 4.0; i += 1
kt = np.arange(int(0.3*SR))/SR; kick = np.sin(2*np.pi*52*kt)*np.exp(-kt*11)
for bt in np.arange(0.5, dur, 0.5): add(out, bt, kick, 0.38 if int(bt*2) % 2 == 0 else 0.2)
add(out, 0.05, boom(), 0.9)
add(out, cue(1, "it passes")-0.5, whoosh(1.8), 1.0)
add(out, cue(1, "T-rex stays")+0.1, boom(1.6, 48), 0.9)
for k in range(5): add(out, cue(1, "Rush hour")+0.3+k*0.42, honk(), 0.22 if k % 2 else 0.3)
add(out, cue(1, "We never"), whoosh(1.0), 0.5)
add(out, cue(1, "One rock"), boom(1.2, 55), 0.7)
write(1, out)

# ---------- video 2: deep ocean ----------
dur = T[1]['duration']; n = int(dur*SR); out = np.zeros(n); tt = np.arange(n)/SR
t_hit = cue(2, "You hit"); t_dark = cue(2, "One thousand"); t_bot = cue(2, "The bottom")
deep = np.clip((tt-t_hit)/(t_bot-t_hit), 0, 1)
drone = (0.5*np.sin(2*np.pi*55*tt)+0.3*np.sin(2*np.pi*82.4*tt+np.sin(tt*0.3))+0.22*np.sin(2*np.pi*65.4*tt))*(0.5+0.5*np.sin(2*np.pi*tt/9))
noise = rng.standard_normal(n)
water = smooth(noise, 220)*7*(0.6+0.4*np.sin(2*np.pi*tt/5.5))
out += drone*(0.25+0.6*deep)+water*(0.5-0.25*deep)
pad = [[220.0,261.63,329.63],[174.61,220.0,261.63]]
for j, t in enumerate(np.arange(0, dur, 5.0)): add(out, t, sum(note(f, 6, 0.1, 1.5) for f in pad[j % 2])*(1-0.6*deep[min(n-1, int(t*SR))]))
splash = smooth(rng.standard_normal(int(1.2*SR)), 8)*np.exp(-np.arange(int(1.2*SR))/SR*3.5)
add(out, t_hit+0.75, splash/np.abs(splash).max(), 1.2)
for ph in ["Two hundred", "One thousand", "Three thousand", "Eight thousand", "Nearly eleven"]: add(out, cue(2, ph)-0.05, ping(), 0.5)
hb = np.arange(int(0.3*SR))/SR; beat = np.sin(2*np.pi*46*hb)*np.exp(-hb*12)
for bt in np.arange(cue(2, "Three thousand"), t_bot, 0.86):
    add(out, bt, beat, 0.6); add(out, bt+0.24, beat, 0.35)
add(out, cue(2, "Keep sinking"), whoosh(1.4), 0.5)
add(out, t_bot, boom(1.8, 42), 1.3)
add(out, cue(2, "eight tons"), boom(1.2, 50), 0.7)
add(out, cue(2, "A plastic")-0.1, ping(1700, 1.6), 0.45)
write(2, out)
