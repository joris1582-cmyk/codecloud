import json, re, subprocess, sys, os
sys.path.insert(0, '../dino_video')
LEAD, TEMPO = 0.6, 0.93
story = json.load(open('story.json'))
def dur(f): return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]))
def islands(f):
    out = subprocess.run(['ffmpeg','-i',f,'-af','silencedetect=noise=-38dB:d=0.2','-f','null','-'],capture_output=True,text=True).stderr
    ss=[float(x) for x in re.findall(r'silence_start: ([\d.]+)',out)]; se=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',out)]
    d=dur(f); isl=[]; t=0.0
    for a,b in zip(ss,se+[d]*(len(ss)-len(se))):
        if a>t+0.05: isl.append((t,a))
        t=b
    if t<d-0.05: isl.append((t,d))
    return isl
parts = json.load(open('timing.json')) if os.path.exists('timing.json') else [None]*6
for p in range(1,7):
    raw=f'audio/raw_p{p}.mp3'
    if not os.path.exists(raw): continue
    slow=f'audio/slow_p{p}.wav'
    subprocess.run(['ffmpeg','-y','-v','error','-i',raw,'-af',f'atempo={TEMPO},aresample=44100','-ac','1',slow],check=True)
    words=[w for w in re.sub(r'\[[^\]]*\]',' ',story[p-1]['spoken']).replace('...',' ').split()]
    isl=islands(slow); total=sum(b-a for a,b in isl)
    wts=[len(x)+1.5 for x in words]; Wt=sum(wts); acc=0; res=[]
    def mp(s):
        for a,b in isl:
            if s<=b-a: return a+s
            s-=b-a
        return isl[-1][1]
    for w,ww in zip(words,wts):
        s0=acc/Wt*total; acc+=ww; s1=acc/Wt*total
        res.append({'w':w,'t0':LEAD+mp(s0+1e-4),'t1':LEAD+mp(s1-1e-4)})
    d=dur(slow); tail = 4.0 if p==6 else 2.2
    T=max(LEAD+d+tail, 61.0)
    subprocess.run(['ffmpeg','-y','-v','error','-i',slow,'-af',f'adelay={int(LEAD*1000)},apad','-t',f'{T:.3f}','-ar','44100','-ac','1',f'audio/voice_p{p}.wav'],check=True)
    parts[p-1]={'part':p,'duration':T,'words':res}
    print(p, round(d,2), round(T,2), len(res))
json.dump(parts,open('timing.json','w'))
