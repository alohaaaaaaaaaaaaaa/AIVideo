#!/usr/bin/env python3
"""Offline synthetic 6-second end-to-end regression, not a visual style template."""
from pathlib import Path
import argparse,json,math,subprocess,sys,wave
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import av,imageio_ffmpeg
from studio_media import Film,save

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(__file__).parent/'离线测试');args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    font_path=Path('/System/Library/Fonts/Hiragino Sans GB.ttc')
    if not font_path.exists():font_path=Path(__file__).resolve().parents[2]/'参考库/动画/字体/NotoSansCJKsc-Regular.otf'
    font=ImageFont.truetype(str(font_path),18)
    for name,label in [('a','素材完整，来源清楚'),('b','我是啊子牙')]:
        im=Image.new('RGB',(640,360),'#102030');ImageDraw.Draw(im).text((50,90),label,font=font,fill='white');im.save(out/f'{name}.png')
    logo=Image.new('RGBA',(100,36));ImageDraw.Draw(logo).text((3,5),'啊子牙',font=font,fill=(240,240,255,180));logo.save(out/'logo.png')
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    p=subprocess.Popen([ff,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','640x360','-r','25','-i','-','-an','-c:v','libx264','-pix_fmt','yuv420p',str(out/'animation.mp4')],stdin=subprocess.PIPE)
    for i in range(50):
        im=Image.new('RGB',(640,360),'#102030');d=ImageDraw.Draw(im);d.text((20,20),'原生说明 · 流程测试',font=font,fill='white');x=100+i*7;d.ellipse((x,150,x+14,164),fill='#76c7ff');p.stdin.write(im.tobytes())
    p.stdin.close();assert p.wait()==0
    sr=48000;t=np.arange(sr*6)/sr;waveform=.05*np.sin(2*np.pi*220*t)*np.minimum(1,t/.1)*np.minimum(1,(6-t)/.1)
    stereo=np.stack([waveform,waveform],axis=1)
    with wave.open(str(out/'mix.wav'),'wb') as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(sr);wav.writeframes((stereo*32767).astype('<i2').tobytes())
    m={'schema_version':1,'title':'离线技术测试（非视觉模板）','fps':25,'width':640,'height':360,'output_dir':'导出',
       'shots':[{'id':'S01','path':'a.png','duration':2,'kind':'image','native_label':False,'source_note':'来源：自制技术测试图','source_note_safe_area':True},
                {'id':'S02','path':'animation.mp4','duration':2,'kind':'animation','native_label':True,'watermark_position':[520,40]},
                {'id':'S03','path':'b.png','duration':2,'kind':'image','native_label':False}],
       'audio':{'path':'mix.wav'},'subtitles':[{'start':.32,'end':1.68,'text':'字幕应可读，不能贴底'},{'start':2.12,'end':3.72,'text':'原生说明不重复添加'},{'start':4.24,'end':5.68,'text':'名字保留，水印可切换'}],
       'chapters':[{'start':0,'title':'来源'},{'start':2,'title':'动画'},{'start':4,'title':'片尾'}],
       'watermark':{'path':'logo.png','width':100,'x':520,'y':20},
       'versions':[{'id':'clean','label':'无水印版','watermark':False},{'id':'bili','label':'B站版','watermark':True}],
       'subtitle_style':{'font':'Hiragino Sans GB' if font_path.suffix=='.ttc' else 'Noto Sans CJK SC','font_size':20,'margin_v':25}}
    save(out/'manifest.json',m);film=Film(out/'manifest.json');film.render();film.verify();film.player()
    def frame(path,n):
        with av.open(str(path)) as c:
            for i,f in enumerate(c.decode(video=0)):
                if i==n:return f.to_ndarray(format='rgb24')
    clean=out/'导出/clean.mp4';marked=out/'导出/bili.mp4'
    # Actual burned subtitle ROI must gain bright text at .64s vs pre-caption .0s.
    at=frame(clean,16);before=frame(clean,0);roi=(slice(298,339),slice(40,600))
    white_at=int(np.count_nonzero(np.all(at[roi]>185,axis=2)));white_before=int(np.count_nonzero(np.all(before[roi]>185,axis=2)))
    assert white_at>white_before+150,(white_at,white_before)
    b=frame(marked,16);delta=np.abs(b.astype(float)-at.astype(float));assert float(delta[20:56,520:620].mean())>2
    # Guard failure cases must fail validation without changing valid adopted manifest.
    guards={}
    cases={'repeat_ai':lambda d:(d['shots'][1].update(kind='ai'),d['shots'].append(dict(d['shots'][1],id='S04'))),
           'duplicate_annotation':lambda d:d['shots'][1].update(source_note='多余的新备注'),
           'overlong_video':lambda d:d['shots'][1].update(duration=2.04),
           'moving_watermark':lambda d:d['shots'][0].update(watermark_position=['t*20',20]),
           'missing_ai_label':lambda d:d['shots'][1].update(kind='ai',native_label=False)}
    for name,modify in cases.items():
        bad=json.loads(json.dumps(m));modify(bad);save(out/'invalid.json',bad)
        try:Film(out/'invalid.json').validate()
        except ValueError as e:guards[name]=str(e)
        else:raise AssertionError(f'Guard failed: {name}')
    (out/'invalid.json').unlink();film.validate()
    save(out/'离线测试结果.json',{'status':'passed','duration':6,'frames':150,'full_decode_both_versions':True,'actual_burned_subtitle_white_pixels':white_at,'pre_caption_white_pixels':white_before,'watermark_difference_verified':True,'guard_rejections':guards,'note':'测试图仅验证技术，不作为频道成片美术样式。'})
    print(out/'离线测试结果.json')
if __name__=='__main__':main()
