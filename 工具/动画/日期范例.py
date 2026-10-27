# 2026-10-26 独立参考迁移版：路径/字体已本地化；历史事实与数值只供原案例复现。
"""A practical tabletop date check, with real paper deformation and clock hands.

Import frame(phase, p, width=1280, height=720) -> RGB PIL Image.
Phases: source, timezone, to_event, event, to_next, gap.
p is local normalized time. Source pixels are fixed within the source shot.
This module neither submits generation requests nor changes the approved script.
"""
from pathlib import Path
from functools import lru_cache
from datetime import date, timedelta
import argparse, hashlib, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'参考库/动画/01_星月与日期'
EVIDENCE=BASE/'证据'
W,H=1280,720
INK=(43,46,42);PAPER=(238,228,203);RED=(156,61,45)
FONT=str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Regular.otf');BOLD=str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Bold.otf');MONO=str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Regular.otf')

def clamp(x):return max(0.,min(1.,float(x)))
def ease(x):x=clamp(x);return x*x*(3-2*x)
@lru_cache(maxsize=64)
def font(n,bold=False,mono=False):return ImageFont.truetype(MONO if mono else BOLD if bold else FONT,n)
def center(d,xy,text,size,fill=INK,bold=False,mono=False):
 f=font(size,bold,mono);box=d.textbbox((0,0),text,font=f);d.text((xy[0]-(box[2]-box[0])/2,xy[1]-(box[3]-box[1])/2-box[1]),text,font=f,fill=fill)

@lru_cache(maxsize=1)
def desk():
 y,x=np.mgrid[:H,:W];rng=np.random.default_rng(20100707)
 grain=rng.normal(0,1.1,(H,W))+1.3*np.sin(y*.72+x*.001)+.8*np.sin(y*.11+x*.018)
 light=20*np.exp(-((x-635)**2/(620**2)+(y-335)**2/(460**2)))
 edge=1-.23*((x-W/2)/(W/2))**2-.16*((y-H/2)/(H/2))**2
 rgb=np.stack([(35+light+grain)*edge,(39+light*.82+grain)*edge,(38+light*.59+grain)*edge],axis=2)
 im=Image.fromarray(np.uint8(np.clip(rgb,0,255)),'RGB').convert('RGBA');d=ImageDraw.Draw(im)
 # Quiet physical desk seams, a document corner, and a brass pencil.
 d.line([(0,664),(1280,666)],fill=(19,22,20),width=2)
 d.polygon([(1125,0),(1280,0),(1280,180),(1170,202)],fill=(62,61,50))
 d.line([(1135,494),(1216,642)],fill=(11,14,13),width=13)
 d.line([(1130,490),(1212,639)],fill=(163,122,62),width=8)
 d.line([(1128,489),(1209,635)],fill=(208,172,100),width=2)
 d.polygon([(1210,634),(1220,659),(1205,644)],fill=(189,168,126))
 d.polygon([(1215,650),(1220,659),(1212,653)],fill=(41,41,38))
 return im

def shadow(im,polygon,blur=12,opacity=95,offset=(8,12)):
 xy=[(x+offset[0],y+offset[1]) for x,y in polygon];pad=blur*3
 l=max(0,int(min(x for x,y in xy)-pad));t=max(0,int(min(y for x,y in xy)-pad))
 r=min(W,int(max(x for x,y in xy)+pad+1));b=min(H,int(max(y for x,y in xy)+pad+1))
 if r<=l or b<=t:return
 layer=Image.new('RGBA',(r-l,b-t));d=ImageDraw.Draw(layer)
 d.polygon([(x-l,y-t) for x,y in xy],fill=(0,0,0,opacity));im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)),(l,t))

