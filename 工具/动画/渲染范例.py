"""离线重渲染已采用动画的独立参考。所有路径相对新工作室根目录。

python 工具/动画/渲染范例.py --config 工具/动画/配置/星月_转身找金星_8秒.json
只调用本地字体、数据及 FFmpeg；不调用生成式 API，不接触旧项目。
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, platform, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import PIL
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[2]
ENGINES={'sky':'星月范例.py','calendar':'日期范例.py','exposure':'曝光范例.py','radar':'雷达范例.py','convergence':'汇聚范例.py'}

def resolve(value):
    p=Path(value)
    if p.is_absolute():raise ValueError('配置只能使用项目内相对路径')
    result=(ROOT/p).resolve()
    if not result.is_relative_to(ROOT):raise ValueError('路径不能离开新工作室')
    return result

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def load_engine(name):
    p=Path(__file__).parent/ENGINES[name]
    spec=importlib.util.spec_from_file_location('studio_reference_'+name,p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m,p

def render(config_path):
    p=resolve(config_path);cfg=json.loads(p.read_text(encoding='utf-8'))
    assert cfg['schema_version']==1 and cfg['mode']=='historical_reference_only', '历史复现配置必须明确标识'
    fps=cfg['fps'];w,h=cfg['size']
    assert fps==25 and w>0 and h>0 and w%2==0 and h%2==0
    for name,expected in cfg.get('input_sha256',{}).items():
        assert digest(resolve(name))==expected, f'历史数据被改动，需为新题另外编写并核验渲染逻辑：{name}'
    kind=cfg['case'];engine,engine_path=load_engine(kind)
    target=resolve(cfg['output']);target.parent.mkdir(parents=True,exist_ok=True)
    working=target.with_name(target.stem+'_处理中.mp4')
    writer=imageio_ffmpeg.write_frames(str(working),(w,h),fps=fps,codec='libx264',quality=None,macro_block_size=1,pix_fmt_out='yuv420p',
        ffmpeg_log_level='warning',output_params=['-crf','18','-preset','fast','-movflags','+faststart'])
    writer.send(None);total=0;segments=[]
    try:
        for shot in cfg['shots']:
            duration=float(shot['duration']);count=round(duration*fps)
            assert abs(count/fps-duration)<1e-8 and count>1
            segments.append({'phase':shot.get('phase',kind),'start_frame':total,'frames':count})
            for i in range(count):
                q=i/(count-1);t=i/fps;captions=cfg.get('captions',False)
                if kind in ['sky','exposure']:im=engine.frame(phase=shot['phase'],p=q,captions=captions)
                elif kind=='calendar':im=engine.frame(shot['phase'],q,captions=captions)
                elif kind=='radar':
                    knots=shot['progress_knots'];at=float(np.interp(t,[x[0] for x in knots],[x[1] for x in knots]))
                    im=engine.frame(at,captions=captions)
                elif kind=='convergence':im=engine.frame(shot['phase'],t,duration,clock=total/fps)
                if im.size!=(w,h):im=im.resize((w,h),Image.Resampling.LANCZOS)
                writer.send(np.asarray(im.convert('RGB')));total+=1
            print('RENDERED',shot.get('phase',kind),count,'frames',flush=True)
    finally:writer.close()
    reader=imageio_ffmpeg.read_frames(str(working),pix_fmt='rgb24')
    metadata=next(reader);assert tuple(metadata['size'])==(w,h)
    samples=sorted(set(round((total-1)*f) for f in [0,.2,.4,.6,.8,1]))
    decoded=0;stills=[];check=target.parent/(target.stem+'_检查');check.mkdir(exist_ok=True)
    for raw in reader:
        if decoded in samples:
            im=Image.frombytes('RGB',(w,h),raw);name=f'实际解码_{decoded:04d}.png';im.save(check/name);stills.append((decoded,im))
        decoded+=1
    assert decoded==total, (decoded,total)
    working.replace(target)
    tw,th=480,270;sheet=Image.new('RGB',(tw*3,(th+30)*2),(9,15,24));d=ImageDraw.Draw(sheet)
    f=ImageFont.truetype(str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Regular.otf'),16)
    for j,(i,im) in enumerate(stills):
        x=(j%3)*tw;y=(j//3)*(th+30);sheet.paste(im.resize((tw,th),Image.Resampling.LANCZOS),(x,y));d.text((x+12,y+th+3),f'{i/fps:.2f} s / frame {i}',font=f,fill=(225,232,239))
    sheet.save(check/'实际解码联系表.jpg',quality=94)
    report={'status':'full_decode_passed_visual_review_pending','date_local':'2026-10-26','video':str(target.relative_to(ROOT)),
        'video_sha256':digest(target),'engine':str(engine_path.relative_to(ROOT)),'engine_sha256':digest(engine_path),
        'config':str(p.relative_to(ROOT)),'config_sha256':digest(p),'frames':total,'decoded_frames':decoded,'fps':fps,'duration_seconds':total/fps,
        'size':[w,h],'audio':False,'segments':segments,'sample_frames':samples,
        'runtime':{'python':platform.python_version(),'numpy':np.__version__,'Pillow':PIL.__version__,'imageio_ffmpeg':imageio_ffmpeg.__version__},
        'paid_api_calls':0,'network_calls':0,'old_project_runtime_dependencies':0,'scope':'历史案例离线复现，非新题事实论证'}
    (check/'核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return target

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);args=ap.parse_args();render(args.config)
