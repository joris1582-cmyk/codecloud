"""Tighten pauses, fit narration to ~60 s, estimate word timings, write voice tracks + timing.json."""
import json, re, subprocess, os
LEAD, TARGET = 0.25, 58.6
story = json.load(open('story.json'))
def dur(f): return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]))
def islands(f):
    out = subprocess.run(['ffmpeg','-i',f,'-af','silencedetect=noise=-38dB:d=0.18','-f','null','-'],capture_output=True,text=True).stderr
    ss=[float(x) for x in re.findall(r'silence_start: ([\d.]+)',out)]; se=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',out)]
    d=dur(f); isl=[]; t=0.0
    for a,b in zip(ss,se+[d]*(len(ss)-len(se))):
        if a>t+0.05: isl.append((t,a))
        t=b
    if t<d-0.05: isl.append((t,d))
    return isl
parts = json.load(open('timing.json')) if os.path.exists('timing.json') else [None]*len(story)
for p in range(1,len(story)+1):
    raw=f'audio/raw_p{p}.mp3'
    if not os.path.exists(raw): continue
    # 1) cap every pause at 0.45 s
    tight=f'audio/tight_p{p}.wav'
    subprocess.run(['ffmpeg','-y','-v','error','-i',raw,'-af',
        'silenceremove=stop_periods=-1:stop_duration=0.45:stop_threshold=-38dB,aresample=44100','-ac','1',tight],check=True)
    d0=dur(tight); tempo=min(1.15,max(0.94,d0/TARGET))
    fit=f'audio/fit_p{p}.wav'
    subprocess.run(['ffmpeg','-y','-v','error','-i',tight,'-af',f'atempo={tempo:.4f}','-ac','1',fit],check=True)
    words=re.sub(r'\[[^\]]*\]',' ',story[p-1]['spoken']).replace('...',' ').split()
    isl=islands(fit); total=sum(b-a for a,b in isl)
    wts=[len(x)+1.5 for x in words]; Wt=sum(wts); acc=0; res=[]
    def mp(s):
        for a,b in isl:
            if s<=b-a: return a+s
            s-=b-a
        return isl[-1][1]
    for w,ww in zip(words,wts):
        s0=acc/Wt*total; acc+=ww; s1=acc/Wt*total
        res.append({'w':w,'t0':LEAD+mp(s0+1e-4),'t1':LEAD+mp(s1-1e-4)})
    d=dur(fit)
    follow=next(x['t0'] for x in res if x['w'].lower().startswith('follow'))
    T=max(LEAD+d+0.3, follow+1.7, 61.0)
    subprocess.run(['ffmpeg','-y','-v','error','-i',fit,'-af',f'adelay={int(LEAD*1000)},apad','-t',f'{T:.3f}','-ar','44100','-ac','1',f'audio/voice_p{p}.wav'],check=True)
    parts[p-1]={'part':p,'duration':T,'words':res}
    print(p,'raw',round(dur(raw),1),'tight',round(d0,1),'tempo',round(tempo,3),'fit',round(d,1),'total',round(T,2),'words',len(res))
json.dump(parts,open('timing.json','w'))