def quad_image(im,tex,quad,shade=1.,alpha=255):
 """Perspective warp only the local bounding rectangle, not a whole-frame layer."""
 xs=[v[0] for v in quad];ys=[v[1] for v in quad]
 l=max(0,int(math.floor(min(xs))));t=max(0,int(math.floor(min(ys))));r=min(W,int(math.ceil(max(xs))));b=min(H,int(math.ceil(max(ys))))
 if r<=l or b<=t:return
 dst=[(x-l,y-t) for x,y in quad];tw,th=tex.size;src=[(0,0),(tw,0),(tw,th),(0,th)]
 A=[];B=[]
 for (x,y),(u,v) in zip(dst,src):
  A.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]]);B.extend([u,v])
 try:coeff=np.linalg.solve(np.asarray(A,float),np.asarray(B,float))
 except np.linalg.LinAlgError:return
 patch=tex.transform((r-l,b-t),Image.Transform.PERSPECTIVE,coeff,Image.Resampling.BICUBIC)
 if shade!=1.:
  arr=np.array(patch);arr[:,:,:3]=np.clip(arr[:,:,:3].astype(float)*shade,0,255).astype(np.uint8);patch=Image.fromarray(arr)
 if alpha<255:patch.putalpha(patch.getchannel('A').point(lambda v:int(v*alpha/255)))
 im.alpha_composite(patch,(l,t))

@lru_cache(maxsize=36)
def calendar_tex(month,day,tag='',time='',is_back=False):
 w,h=390,430;rng=np.random.default_rng(month*100+day)
 noise=rng.normal(0,.65,(h,w));arr=np.empty((h,w,4),np.uint8)
 for i,c in enumerate(PAPER):arr[:,:,i]=np.clip(c+noise,0,255)
 arr[:,:,3]=255;im=Image.fromarray(arr);d=ImageDraw.Draw(im)
 if is_back:
  for yy in range(46,400,23):d.line([(25,yy),(365,yy)],fill=(225,216,195),width=1)
  return im
 d.rectangle((0,0,w,56),fill=(113,49,39));center(d,(195,27),'2010',24,(239,224,197),mono=True)
 center(d,(195,94),f'{month}月',30,INK)
 center(d,(195,221),str(day),156,RED if tag=='萧山这晚' else INK,bold=True)
 weekday='一二三四五六日'[date(2010,month,day).weekday()]
 center(d,(195,325),'星期'+weekday,18,(95,96,82))
 d.line([(36,350),(354,350)],fill=(178,172,150),width=1)
 if tag:center(d,(195,374),tag,23,RED if tag=='萧山这晚' else INK,bold=True)
 if time:center(d,(195,408),time,17,(93,94,83),mono=False)
 return im

def page_quad(cx,cy,w=390,h=430,angle=-3):
 a=math.radians(angle);ca,sa=math.cos(a),math.sin(a)
 return [(cx+(x-w/2)*ca-(y-h/2)*sa,cy+(x-w/2)*sa+(y-h/2)*ca) for x,y in [(0,0),(w,0),(w,h),(0,h)]]

def loose_page(im,month,day,cx,cy,w=215,h=237,angle=-12,tag='',time=''):
 q=page_quad(cx,cy,w,h,angle);shadow(im,q,7,80,(7,9));quad_image(im,calendar_tex(month,day,tag,time),q)

def calendar_base(im,month,day,x=500,y=207,tag='',time=''):
 w,h=390,430;d=ImageDraw.Draw(im)
 shadow(im,[(x-15,y-28),(x+w+18,y-28),(x+w+18,y+h+21),(x-15,y+h+21)],16,150)
 d.rounded_rectangle((x-16,y-28,x+w+18,y+h+20),radius=10,fill=(78,66,52),outline=(132,110,77),width=2)
 for k in range(7,0,-1):d.rectangle((x+k,y+k*1.7,x+w+k,y+h+k*1.7),fill=(203+k*2,195+k*2,176+k*2),outline=(177,169,150))
 im.alpha_composite(calendar_tex(month,day,tag,time),(x,y))

def rings(im,x=500,y=207):
 d=ImageDraw.Draw(im)
 for xx in [x+72,x+318]:
  d.ellipse((xx-10,y-14,xx+10,y+9),fill=(74,62,43),outline=(31,33,30),width=2)
  d.arc((xx-10,y-29,xx+11,y+10),185,530,fill=(172,170,150),width=5)
  d.arc((xx-8,y-28,xx+9,y+8),195,360,fill=(227,221,192),width=2)

