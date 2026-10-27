#!/usr/bin/env python3
"""Independent original-pixel evidence animation; configurations are relative to their own file.
Modes: fullframe, capture_focus, page_scroll, cursor_click. Never retype evidence.
"""
from pathlib import Path
from functools import lru_cache
import argparse, hashlib, json, math
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT=Path(__file__).resolve().parents[2]
W,H=1920,1080
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clamp(p):return max(0.,min(1.,p))
def ease(p):p=clamp(p);return p*p*(3-2*p)
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def resolve(base,p):return (base/p).resolve()
@lru_cache(maxsize=16)
def imread(p):return Image.open(p).convert('RGB')
@lru_cache(maxsize=16)
def font(size):
 primary=Path('/System/Library/Fonts/Hiragino Sans GB.ttc')
 return ImageFont.truetype(str(primary if primary.exists() else ROOT/'参考库/动画/字体/NotoSansCJKsc-Regular.otf'),size)
def underline(im,segments,p,width=5,color=(230,67,52)):
 left=sum(math.hypot(r[2]-r[0],r[3]-r[1]) for r in segments)*clamp(p);d=ImageDraw.Draw(im)
 for x1,y1,x2,y2 in segments:
  n=math.hypot(x2-x1,y2-y1);q=min(1.,left/max(n,.001))
  if q<=0:break
  xe=x1+(x2-x1)*q;ye=y1+(y2-y1)*q
  d.line((round(x1),round(y1),round(xe),round(ye)),fill=tuple(color),width=width)
  d.ellipse((xe-width/2,ye-width/2,xe+width/2,ye+width/2),fill=tuple(color));left-=n
def footer(im,cfg):
 if not cfg:return im
 assert cfg.get('safe_area_confirmed') is True,'Bottom footer needs explicit safe-area confirmation'
 d=ImageDraw.Draw(im);d.rectangle((0,870,W,H),fill=(16,20,26))
 lines=cfg.get('lines',[]);assert len(lines)<=2
 for i,s in enumerate(lines):
  size=cfg.get('font_sizes',[27,23])[i]
  assert d.textlength(s,font=font(size))<=1856,'Footer too long: edit label, do not shrink page'
  d.text((32,cfg.get('first_y',884)+42*i),s,font=font(size),fill=(230,235,244) if i==0 else (173,187,205))
 return im
def captured(base,cfg):
 cp=resolve(base,cfg['capture']);cap=read(cp);r=next(r for r in cap['regions'] if r['id']==cfg['region'])
 raw=imread(str(cp.parent/r['image']));k=W/raw.width
 # No non-uniform stretch: only the declared 720 x 326.25 CSS crop is 1920 x 870.
 h=round(raw.height*k);assert abs(h-870)<=2,'Use a 1920:870 source region for this composition'
 src=raw.resize((W,870),Image.Resampling.LANCZOS)
 dim=Image.blend(src.filter(ImageFilter.GaussianBlur(cfg.get('blur',8.5))),Image.new('RGB',src.size,(16,20,26)),cfg.get('dim',.36))
 mask=Image.new('L',src.size,0);d=ImageDraw.Draw(mask)
 b=r['focus_rect_image_pixels'];box=[round(v*k) for v in b]
 d.rectangle((box[0]-10,box[1]-10,box[2]+10,box[3]+10),fill=255)
 frame=Image.new('RGB',(W,H),(16,20,26));frame.paste(Image.composite(src,dim,mask.filter(ImageFilter.GaussianBlur(1.2))),(0,0))
 marks={m['id']:[[a*k,b*k+5,c*k,b*k+5] for a,_,c,b in m['rects_image_pixels']] for m in r['marks']}
 return frame,marks,r
def cursor(im,x,y,click):
 d=ImageDraw.Draw(im)
 if click>0:
  r=8+24*click;d.ellipse((x-r,y-r,x+r,y+r),outline=(170,66,47),width=3)
 d.polygon([(x,y),(x+8,y+39),(x+16,y+27),(x+28,y+33),(x+33,y+25),(x+20,y+19),(x+33,y+11)],fill=(245,240,227),outline=(40,43,40),width=2)
