# 2026-10-26 独立参考迁移版：路径/字体已本地化；历史事实与数值只供原案例复现。
"""Six-source spatial investigation after the rejected flat diagram.

The camera travels in a single 3D coordinate volume. Six source routes signify
a shared explanation, never measured flight tracks or confirmed same objects.
frame(phase,t,duration,clock=None,clock_offset=None,verdict_at=None,message_cues=None)
returns RGB 1920×1080. No personal marks or narration subtitles.
"""
from pathlib import Path
from functools import lru_cache
import argparse,json,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'参考库/动画/03_六路汇聚';OUT=BASE/'独立重渲染'
W,H,FPS=1920,1080,25;FONT=str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Regular.otf'); BOLD_FONT=str(ROOT/'参考库/动画/字体/NotoSansCJKsc-Bold.otf')
BLUE=(119,202,232);GOLD=(247,207,132);WHITE=(227,238,244);MUTED=(132,163,181)
PHASES=['intro','morphology','exposure','passenger','messages','converge','meaning','limits','verdict']
NAMES=['目标形态','照片长曝光','乘客见闻','网友转述','私人飞机留言','同期新闻']
SHORT=['闪烁圆点','常亮成线 · 闪烁成点','红光 · 小型飞机轮廓','“不明飞机”','“私人飞机”','“很可能是私人飞机”']
SOURCES=['杭州日报 · 机场工作人员转述','麻世俊照片 · 白涛摄影分析','都市快报 · FM808途经乘客','岚隐溪畔 · 转述乘客的机组消息','望洋之鱼 · 来自母亲的说法','中新社 · 2010年7月8日']
COLORS=[(131,214,244),(247,210,144),(142,194,225),(143,219,208),(224,179,122),(176,199,247)]
def clamp(x):return max(0.,min(1.,float(x)))
def ease(x):x=clamp(x);return x*x*(3-2*x)
def rgba(c,a=255):return tuple(c)+(max(0,min(255,round(a))),)
@lru_cache(maxsize=64)
def font(n,bold=False):return ImageFont.truetype(BOLD_FONT if bold else FONT,n)
def vec(az,alt,r):
 a,h=math.radians(az),math.radians(alt)
 return np.array([r*math.cos(h)*math.sin(a),r*math.cos(h)*math.cos(a),r*math.sin(h)])
POSITIONS=[vec(225,30,3.2),vec(175,12,3.25),vec(103,33,3.1),vec(35,22,3.5),vec(-23,28,3.2),vec(-95,10,3.25)]
SOURCE_FILES=[
 BASE/'证据/COMMENT_C02_NINGBO_完整楼层高光1080.png',
 BASE/'证据/COMMENT_C01_PRIVATE_完整楼层高光1080.png',
 BASE/'证据/E04b_中新社署名与匿名人士完整首段_高光1080.png',
]
@lru_cache(maxsize=3)
def source_page(i):return Image.open(SOURCE_FILES[i]).convert('RGB')
@lru_cache(maxsize=1)
def background():
 y,x=np.mgrid[0:H,0:W];g=np.exp(-(((x-1050)/800)**2+((y-530)/580)**2));floor=np.exp(-(((x-900)/850)**2+((y-775)/230)**2))
 return Image.fromarray(np.uint8(np.stack([3+g*5,7+g*12+floor*5,14+g*22+floor*8],axis=2)))
@lru_cache(maxsize=1)
def stars():
 rng=np.random.default_rng(20100707);a=rng.normal(size=(480,3));a/=np.linalg.norm(a,axis=1)[:,None]
 return a*rng.uniform(16,40,size=(480,1)),rng.uniform(.3,1,size=480)
