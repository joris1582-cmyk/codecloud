import json, numpy as np, subprocess, wave, sys, os
SR=44100
T=json.load(open('timing.json'))
rng=np.random.default_rng(5)
def lowpass(x, k):
    y=np.empty_like(x); a=0.0
    alpha=k
    # one-pole IIR via cumulative trick
    from scipy.signal import lfilter
    return lfilter([alpha],[1,alpha-1],x)
def bellsound(d=4.0, f=196.0):
    t=np.arange(int(d*SR))/SR
    return sum(a*np.sin(2*np.pi*f*m*t)*np.exp(-t*dk) for m,a,dk in [(1,1,0.9),(2.76,0.5,1.4),(5.4,0.25,2.2),(0.5,0.4,0.6)])
for p in range(1,7):
    if not T[p-1] or os.path.exists(f'audio/mix_p{p}.wav') and '--force' not in sys.argv: 
        if T[p-1]: print('skip',p)
        continue
    dur=T[p-1]['duration']; n=int(dur*SR); t=np.arange(n)/SR
    drone=(0.5*np.sin(2*np.pi*55*t)+0.35*np.sin(2*np.pi*55*1.5*t+np.sin(t*0.3))+0.25*np.sin(2*np.pi*65.4*t)
           +0.2*np.sin(2*np.pi*110*1.06*t))*(0.6+0.4*np.sin(2*np.pi*t/9))
    noise=rng.standard_normal(n)
    try:
        sea=lowpass(noise,0.02)*(0.6+0.4*np.sin(2*np.pi*t/6.5))*4
        wind=lowpass(noise[::-1].copy(),0.06)*(0.5+0.5*np.sin(2*np.pi*t/11+1))*2
    except Exception:
        sea=np.convolve(noise,np.ones(200)/200,'same')*6; wind=np.convolve(noise,np.ones(40)/40,'same')*2
    out=drone*0.5+sea*0.35+wind*0.15
    # bell tolls
    for bt in np.arange(3.0, dur-2, 13.0):
        b=bellsound(); a=int(bt*SR); out[a:a+len(b)]+=b[:n-a]*0.35
    if p in (4,5):  # heartbeat
        kt=np.arange(int(0.3*SR))/SR; kick=np.sin(2*np.pi*48*kt)*np.exp(-kt*12)
        for bt in np.arange(1.0,dur,0.8):
            a=int(bt*SR); out[a:a+len(kick)]+=kick[:n-a]*0.7
    f=int(1.0*SR); out[:f]*=np.linspace(0,1,f); out[-f:]*=np.linspace(1,0,f)
    out=out/(np.abs(out).max()+1e-9)*0.9
    with wave.open(f'audio/music_p{p}.wav','wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out*32767).astype(np.int16).tobytes())
    subprocess.run(['ffmpeg','-y','-v','error','-i',f'audio/voice_p{p}.wav','-i',f'audio/music_p{p}.wav','-filter_complex',
        '[1]volume=0.22[m];[0]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=3:attack=20:release=500[md];'
        '[v][md]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[o]','-map','[o]','-ar','44100','-ac','2',f'audio/mix_p{p}.wav'],check=True)
    print('mixed',p)
