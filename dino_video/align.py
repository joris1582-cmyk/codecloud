import json, re, subprocess
LEAD, GAP, TAIL = 0.5, 0.35, 1.6
chunks = json.load(open('chunks.json'))
titles = ["Part one. The night the mountain woke up.","Part two. Alone in the ash.","Part three. The sky hunter.",
          "Part four. The valley of bones.","Part five. Small horns, big heart.","Part six. The way home."]
def dur(f):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]))
def speech_islands(f):
    out = subprocess.run(['ffmpeg','-i',f,'-af','silencedetect=noise=-35dB:d=0.18','-f','null','-'],capture_output=True,text=True).stderr
    ss=[float(x) for x in re.findall(r'silence_start: ([\d.]+)',out)]
    se=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',out)]
    d=dur(f); isl=[]; t=0.0
    for a,b in zip(ss,se+[d]*(len(ss)-len(se))):
        if a>t+0.05: isl.append((t,a))
        t=b
    if t<d-0.05: isl.append((t,d))
    return isl
def words_of(text):
    text=re.sub(r'\[[^\]]*\]',' ',text)
    return text.split()
def time_words(f, words, offset):
    isl=speech_islands(f)
    total=sum(b-a for a,b in isl)
    w=[len(x)+1.5 for x in words]; W=sum(w)
    res=[]; acc=0.0
    def map_t(s):  # speech-time -> real time
        for a,b in isl:
            if s<=b-a: return a+s
            s-=b-a
        return isl[-1][1]
    for word,ww in zip(words,w):
        s0=acc/W*total; acc+=ww; s1=acc/W*total
        res.append({'w':word,'t0':offset+map_t(s0+1e-4),'t1':offset+map_t(s1-1e-4)})
    return res
parts=[]
for p in range(1,7):
    files=[]; texts=[]
    if p==1: files.append('audio/p1_t.mp3'); texts.append(titles[0])
    for c in chunks:
        if c['part']==p:
            files.append(f"audio/p{p}_{c['idx']}.mp3")
            t=c['text']
            if c['idx']==0 and p>1: t=titles[p-1]+' '+t
            texts.append(t)
    t=LEAD; words=[]; segs=[]
    for f,tx in zip(files,texts):
        d=dur(f); words+=time_words(f,words_of(tx),t); segs.append((f,t)); t+=d+GAP
    total=t-GAP+(TAIL if p<6 else 4.0)
    # build part audio
    inputs=[]; filt=[]
    for i,(f,st) in enumerate(segs):
        inputs+=['-i',f]; filt.append(f"[{i}]adelay={int(st*1000)}|{int(st*1000)},aresample=44100,pan=mono|c0=c0[a{i}]")
    filt.append(''.join(f'[a{i}]' for i in range(len(segs)))+f"amix=inputs={len(segs)}:normalize=0,apad,atrim=0:{total:.3f}[o]")
    subprocess.run(['ffmpeg','-y','-v','error',*inputs,'-filter_complex',';'.join(filt),'-map','[o]','-ar','44100','-ac','1',f'audio/voice_p{p}.wav'],check=True)
    parts.append({'part':p,'duration':total,'words':words})
    print(p, round(total,2), len(words))
json.dump(parts,open('timing.json','w'),indent=0)
print('sum',sum(x['duration'] for x in parts))