class Renderer:
 def __init__(self,path):
  self.path=Path(path).resolve();self.base=self.path.parent;self.cfg=read(self.path);c=self.cfg;self.mode=c['mode'];self.duration=float(c['duration']);self.fps=int(c.get('fps',25));self.inputs=[self.path,Path(__file__).resolve()]
  assert self.duration>0 and self.mode in ['fullframe','capture_focus','page_scroll','cursor_click']
  self.marks=c.get('marks',{});self.base_image=None
  for k in ['source','target','capture']:
   if k in c:self.inputs.append(resolve(self.base,c[k]))
  if self.mode=='capture_focus':
   self.base_image,self.marks,r=captured(self.base,c);self.inputs.append(resolve(self.base,c['capture']).parent/r['image'])
  else:
   self.base_image=imread(str(resolve(self.base,c['source'])))
   if self.mode in ['fullframe','cursor_click']:assert self.base_image.size==(W,H),'fullframe preserves original geometry'
  if self.mode=='page_scroll':
   self.target=imread(str(resolve(self.base,c['target'])));assert self.target.size==(W,H)
  for cue in c.get('cues',[]):assert cue['mark'] in self.marks,'Missing actual original-pixel coordinates: '+cue['mark']
 def frame(self,t):
  c=self.cfg;im=self.base_image.copy()
  if self.mode=='page_scroll':
   s=c['scroll'];q=ease((t-s['start'])/s['duration']);cy=s['from_y']+(s['to_y']-s['from_y'])*q;dpr=s['dpr'];x=s.get('x',0);width=s['width'];height=s['height']
   im=im.crop((round(x*dpr),round(cy*dpr),round((x+width)*dpr),round((cy+height)*dpr))).resize((W,H),Image.Resampling.LANCZOS)
   tr=c.get('target_transition',{'start':2.4,'duration':.4})
   if t>tr['start']:im=Image.blend(im,self.target,ease((t-tr['start'])/tr['duration']))
   ui=c.get('editorial_find_overlay')
   if ui and t<ui['until']:
    layer=Image.new('RGBA',(W,H));d=ImageDraw.Draw(layer);d.rounded_rectangle((1375,30,1888,118),13,fill=(18,24,31,242),outline=(92,107,120),width=2)
    d.text((1395,44),'页内查找',font=font(21),fill=(162,178,194));n=sum(t>x for x in ui['character_times']);d.text((1517,41),ui['text'][:n],font=font(31),fill=(241,229,196));d.text((1770,48),'↵',font=font(24),fill=(162,178,194))
    im=Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')
  if self.mode=='cursor_click':
   u=c['cursor'];p=clamp(t/self.duration);q=ease(p/u['move_fraction']);x=u['from'][0]+(u['to'][0]-u['from'][0])*q;y=u['from'][1]+(u['to'][1]-u['from'][1])*q
   cursor(im,x,y,max(0,1-abs(p-u['click_fraction'])/u['pulse_halfwidth']))
  for cue in c.get('cues',[]):
   p=(t-cue['start'])/cue.get('draw_duration',.52)
   underline(im,self.marks[cue['mark']],ease(p) if cue.get('ease') else p,cue.get('width',5),cue.get('color',[230,67,52]))
  return footer(im,c.get('footer'))
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('config',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();r=Renderer(a.config);out=a.output.resolve();report=out.with_suffix('.json');out.parent.mkdir(parents=True,exist_ok=True)
 deps=[{'path':str(p),'sha256':sha(p)} for p in r.inputs];signature=hashlib.sha256(json.dumps([x['sha256'] for x in deps]).encode()).hexdigest()
 if out.exists():
  if report.exists() and read(report).get('input_signature')==signature and read(report).get('sha256')==sha(out):print(json.dumps({'status':'reused_verified_cache','output':str(out)},ensure_ascii=False));return
  raise FileExistsError('Output exists with different inputs; use a new versioned output path')
 n=round(r.duration*r.fps);writer=imageio_ffmpeg.write_frames(str(out),(W,H),fps=r.fps,codec='libx264',pix_fmt_in='rgb24',pix_fmt_out='yuv420p',macro_block_size=1,output_params=['-crf','18','-preset','fast'])
 writer.send(None)
 try:
  for i in range(n):writer.send(np.asarray(r.frame(i/r.fps)))
 finally:writer.close()
 times=r.cfg.get('review_times',[0,r.duration/2,max(0,r.duration-.04)]);samples=[]
 for i,t in enumerate(times):
  p=out.with_name(out.stem+f'_检查{i:02d}_{t:.2f}s.png');r.frame(t).save(p);samples.append({'path':p.name,'time':t,'sha256':sha(p)})
 primary=Path('/System/Library/Fonts/Hiragino Sans GB.ttc')
 data={'status':'rendered_requires_decode_and_visual_review','output':str(out),'sha256':sha(out),'duration':n/r.fps,'frames':n,'size':[W,H],'fps':r.fps,'audio':False,'mode':r.mode,'source_pixels_retyped':False,'input_signature':signature,'inputs':deps,'review_samples':samples,'font_used':'Hiragino Sans GB' if primary.exists() else 'Noto Sans CJK SC fallback; different glyphs','editorial_ui_not_live_site_recording':r.mode in ['page_scroll','cursor_click']}
 report.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':data['status'],'output':str(out),'frames':n},ensure_ascii=False))
if __name__=='__main__':main()