def curled_page(im,month,day,progress,x=500,y=207):
 """A curved 3-D sheet, split into 28 strips, with a real reverse face."""
 theta=math.pi*ease(progress);w,h=390,430;D=1050.;N=28
 front=calendar_tex(month,day);back=calendar_tex(month,day,is_back=True)
 pts=[]
 for i in range(N+1):
  v=i/N;a=theta*(.58+.42*v);yy=v*h*math.cos(a);z=v*h*math.sin(a)
  persp=D/(D-z);curl=(math.sin(v*math.pi)*math.sin(theta))*17
  pts.append([(x+w/2+(u-w/2)*persp+curl,y+yy*persp) for u in [0,w]])
 outline=[r[0] for r in pts]+[r[1] for r in pts[::-1]]
 shadow(im,outline,14,100,offset=(10+24*math.sin(theta),16+22*math.sin(theta)))
 # Strip order handles the page folding back over itself.
 order=range(N) if theta<math.pi*.5 else range(N-1,-1,-1)
 for i in order:
  v=(i+.5)/N;a=theta*(.58+.42*v);reverse=math.cos(a)<0
  a0=int(i*h/N);a1=int((i+1)*h/N)+1
  tex=(back if reverse else front).crop((0,a0,w,min(h,a1)))
  quad=[pts[i][0],pts[i][1],pts[i+1][1],pts[i+1][0]]
  shade=.94-.19*abs(math.sin(a)) if reverse else .98-.12*abs(math.sin(a))
  quad_image(im,tex,quad,shade=shade)
 # Highlight the moving free edge and paper curl, not the source-page pixels.
 d=ImageDraw.Draw(im);d.line([tuple(pts[-1][0]),tuple(pts[-1][1])],fill=(244,235,211),width=2)

def clock(im,cx,cy,total_minutes,label,date_label,accent=False,r=137):
 d=ImageDraw.Draw(im);shadow(im,[(cx-r,cy-r),(cx+r,cy-r),(cx+r,cy+r),(cx-r,cy+r)],15,125)
 for rad,col in [(r+8,(38,40,37)),(r+4,(144,135,109)),(r,(69,70,61)),(r-6,(226,216,191))]:d.ellipse((cx-rad,cy-rad,cx+rad,cy+rad),fill=col)
 for k in range(60):
  a=k*math.pi/30;ln=12 if k%5==0 else 5;rr=r-16
  d.line((cx+math.sin(a)*rr,cy-math.cos(a)*rr,cx+math.sin(a)*(rr-ln),cy-math.cos(a)*(rr-ln)),fill=(74,77,65),width=2 if k%5==0 else 1)
 for n in range(1,13):
  a=n*math.pi/6;center(d,(cx+math.sin(a)*(r-40),cy-math.cos(a)*(r-40)),str(n),20,INK,mono=True)
 for mins,length,width,col in [(total_minutes/12,r*.49,7,INK),(total_minutes,r*.76,4,RED if accent else INK)]:
  a=mins*math.pi/30
  d.line((cx-math.sin(a)*10,cy+math.cos(a)*10,cx+math.sin(a)*length,cy-math.cos(a)*length),fill=col,width=width)
 d.ellipse((cx-6,cy-6,cx+6,cy+6),fill=(154,76,48))
 center(d,(cx,cy+r+31),label,20,(211,208,186));center(d,(cx,cy+r+60),date_label,18,(173,180,166),mono=True)

@lru_cache(maxsize=1)
def raw_date_strip():
 m=json.loads((EVIDENCE/'manifest.json').read_text('utf-8'));a=next(x for x in m['assets'] if x['id']=='NASA_date')
 r=next(x['box'] for x in a['focus_regions'] if x['label']=='June 30 at 11:35 a.m. EDT')
 im=Image.open(EVIDENCE/a['plain_path']).convert('RGBA');l,t,rgt,b=r
 return im.crop((int(l)-3,int(t)-2,int(rgt)+3,int(b)+2))

