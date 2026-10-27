"""照片、长曝光与雷达调查的实际时间线合成；仅本地渲染，无生成 API。

timeline.json uses shots with id/start/end/kind. Supported kinds:
evidence: asset in 素材接线.json; source pixels remain fixed, no new labels.
exposure: phase, p_range or progress_knots=[local seconds, normalized progress].
radar: t_range or progress_knots=[local seconds, component seconds].
geometry: same component seconds, or phase with normalized progress knots.
video: source_id in 检查/生成素材清单.json, source_in, normal speed only.

--only ID... renders only those shots; --assemble only joins existing shot files;
--frames-only saves composition check frames. None modifies timeline or narration.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import imageio_ffmpeg
import numpy as np
from PIL import Image,ImageDraw,ImageFont

BASE=Path(__file__).resolve().parents[1]
CACHE=BASE/'缓存';OUT=BASE/'导出';CHECK=BASE/'检查'
W,H,FPS=1920,1080,25
FF=imageio_ffmpeg.get_ffmpeg_exe()
KINDS={'evidence','video','exposure','radar','geometry'}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_text(path,content,encoding='utf-8'):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    temp.write_text(content,encoding=encoding);temp.replace(path)


def resolve(path):
    path=Path(path)
    return path if path.is_absolute() else BASE/path


@lru_cache(maxsize=3)
def component(kind):
    filename={'exposure':'制作长曝光动画.py','radar':'制作雷达动作.py','geometry':'制作几何推演.py'}[kind]
    path=BASE/'工具'/filename
    spec=importlib.util.spec_from_file_location('photo_radar_'+kind,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def assets():
    entries=read(BASE/'素材接线.json')['assets'];result={}
    for asset,value in entries.items():
        result[asset]=resolve(value['path'] if isinstance(value,dict) else value)
    return result


@lru_cache(maxsize=1)
def videos():
    manifest=read(CHECK/'生成素材清单.json')
    if isinstance(manifest,dict):manifest=manifest.get('videos',manifest.get('assets',[]))
    return {row['id']:{**row,'path':resolve(row['path'])} for row in manifest}


@lru_cache(maxsize=32)
def evidence_image(path):
    im=Image.open(path).convert('RGB')
    if im.size!=(W,H):raise ValueError(f'证据图必须是固定的1920×1080编排图：{path}，实际{im.size}')
    return im


def normalized_progress(shot,t):
    duration=shot['end']-shot['start'];p=min(1,max(0,t/max(1/FPS,duration-1/FPS)))
    lo,hi=shot.get('p_range',[0,1])
    return float(lo+(hi-lo)*p)


def knots_value(shot,t):
    knots=shot['progress_knots']
    return float(np.interp(t,[k[0] for k in knots],[k[1] for k in knots]))


def component_time(shot,t):
    if 'progress_knots' in shot:return knots_value(shot,t)
    if 't_range' in shot:
        lo,hi=shot['t_range'];p=normalized_progress(shot,t)
        return float(lo+(hi-lo)*p)
    return float(shot.get('source_t',0)+t)


def frame(shot,t):
    kind=shot['kind']
    if kind=='evidence':
        # Evidence composites already contain their source footer and markup.
        # Return unchanged pixels: no pan, zoom, jitter or duplicate long label.
        return evidence_image(str(assets()[shot['asset']])).copy()
    if kind=='exposure':
        p=knots_value(shot,t) if 'progress_knots' in shot else normalized_progress(shot,t)
        return component('exposure').frame(phase=shot['phase'],p=p,captions=False)
    if kind=='radar':return component('radar').frame(component_time(shot,t),captions=False).convert('RGB')
    if kind=='geometry':
        if 'phase' in shot:
            p=knots_value(shot,t) if 'progress_knots' in shot else normalized_progress(shot,t)
            return component('geometry').frame(phase=shot['phase'],p=p,captions=False)
        return component('geometry').frame(t=component_time(shot,t),captions=False)
    raise ValueError(f'不能直接取帧的镜头种类：{kind}')


def ass_time(t):
    cs=round(t*100);h,cs=divmod(cs,360000);m,cs=divmod(cs,6000);s,cs=divmod(cs,100)
    return f'{h}:{m:02}:{s:02}.{cs:02}'


def srt_time(t):
    ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def subtitles(timeline):
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
    for i,sub in enumerate(timeline['subtitles'],1):
        caption=sub['text'].rstrip('，。').replace('\n',r'\N')
        rows.append(f"Dialogue: 0,{ass_time(sub['start'])},{ass_time(sub['end'])},Default,,0,0,0,,{caption}")
        srt.append(f"{i}\n{srt_time(sub['start'])} --> {srt_time(sub['end'])}\n{sub['text']}")
    ass=OUT/'照片与雷达调查_字幕.ass'
    atomic_text(ass,header+'\n'.join(rows)+'\n','utf-8-sig')
    atomic_text(OUT/'照片与雷达调查_字幕.srt','\n\n'.join(srt)+'\n')
    return ass


def run(args,log):
    with Path(log).open('w',encoding='utf-8') as stream:
        result=subprocess.run([FF,'-y','-hide_banner',*[str(a) for a in args]],stdout=stream,stderr=stream)
    if result.returncode:raise RuntimeError(f'FFmpeg失败，见 {log}')


@lru_cache(maxsize=64)
def sha256_file(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(shot):
    payload=json.dumps(shot,ensure_ascii=False,sort_keys=True).encode('utf-8')+Path(__file__).read_bytes()
    if shot['kind']=='evidence':payload+=bytes.fromhex(sha256_file(str(assets()[shot['asset']])))
    elif shot['kind']=='video':payload+=bytes.fromhex(sha256_file(str(videos()[shot['source_id']]['path'])))
    elif shot['kind']=='exposure':payload+=(BASE/'工具/制作长曝光动画.py').read_bytes()
    elif shot['kind']=='radar':payload+=(BASE/'工具/制作雷达动作.py').read_bytes()
    elif shot['kind']=='geometry':payload+=(BASE/'工具/制作几何推演.py').read_bytes()
    return hashlib.sha256(payload).hexdigest()


def validate_timeline(timeline):
    if timeline.get('fps',FPS)!=FPS:raise ValueError('本环固定25fps')
    if timeline.get('width',W)!=W or timeline.get('height',H)!=H:raise ValueError('本环固定1920×1080')
    ids=set();sources=set();end=0.
    for shot in timeline['shots']:
        sid=shot['id'];kind=shot['kind'];duration=shot['end']-shot['start']
        if not re.fullmatch(r'[A-Za-z0-9_-]+',sid) or sid in ids:raise ValueError(f'重复或不安全镜号：{sid}')
        ids.add(sid)
        if kind not in KINDS:raise ValueError(f'未知镜头类型：{kind}')
        if duration<=0 or abs(shot['start']-end)>1e-6:raise ValueError(f'镜头时间有空洞、重叠或非正时长：{sid}')
        if abs(round(duration*FPS)-duration*FPS)>1e-5:raise ValueError(f'镜头时长未对齐25fps：{sid}')
        end=shot['end']
        if kind=='video':
            if float(shot.get('speed',1))!=1:raise ValueError(f'AI视频不能变速：{sid}')
            if shot['source_id'] in sources:raise ValueError(f'AI源片段重复使用：{shot["source_id"]}')
            sources.add(shot['source_id'])
        if 'progress_knots' in shot:
            knots=shot['progress_knots']
            if not knots or any(b[0]<=a[0] for a,b in zip(knots,knots[1:])):raise ValueError(f'动作节点时间未递增：{sid}')
    if abs(end-timeline['duration'])>1e-6:raise ValueError('镜头总长与duration不一致')


def validate_video(shot,path):
    import av
    with av.open(str(path)) as container:
        stream=container.streams.video[0]
        available=float(stream.duration*stream.time_base) if stream.duration is not None else container.duration/1_000_000
    requested=shot.get('source_in',0)+shot['end']-shot['start']
    if requested>available+1/FPS:raise ValueError(f'{shot["id"]}所需{requested:.3f}秒超过源视频{available:.3f}秒，不能定帧补长')


def render_one(shot,target):
    count=round((shot['end']-shot['start'])*FPS)
    if shot['kind']=='video':
        source=videos()[shot['source_id']]['path'];validate_video(shot,source)
        # Constant title comes from a text file, avoiding quoting arbitrary strings
        # into the filter graph; subprocess receives an argument list, not a shell.
        label=CACHE/(shot['id']+'_情境标签.txt')
        atomic_text(label,shot.get('label') or '情境示意')
        labelpath=label.resolve().as_posix().replace(':',r'\:').replace("'",r"\'")
        vf=("fps=25,scale=1920:1080,setsar=1,drawtext=fontfile='C\\:/Windows/Fonts/msyh.ttc':"
            f"textfile='{labelpath}':fontsize=27:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10:x=45:y=36")
        run(['-ss',shot.get('source_in',0),'-i',source,'-an','-vf',vf,'-frames:v',count,
             '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
             '-video_track_timescale','12800','-movflags','+faststart',target],CACHE/(shot['id']+'.log'))
        return
    cmd=[FF,'-y','-hide_banner','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
         '-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',
         '-video_track_timescale','12800','-movflags','+faststart',str(target)]
    with (CACHE/(shot['id']+'.log')).open('w',encoding='utf-8') as stream:
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=stream,stderr=stream)
        try:
            for i in range(count):
                im=frame(shot,i/FPS)
                if im.size!=(W,H) or im.mode!='RGB':raise ValueError(f'组件输出格式错误：{shot["id"]}')
                proc.stdin.write(im.tobytes())
            proc.stdin.close()
            if proc.wait():raise RuntimeError(f'{shot["id"]}编码失败')
        finally:
            if proc.poll() is None:proc.terminate()


def assemble(timeline,ass,paths):
    for path in paths:
        if not path.exists():raise FileNotFoundError(f'尚未渲染：{path}')
    concat=CACHE/'concat.txt'
    atomic_text(concat,'\n'.join("file '"+p.resolve().as_posix().replace("'","'\\''")+"'" for p in paths)+'\n')
    raw=CACHE/'照片雷达_无字幕.mp4'
    run(['-f','concat','-safe','0','-i',concat,'-c','copy',raw],CACHE/'拼接.log')
    assfilter=ass.resolve().as_posix().replace(':',r'\:').replace("'",r"\'")
    out=OUT/'照片与雷达调查_无BGM_1080p.mp4'
    run(['-i',raw,'-i',resolve(timeline['audio']),'-vf',f"ass='{assfilter}'",'-map','0:v:0','-map','1:a:0',
         '-t',timeline['duration'],'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
         '-c:a','aac','-b:a','256k','-movflags','+faststart',out],CACHE/'封装.log')
    print('ASSEMBLED',out,flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--only',nargs='+');ap.add_argument('--assemble',action='store_true')
    ap.add_argument('--frames-only',action='store_true');args=ap.parse_args()
    if args.assemble and (args.only or args.frames_only):ap.error('--assemble不可与--only或--frames-only并用')
    for folder in [CACHE,OUT,CHECK]:folder.mkdir(parents=True,exist_ok=True)
    timeline=read(BASE/'timeline.json');validate_timeline(timeline)
    if args.only:
        missing=set(args.only)-{s['id'] for s in timeline['shots']}
        if missing:ap.error('不存在镜号：'+','.join(sorted(missing)))
    ass=subtitles(timeline);paths=[]
    for shot in timeline['shots']:
        target=CACHE/(shot['id']+'.mp4');paths.append(target)
        if args.assemble:continue
        if args.only and shot['id'] not in args.only:continue
        if shot['kind']!='video':
            frame(shot,(shot['end']-shot['start'])*.6).save(CHECK/(shot['id']+'_合成前.png'))
        if args.frames_only:continue
        signature=fingerprint(shot);stamp=target.with_suffix('.stamp')
        if target.exists() and stamp.exists() and stamp.read_text()==signature:continue
        print('RENDER',shot['id'],round(shot['end']-shot['start'],2),flush=True)
        render_one(shot,target);atomic_text(stamp,signature)
    if args.only or args.frames_only:return
    assemble(timeline,ass,paths)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
