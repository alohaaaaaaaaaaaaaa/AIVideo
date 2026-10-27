"""雷达通信过程的原创原理动画；不重建萧山当晚设备、位置或航迹。"""
from pathlib import Path
import math, json, subprocess, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'动画/雷达原理'
OUT.mkdir(parents=True,exist_ok=True)
W,H=1920,1080
FONT='C:/Windows/Fonts/msyh.ttc'
FONTS={n:ImageFont.truetype(FONT,n) for n in [22,26,30,34,40,48]}

yy,xx=np.mgrid[0:H,0:W]
v=np.exp(-((xx-1000)/1050)**2-((yy-550)/570)**2)
rgb=np.dstack([8+v*9,15+v*17,23+v*22]).astype(np.uint8)
BACKGROUND=Image.fromarray(rgb)

def point(a,b,p): return (a[0]+(b[0]-a[0])*p,a[1]+(b[1]-a[1])*p)
def smooth(p):
    p=max(0,min(1,p));return p*p*(3-2*p)
def txt(d,xy,s,n=30,color='#dce8ec',anchor=None):
    d.text(xy,s,font=FONTS[n],fill=color,anchor=anchor)

def draw_site(d,phase):
    # Ground plane, mast and generic parabolic reflector, deliberately no real airport marks.
    d.ellipse((95,592,710,813),fill='#111e2b',outline='#2a4354',width=2)
    d.polygon([(304,686),(389,665),(442,689),(353,716)],fill='#354656')
    d.polygon([(304,686),(353,716),(353,746),(304,714)],fill='#263746')
    d.polygon([(353,716),(442,689),(442,716),(353,746)],fill='#1c2b38')
    d.polygon([(341,418),(370,413),(378,691),(347,700)],fill='#596d79')
    d.line([(344,459),(269,598),(349,622),(426,577),(369,455)],fill='#8796a0',width=4)
    angle=math.sin(phase*.2)*.065
    # Reflector ribs curve toward focal point; small rotation is an explanatory model motion.
    for j in range(9):
        ys=325+j*19
        line=[]
        for i in range(61):
            u=i/60; x=235+u*208; y=ys+math.sin(u*math.pi)*33
            line.append((x+angle*(y-420),y))
        d.line(line,fill='#8399a5' if j in [0,8] else '#455f71',width=3 if j in [0,8] else 2)
    for k in range(9):
        x=235+k*26
        d.line([(x,325+math.sin(k/8*math.pi)*33),(x,477+math.sin(k/8*math.pi)*33)],fill='#526e80',width=2)
    d.line([(238,332),(519,395),(444,480)],fill='#8c9da6',width=4)
    d.ellipse((506,382,534,410),fill='#b9d4df')
    txt(d,(349,786),'地面设备示意',30,anchor='mm')

def draw_aircraft(d,active=False):
    # A generic locally drawn silhouette, not a particular aircraft type or historical target.
    x,y=1425,396
    d.ellipse((1170,613,1715,775),fill='#101b25',outline='#203849',width=2)
    pts=[(x-218,y+4),(x-83,y-34),(x-34,y-182),(x-4,y-194),(x+16,y-37),(x+140,y-6),(x+190,y-64),(x+220,y-64),(x+203,y+17),(x+220,y+84),(x+187,y+87),(x+139,y+36),(x+17,y+59),(x-5,y+203),(x-35,y+209),(x-84,y+58),(x-218,y+34)]
    d.polygon([(a+10,b+18) for a,b in pts],fill='#0c1620')
    d.polygon(pts,fill='#73838c',outline='#a4b1b7',width=3)
    d.line([(x-208,y+21),(x+191,y+23)],fill='#b5c3c8',width=3)
    d.rounded_rectangle((x-36,y-13,x+48,y+51),radius=7,fill='#202f3b',outline='#e4c68b' if active else '#5b7380',width=3)
    d.ellipse((x+21,y+4,x+34,y+17),fill='#edc675' if active else '#465664')
    txt(d,(1445,785),'目标示意',30,anchor='mm')

def glow_path(im,pts,color,width=5):
    lay=Image.new('RGBA',(W,H));ld=ImageDraw.Draw(lay)
    ld.line(pts,fill=(*color,255),width=width)
    return Image.alpha_composite(Image.alpha_composite(im.convert('RGBA'),lay.filter(ImageFilter.GaussianBlur(14))),lay)