def source_slip(im,x=74,y=565):
 # Original date pixels always remain fixed and upright in this scene.
 d=ImageDraw.Draw(im);q=[(x,y),(x+510,y),(x+510,y+86),(x,y+86)];shadow(im,q,8,95,(5,7));d.rectangle((x,y,x+510,y+86),fill=(238,235,219))
 d.text((x+15,y+10),'NASA 原文 · 发射时间',font=font(14),fill=(88,94,83))
 raw=raw_date_strip();raw.thumbnail((480,38),Image.Resampling.LANCZOS);im.alpha_composite(raw,(x+15,y+40))
 d.ellipse((x+250,y-5,x+261,y+6),fill=(136,61,43),outline=(204,150,109),width=1)

def note(im,xy,text,size=18,color=(197,198,181)):
 ImageDraw.Draw(im).text(xy,text,font=font(size),fill=color)

def stamp_circle(im,x,y,r,progress=1,color=(153,59,43),width=4):
 d=ImageDraw.Draw(im);pts=[]
 for k in range(max(2,int(120*clamp(progress)))):
  a=(k/119)*math.tau-.6;rr=r+math.sin(a*3)*2;pts.append((x+math.cos(a)*rr,y+math.sin(a)*rr*.88))
 if len(pts)>1:d.line(pts,fill=color,width=width)

def scene(phase,p,captions=True):
 p=clamp(p)
 if phase=='source':
  # Genuine evidence holds still. Only a separate editorial underline draws on.
  im=Image.open(EVIDENCE/'NASA_context.png').convert('RGB').resize((W,H),Image.Resampling.LANCZOS).convert('RGBA')
  d=ImageDraw.Draw(im);d.rectangle((0,0,W,38),fill=(20,28,28,255));d.text((22,8),'NASA · 2010年任务文章 · 网页归档',font=font(17),fill=(233,228,207))
  return im
 im=desk().copy()
 if phase=='timezone':
  mins=11*60+35;shift=12*60*ease((p-.13)/.62);target=mins+shift
  clock(im,320,235,mins,'EDT  美国东部夏令时','JUN 30  ·  11:35 AM')
  clock(im,925,235,target,'北京  UTC+8',f'JUN 30  ·  {int(target//60):02d}:{int(target%60):02d}',True)
  center(ImageDraw.Draw(im),(622,232),'+12',56,(194,166,111),mono=True)
  center(ImageDraw.Draw(im),(622,279),'小时',18,(177,183,166))
  source_slip(im,75,566 if captions else 530)
  loose_page(im,6,30,780,563,160,176,4,tag='',time='23:35' if p>.76 else '')
  if p>.82:stamp_circle(im,780,563,49,ease((p-.82)/.17),width=3)
 elif phase in ['to_event','event']:
  cy=207 if captions else 190
  k=min(6,int(p*7));local=(p*7-k) if p<1 else 1
  if phase=='event':k=7;local=1
  dates=[date(2010,6,30)+timedelta(days=i) for i in range(8)]
  # Removed daily leaves gather into a real pile beside the calendar.
  for i in range(min(k,6)):
   dt=dates[i];loose_page(im,dt.month,dt.day,190+12*i,412+11*i,210,232,-18+6*i)
  if phase=='to_event' and p<.995:
   nxt=dates[k+1];calendar_base(im,nxt.month,nxt.day,y=cy,tag='萧山这晚' if k==6 else '',time='7月7日晚' if k==6 else '')
   cur=dates[k];curled_page(im,cur.month,cur.day,local,y=cy)
  else:calendar_base(im,7,7,y=cy,tag='萧山这晚',time='停航与目击的当晚')
  rings(im,y=cy)
  if phase=='event':
   loose_page(im,6,30,235,400,240,265,-9,tag='进步号发射',time='北京时间 23:35')
   stamp_circle(im,695,cy+221,110,ease(p/.42))
   if p>.42 and captions:note(im,(132,615),'早了将近七天',28)
 elif phase=='to_next':
  cy=207 if captions else 190
  dates=[date(2010,7,7)+timedelta(days=i) for i in range(5)];k=min(3,int(p*4));local=p*4-k if p<1 else 1
  loose_page(im,6,30,190,427,205,226,-15,tag='进步号发射',time='23:35')
  loose_page(im,7,7,320,470,205,226,10,tag='萧山这晚')
  if p<.995:
   nxt=dates[k+1];calendar_base(im,nxt.month,nxt.day,y=cy,tag='下一次公开轨道发射' if k==3 else '',time='北京时间 02:40' if k==3 else '')
   cur=dates[k];curled_page(im,cur.month,cur.day,local,y=cy)
  else:calendar_base(im,7,11,y=cy,tag='下一次公开轨道发射',time='北京时间 02:40')
  rings(im,y=cy)
 elif phase=='gap':
  # The same three physical sheets now lie next to one another on the desk.
  loose_page(im,6,30,252,333,280,309,-7,tag='进步号发射',time='北京时间 23:35')
  loose_page(im,7,11,1005,333,280,309,7,tag='下一次公开轨道发射',time='北京时间 02:40')
  yy=615-260*ease(p/.4)
  loose_page(im,7,7,633,yy,300,331,-1,tag='萧山这晚')
  if p>.45:stamp_circle(im,633,yy+5,90,ease((p-.45)/.25))
  if p>.76 and captions:
   note(im,(410,582),'这晚，没找到对应的入轨发射',23)
   note(im,(383,627),'公开轨道记录；不据此排除导弹、亚轨道或旧碎片',16,(147,160,149))
 else:raise ValueError('Unknown phase: '+str(phase))
 # A calm engraved date reference, never falsely claiming a measured event second.
 note(im,(32,25),'2010  /  日期核对',15,(116,130,118))
 return im

