"""A moving pair of teaching lights photographed through one exposure.

Native 1920x1080, 25 fps. frame(t=None, phase=None, p=0, captions=True)
returns an RGB PIL frame. No source photograph is read or modified.
The Gaussian point-spread exposure is integrated analytically along a straight
teaching path; periodic pulses create finite short marks, not invented windows.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

import imageio_ffmpeg
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
from scipy.special import erf

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'动画';CHECK=OUT/'检查'
W,H,FPS=1920,1080,25
EXPOSURE=2.5
PHASES=[('lights',4.0),('open',.6),('expose',10.0),('close',.6),('develop',2.8),('inspect',8.0)]
DURATION=sum(x[1] for x in PHASES)
SANS='C:/Windows/Fonts/msyh.ttc';BOLD='C:/Windows/Fonts/msyhbd.ttc';MONO='C:/Windows/Fonts/consola.ttf'
WHITE=(235,237,230);GOLD=(237,194,124);BLUE=(160,199,212);MUTED=(132,151,156)
SENSOR=(144,226,1776,820)
ROI=(300,298,1610,725)
P0=np.array([407.,630.]);P1=np.array([1513.,424.])
DELTA=P1-P0;LENGTH=float(np.linalg.norm(DELTA));TANGENT=DELTA/LENGTH
NORMAL=np.array([TANGENT[1],-TANGENT[0]])
LAMP_GAP=48.0
PULSE_PERIOD=.45;PULSE_WIDTH=.040;PULSE_PHASE=.075
PULSES=[(PULSE_PHASE+i*PULSE_PERIOD,PULSE_PHASE+i*PULSE_PERIOD+PULSE_WIDTH) for i in range(6)]


def clamp(v):return max(0.,min(1.,float(v)))
def ease(v):v=clamp(v);return v*v*(3-2*v)

@lru_cache(maxsize=48)
def font(size,bold=False,mono=False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else SANS,size)


def text(im,xy,s,size=26,fill=WHITE,bold=False,anchor='mm',mono=False):
    ImageDraw.Draw(im).text(xy,s,font=font(size,bold,mono),fill=fill,anchor=anchor)


@lru_cache(maxsize=1)
def background():
    yy,xx=np.mgrid[:H,:W];rng=np.random.default_rng(20100707)
    grain=rng.normal(0,.43,(H,W))
    light=np.exp(-((xx-1020)**2/880**2+(yy-430)**2/700**2))
    rgb=np.stack([8+light*16+grain,13+light*20+grain,16+light*22+grain],axis=-1)
    im=Image.fromarray(np.uint8(np.clip(rgb,0,255)),'RGB');d=ImageDraw.Draw(im)
    # A low, matte camera gate, not a floating text card.
    d.rounded_rectangle((88,172,1832,884),radius=34,fill=(4,9,12),outline=(46,60,64),width=2)
    d.rounded_rectangle((111,199,1809,848),radius=22,fill=(3,7,10),outline=(63,70,69),width=3)
    d.line((147,213,1771,213),fill=(99,99,83),width=1)
    d.line((147,839,1771,839),fill=(15,23,26),width=4)
    for x,y in [(111,193),(1809,193),(111,861),(1809,861)]:
        d.ellipse((x-5,y-5,x+5,y+5),fill=(69,76,74))
        d.line((x-2,y+3,x+2,y-3),fill=(18,22,23),width=2)
    return im


@lru_cache(maxsize=1)
def coordinates():
    l,t,r,b=ROI;yy,xx=np.mgrid[t:b,l:r]
    dx,dy=xx-P0[0],yy-P0[1]
    along=(dx*TANGENT[0]+dy*TANGENT[1]).astype(np.float32)
    cross=(dx*NORMAL[0]+dy*NORMAL[1]).astype(np.float32)
    return along,cross


def exposure_profile(tau,offset=0.,sigma=2.4,pulsed=False):
    """Integral of a Gaussian moving point source, proportional to exposure.

    Normalized by constant image-plane speed. A pulsed source integrates only
    during its on intervals. Linear radiance is tone-mapped only when displayed.
    """
    s,d=coordinates();d=d-offset;result=np.zeros_like(s)
    intervals=PULSES if pulsed else [(0.,EXPOSURE)]
    for start,end in intervals:
        a=max(0.,start);b=min(tau,end)
        if b<=a:continue
        a=a/EXPOSURE*LENGTH;b=b/EXPOSURE*LENGTH
        result+=.5*(erf((s-a)/(math.sqrt(2)*sigma))-erf((s-b)/(math.sqrt(2)*sigma)))
    result*=np.exp(-.5*(d/sigma)**2)
    return result


@lru_cache(maxsize=280)
def recorded_roi(tick):
    # 1/100 second exposure sampling is finer than the 1/4-speed preview frames.
    tau=min(EXPOSURE,max(0,tick/100))
    l,t,r,b=ROI;rgb=np.zeros((b-t,r-l,3),dtype=np.float32)
    for pulsed,offset,color in [(False,0,np.array([1.,.86,.66],np.float32)),
                                (True,LAMP_GAP,np.array([.82,.93,1.],np.float32))]:
        for sigma,gain in [(2.4,1.9),(6.,.33),(18.,.055)]:
            profile=exposure_profile(tau,offset,sigma,pulsed)
            rgb+=profile[:,:,None]*color[None,None,:]*gain
    rgb=255*(1-np.exp(-rgb))
    return np.uint8(np.clip(rgb,0,255))


def sensor_image(tau):
    im=background().copy();l,t,r,b=ROI
    base=np.asarray(im.crop(ROI),dtype=np.uint16)
    charge=recorded_roi(round(tau*100)).astype(np.uint16)
    combined=np.minimum(255,base+charge).astype(np.uint8)
    im.paste(Image.fromarray(combined,'RGB'),(l,t))
    return im


def glow(im,xy,color=WHITE,radius=6,strength=1):
    # Local float geometry prevents one-pixel jumps in moving sources.
    x,y=xy;pad=math.ceil(radius*17);l=int(x)-pad;t=int(y)-pad
    yy,xx=np.mgrid[t:t+2*pad,l:l+2*pad]
    distance=(xx-x)**2+(yy-y)**2
    intensity=np.zeros_like(xx,dtype=np.float32)
    for sigma,gain in [(radius,1.0),(radius*2.5,.25),(radius*5,.075)]:
        intensity+=np.exp(-distance/(2*sigma*sigma))*gain*strength
    patch=np.asarray(im.crop((l,t,l+2*pad,t+2*pad)),dtype=np.float32)
    patch=np.minimum(255,patch+intensity[:,:,None]*np.array(color)[None,None,:])
    im.paste(Image.fromarray(np.uint8(patch),'RGB'),(l,t))


def live_pair(im,tau,t=0,rig=False,scale=1,labels=False,center_override=None):
    center=P0+DELTA*(tau/EXPOSURE)
    if center_override is not None:center=np.asarray(center_override)
    steady=center;flasher=center+NORMAL*LAMP_GAP*scale
    if rig:
        d=ImageDraw.Draw(im)
        # The shared bare bracket is a teaching apparatus, never a craft body.
        d.line([tuple(steady),tuple(flasher)],fill=(56,70,76),width=round(10*scale))
        for point in [steady,flasher]:
            x,y=point;r=13*scale
            d.ellipse((x-r,y-r,x+r,y+r),fill=(17,27,32),outline=(94,110,114),width=2)
            d.ellipse((x-r*.82,y-r*.82,x+r*.82,y+r*.82),outline=(51,65,71),width=2)
    glow(im,steady,(252,225,184),5.8*scale)
    on=any(a<=tau<b for a,b in PULSES) if not rig else ((t%PULSE_PERIOD)<.11)
    if on:glow(im,flasher,(218,240,255),6.5*scale)
    if labels:
        d=ImageDraw.Draw(im)
        d.line((steady[0]+30,steady[1]+12,steady[0]+120,steady[1]+49),fill=GOLD,width=2)
        text(im,(steady[0]+134,steady[1]+49),'常亮灯',28,GOLD,anchor='lm')
        d.line((flasher[0]+30,flasher[1]-10,flasher[0]+120,flasher[1]-60),fill=BLUE,width=2)
        text(im,(flasher[0]+134,flasher[1]-60),'闪烁灯',28,BLUE,anchor='lm')


def aperture(im,opening):
    """A stylized camera shutter; this is not a model of the source camera."""
    opening=clamp(opening)
    if opening>=1:return
    l,t,r,b=SENSOR;center=np.array([(l+r)/2,(t+b)/2]);radius=1170*opening
    overlay=Image.new('RGBA',(W,H));d=ImageDraw.Draw(overlay)
    d.rounded_rectangle((l,t,r,b),radius=7,fill=(13,19,22,255))
    # The moving six-sided opening is erased from the curtain layer.
    if radius>0:
        poly=[tuple(center+radius*np.array([math.cos(a),math.sin(a)])) for a in np.linspace(0,2*math.pi,6,endpoint=False)]
        d.polygon(poly,fill=(0,0,0,0))
        d.line(poly+[poly[0]],fill=(115,126,122,255),width=2)
    for a in np.linspace(0,2*math.pi,6,endpoint=False):
        inner=center+max(1,radius)*np.array([math.cos(a),math.sin(a)])
        outer=inner+1200*np.array([math.cos(a+.65),math.sin(a+.65)])
        d.line([tuple(inner),tuple(outer)],fill=(38,48,52,255),width=2)
    # Keep shutter blades inside the physical gate.
    mask=Image.new('L',(W,H));ImageDraw.Draw(mask).rounded_rectangle(SENSOR,radius=7,fill=255)
    overlay.putalpha(Image.fromarray(np.minimum(np.asarray(overlay.getchannel('A')),np.asarray(mask))))
    im.paste(overlay,(0,0),overlay)


def progress(im,tau,state,visible=True):
    d=ImageDraw.Draw(im)
    text(im,(1540,102),f'{tau:0.2f}',55,GOLD,anchor='rm',mono=True)
    text(im,(1557,106),'秒',25,MUTED,anchor='lm')
    text(im,(164,103),state,29,WHITE,bold=True,anchor='lm')
    if visible:
        d.line((164,864,1754,864),fill=(39,57,62),width=3)
        end=164+(1754-164)*clamp(tau/EXPOSURE)
        d.line((164,864,end,864),fill=GOLD,width=3)
        d.ellipse((end-4,860,end+4,868),fill=GOLD)
    text(im,(164,905),'教学假设：直线移动、灯距、闪光周期；非当晚轨迹或机型参数',20,MUTED,anchor='lm')
    text(im,(1754,905),'2.5秒：报告参数例示',20,MUTED,anchor='rm')


def chrome(im,caption,captions):
    text(im,(93,43),'光怎样变成“形状”',24,WHITE,bold=True,anchor='lm')
    text(im,(1827,43),'成像原理示意 · 非历史照片',19,MUTED,anchor='rm')
    if captions and caption:text(im,(960,1000),caption,37,WHITE,bold=False)


def phase_at(t):
    t=max(0,float(t));start=0.
    for name,duration in PHASES:
        if t<start+duration:return name,(t-start)/duration
        start+=duration
    return PHASES[-1][0],1.


def frame(t=None,phase=None,p=0,captions=True):
    if phase is None:phase,p=phase_at(0 if t is None else t)
    p=clamp(p);q=ease(p)
    im=background().copy();caption=''
    if phase=='lights':
        # Start close enough to see a single blinking emitter, then pull back to
        # the exact exposure start. This move belongs only to the teaching rig.
        pull=ease((p-.35)/.65);scale=2.65-1.65*pull
        center=np.array([820.,584.])*(1-pull)+P0*pull
        live_pair(im,0,t=p*4,rig=True,scale=scale,labels=True,center_override=center)
        progress(im,0,'快门还没打开',False)
        caption='一盏常亮，一盏闪烁。'
    elif phase=='open':
        live_pair(im,0,rig=True)
        aperture(im,q)
        progress(im,0,'快门打开')
        caption='开始记录。'
    elif phase=='expose':
        tau=p*EXPOSURE;im=sensor_image(tau)
        d=ImageDraw.Draw(im)
        x,y=P0+DELTA*p
        d.line((x,y+36,x,y+58),fill=(165,177,166),width=1)
        text(im,(x,y+79),'灯现在到这里',18,MUTED)
        progress(im,tau,'快门开着 · 正在累计')
        text(im,(1755,158),'4倍慢放演示',19,MUTED,anchor='rm')
        # Optical current-position lights are kept subtle over the integrated trace.
        live_pair(im,tau)
        if p<.34:caption='快门没关，光就一直记在这张画面里。'
        elif p<.64:caption='常亮灯走过的地方，连成一条线。'
        else:caption='闪一下，记一下；熄灭的时候，就留下间隔。'
    elif phase=='close':
        im=sensor_image(EXPOSURE);aperture(im,1-q)
        progress(im,EXPOSURE,'快门关闭 · 停止累计')
        caption='快门一关，记录停在这里。'
    elif phase in ['develop','inspect']:
        # A developed exposure moves forward as one physical image. This is the
        # local teaching image only, never a zoom of the historical photograph.
        out=sensor_image(EXPOSURE).crop((270,290,1660,738))
        if phase=='develop':scale=.55+.45*q;alpha=ease(p*2)
        else:scale=1.;alpha=1.
        ow,oh=round(out.width*scale),round(out.height*scale)
        out=out.resize((ow,oh),Image.Resampling.LANCZOS)
        left=round((W-ow)/2);top=round(520-oh/2)
        im=background().copy();aperture(im,0)
        # Cover the camera gate with a clean photographic proof border.
        proof=Image.new('RGBA',(ow+32,oh+32),(28,33,35,255));proof.paste(out,(16,16))
        pd=ImageDraw.Draw(proof);pd.rectangle((0,0,ow+31,oh+31),outline=(101,112,109),width=2)
        if alpha<1:proof.putalpha(round(255*alpha))
        im.paste(proof,(left-16,top-16),proof)
        progress(im,EXPOSURE,'快门已关 · 看留下的记录',False)
        if phase=='develop':caption='它记录的是一段时间，不是某一瞬间。'
        else:
            # Labels point to the rendered recording, not a supposed aircraft.
            d=ImageDraw.Draw(im)
            lx=left+(LENGTH*.38+P0[0]-270)
            ly=top+(P0[1]-290)+DELTA[1]*.38
            if p<.55:
                u=ease(p/.18)
                d.line((lx,ly+18,lx,ly+18+55*u),fill=GOLD,width=2)
                if p>.13:text(im,(lx,ly+100),'一盏常亮灯留下的连续光迹',26,GOLD)
                mx=left+(P0[0]-270)+DELTA[0]*(PULSES[3][0]/EXPOSURE)
                my=top+(P0[1]-290)+DELTA[1]*(PULSES[3][0]/EXPOSURE)+NORMAL[1]*LAMP_GAP
                d.line((mx,my-18,mx,my-18-55*u),fill=BLUE,width=2)
                if p>.13:text(im,(mx,my-98),'同一盏灯多次闪亮的记录',26,BLUE)
                caption='长线像“机身”，亮点像“窗户”——也可能只是光迹。'
            else:
                caption='先看清成像方式，再回去核对原照片。'
                text(im,(960,799),'这只是成像机制，不是机型鉴定。',25,MUTED)
    else:raise ValueError(phase)
    chrome(im,caption,captions)
    return im


def make_sfx(path):
    """Original local mechanical ticks, explicitly illustrative and not location audio."""
    sr=48000;n=round(DURATION*sr);audio=np.zeros(n,np.float32);rng=np.random.default_rng(7)
    events=[(4.0,.10),(4.6,.075),(14.6,.12),(15.2,.06)]
    for start,amp in events:
        duration=.18;tt=np.arange(round(duration*sr))/sr
        attack=np.minimum(1,tt/.003);env=np.exp(-tt*28)*attack
        noise=rng.normal(0,.15,len(tt));tone=np.sin(2*np.pi*620*tt)+.4*np.sin(2*np.pi*1040*tt)
        snd=(tone*.6+noise)*env*amp;i=round(start*sr);audio[i:i+len(snd)]+=snd
    # No blink beeps: avoid suggesting the original event sounded like this.
    stereo=np.stack([audio*.7071,audio*.7071],axis=1)
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes(np.int16(stereo*32767).tobytes())
    return {'sample_rate':sr,'channels':2,'peak':float(np.max(np.abs(stereo))),'description':'本地合成快门机械提示声；无旁白、无历史现场音频'}


def verify(target):
    import av
    stream=av.open(str(target));v=stream.streams.video[0];count=0;black=0;last=-1;samples={25,115,165,240,330,390,470,570,635}
    for f in stream.decode(v):
        assert f.time>last;last=f.time;arr=f.to_ndarray(format='rgb24')
        if np.max(arr)<8:black+=1
        if count in samples:Image.fromarray(arr).save(CHECK/f'实际导出_{count/FPS:05.2f}s.png')
        count+=1
    result={'decoded_video_frames':count,'expected_frames':round(DURATION*FPS),'duration':float(v.duration*v.time_base),
            'width':v.width,'height':v.height,'fps':str(v.average_rate),'completely_black_frames':black,
            'video_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    stream.close();stream=av.open(str(target));audio=[]
    for f in stream.decode(audio=0):audio.append(f.to_ndarray())
    result['decoded_audio_samples']=sum(a.shape[-1] for a in audio)
    result['decoded_audio_peak']=float(max(np.max(np.abs(a)) for a in audio))
    stream.close()
    assert count==round(DURATION*FPS) and black==0
    assert result['decoded_audio_peak']<1
    # Check the closed shutter freezes accumulation; blink/off intervals differ.
    assert np.array_equal(recorded_roi(250),recorded_roi(251))
    dots=exposure_profile(EXPOSURE,LAMP_GAP,2.4,True)
    assert np.array_equal(exposure_profile(.20,LAMP_GAP,2.4,True),exposure_profile(.30,LAMP_GAP,2.4,True))
    assert not np.any(exposure_profile(.07,LAMP_GAP,2.4,True))
    energies=[float(exposure_profile(t).sum()) for t in [0.,.5,1.,1.5,2.,2.5]]
    assert all(b>a for a,b in zip(energies,energies[1:]))
    result['recording_checks']={'exposure_clamped_at_2_5_seconds':True,'pulse_count':len(PULSES),
      'pulses_within_exposure':all(0<=a<b<=EXPOSURE for a,b in PULSES),'maximum_pulsed_integral':float(dots.max()),
      'no_flash_accumulation_while_lamp_off':True,'no_recorded_flash_before_first_pulse':True,
      'continuous_recording_energy_increases':energies,
      'motion_path_is_teaching_assumption':True,'historical_photo_pixels_read':False}
    return result


def metadata(target=None):
    return {'duration_seconds':DURATION,'fps':FPS,'size':[W,H],'paid_api_calls':0,'historical_images_used':[],
      'phases':[{'phase':p,'duration':d} for p,d in PHASES],
      'interface':'frame(t=None, phase=None, p=0, captions=True) -> PIL RGB 1920x1080',
      'exposure_example_seconds':EXPOSURE,'exposure_provenance':'报告参数例示；具体历史照片参数需与来源核对',
      'teaching_assumptions':{'path':'straight line in image plane; no world speed implied','start_px':P0.tolist(),
        'end_px':P1.tolist(),'lamp_gap_px':LAMP_GAP,'flash_period_s':PULSE_PERIOD,'flash_width_s':PULSE_WIDTH,
        'flash_phase_s':PULSE_PHASE,'flash_intervals':PULSES,'exposure_playback_slowdown':4},
      'method':'analytic integral of moving Gaussian point spread; a pulsed light integrates only during on intervals',
      'inference_limit':'demonstrates a possible imaging mechanism, not proof of aircraft type, trajectory or airport target identity',
      'captions_false':'Hide demo bottom sentences; reserve y>=950 for final subtitles.',
      'output':str(target) if target else None}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stills',action='store_true');ap.add_argument('--verify-only',action='store_true');args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);CHECK.mkdir(parents=True,exist_ok=True)
    target=OUT/'长曝光_线与点_原理预演_1080p.mp4'
    if args.verify_only:
        (CHECK/'导出核验.json').write_text(json.dumps(verify(target),ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return
    for t in [1,4.6,6.6,9.6,13.2,15.6,18.8,22.8,25.4]:frame(t=t).save(CHECK/f'合成前_{t:05.2f}s.png')
    if args.stills:print('STILLS_READY');return
    sound=OUT/'快门示意声_48k.wav';soundinfo=make_sfx(sound)
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    cmd=[ff,'-y','-hide_banner','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
      '-i',str(sound),'-map','0:v:0','-map','1:a:0','-t',str(DURATION),'-c:v','libx264','-preset','fast','-crf','18',
      '-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(target)]
    with (OUT/'render.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log)
        try:
            for i in range(round(DURATION*FPS)):
                proc.stdin.write(frame(t=i/FPS).tobytes())
                if i%(FPS*4)==0:print(f'FRAME {i}/{round(DURATION*FPS)}',flush=True)
            proc.stdin.close()
            if proc.wait():raise RuntimeError('encoder failed')
        finally:
            if proc.poll() is None:proc.terminate()
    meta=metadata(target);meta['sound']=soundinfo
    (OUT/'动画说明.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (CHECK/'导出核验.json').write_text(json.dumps(verify(target),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('VIDEO_READY',target,flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
