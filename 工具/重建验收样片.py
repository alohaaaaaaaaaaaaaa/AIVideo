"""Rebuild the local reference demo without any paid service or old project input."""
from pathlib import Path
from datetime import datetime
import argparse, json, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
DEMO=ROOT/'参考库/全流程验收样片'

def run(*args):
    subprocess.run([sys.executable,str(ROOT/'工具/studio.py'),*args],cwd=ROOT,check=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reuse-animation',action='store_true',help='Reuse a previously validated local animation')
    a=ap.parse_args()
    base='参考库/全流程验收样片/'
    existing=[DEMO/name for name in ['编排','混音'] if (DEMO/name).exists()]
    if existing:
        archive=DEMO/'历史'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        archive.mkdir(parents=True)
        for old in existing:old.rename(archive/old.name)
    run('assemble','--paragraphs',base+'输入/paragraphs.json','--layout',base+'输入/layout.json','--output',base+'编排')
    if not a.reuse_animation:
        run('animation','--config',base+'输入/animation.json')
    run('audio','--timeline',base+'编排/timeline.json','--narration',base+'编排/narration_48k_mono.wav','--output',base+'混音')
    t=json.loads((DEMO/'编排/timeline.json').read_text())
    sources=[('输入/船票评论_真实采用画面.png','image'),('输入/星月转身_8秒.mp4','animation'),('输入/片尾啊子牙.png','image')]
    shots=[]
    for i,((path,kind),seg) in enumerate(zip(sources,t['segments'],strict=True)):
        shots.append({'id':f'DEMO_{i+1:03d}','path':path,'kind':kind,'native_label':True,
                      'duration':round(seg['end']-seg['start'],8)})
    shots[0]['native_label']=False
    shots[0]['source_note']='来源：天涯社区原帖归档，第12页；回复日期：2010-07-11'
    shots[0]['source_note_safe_area']=True
    shots[0]['layout']={'mode':'fullframe'}
    shots[1]['watermark_position']=[1664,880]
    m={'schema_version':1,'title':'啊子牙视频工作室 · 19秒工程演示（非叙事质量样片）','width':1920,'height':1080,'fps':25,
       'output_dir':'导出','shots':shots,'audio':{'path':'混音/mix_48k_stereo.wav'},
       'subtitles':[{'start':p['start'],'end':p['end'],'text':p['text']} for p in t['subtitles']],
       'chapters':[{'start':c['start'],'title':c['title']} for c in t['chapters']],
       'subtitle_style':{'profile':'main'},
       'watermark':{'path':'../品牌/B站/透明PNG/啊子牙_悠哉_B站无账号_1080p.png','width':224,'x':1664,'y':40,'opacity':1},
       'versions':[{'id':'bili','label':'B站水印版','watermark':True},{'id':'clean','label':'无个人水印版','watermark':False}]}
    manifest=DEMO/'manifest.json';manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    run('render','all',str(manifest))

if __name__=='__main__':main()