def frame(phase,p,width=1280,height=720,captions=True):
 """Return a single frame; sources can be reordered against actual narration."""
 im=scene(phase,p,captions=captions).convert('RGB')
 return im if (width,height)==(W,H) else im.resize((int(width),int(height)),Image.Resampling.LANCZOS)

DEMO=[('source',3),('timezone',7),('to_event',8),('event',4),('to_next',6),('gap',7)]
def artframes():
 out=BASE/'日期动画/美术帧';out.mkdir(parents=True,exist_ok=True)
 cases=[('01_双时区拨针','timezone',.66),('02_翻到事发当晚','to_event',.50),('03_日期错位','event',.90),('04_翻查下一次发射','gap',.90)]
 for name,phase,p in cases:frame(phase,p).save(out/(name+'.png'))
 sheet=Image.new('RGB',(1280,1440))
 for i,(name,phase,p) in enumerate(cases):sheet.paste(frame(phase,p).resize((640,360)),((i%2)*640,(i//2)*360))
 sheet=sheet.crop((0,0,1280,720));sheet.save(out/'四帧联图.jpg',quality=95)
 return out

def render_demo():
 import imageio_ffmpeg
 out=BASE/'日期动画';out.mkdir(parents=True,exist_ok=True)
 target=out/'日期查证_动作演示_35秒_720p.mp4';fps=25
 writer=imageio_ffmpeg.write_frames(str(target),(W,H),fps=fps,codec='libx264',quality=None,ffmpeg_log_level='error',output_params=['-crf','19','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart']);writer.send(None)
 timeline=[];start=0
 for phase,duration in DEMO:
  timeline.append({'phase':phase,'start':start,'end':start+duration,'narration':'none; demonstration only'})
  count=int(duration*fps)
  for i in range(count):writer.send(np.asarray(frame(phase,i/max(1,count-1))))
  print(phase,flush=True);start+=duration
 writer.close()
 info={'video':target.name,'duration':start,'fps':fps,'size':[W,H],'audio':'无旁白，无配乐，动画组件演示，非最终片','phases':timeline,'paid_api_calls':0,'evidence_audit':'../../核验/发射与评论核对.json','constraints':['原文来源镜头固定不抖','EDT+12小时=北京时间，仍为6月30日','7月7日晚未锁定秒级目击时刻','7月11日为下一次公开轨道发射，不包办旧碎片再入'],'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 (out/'演示说明.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),'utf-8');return target

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--demo',action='store_true');args=parser.parse_args();print(artframes(),flush=True)
 if args.demo:print(render_demo(),flush=True)
