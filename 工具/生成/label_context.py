#!/usr/bin/env python3
"""Add one verified contextual label to an unlabeled generated source, before film assembly."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile,shutil
import av,imageio_ffmpeg

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--text',default='情境示意');ap.add_argument('--confirmed-unlabeled',action='store_true',help='Only after actual first/middle/last inspection confirms no existing contextual label');a=ap.parse_args()
 assert a.confirmed_unlabeled,'先检查原片没有情境说明；已有说明直接使用，不叠第二层'
 assert a.input.resolve()!=a.output.resolve() and not a.output.exists(),'保留原片，输出必须是新路径'
 assert not a.input.with_suffix('.context.json').exists(),'输入已经有context制作记录，禁止重复添加'
 assert '\n' not in a.text and len(a.text)<=35 and not any(x in a.text for x in '{}\\'),'说明保持简短，不能包含ASS控制符'
 with av.open(str(a.input)) as c:
  v=c.streams.video[0];w,h=v.width,v.height;duration=float(v.duration*v.time_base);fps=v.average_rate;count=sum(1 for _ in c.decode(v))
 root=Path(__file__).resolve().parents[2];fonts=root/'参考库/动画/字体';font='Noto Sans CJK SC'
 a.output.parent.mkdir(parents=True,exist_ok=True)
 # Copy fonts into an ASCII temporary workspace, without requiring symlink privileges.
 with tempfile.TemporaryDirectory(prefix='aziya-context-') as tmp:
  p=Path(tmp);shutil.copytree(fonts,p/'fonts')
  def timestamp(t):
   n=round(t*100);hh,n=divmod(n,360000);mm,n=divmod(n,6000);ss,n=divmod(n,100);return f'{hh}:{mm:02}:{ss:02}.{n:02}'
  ass=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Context,{font},{round(25*h/1080)},&H20FFFFFF,&H20FFFFFF,&H80101820,&H80101820,0,0,0,0,100,100,0,0,3,5,0,7,{round(32*w/1920)},32,{round(26*h/1080)},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{timestamp(duration)},Context,,0,0,0,,{a.text}
'''
  (p/'context.ass').write_text(ass,encoding='utf-8-sig');partial=a.output.with_name(a.output.stem+'_处理中.mp4')
  with a.output.with_suffix('.log').open('w') as log:
   subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-nostdin','-y','-i',str(a.input.resolve()),'-vf','ass=context.ass:fontsdir=fonts','-map','0:v:0','-map','0:a?','-c:v','libx264','-crf','17','-preset','fast','-threads','2','-c:a','copy','-movflags','+faststart',str(partial.resolve())],cwd=p,stdout=log,stderr=log,check=True)
  with av.open(str(partial)) as c:
   v=c.streams.video[0];assert sum(1 for _ in c.decode(v))==count and abs(float(v.duration*v.time_base)-duration)<.001
  partial.replace(a.output)
 report={'input_sha256':sha(a.input),'output_sha256':sha(a.output),'native_label':True,'label_text':a.text,'label_full_duration':True,'source_frame_count':count,'duration':duration,'source_speed_changed':False,'confirmed_unlabeled_before_add':True,'needs_actual_visual_review':True}
 a.output.with_suffix('.context.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(a.output)
if __name__=='__main__':main()
