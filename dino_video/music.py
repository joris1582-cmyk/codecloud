import json, numpy as np, subprocess, wave
SR = 44100
T = json.load(open('timing.json'))
rng = np.random.default_rng(3)
def note(f, dur, amp=1.0):
    t = np.arange(int(dur * SR)) / SR
    w = (np.sin(2*np.pi*f*t) + 0.35*np.sin(2*np.pi*f*2.003*t) + 0.15*np.sin(2*np.pi*f*3.01*t))
    env = np.minimum(1, t/1.2) * np.minimum(1, (dur - t)/1.2)
    return w * env * amp
def chord(freqs, dur):
    return sum(note(f, dur, 0.25) for f in freqs)
# moods: minor progression (Am F C G) / tense (Dm Bb A) / hopeful (C G Am F)
A=[220.0,261.63,329.63]; F=[174.61,220.0,261.63]; C=[196.0,261.63,329.63]; G=[196.0,246.94,293.66]
Dm=[146.83,174.61,220.0]; Bb=[116.54,146.83,174.61]; Am_low=[110.0,130.81,164.81]; E=[164.81,207.65,246.94]
MOOD = {1:[A,F,C,G], 2:[Dm,Bb,Dm,E], 3:[Dm,Bb,F,E], 4:[A,F,Dm,E], 5:[Dm,Bb,C,A], 6:[C,G,A,F]}
PULSE = {1:0.5, 2:0.8, 3:1.0, 4:0.6, 5:1.0, 6:0.0}
for p in range(1,7):
    dur = T[p-1]['duration']; n = int(dur*SR)
    out = np.zeros(n + SR*5)
    step = 4.0; i = 0; t0 = 0.0
    while t0 < dur:
        ch = MOOD[p][i % 4]
        seg = chord(ch, step + 1.5) + note(ch[0]/2, step+1.5, 0.3)
        a = int(t0*SR); out[a:a+len(seg)] += seg[:len(out)-a]
        t0 += step; i += 1
    # heartbeat pulse
    if PULSE[p]:
        bpm = 72 if p != 3 and p != 5 else 96
        beat = 60/bpm; t = 0.5
        kt = np.arange(int(0.35*SR))/SR
        kick = np.sin(2*np.pi*(55*np.exp(-kt*8))*kt*6) * np.exp(-kt*9)
        while t < dur:
            for off, amp in [(0, 1.0), (0.22, 0.6)]:
                a = int((t+off)*SR); out[a:a+len(kick)] += kick[:len(out)-a] * 0.55 * PULSE[p]
            t += beat
    out = out[:n]
    # lowpass-ish smoothing + fade
    k = np.ones(8)/8; out = np.convolve(out, k, mode='same')
    fade = np.ones(n); f = int(1.0*SR); fade[:f] = np.linspace(0,1,f); fade[-f:] = np.linspace(1,0,f)
    out = out * fade
    out = out / (np.abs(out).max() + 1e-9) * 0.9
    pcm = (out * 32767).astype(np.int16)
    with wave.open(f'audio/music_p{p}.wav','wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    # mix: voice + music at -19 dB, ducked under voice
    subprocess.run(['ffmpeg','-y','-v','error','-i',f'audio/voice_p{p}.wav','-i',f'audio/music_p{p}.wav','-filter_complex',
        '[1]volume=0.16[m];[0]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=400[md];'
        '[v][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[o]','-map','[o]','-ar','44100','-ac','2',
        f'audio/mix_p{p}.wav'],check=True)
    print('mixed',p)