class Scene:
 def __init__(self,az,elevation,distance,target=(0,0,.3),focal=1570):
  self.target=np.array(target,dtype=float);self.camera=self.target+vec(az,elevation,distance)
  self.forward=self.target-self.camera;self.forward/=np.linalg.norm(self.forward)
  self.right=np.cross(self.forward,[0,0,1]);self.right/=np.linalg.norm(self.right)
  self.up=np.cross(self.right,self.forward);self.focal=focal
  self.im=background().copy().convert('RGBA');self.layer=Image.new('RGBA',(W,H));self.d=ImageDraw.Draw(self.layer)
  self.glows=Image.new('RGBA',(W,H));self.g=ImageDraw.Draw(self.glows)
 def project(self,p):
  v=np.asarray(p)-self.camera;z=float(v@self.forward)
  if z<.25:return None
  return (960+float(v@self.right)*self.focal/z,490-float(v@self.up)*self.focal/z,z)
 def line(self,pts,color,width=1,alpha=255):
  pp=[self.project(x) for x in pts];pp=[(x[0],x[1]) for x in pp if x is not None]
  if len(pp)>1:self.d.line(pp,fill=rgba(color,alpha),width=width,joint='curve')
 def glow(self,p,color,r=5,alpha=255):
  q=self.project(p)
  if q is None:return
  x,y,z=q
  if not(-20<x<W+20 and -20<y<H+20):return
  self.g.ellipse((x-r*4,y-r*4,x+r*4,y+r*4),fill=rgba(color,alpha*.6))
  self.d.ellipse((x-r,y-r,x+r,y+r),fill=rgba(color,alpha));self.d.ellipse((x-1,y-1,x+1,y+1),fill=rgba(WHITE,alpha))
 def text(self,pos,s,size=24,color=WHITE,anchor='mm',alpha=255,bold=False):
  self.d.text(pos,s,font=font(size,bold),fill=rgba(color,alpha),anchor=anchor)
 def finish(self):
  self.im.alpha_composite(self.glows.filter(ImageFilter.GaussianBlur(14)));self.im.alpha_composite(self.layer);return self.im.convert('RGB')

def draw_space(sc,clock,amount=1):
 positions,brightness=stars()
 for point,b in zip(positions,brightness):
  p=sc.project(point)
  if p and 0<p[0]<W and 0<p[1]<H:
   x,y,z=p;r=.55 if b<.85 else 1.;sc.d.ellipse((x-r,y-r,x+r,y+r),fill=rgba((130,163,185),b*95))
 # Meridian and latitude arcs describe a volume, not a rectangular graph sheet.
 for az in range(0,360,30):sc.line([vec(az,h,3.8) for h in np.linspace(-70,70,45)],BLUE,1,18*amount)
 for alt in [-45,-20,0,25,50]:sc.line([vec(a,alt,3.8) for a in np.linspace(0,360,100)],BLUE,1,25*amount)
 sc.line([vec(a,0,3.84) for a in np.linspace(0,360,140)],(106,165,190),2,64*amount)
 for rr in [1.05,1.26,2.25]:sc.line([(rr*math.sin(a),rr*math.cos(a),-.62) for a in np.linspace(0,math.tau,100)],BLUE,1,38*amount)

def route(idx,p):
 a=POSITIONS[idx];end=np.array([0,0,.45]);tangent=np.cross(a,[0,0,1]);tangent/=max(.1,np.linalg.norm(tangent))
 b=a*.66+tangent*.65+np.array([0,0,.5]);c=a*.22-tangent*.45+np.array([0,0,.7]);q=1-p
 return q**3*a+3*q*q*p*b+3*q*p*p*c+p**3*end
def draw_routes(sc,active,clock,converge):
 for idx,amount in enumerate(active):
  if amount<=0:continue
  color=COLORS[idx];growth=ease(amount)
  sc.line([route(idx,p) for p in np.linspace(0,growth,100)],color,2,125)
  q=(clock*.115+idx*.14)%1
  if converge is not None:q=.1+.9*ease(converge)
  q=min(q,growth)
  for k in range(8):sc.glow(route(idx,max(0,q-.012*k)),color,r=2.1 if k else 3.8,alpha=(1-k/9)*180)
  sc.glow(POSITIONS[idx],color,r=4.4,alpha=185)

def transform(v,yaw):
 a=math.radians(yaw);c,s=math.cos(a),math.sin(a);x,y,z=v
 return np.array([x*c-y*s,x*s+y*c,z+.45])
