"""实际声画时间线驱动的天空/日历动画成片；本地合成、无生成API。"""
from pathlib import Path
from functools import lru_cache
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont

BASE=Path(__file__).resolve().parents[1];SECTION=BASE.parent;PLAN=SECTION.parent
CACHE=BASE/'缓存';OUT=BASE/'导出';CHECK=BASE/'检查'
for p in [CACHE,OUT,CHECK]:p.mkdir(parents=True,exist_ok=True)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


sky=load('action_sky',BASE/'工具/制作天空动画.py')
date=load('action_dates',BASE/'工具/制作日期动画.py')
old=load('evidence_marking',PLAN/'开场样片/风格试片_v2/工具/制作风格试片.py')
FF=old.FFMPEG;FPS=25;W,H=1920,1080
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
ASSETS={}
for manifest in [SECTION/'证据素材/manifest.json',PLAN/'完整开场/真实证据/manifest.json']:
    for a in read(manifest)['assets']:
        ASSETS[a['id']]={**a,'file':str(manifest.parent/a['path'])}
for a in list(ASSETS.values()):
    if a['id'].endswith('_focus'):ASSETS.setdefault(a['id'][:-6],a)
VIDEOS={v['id']:v for v in read(CHECK/'生成素材清单.json')}


@lru_cache(maxsize=24)
def image(path):return Image.open(path).convert('RGB')


def label(im,text):
    im=im.convert('RGBA');layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer)
    f=old.font(24);box=d.textbbox((0,0),text,font=f)
    d.rounded_rectangle((30,24,60+box[2],73),radius=4,fill=(8,14,19,210));d.text((44,33),text,font=f,fill='#f1ead9')
    return Image.alpha_composite(im,layer).convert('RGB')


def progress(shot,t):
    duration=shot['end']-shot['start'];p=min(1,t/max(.04,duration-.04))
    if 'progress_knots' in shot:
        knots=shot['progress_knots'];return float(np.interp(t,[k[0] for k in knots],[k[1] for k in knots]))
    lo,hi=shot.get('p_range',[0,1]);return lo+(hi-lo)*p


def frame(shot,t):
    p=progress(shot,t)
    if shot['kind']=='sky':return sky.frame(phase=shot['phase'],p=p,captions=False).resize((W,H),Image.Resampling.LANCZOS)
    if shot['kind']=='date':return date.frame(shot['phase'],p,width=W,height=H,captions=False)
    if shot['kind']=='evidence':
        a=ASSETS[shot['asset']];im=image(a['file']).copy();actions=[]
        if 'emphasis' in shot:
            for r in a.get('focus_regions',[]):
                if shot['emphasis'] in r['label'] or r['label'] in shot['emphasis']:
                    actions.append({'type':'underline','at':.3,'duration':.65,'box':r['box']})
        im=old.apply_actions(im,{'actions':actions},t)
        return label(im,shot.get('label',a.get('source','')))
    raise ValueError(shot['kind'])


def ass_time(t):
    cs=round(t*100);h,cs=divmod(cs,360000);m,cs=divmod(cs,6000);s,cs=divmod(cs,100);return f'{h}:{m:02}:{s:02}.{cs:02}'


def subtitles(tl):
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,48,&H00F4F1E8,&H000000FF,&H00130E0A,&H900A0C10,0,0,0,0,100,100,1,0,1,2.5,1.1,2,70,70,74,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    rows=[];srt=[]
    for i,s in enumerate(tl['subtitles'],1):
        text=s['text'];text=text.replace('，','，').rstrip('，。')
        rows.append(f"Dialogue: 0,{ass_time(s['start'])},{ass_time(s['end'])},Default,,0,0,0,,{text}")
        def st(t):
            ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);sec,ms=divmod(ms,1000);return f'{h:02}:{m:02}:{sec:02},{ms:03}'
        srt.append(f"{i}\n{st(s['start'])} --> {st(s['end'])}\n{s['text']}")
    ass=OUT/'天空与发射调查_字幕.ass';ass.write_text(header+'\n'.join(rows)+'\n',encoding='utf-8-sig')
    (OUT/'天空与发射调查_字幕.srt').write_text('\n\n'.join(srt)+'\n',encoding='utf-8')
    return ass


def run(args,log):old.run(args,log)


def render_one(s,target):
    duration=s['end']-s['start']
    if s['kind']=='video':
        source=VIDEOS[s['source_id']]['path']
        # Original action at normal speed; 24→25fps duplicates cadence only, no duration stretching.
        vf="fps=25,scale=1920:1080,drawtext=fontfile='C\\:/Windows/Fonts/msyh.ttc':text='情境示意':fontsize=27:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10:x=45:y=36"
        run(['-i',source,'-an','-t',duration,'-vf',vf,'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-video_track_timescale','12800',target],CACHE/(s['id']+'.log'))
        return
    cmd=[FF,'-y','-hide_banner','-f','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r','25','-i','-',
         '-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-video_track_timescale','12800','-movflags','+faststart',str(target)]
    with (CACHE/(s['id']+'.log')).open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log)
        try:
            for i in range(round(duration*FPS)):proc.stdin.write(frame(s,i/FPS).tobytes())
            proc.stdin.close()
            if proc.wait():raise RuntimeError(s['id']+' encoder failed')
        finally:
            if proc.poll() is None:proc.terminate()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--frames-only',action='store_true');ap.add_argument('--only',nargs='*');ap.add_argument('--assemble',action='store_true');args=ap.parse_args()
    tl=read(BASE/'timeline.json');ass=subtitles(tl);paths=[]
    for s in tl['shots']:
        target=CACHE/(s['id']+'.mp4');paths.append(target)
        if args.assemble:continue
        if args.only and s['id'] not in args.only:continue
        if s['kind']!='video':frame(s,(s['end']-s['start'])*.6).save(CHECK/(s['id']+'_合成前.png'))
        if args.frames_only:continue
        fingerprint=hashlib.sha256(json.dumps(s,sort_keys=True).encode()+Path(__file__).read_bytes()+ (BASE/'工具/制作天空动画.py').read_bytes()+(BASE/'工具/制作日期动画.py').read_bytes()).hexdigest()
        if s['kind']=='evidence':fingerprint+=hashlib.sha256(Path(ASSETS[s['asset']]['file']).read_bytes()).hexdigest()
        stamp=target.with_suffix('.stamp')
        if target.exists() and stamp.exists() and stamp.read_text()==fingerprint:continue
        print('RENDER',s['id'],round(s['end']-s['start'],2),flush=True);render_one(s,target);stamp.write_text(fingerprint)
    if args.frames_only or args.only:return
    for path in paths:assert path.exists(),path
    concat=CACHE/'concat.txt';concat.write_text('\n'.join("file '"+str(p.as_posix())+"'" for p in paths),encoding='utf-8')
    raw=CACHE/'天空调查_无字幕.mp4';run(['-f','concat','-safe','0','-i',concat,'-c','copy',raw],CACHE/'拼接.log')
    assfilter=str(ass.as_posix()).replace(':',r'\:')
    out=OUT/'天空与发射调查_无BGM_1080p.mp4'
    run(['-i',raw,'-i',tl['audio'],'-vf',f"ass='{assfilter}'",'-map','0:v:0','-map','1:a:0','-t',tl['duration'],'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-movflags','+faststart',out],CACHE/'封装.log')
    print('ASSEMBLED',out,flush=True)


if __name__=='__main__':main()