def frame(t, captions=True):
    im=BACKGROUND.copy();d=ImageDraw.Draw(im)
    mode=0 if t<11 else 1
    tt=t if mode==0 else t-11
    cycle=max(0,min(1,(tt-.6)/(9 if mode==0 else 10.5)))
    active=mode==1 and .48<cycle<.94
    draw_site(d,t);draw_aircraft(d,active)
    start=(524,396);end=(1445,408) if mode else (1220,417)
    send=smooth(min(1,cycle/.44))
    back=smooth((cycle-.50)/.44)
    if cycle<.48:
        c=point(start,end,send)
        trail=[point(start,end,max(0,send-i*.0035)) for i in range(55)]
        im=glow_path(im,trail,(102,191,219),6)
        d=ImageDraw.Draw(im)
        for radius in [14,28,44]:
            d.arc((c[0]-radius,c[1]-radius,c[0]+radius,c[1]+radius),-50,50,fill='#b5e4f1',width=3)
    elif cycle>.50:
        a=(1445,430) if mode else (1220,453);b=(524,432)
        c=point(a,b,back)
        trail=[point(a,b,max(0,back-i*.0035)) for i in range(55)]
        im=glow_path(im,trail,(222,176,94) if mode else (112,175,191),5)
        d=ImageDraw.Draw(im)
        if mode:
            d.rounded_rectangle((c[0]-32,c[1]-12,c[0]+32,c[1]+12),radius=5,fill='#e1b76d')
        else:
            for radius in [13,26,39]:d.arc((c[0]-radius,c[1]-radius,c[0]+radius,c[1]+radius),130,230,fill='#aed5df',width=2)
    d=ImageDraw.Draw(im)
    txt(d,(880,340),'发出探测信号' if mode==0 else '发出询问',34,'#a6d6e5',anchor='mm')
    txt(d,(880,520),'反射回波' if mode==0 else '应答机回复',34,'#d3c39e' if mode else '#b4d0d8',anchor='mm')
    if cycle>.95:
        d.ellipse((502,414,546,458),outline='#e7c482' if mode else '#b3dae3',width=4)
    if mode:
        d.line([(1450,415),(1605,533),(1740,533)],fill='#d4b474',width=2)
        txt(d,(1648,568),'机载应答机',30,'#dfbd7c',anchor='mm')
    # Follow the question toward the aircraft, then pull back as its answer returns.
    # This is motion in an original explanatory scene, never movement of evidence pixels.
    if mode:
        push=smooth(tt/3)*(1-smooth((tt-6)/4))
        zoom=1+.3*push;cw=W/zoom;ch=H/zoom
        cx=960+235*push;cy=540-45*push
        im=im.crop((cx-cw/2,cy-ch/2,cx+cw/2,cy+ch/2)).resize((W,H),Image.Resampling.LANCZOS)
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,W,208),fill='#0b1720')
    d.rectangle((0,830,W,H),fill='#0b1720')
    txt(d,(64,45),'萧山调查 / 把“雷达没发现”拆开看',26,'#95a9b5')
    txt(d,(64,90),'原理示意 · 不代表当晚设备配置、目标或航迹',22,'#7d95a5')
    txt(d,(960,166),'先看反射回来的信号' if mode==0 else '再看应答机的回答',48,anchor='mm')
    txt(d,(960,856),'一次雷达：接收反射信号' if mode==0 else '二次雷达：接收合作回复',40,anchor='mm')
    txt(d,(960,918),'传播过程放慢示意；仅说明两种机制，不模拟探测性能。',26,'#8da3ae',anchor='mm')
    if captions:txt(d,(960,1008),'原理动作预演 · 尚未配音',26,'#aebbc3',anchor='mm')
    return im.convert('RGB')

def main():
    fps=25;duration=24;path=OUT/'雷达两种机制_无旁白预演.mp4'
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s','1920x1080','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(path)]
    with (OUT/'渲染.log').open('wb') as log:
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
        for i in range(int(fps*duration)):
            proc.stdin.write(frame(i/fps).tobytes())
        proc.stdin.close();assert proc.wait()==0
    report={'duration':duration,'fps':fps,'size':[W,H],'paid_api_calls':0,'source':'FAA AIM 4-5-2(a)(1)-(2)，官方原文见本环来源缓存与军机雷达核验','limits':['图形为原创机制示意，不是2010设备或原航迹。','传播速度放慢，不模拟射频参数或实际探测概率。','第二种机制需要应答，不代表全部雷达均依赖应答机。'],'video':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    import av
    with av.open(str(path)) as c:
        count=0
        for f in c.decode(video=0):
            if count in [75,175,325,425,550]:f.to_image().save(OUT/f'实际导出_{count:04d}.png')
            count+=1
    assert count==600;report['decoded_frames']=count
    (OUT/'说明与核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    sheet=Image.new('RGB',(1920,1080))
    for i,n in enumerate([75,175,325,425]):sheet.paste(Image.open(OUT/f'实际导出_{n:04d}.png').resize((960,540)),((i%2)*960,(i//2)*540))
    sheet.save(OUT/'实际导出联系表.jpg',quality=92)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
