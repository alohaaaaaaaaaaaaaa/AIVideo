# 2026-10-26 独立参考迁移版：路径/字体已本地化；历史事实与数值只供原案例复现。
"""真实星历驱动的三维地平天穹：本地预演，可被声画合成脚本 import。

frame(t=秒) 或 frame(phase='altitude', p=0..1) -> 1280x720 PIL RGB。
支持 locate / convert / altitude / azimuth / turn / compare / below / time。
天体位置来自保存星历，时间段的节点之间仅做线性动画插值，非逐帧星历。
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

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'参考库/动画/01_星月与日期'
DATA_PATH=BASE/'数据/sky_positions.json'
CALC_PATH=BASE/'数据/金星计算演示.json'
OUT=BASE/'独立重渲染'
W,H,FPS=1280,720,25
PHASES=[('locate',5),('convert',6),('altitude',6),('azimuth',7),('compare',7),('below',6),('time',9)]
DURATION=sum(d for _,d in PHASES)
SANS=str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Regular.otf')
BOLD=str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Bold.otf')
MONO=str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Regular.otf')
GOLD=(248,208,126)
BLUE=(113,183,219)
ORANGE=(235,151,105)
WHITE=(226,234,237)
MUTED=(121,151,167)
PLANETS=['Venus','Mars','Saturn','Mercury','Jupiter','Sun','Moon']
COLORS={'Venus':GOLD,'Mars':(235,166,136),'Saturn':(172,208,224),
        'Mercury':(139,189,210),'Jupiter':(170,180,208),'Sun':(212,174,124),'Moon':(188,211,222)}


@lru_cache(maxsize=40)
def font(size,bold=False,mono=False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else SANS,size)


@lru_cache(maxsize=1)
def dataset():
    p=json.loads(DATA_PATH.read_text(encoding='utf-8-sig'))
    return {o['id']:o for o in p['objects']}


@lru_cache(maxsize=1)
def calculate_venus():
    """Actual coordinate conversion, rather than using the output column as input."""
    src=json.loads(CALC_PATH.read_text(encoding='utf-8-sig'))
    given=src['jpl_direct_inputs'];phi=math.radians(src['query_inputs']['geodetic_latitude_north_deg'])
    alpha=given['alpha_ra_deg'];delta=math.radians(given['delta_dec_deg'])
    theta=15*given['LAST_decimal_hours'];hour_angle=theta-alpha;hh=math.radians(hour_angle)
    east=-math.cos(delta)*math.sin(hh)
    north=math.cos(phi)*math.sin(delta)-math.sin(phi)*math.cos(delta)*math.cos(hh)
    up=math.sin(phi)*math.sin(delta)+math.cos(phi)*math.cos(delta)*math.cos(hh)
    result={'theta':theta,'H':hour_angle,'E':east,'N':north,'U':up,
            'h':math.degrees(math.asin(up)),'A':math.degrees(math.atan2(east,north))%360,
            'alpha':alpha,'delta':given['delta_dec_deg'],'LAST':given['LAST_decimal_hours']}
    assert abs(result['h']-dataset()['Venus']['primary']['alt_deg'])<1e-7
    assert abs(result['A']-dataset()['Venus']['primary']['az_deg'])<1e-7
    return result


def ease(v):
    v=max(0,min(1,v));return v*v*(3-2*v)


def enu(az,alt,r=1):
    a,h=math.radians(az),math.radians(alt)
    return np.array([r*math.cos(h)*math.sin(a),r*math.cos(h)*math.cos(a),r*math.sin(h)])


def rgba(c,a=255):return tuple(c)+(int(max(0,min(255,a))),)


@lru_cache(maxsize=1)
def background():
    yy,xx=np.mgrid[0:H,0:W]
    glow=np.exp(-(((xx-670)/590)**2+((yy-390)/310)**2))
    floor=np.exp(-(((xx-675)/540)**2+((yy-490)/155)**2))
    rgb=np.stack([5+glow*10+floor*2,10+glow*18+floor*6,18+glow*25+floor*7],axis=-1)
    return Image.fromarray(np.uint8(np.clip(rgb,0,255)))


class Scene:
    def __init__(self,az=140,elevation=23,dist=3.45,scale=820,center=(676,364)):
        a,e=math.radians(az),math.radians(elevation)
        self.target=np.array([0.,0.,.08])
        self.camera=np.array([dist*math.cos(e)*math.sin(a),dist*math.cos(e)*math.cos(a),dist*math.sin(e)])
        self.forward=self.target-self.camera;self.forward/=np.linalg.norm(self.forward)
        self.right=np.cross(self.forward,np.array([0.,0.,1.]));self.right/=np.linalg.norm(self.right)
        self.up=np.cross(self.right,self.forward)
        self.scale,self.center=scale,center
        self.labels=[]
        self.im=background().copy().convert('RGBA')
        self.layer=Image.new('RGBA',(W,H))
        self.d=ImageDraw.Draw(self.layer)

    def project(self,v):
        rel=np.asarray(v)-self.camera
        depth=float(np.dot(rel,self.forward))
        return (self.center[0]+float(np.dot(rel,self.right))*self.scale/depth,
                self.center[1]-float(np.dot(rel,self.up))*self.scale/depth)

    def line(self,points,color,width=1,alpha=255):
        pts=[self.project(p) for p in points]
        if len(pts)>1:self.d.line(pts,fill=rgba(color,alpha),width=width,joint='curve')

    def ring(self,alt=0,r=1,start=0,end=360,color=BLUE,width=1,alpha=80):
        pts=[enu(a,alt,r) for a in np.linspace(start,end,max(2,int(abs(end-start)/3)+1))]
        self.line(pts,color,width,alpha)

    def text(self,pos,text,size=20,color=WHITE,bold=False,anchor='mm',mono=False,alpha=255):
        f=font(size,bold,mono)
        self.d.text(pos,text,font=f,fill=rgba(color,alpha),anchor=anchor)
        if alpha>100:self.labels.append(self.d.textbbox(pos,text,font=f,anchor=anchor))

    def label(self,v,text,offset=(0,0),size=20,color=WHITE,anchor='mm',bold=False,alpha=255):
        x,y=self.project(v);self.text((x+offset[0],y+offset[1]),text,size,color,bold,anchor,alpha=alpha)

    def glow(self,v,color,r=5,alpha=255):
        x,y=self.project(v)
        light=Image.new('RGBA',(W,H))
        ld=ImageDraw.Draw(light)
        for k in range(4,0,-1):
            rr=r+k*4
            ld.ellipse((x-rr,y-rr,x+rr,y+rr),fill=rgba(color,alpha*(5-k)*.025))
        ld.ellipse((x-r,y-r,x+r,y+r),fill=rgba(color,alpha))
        ld.ellipse((x-1.5,y-1.5,x+1.5,y+1.5),fill=rgba((255,248,220),alpha))
        self.layer.alpha_composite(light)

    def arrow(self,end,color=GOLD,progress=1,alpha=230,width=2,start=None):
        start=np.array([0.,0.,0.]) if start is None else np.asarray(start)
        target=start+(np.asarray(end)-start)*min(1,max(0,progress))
        self.line([start,target],color,width,alpha)
        x,y=self.project(target);sx,sy=self.project(start)
        a=math.atan2(y-sy,x-sx);s=9
        pts=[(x,y),(x-s*math.cos(a-.38),y-s*math.sin(a-.38)),(x-s*math.cos(a+.38),y-s*math.sin(a+.38))]
        self.d.polygon(pts,fill=rgba(color,alpha))

    def finish(self):
        self.im.alpha_composite(self.layer)
        return self.im.convert('RGB')


def draw_dome(sc,reveal=1,below=0,ground_alpha=100):
    if reveal<=0:return
    r=max(.02,reveal)
    ground=[sc.project(enu(a,0,r*1.08)) for a in np.linspace(0,360,121)]
    sc.d.polygon(ground,fill=(29,61,73,ground_alpha))
    # Meridian and altitude arcs make a navigable volume, not a flat scatter chart.
    for az in range(0,360,30):
        sc.line([enu(az,h,r) for h in np.linspace(0,90,35)],BLUE,1,35)
        if below:
            sc.line([enu(az,h,r) for h in np.linspace(0,-80,35)],BLUE,1,35*below)
    for h in [30,60]:sc.ring(h,r,color=BLUE,alpha=28)
    if below:
        for h in [-30,-60]:sc.ring(h,r,color=BLUE,alpha=28*below)
    sc.ring(0,r,color=(128,181,202),width=2,alpha=210)
    sc.ring(0,r*1.08,color=BLUE,width=1,alpha=55)
    for az in range(0,360,10):
        sc.line([enu(az,0,r),enu(az,0,r*(1.04 if az%90==0 else 1.017))],BLUE,1,90)
    for az,name in [(0,'北 N'),(90,'东 E'),(180,'南 S'),(270,'西 W')]:
        sc.label(enu(az,0,r*1.16),name,size=21,color=(171,207,221),bold=True)


def observer(sc,reveal=1):
    # Generic scale figure at the mathematical origin; not an actual crew member.
    alpha=int(255*reveal)
    sc.ring(0,.105,color=(187,223,232),width=2,alpha=150*reveal)
    sc.ring(0,.13,color=BLUE,width=1,alpha=60*reveal)
    head=sc.project((0,0,.087));feet=sc.project((0,0,0))
    x,y=head;fx,fy=feet
    sc.d.ellipse((x-4,y-9,x+4,y-1),fill=rgba((203,222,227),alpha))
    sc.d.line((x,y,x,fy-4),fill=rgba((203,222,227),alpha),width=4)
    sc.d.line((x,y+3,x-7,y+9),fill=rgba((203,222,227),alpha),width=2)
    sc.d.line((x,y+3,x+7,y+9),fill=rgba((203,222,227),alpha),width=2)
    sc.d.line((x,fy-5,fx-5,fy+4),fill=rgba((203,222,227),alpha),width=2)
    sc.d.line((x,fy-5,fx+5,fy+4),fill=rgba((203,222,227),alpha),width=2)
    sc.label((0,0,0),'地面参考点',offset=(0,32),size=13,color=MUTED,alpha=alpha)


def node_position(obj,node_float=None):
    if node_float is None:return obj['primary']['az_deg'],obj['primary']['alt_deg']
    lo=min(6,max(0,int(node_float)));hi=min(6,lo+1);p=node_float-lo
    a,b=obj['nodes'][lo],obj['nodes'][hi]
    diff=(b['az_deg']-a['az_deg']+180)%360-180
    return (a['az_deg']+p*diff)%360,a['alt_deg']+p*(b['alt_deg']-a['alt_deg'])


def planet(sc,oid,alpha=1,node=None,label=True,offset=None):
    obj=dataset()[oid];az,alt=node_position(obj,node);v=enu(az,alt)
    sc.glow(v,COLORS[oid],r=5 if oid=='Venus' else 4,alpha=int(255*alpha))
    if label:
        default={'Venus':(-13,-22),'Mars':(12,-25),'Saturn':(0,-25),
                 'Mercury':(22,24),'Sun':(24,22),'Moon':(-36,0),'Jupiter':(0,25)}
        chosen=offset or default[oid]
        x,y=sc.project(v)
        candidates=[chosen,(36,-5),(-38,-5),(0,-31),(0,29),(40,24),(-42,22),(36,-28)]
        f=font(21,oid=='Venus')
        for dx,dy in candidates:
            box=sc.d.textbbox((x+dx,y+dy),obj['name'],font=f,anchor='mm')
            overlap=any(box[0]<b[2]+5 and box[2]>b[0]-5 and box[1]<b[3]+5 and box[3]>b[1]-5 for b in sc.labels)
            if not overlap and box[3]<610 and box[0]>15 and box[2]<W-15:
                chosen=(dx,dy);break
        sc.label(v,obj['name'],offset=chosen,size=21,color=COLORS[oid],bold=oid=='Venus',alpha=int(255*alpha))
    return v


def southeast(sc,alpha=1):
    # Broad quadrant annotation, no invented target or measured 135 degree sightline.
    for r in [.97,1,1.03]:sc.ring(0,r,start=95,end=175,color=ORANGE,width=3,alpha=90*alpha)
    sc.label(enu(135,0,1.28),'报道：东南面',offset=(0,7),size=20,color=ORANGE,bold=True,alpha=255*alpha)
    sc.label(enu(135,0,1.28),'区域示意',offset=(0,32),size=12,color=(174,135,112),alpha=255*alpha)


def chrome(sc,phase,p,moment='20:40',action='',captions=True):
    sc.text((42,26),'2010.07.07  /  萧山附近地面参考点',13,MUTED,anchor='lt')
    sc.text((1238,24),moment,29,GOLD,anchor='rt',mono=True)
    sc.text((1238,62),'北京时间',12,MUTED,anchor='rt')
    if action and captions:sc.text((W/2,646),action,25,WHITE,bold=True)
    source='JPL星历输入 / 本地坐标转换 · 地面参考点'
    if captions:source+=' · 无旁白预演'
    sc.text((42,85),source,12,MUTED,anchor='ls')
    note='节点间为动画过渡' if phase=='time' else '不是机组实测视线'
    sc.text((1238,98),note,12,MUTED,anchor='rs')


def phase_at(t):
    offset=0
    for name,duration in PHASES:
        if t<offset+duration:return name,(t-offset)/duration
        offset+=duration
    return PHASES[-1][0],1.


def turn_view(p,captions=True):
    """Look from the reference point toward SE, turn to Venus, then pull back.

    This is a cylindrical angular viewport of the same real ENU sky; no invented
    event target is drawn. The 145-degree look-back is visibly an action.
    """
    calc=calculate_venus();az=calc['A']
    heading=120+15*ease(p/.16)
    if p>.34:heading=135+(az-135)*ease((p-.34)/.28)
    im=background().copy().convert('RGBA');d=ImageDraw.Draw(im)
    center_x,horizon,pixels_per_degree=640,416,8.1
    def wrap(a):return (a-heading+180)%360-180
    def xy(a,h):return center_x+wrap(a)*pixels_per_degree,horizon-h*pixels_per_degree
    d.rectangle((0,horizon,W,H),fill=(13,29,38,255))
    for bearing in range(0,360,10):
        x,_=xy(bearing,0)
        if -20<x<W+20:
            d.line((x,112,x,552),fill=(54,90,108,75),width=1)
            d.line((x,horizon-6,x,horizon+9),fill=(128,181,202,200),width=2)
            if bearing%30==0:d.text((x,horizon+24),f'{bearing}°',font=font(15,mono=True),fill=rgba(MUTED),anchor='mt')
    for height in [10,20,30]:
        y=horizon-height*pixels_per_degree
        d.line((0,y,W,y),fill=(54,90,108,65),width=1)
    d.line((0,horizon,W,horizon),fill=rgba(BLUE,220),width=2)
    for bearing,name in [(0,'北'),(90,'东'),(180,'南'),(270,'西')]:
        x,_=xy(bearing,0)
        if 30<x<W-30:d.text((x,horizon+61),name,font=font(25,True),fill=rgba(WHITE),anchor='mt')
    # Broad reported quadrant, marked as such; never a point target.
    points=[xy(a,0)[0] for a in np.linspace(95,175,81) if abs(wrap(a))<88]
    if points:
        d.line((max(0,min(points)),horizon-3,min(W,max(points)),horizon-3),fill=rgba(ORANGE),width=6)
        labelx=max(180,min(W-180,xy(135,0)[0]))
        d.text((labelx,horizon-29),'报道：东南面 · 区域示意',font=font(20,True),fill=rgba(ORANGE),anchor='mb')
    x,y=xy(az,calc['h'])
    if -25<x<W+25:
        light=Image.new('RGBA',(W,H));ld=ImageDraw.Draw(light)
        for radius,alpha in [(27,15),(18,25),(10,55),(5,255)]:
            ld.ellipse((x-radius,y-radius,x+radius,y+radius),fill=rgba(GOLD,alpha))
        im.alpha_composite(light);d=ImageDraw.Draw(im)
        d.text((max(55,min(W-55,x)),y-35),'金星',font=font(27,True),fill=rgba(GOLD),anchor='mm')
    d.text((42,26),'2010.07.07  /  萧山附近地面参考点',font=font(13),fill=rgba(MUTED),anchor='lt')
    d.text((1238,24),'20:40',font=font(29,mono=True),fill=rgba(GOLD),anchor='rt')
    d.text((1238,62),'北京时间',font=font(12),fill=rgba(MUTED),anchor='rt')
    d.text((42,85),'JPL星历输入 / 本地坐标转换 · 地面参考点',font=font(12),fill=rgba(MUTED),anchor='ls')
    d.text((1238,98),'不是机组实测视线',font=font(12),fill=rgba(MUTED),anchor='rs')
    if p<.35:direction='面向东南'
    elif p<.60:direction='转身，看另一侧'
    else:direction='西偏北'
    d.text((640,142),direction,font=font(26,True),fill=rgba(WHITE),anchor='mm')
    d.text((640,547),'从地面参考点看出去 · 方位视窗',font=font(13),fill=rgba(MUTED),anchor='mm')
    if captions:d.text((640,646),'转过去，再回头找金星',font=font(25,True),fill=rgba(WHITE),anchor='mm')
    return im.convert('RGB')


def frame(t=None,phase=None,p=0,captions=True):
    """Independent phase progress makes retiming possible without changing source data."""
    if phase is None:phase,p=phase_at(0 if t is None else t)
    p=max(0,min(1,p));q=ease(p)
    calc=calculate_venus();az,alt=calc['A'],calc['h'];v=np.array([calc['E'],calc['N'],calc['U']])
    azcam,elev=135.,22.
    if phase=='locate':azcam,elev=135+12*q,37-15*q
    elif phase=='convert':azcam,elev=147-10*q,22.
    elif phase=='altitude':azcam,elev=137.,22.
    elif phase=='azimuth':azcam,elev=137-27*q,22+11*q
    elif phase=='turn':azcam,elev=110.,33.
    elif phase=='compare':azcam,elev=110-80*q,33-3*q
    elif phase=='below':azcam,elev=30-15*q,30-15*q
    elif phase=='time':azcam,elev=15+18*q,15.
    # Reserve y>=620 for actual-film subtitles; below-horizon bodies need extra room.
    scale=1000 if phase not in ['below','time'] else (1000-200*q if phase=='below' else 800)
    center_y=328 if phase not in ['below','time'] else (328-18*q if phase=='below' else 310)
    sc=Scene(azcam,elev,dist=3.3,scale=scale,center=(675,center_y))
    below=0 if phase not in ['below','time'] else (q if phase=='below' else 1)
    reveal=ease(p*2) if phase=='locate' else 1
    draw_dome(sc,reveal,below,ground_alpha=int(95-65*below))
    observer(sc,reveal)
    if phase=='locate':
        sc.label((0,0,.06),'120.3°E  30.2°N',offset=(0,-38),size=21,color=GOLD)
        sc.text((W/2,130),'2010年7月7日  20:40',30,WHITE,bold=True,alpha=255*ease(p*4))
        sc.label((0,0,0),'海拔 10 米',offset=(0,58),size=14,color=MUTED)
        chrome(sc,phase,p,action='把时间和站的位置先放回去',captions=captions)
    elif phase=='convert':
        sc.arrow((0,0,.92),BLUE,ease(p*2),alpha=180)
        sc.label((0,0,.98),'当地天顶',offset=(0,-12),size=16,color=BLUE)
        sc.arrow(v,GOLD,ease((p-.25)*2),alpha=215)
        if p>.56:planet(sc,'Venus',ease((p-.56)*4))
        # Kept secondary to the geometry, a real coordinate input rather than fake UI.
        sc.text((44,117),'JPL 星历输入',15,MUTED,anchor='lt')
        for i,(text,start) in enumerate([(f"α {calc['alpha']:.4f}°",.06),
                                         (f"δ  {calc['delta']:.4f}°",.16),
                                         (f"LAST {calc['LAST']:.6f} h",.26)]):
            if p>start:sc.text((44,147+i*31),text,19,WHITE,anchor='lt',mono=True,alpha=255*ease((p-start)*5))
        if p>.45:sc.text((44,263),f"时角 H = {calc['H']:.2f}°",18,MUTED,anchor='lt')
        if p>.63:
            up=np.array([0.,0.,calc['U']]);fraction=ease((p-.63)/.3)
            sc.line([v,v+(up-v)*fraction],BLUE,1,180)
            sc.arrow(up,BLUE,fraction,width=4)
            sc.label(up,'向上投影 +0.177805',offset=(140,0),size=18,color=BLUE)
            sc.text((44,300),'视线 · 天顶 = 0.177805',17,GOLD,anchor='lt')
        chrome(sc,phase,p,action='把星空坐标，换成脚下这个点的视线',captions=captions)
    elif phase=='altitude':
        planet(sc,'Venus')
        sc.arrow(v,GOLD,1,width=2)
        sc.line([(0,0,0),enu(az,0)],(129,164,181),1,170)
        # An actual 10.2419-degree angle arc, with its horizontal projection.
        for r in [.47,.51]:
            sc.line([enu(az,a,r) for a in np.linspace(0,alt*ease(p*2),30)],GOLD,2,220)
        projected=enu(az,0)*math.cos(math.radians(alt))
        sc.line([projected,v],GOLD,1,130)
        hp=sc.project(enu(az,alt*.5,.55))
        sc.text((hp[0]-15,hp[1]-35),'+10.24°',30,GOLD,bold=True,anchor='mm')
        if p>.3:sc.text((46,134),'sin h = 0.177805',20,MUTED,anchor='lt',mono=True)
        if p>.5:sc.text((46,170),'h = +10.24°',24,GOLD,anchor='lt',mono=True)
        chrome(sc,phase,p,action='正十度。金星确实还在地平线上方',captions=captions)
    elif phase=='azimuth':
        planet(sc,'Venus')
        sc.arrow(v,GOLD,1,alpha=160)
        # Sweep clockwise from north, exactly matching the stated azimuth convention.
        progress=ease(max(0,(p-.32)/.55))
        sc.ring(0,.76,start=0,end=az*progress,color=GOLD,width=3,alpha=220)
        sc.glow(enu(az*progress,0,.76),GOLD,r=3)
        sc.line([enu(az,0,.76),v],GOLD,1,110)
        ground=np.array([calc['E'],calc['N'],0.]);east=np.array([calc['E'],0.,0.])
        sc.line([v,ground],BLUE,1,150)
        sc.arrow(east,BLUE,ease(p*4),alpha=190,width=2)
        if p>.22:sc.arrow(ground,BLUE,ease((p-.22)*4),alpha=210,width=2,start=east)
        if p>.3:
            sc.text((44,136),'东分量  −0.967716',17,MUTED,anchor='lt')
            sc.text((44,168),'北分量  +0.178637',17,MUTED,anchor='lt')
            sc.text((44,213),'280.46°',32,GOLD,bold=True,anchor='lt',mono=True)
            sc.text((44,256),'西偏北',23,GOLD,bold=True,anchor='lt')
        chrome(sc,phase,p,action='再沿地平圈找方向：西偏北',captions=captions)
    elif phase=='turn':
        planet(sc,'Venus');southeast(sc,1)
        sc.arrow(v,GOLD,1,alpha=130)
        sc.ring(0,.76,start=270,end=az,color=GOLD,width=3,alpha=220)
        sc.text((44,136),'西偏北',24,GOLD,bold=True,anchor='lt')
        sc.text((44,176),'280.46°',23,GOLD,anchor='lt',mono=True)
        chrome(sc,phase,p,action='金星在身后的西偏北',captions=captions)
        return Image.blend(turn_view(p,captions),sc.finish(),ease((p-.66)/.20))
    elif phase=='compare':
        planet(sc,'Venus')
        # K05 starts at 33.12 s; Mars/Saturn are named at 36.7113 s (p≈.35).
        if p>.35:
            for oid in ['Mars','Saturn']:planet(sc,oid,ease((p-.35)/.13))
        southeast(sc,1)
        sc.arrow(v,GOLD,1,alpha=130)
        chrome(sc,phase,p,action='它们在西侧。报道指向东南',captions=captions)
    elif phase=='below':
        for oid in PLANETS:planet(sc,oid,1 if oid in ['Venus','Mars','Saturn'] else ease(p*2))
        southeast(sc,.55)
        sc.label((0,0,-.7),'地平面以下',offset=(0,18),size=18,color=MUTED)
        chrome(sc,phase,p,action='水星、木星，以及补查的太阳和月亮，都在下面',captions=captions)
    elif phase=='time':
        node=6*q
        for oid in PLANETS:planet(sc,oid,node=node)
        southeast(sc,.55)
        minutes=120*q
        hh=20+int(minutes)//60;mm=int(minutes)%60
        if p>=1:hh,mm=22,0
        # A scrubber represents animation between the seven saved positions.
        left,right,yy=345,1005,590
        sc.d.line((left,yy,right,yy),fill=rgba(MUTED,110),width=2)
        for i,lab in enumerate(['20:00','20:20','20:40','21:00','21:20','21:40','22:00']):
            x=left+(right-left)*i/6
            sc.d.ellipse((x-3,yy-3,x+3,yy+3),fill=rgba(MUTED,170))
            sc.text((x,yy+17),lab,13,MUTED,anchor='mt',mono=True)
        x=left+(right-left)*q
        sc.d.ellipse((x-6,yy-6,x+6,yy+6),fill=rgba(GOLD))
        # Draw a real scrub handle; avoid missing-glyph arrows in system fonts.
        sc.d.polygon([(x-8,yy-29),(x+8,yy-29),(x+8,yy-18),(x,yy-12),(x-8,yy-18)],fill=rgba(GOLD))
        chrome(sc,phase,p,moment=f'{hh:02}:{mm:02}',action='把时间前后拨动，位置也跟着变化',captions=captions)
    else:raise ValueError(f'Unknown phase: {phase}')
    return sc.finish()


def metadata(target):
    return {'duration_seconds':DURATION,'fps':FPS,'size':[W,H],'audio':False,'paid_api_calls':0,
            'phases':PHASES,'interface':'frame(t=None, phase=None, p=0, captions=True) -> PIL RGB 1280x720',
            'final_film_usage':'Set captions=False to remove demo action captions; y>=620 reserved for subtitles.',
            'position_mapping':'x=cos(h)sin(A), y=cos(h)cos(A), z=sin(h); x east/y north/z up',
            'data_sha256':hashlib.sha256(DATA_PATH.read_bytes()).hexdigest(),
            'calculation_file_sha256':hashlib.sha256(CALC_PATH.read_bytes()).hexdigest(),
            'locally_recalculated':calculate_venus(),
            'time_motion':'linear az/alt interpolation between seven saved 20-minute nodes; not ephemeris recomputation',
            'reported_direction':'broad southeast quadrant annotation, not a measured 135-degree ray or uncertainty interval',
            'scope':'seven bodies only; no invented background stars or object',
            'output':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stills',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    for phase,p in [('locate',.8),('altitude',.75),('compare',.55),('below',.9),('time',.75)]:
        frame(phase=phase,p=p).save(OUT/f'美术检查_{phase}.png')
    if args.stills:print('STILLS_READY',flush=True);return
    target=OUT/'三维天空推演_无旁白.mp4'
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-hide_banner','-f','rawvideo','-pix_fmt','rgb24',
         '-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast',
         '-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
    with (OUT/'render.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log)
        try:
            for i in range(DURATION*FPS):
                proc.stdin.write(frame(t=i/FPS).tobytes())
                if i%(FPS*6)==0:print(f'FRAME {i}/{DURATION*FPS}',flush=True)
            proc.stdin.close()
            if proc.wait():raise RuntimeError('ffmpeg failed')
        finally:
            if proc.poll() is None:proc.terminate()
    (OUT/'动画说明.json').write_text(json.dumps(metadata(target),ensure_ascii=False,indent=2),encoding='utf-8')
    print('VIDEO_READY',target,flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