def aircraft_mesh(yaw):
 faces=[];rings=[]
 for y,rx,rz in [(-1.36,.025,.035),(-1.12,.075,.07),(-.65,.12,.115),(.05,.135,.13),(.78,.10,.11),(1.14,.075,.085),(1.38,.012,.02)]:
  rings.append([transform((math.cos(a)*rx,y,math.sin(a)*rz),yaw) for a in np.linspace(0,math.tau,21)[:-1]])
 for a,b in zip(rings,rings[1:]):
  for i in range(20):faces.append([a[i],a[(i+1)%20],b[(i+1)%20],b[i]])
 for sign in [-1,1]:
  top=[(.08*sign,.25,.025),(1.36*sign,.03,.015),(1.46*sign,-.24,.015),(.11*sign,-.38,.02)];lower=[(x,y,z-.055) for x,y,z in top]
  faces.append([transform(v,yaw) for v in top]);faces.append([transform(v,yaw) for v in lower])
  for i in range(4):faces.append([transform(top[i],yaw),transform(top[(i+1)%4],yaw),transform(lower[(i+1)%4],yaw),transform(lower[i],yaw)])
  tail=[(.04*sign,-1.03,.045),(.57*sign,-1.17,.06),(.62*sign,-1.36,.06),(.03*sign,-1.26,.05)];faces.append([transform(v,yaw) for v in tail])
 faces.append([transform(v,yaw) for v in [(0,-.83,.06),(0,-1.08,.55),(0,-1.33,.46),(0,-1.28,.035)]])
 return faces,rings
def draw_aircraft(sc,clock,alpha=1):
 yaw=21+clock*1.55;faces,rings=aircraft_mesh(yaw);lamp=np.array([-.4,-.5,1.]);lamp/=np.linalg.norm(lamp);ordered=[]
 for face in faces:
  projected=[sc.project(p) for p in face]
  if any(p is None for p in projected):continue
  depth=sum(p[2] for p in projected)/len(projected);normal=np.cross(face[1]-face[0],face[2]-face[0]);normal/=max(.001,np.linalg.norm(normal))
  view=sc.camera-np.mean(face,axis=0);view/=np.linalg.norm(view);halfvec=lamp+view;halfvec/=np.linalg.norm(halfvec)
  diffuse=abs(float(normal@lamp));specular=abs(float(normal@halfvec))**28;rim=(1-abs(float(normal@view)))**3
  light=.48+.5*diffuse+.5*specular+.16*rim;color=tuple(min(255,round(v*light)) for v in (139,202,226));ordered.append((depth,projected,color))
 for _,projected,color in sorted(ordered,reverse=True,key=lambda r:r[0]):
  sc.d.polygon([(x,y) for x,y,z in projected],fill=rgba(color,245*alpha))
 # Continuous illuminated silhouettes keep the volume crisp without a mesh-grid look.
 for sign in [-1,1]:
  edge=[(.08*sign,.25,.025),(1.36*sign,.03,.015),(1.46*sign,-.24,.015),(.11*sign,-.38,.02)]
  sc.line([transform(v,yaw) for v in edge],(183,235,251),2,230*alpha)
  sc.line([transform(v,yaw) for v in [(.04*sign,-1.03,.045),(.57*sign,-1.17,.06),(.62*sign,-1.36,.06),(.03*sign,-1.26,.05)]],BLUE,2,195*alpha)
 for j in [0,5,10,15]:sc.line([r[j] for r in rings],(178,226,242),1,155*alpha)
 sc.line([transform(v,yaw) for v in [(0,-.83,.06),(0,-1.08,.55),(0,-1.33,.46),(0,-1.28,.035)]],(194,237,247),2,210*alpha)
 for sign in [-1,1]:
  sc.glow(transform((sign*1.40,-.09,.015),yaw),(131,222,250),3,115*alpha)
 sc.glow(transform((0,1.38,.02),yaw),WHITE,2,180*alpha)
 sc.glow(transform((-1.4,-.4,.015),yaw),(235,132,109),2.1,125*alpha);sc.glow(transform((1.4,-.4,.015),yaw),(123,204,176),2.1,125*alpha)

def phase_track(phase,p,t,duration,message_cues):
 if phase=='intro':return -.7+.7*ease(p),[0]*6,None,-1
 if phase=='morphology':k=0;u=p
 elif phase=='exposure':k=1;u=p
 elif phase=='passenger':k=2;u=p
 elif phase=='messages':
  cues=message_cues or [3.0222,6.1778,8.8]
  if t<cues[0]:return 3,[1,1,1,0,0,0],None,-1
  k=3 if t<cues[1] else 4 if t<cues[2] else 5;lo=cues[k-3];hi=cues[k-2] if k<5 else duration;u=clamp((t-lo)/max(.1,hi-lo))
 elif phase=='converge':return 6+ease(p),[1]*6,p,-1
 elif phase in ['meaning','limits','verdict']:return 7+(.12*ease(p) if phase=='meaning' else .12),[1]*6,1,-1
 else:raise ValueError(phase)
 active=[1 if i<k else ease(u/.55) if i==k else 0 for i in range(6)]
 return k+ease(u),active,None,k
CAMERAS=[(228,22,8.7),(187,16,8.5),(131,26,8.8),(73,12,9.0),(15,25,8.8),(-43,16,9.0),(-91,15,8.8),(-42,27,10.3)]
def camera_at(stage):
 if stage<0:
  p=clamp(stage+.7)/.7;return (243-15*p,32-10*p,11.2-2.5*p)
 i=min(6,int(stage));p=clamp(stage-i)
 if stage>=7:return (-42+(stage-7)*14,27,10.3)
 a,b=CAMERAS[i],CAMERAS[i+1];return tuple(a[j]+(b[j]-a[j])*p for j in range(3))
def active_geometry(sc,idx,clock,activation):
 if idx<0:return
 center=POSITIONS[idx];color=COLORS[idx]
 if idx==0:
  sc.glow(center,color,7+3*math.sin(clock*4)**2,240)
  for r in [.16,.29]:sc.line([center+vec(a,0,r) for a in np.linspace(0,360,70)],color,1,130)
 elif idx==1:
  tangent=np.cross(center,[0,0,1]);tangent/=np.linalg.norm(tangent);start=center-tangent*.45;end=center+tangent*.45
  sc.line([start,end],(243,217,171),4,200)
  for v in np.linspace(.05,.95,7):sc.glow(start+(end-start)*v+np.array([0,0,.11]),(239,226,212),2.8,200)
 elif idx==2:
  tangent=np.cross(center,[0,0,1]);tangent/=np.linalg.norm(tangent)
  pts=[center+tangent*.25*math.sin(a)+np.array([0,0,.4*math.cos(a)]) for a in np.linspace(0,math.tau,80)]
  sc.line(pts,color,2,190);sc.glow(center-np.array([0,0,.08]),(230,137,109),4,210)
 else:sc.glow(center,color,7,220)
def scene_labels(sc,active,idx,stage,phase,p):
 if idx>=0:
  q=sc.project(POSITIONS[idx]);x,y,_=q;x=max(340,min(1580,x));label_y=780
  name='机组说法（网友转述）' if idx==3 else NAMES[idx]
  sc.text((x,label_y),name,32,COLORS[idx],bold=True);sc.text((x,label_y+47),SHORT[idx],28,WHITE);sc.text((x,label_y+89),SOURCES[idx],20,MUTED)
 elif phase in ['converge','meaning','limits','verdict']:
  alpha=255*ease((p-.82)/.18) if phase=='converge' else 255
  for i,point in enumerate(POSITIONS):
   q=sc.project(point)
   if q is None:continue
   x,y,z=q;dx=-18 if x<960 else 18;anchor='rm' if x<960 else 'lm'
   sc.text((x+dx,y-24),NAMES[i],24,COLORS[i],anchor=anchor,alpha=alpha,bold=True)
def frame(phase,t,duration,clock=None,clock_offset=None,verdict_at=None,message_cues=None):
 p=clamp(t/max(.04,duration-.04));clock=float(clock) if clock is not None else float(clock_offset or 0)+t
 stage,active,converge,idx=phase_track(phase,p,t,duration,message_cues);az,el,dist=camera_at(stage)
 target=np.array([0.,0.,.3])
 sc=Scene(az,el,dist,target=target);draw_space(sc,clock);draw_routes(sc,active,clock,converge)
 draw_aircraft(sc,clock,.78+.22*min(1,sum(active)/5));active_geometry(sc,idx,clock,active[idx] if idx>=0 else 0);scene_labels(sc,active,idx,stage,phase,p)
 sc.text((54,42),'2010.07.07 / 萧山机场 · 线索推演',22,MUTED,anchor='lt')
 if phase in ['converge','meaning','limits']:
  alpha=ease((p-.40)/.25) if phase=='converge' else 1;sc.text((960,836),'飞机',57,WHITE,alpha=255*alpha,bold=True);sc.text((960,890),'共同的解释方向',23,BLUE,alpha=230*alpha)
 if phase=='limits':sc.text((960,939),'线索汇合，不等于已经确认是同一个目标',21,MUTED,alpha=255*ease(p/.3))
 if phase=='verdict':
  at=3.82 if verdict_at is None else verdict_at;a=ease((t-at)/.65)
  if t<at:sc.text((960,836),'飞机',57,WHITE,bold=True)
  sc.text((960,822),'本片判断',23,MUTED,alpha=255*a);sc.text((960,880),'私人飞机黑飞',57,WHITE,alpha=255*a,bold=True)
 result=sc.finish()
 if phase=='messages' and idx>=3:
  cues=message_cues or [3.0222,6.1778,8.8];lo=cues[idx-3];hi=cues[idx-2] if idx<5 else duration
  local=t-lo;hold=min(2.4,(hi-lo)*.55);fade=min(.16,(hi-lo)*.12)
  # Real pages occupy the entire screen first, then dissolve into their own route.
  # No inset boxes, no composited card wall, and no rescaling of the original text.
  if local<hold+fade:
   original=source_page(idx-3)
   if local<hold:result=original.copy()
   else:result=Image.blend(original,result,ease((local-hold)/fade))
 return result
def get_frame(shot,t):
 return frame(shot.get('phase',shot.get('scene','intro')),t,shot.get('duration') or shot['end']-shot['start'],clock=shot.get('clock'),clock_offset=shot.get('clock_offset'),verdict_at=shot.get('verdict_at'),message_cues=shot.get('message_cues'))
def main():
 import av
 ap=argparse.ArgumentParser();ap.add_argument('--preview',action='store_true');args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
 for name,phase,t,dur in [('空间近察','exposure',3.4,8),('三路分开','messages',9.7,13.04),('空间汇合','converge',5.8,8)]:frame(phase,t,dur,clock=13+t).save(OUT/f'三维样帧_{name}.jpg',quality=97)
 if args.preview:
  sequence=[('intro',1),('morphology',1.2),('exposure',1.28),('passenger',1.2),('messages',2.4),('converge',2),('meaning',.92)];i=0
  with av.open(str(OUT/'六路线索_三维镜头预览.mp4'),'w') as c:
   s=c.add_stream('libx264',rate=25);s.width=W;s.height=H;s.pix_fmt='yuv420p';s.options={'crf':'18','preset':'fast','threads':'2'}
   for phase,dur in sequence:
    for j in range(round(dur*25)):
     im=frame(phase,j/25,dur,clock=i/25,message_cues=[0,.8,1.6] if phase=='messages' else None);f=av.VideoFrame.from_image(im);f.pts=i;i+=1
     for pk in s.encode(f):c.mux(pk)
   for pk in s.encode():c.mux(pk)
  print('preview frames',i)
 (OUT/'接口_空间版.json').write_text(json.dumps({'version':'six_sources_3d','phases':PHASES,'message_cues_default':[3.0222,6.1778,8.8],'sources':list(zip(NAMES,SOURCES)),'note':'Six material classes; paths are not actual flight tracks or proof of same-aircraft identity.'},ensure_ascii=False,indent=2)+'\n')
 (OUT/'README.md').write_text('# 当前看六路三维版\n\n当前样品是 `六路线索_三维镜头预览.mp4`，构图见 `三维样帧_*.jpg`。\n\n此前平面四节点样品已被否定，移入 `旧稿_四节点`，不用于最终成片。\n')
if __name__=='__main__':main()
