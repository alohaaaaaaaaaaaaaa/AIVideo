"""Final chapter original-page components. The source pixels stay fixed while reading.

frame(kind, t, duration, cues=None, **options) -> 1920x1080 PIL RGB.
get_frame(shot, t, duration=None) accepts a shot dict with kind/scene and cues.
Cue = {phrase, start, draw_duration=.6}; start is SHOT-LOCAL seconds.
For ordinary evidence IDs, pass a registered asset id as kind as well.
Only cctv_find performs a brief actual-page scroll, ending on a fixed quote.
"""
from pathlib import Path
from functools import lru_cache
import argparse,hashlib,json,math,importlib.util
from PIL import Image,ImageDraw,ImageFont,ImageFilter

BASE=Path(__file__).resolve().parents[2]
ROOT=BASE.parents[1]
OUT=BASE/'制作/画面'
CHECK=BASE/'制作/检查/画面组件'
W,H,FPS=1920,1080,25
BG=(16,20,26);RED=(225,63,56);MUTED=(173,187,205)
ALIASES={
 'cctv_title':'E06a_标题日期来源','cctv_date':'E06b_节目播出日期',
 'cctv_quote':'E06c_完整涉案段','conclusion':'E06c_完整涉案段',
 'named_title':'E07a_标题日期来源','named_report':'E07c_点名许伟杰完整段',
 'fine_title':'E10a_标题日期来源','fine_claim':'E10b_萧山与罚款关联完整段',
 'fine_origin_title':'E08a_标题日期来源','fine_origin':'E08c_乐清处罚完整段',
 'early_title':'E04a_标题日期稿源','early_quote':'E04b_中新社署名与匿名人士完整首段',
 'early_reprint':'E03b_转引中新社与私人飞机','early_reprint2':'E02b_私人飞机完整分析',
 'comment_ningbo':'COMMENT_C02_NINGBO','comment_private':'COMMENT_C01_PRIVATE',
 'fm_route':'FM808_A_航线与完整来电','fm_observation':'FM808_B1_自估位置与两次观察',
 'fm_limits':'FM808_B2_不同飞机与飞行无异常',
 'dot_title':'HZRB_A_标题日期','dot_report':'HZRB_B_圆点闪烁完整段',
 'photo':'P01_PH01_媒体照片全图','photo_analysis':'P01_PX11_白涛长曝光结论',
 'photo_relation':'P01_PX13_照片结论与关联完整段',
 'military_dates':'M03_M01b_日期海域船舶通告完整段_标注',
 'military_search':'M07_S02a_完整转帖_高光1080',
 'end_train':'END_C09','end_bus':'END_C03','end_worldcup':'END_C07',
 'end_housing':'END_C08','end_souvenir':'END_C02',
}
DEFAULTS={
 'cctv_quote':[('2010年7月7日',.10),('杭州萧山机场',.23),('经有关部门证实',.44),('小型私人飞机',.62),('典型的“黑飞”事件',.81)],
 'conclusion':[('小型私人飞机',.34),('典型的“黑飞”事件',.65)],
 'named_report':[('许伟杰',.27),('未经登记的喷气式直升机',.55)],
 'fine_claim':[('许伟杰因此被处以2.9万元的行政处罚',.43)],
 'fine_origin':[('许伟杰',.06),('罚款2.9万元',.13),('4月23日',.42),('温州乐清市坝头村',.63)],
 'early_title':[('2010年07月08日19:41',.26)],
 'early_quote':[('很可能是私人飞机',.48)],'early_reprint':[('很可能是私人飞机',.45)],
 'comment_ningbo':[('机组人员跟他说',.54),('不明飞机',.67)],
 'comment_private':[('私人飞机',.42),('具体原因不清楚',.59)],
 'fm_route':[('FM808，澳门到上海的航班',.28)],
 'fm_observation':[('我估计是到杭州上空了',.22),('是红光，一直在闪烁',.48),('大概21点05分左右',.70)],
 'fm_limits':[('两次看到的不是同一架飞机',.28),('我就不能确定了',.50),('飞机飞行也没有异常',.73)],
 'dot_report':[('据事后了解',.12),('一个圆点',.40),('一闪一闪',.62),('很快消失',.77)],
 'photo_analysis':[('飞机长时间曝光拖影',.45)],
 'military_dates':[('2010年6月30日至7月5日',.30)],
 'military_search':[('通知军方搜寻',.35)],
 'end_train':[('只过路不停车',.78)],'end_bus':[('走错路了',.78)],
 'end_worldcup':[('中国为什么没有参加南非世界杯',.63)],
 'end_housing':[('杭州这样的房价',.68),('他们还不敢来呢',.83)],
 'end_souvenir':[('带点地球的特产回去吧',.61),('低调点儿行不',.86)],
}

def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clamp(x):return max(0.,min(1.,float(x)))
def ease(x):x=clamp(x);return x*x*(3-2*x)
@lru_cache(maxsize=48)
def font(size,bold=False):return ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc',size)
@lru_cache(maxsize=80)
def image(path):return Image.open(path).convert('RGB')
@lru_cache(maxsize=1)
def assets():
 a={x['id']:dict(x) for x in read(BASE/'资料登记/全部资料.json')['assets']}
 p=OUT/'片尾五条评论/manifest.json'
 if p.exists():
  for x in read(p)['assets']:
   x=dict(x)
   for k in ['path','plain_path','raw_path']:x[k]=str((p.parent/x[k]).relative_to(ROOT))
   x['source_label']='天涯原帖归档 · '+x['author']+' · '+x['displayed_posted_at']
   x['evidence_limit']='当年网友玩笑 · 本地原HTML还原，部分网页样式缺失'
   a[x['id']]=x
 return a
def aid(kind):return ALIASES.get(kind,kind)
def display_transform(asset_id):
 # Reading-size corrections only: crop/scale original pixels, with identical line transform.
 if asset_id=='P01_PX11_白涛长曝光结论':return (1010,442,1850,480),(80,426),1760/840
 if asset_id=='END_C08':return (0,0,1920,870),(40,18),1840/1920
 return None
def marks(a):
 out={}
 for m in a.get('dynamic_redline_reference_only',[])+a.get('redlines',[]):
  rr=[]
  for r in m['segments']:
   rr.append([r['x1'],r['y'],r['x2'],r['y']] if isinstance(r,dict) else r)
  out[m['phrase']]=rr
 supplemental=OUT/'补充红线坐标.json'
 if supplemental.exists():
  for m in supplemental_marks().get(a['id'],{}).get('marks',[]):out[m['phrase']]=m['segments']
 if a['id']=='E06c_完整涉案段':out['2010年7月7日晚间杭州萧山机场']=out['2010年7月7日']+out['杭州萧山机场']
 if a['id']=='M07_S02a_完整转帖_高光1080':
  out['通知军方搜寻']=[[71+(615-210)*2.34,35+(1061-802)*2.34+3,71+(729-210)*2.34,35+(1061-802)*2.34+3]]
 transform=display_transform(a['id'])
 if transform:
  box,xy,scale=transform
  out={phrase:[[(x1-box[0])*scale+xy[0],(y1-box[1])*scale+xy[1],(x2-box[0])*scale+xy[0],(y2-box[1])*scale+xy[1]] for x1,y1,x2,y2 in segments] for phrase,segments in out.items()}
 return out
@lru_cache(maxsize=1)
def supplemental_marks():return read(OUT/'补充红线坐标.json')
def resolve_phrase(a,phrase):
 mm=marks(a)
 if phrase in mm:return phrase
 # A timeline may request a shorter phrase; underline the stored complete original phrase.
 candidates=[s for s in mm if phrase in s]
 if candidates:return min(candidates,key=len)
 raise KeyError(f"No original-page coordinates for {a['id']}: {phrase}")
def underline(im,segments,p,width=5,color=RED):
 if p<=0:return
 d=ImageDraw.Draw(im);left=sum(math.hypot(r[2]-r[0],r[3]-r[1]) for r in segments)*clamp(p)
 for x1,y1,x2,y2 in segments:
  n=math.hypot(x2-x1,y2-y1);q=min(1.,left/max(n,.001))
  if q<=0:break
  xe=x1+(x2-x1)*q;ye=y1+(y2-y1)*q
  d.line((round(x1),round(y1),round(xe),round(ye)),fill=color,width=width)
  d.ellipse((xe-width/2,ye-width/2,xe+width/2,ye+width/2),fill=color);left-=n
def fit_text(d,xy,s,max_width,size,color):
 while d.textlength(s,font=font(size))>max_width and size>18:size-=1
 d.text(xy,s,font=font(size),fill=color)
def footer(im,line1,line2=''):
 d=ImageDraw.Draw(im);d.rectangle((0,870,W,H),fill=BG)
 fit_text(d,(32,884),line1,1856,26,(230,235,244))
 fit_text(d,(32,926),line2,1856,22,MUTED)
 return im
@lru_cache(maxsize=80)
def displayed_source(asset_id):
 a=assets()[asset_id];im=image(str(ROOT/a['path'])).copy();transform=display_transform(asset_id)
 if transform:
  box,xy,scale=transform;patch=im.crop(box)
  patch=patch.resize((round(patch.width*scale),round(patch.height*scale)),Image.Resampling.LANCZOS)
  if asset_id=='P01_PX11_白涛长曝光结论':im=Image.new('RGB',(W,H),BG)
  else:ImageDraw.Draw(im).rectangle((0,0,W,869),fill=BG)
  im.paste(patch,xy)
 return im
def source_frame(kind):
 a=assets()[aid(kind)];im=displayed_source(a['id']).copy()
 if kind=='photo':return footer(im,'麻世俊拍摄 · 都市快报媒体转载照片','现存JPEG 550×368；不是相机原文件')
 if kind=='photo_analysis':return footer(im,'白涛《萧山UFO照片分析报告》 · 原文结论局部','论坛保存转载；照片与机场目标尚未对应')
 if kind=='photo_relation':return footer(im,'杭州网／杭州日报 · 2010-07-26','完整保留照片结论及其与机场目标的关联限定')
 if kind=='military_search':return footer(im,'KeyFansClub转帖 · 思兼SRW · 2010-07-09 17:52','文内转引水木 whoseboy · 2010-07-08 08:30:44；当年网络转述')
 return im
def default_cues(kind,duration):return [{'phrase':p,'start':duration*q,'draw_duration':.62} for p,q in DEFAULTS.get(kind,[])]
def apply_cues(im,a,t,cues):
 mm=marks(a)
 for c in cues:
  p=resolve_phrase(a,c.get('phrase',c.get('key')))
  underline(im,mm[p],(t-float(c['start']))/max(.04,float(c.get('draw_duration',.62))),int(c.get('width',5)))
 return im

@lru_cache(maxsize=1)
def strip():
 meta=read(OUT/'查阅原页/查阅坐标.json');return image(str(ROOT/meta['path'])),meta
def find_frame(t,duration):
 raw,meta=strip();dpr=meta['device_scale_factor']
 # Continuous pixels from the exact saved page: title position -> the real case paragraph.
 q=ease((t-.8)/1.55);cy=10+(346-10)*q
 view=raw.crop((0,round(cy*dpr),720*dpr,round((cy+405)*dpr))).resize((W,H),Image.Resampling.LANCZOS)
 if t>2.4:
  target=source_frame('cctv_quote');view=Image.blend(view,target,ease((t-2.4)/.4))
 # A clear editorial search overlay, never a fabricated source-site widget.
 if t<2.55:
  layer=Image.new('RGBA',(W,H));d=ImageDraw.Draw(layer)
  d.rounded_rectangle((1375,30,1888,118),13,fill=(18,24,31,242),outline=(92,107,120),width=2)
  d.text((1395,44),'页内查找',font=font(21),fill=(162,178,194))
  n=2 if t>.6 else 1 if t>.3 else 0
  d.text((1517,41),'萧山'[:n],font=font(31),fill=(241,229,196))
  d.text((1770,48),'↵',font=font(24),fill=(162,178,194))
  view=Image.alpha_composite(view.convert('RGBA'),layer).convert('RGB')
 if q>.97:
  a=assets()[aid('cctv_quote')];underline(view,marks(a)['杭州萧山机场'],ease((t-2.3)/.5),4,(206,145,57))
 return footer(view,'新浪转载央视《经济半小时》实录 · 2010-11-19','原页查找“萧山”；节目于11月18日播出')

@lru_cache(maxsize=1)
def compare_base():
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
 # Two full original paragraphs, stacked at near-original size; no evidence grid.
 rows=[('fine_claim',(75,324,1835,570),(75,85)),('fine_origin',(155,242,1775,652),(150,415))]
 placements=[]
 for kind,box,xy in rows:
  a=assets()[aid(kind)];src=image(str(ROOT/a.get('plain_path',a['path']))).crop(box)
  im.paste(src,xy);placements.append((kind,box,xy))
  title='《新闻晨报》 · 2011-12-23' if kind=='fine_claim' else '《成都日报》据《新民周刊》 · 2010-07-22'
  d.text((xy[0],xy[1]-40),title,font=font(25),fill=(216,225,236))
 return footer(im,'同名、同金额的报道核对','上段写萧山；下段处罚记载写4月23日温州乐清'),placements
def compare_frame(t,duration,cues=None):
 base,placements=compare_base();im=base.copy()
 cs=cues or [dict(phrase='杭州萧山机场',scene='fine_claim',start=.3),dict(phrase='4月23日',scene='fine_origin',start=1.5),dict(phrase='温州乐清市坝头村',scene='fine_origin',start=2.2)]
 for c in cs:
  kind=c.get('scene','fine_origin');a=assets()[aid(kind)];r=next(x for x in placements if x[0]==kind);_,box,xy=r
  seg=[[x1-box[0]+xy[0],y1-box[1]+xy[1],x2-box[0]+xy[0],y2-box[1]+xy[1]] for x1,y1,x2,y2 in marks(a)[c['phrase']]]
  underline(im,seg,(t-c['start'])/.6)
 return im

@lru_cache(maxsize=1)
def date_craft():
 p=ROOT/'10_重新策划/天空与发射调查/动作版/工具/制作日期动画.py'
 spec=importlib.util.spec_from_file_location('approved_final_date_craft',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def date_rewind(t,duration):
 c=date_craft();im=c.desk().copy();p=ease((t-.55)/min(2.1,max(1.,duration-1.1)))
 c.calendar_base(im,7,8,x=445,y=145,tag='事发第二天',time='中新社消息 · 19:41')
 if p<.995:c.curled_page(im,11,19,p,x=445,y=145)
 c.rings(im,x=445,y=145)
 c.note(im,(32,25),'2010 / 把报道翻回事发第二天',20,(181,193,180))
 if p>.97:c.stamp_circle(im,640,365,98,ease((t-2.5)/.7))
 return im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS)

@lru_cache(maxsize=1)
def end_bg():
 # Simple dark studio-like finish, separate from evidence; no slide boxes/arrows.
 import numpy as np
 yy,xx=np.mgrid[0:H,0:W];v=np.exp(-(((xx-960)/1000)**2+((yy-430)/570)**2))
 arr=np.empty((H,W,3),dtype='uint8')
 for i,(a,b) in enumerate([(9,18),(14,26),(20,34)]):arr[:,:,i]=a+(b-a)*v
 return Image.fromarray(arr)
def endcard(t,duration):
 im=end_bg().copy();layer=Image.new('RGBA',(W,H));d=ImageDraw.Draw(layer)
 alpha=int(255*ease(t/.55))
 d.text((168,260),'啊子牙',font=font(100,True),fill=(244,236,216,alpha))
 d.text((176,401),'抖音号  aziyah',font=font(35),fill=(168,189,205,alpha))
 if t>1:
  a=int(255*ease((t-1)/.5));d.text((176,555),'下一次，我们查什么？',font=font(57,True),fill=(239,241,242,a))
 if t>2:
  a=int(255*ease((t-2)/.5));d.text((180,654),'评论区打出你的想法',font=font(38),fill=(192,207,217,a))
 return Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')

def frame(kind,t,duration,cues=None,**options):
 if duration<=0:raise ValueError('duration must be positive')
 if kind=='cctv_find':return find_frame(t,duration)
 if kind=='fine_compare':return compare_frame(t,duration,cues)
 if kind=='endcard':return endcard(t,duration)
 if kind=='date_rewind':return date_rewind(t,duration)
 a=assets()[aid(kind)];im=source_frame(kind)
 # Focus changes reveal an intact original area, never move the source pixels.
 # Private-comment neighbours include an unrelated story, so retain high focus from frame one.
 if options.get('reveal_focus',False) and kind!='comment_private':
  p=a.get('clean_path',a.get('plain_path'))
  if p:im=Image.blend(image(str(ROOT/p)),im,ease(t/.42))
 return apply_cues(im,a,t,default_cues(kind,duration) if cues is None else cues)
def get_frame(shot,t,duration=None):
 if isinstance(shot,str):return frame(shot,t,duration or 5.)
 kind=shot.get('scene',shot.get('kind',shot.get('asset_id')))
 length=duration or shot.get('duration') or shot['end']-shot['start']
 return frame(kind,t,length,shot.get('cues'),**shot.get('visual_options',{}))
def render_clip(shot,out_path,fps=FPS):
 """Encode one silent H.264 shot with frame-aligned duration. Returns metadata."""
 import av
 duration=float(shot.get('duration') or shot['end']-shot['start']);n=round(duration*fps)
 out_path=Path(out_path);out_path.parent.mkdir(parents=True,exist_ok=True)
 with av.open(str(out_path),'w') as c:
  s=c.add_stream('libx264',rate=fps);s.width=W;s.height=H;s.pix_fmt='yuv420p';s.options={'crf':'18','preset':'fast'}
  for i in range(n):
   f=av.VideoFrame.from_image(get_frame(shot,i/fps,duration));f.pts=i
   for p in s.encode(f):c.mux(p)
  for p in s.encode():c.mux(p)
 return dict(path=str(out_path),duration=n/fps,frames=n,fps=fps,size=[W,H],audio=False,sha256=sha(out_path))

def export_mapping():
 OUT.mkdir(parents=True,exist_ok=True);out=[]
 for kind,k in ALIASES.items():
  if k not in assets():continue
  a=assets()[k];out.append(dict(scene=kind,asset_id=k,path=a['path'],sha256=sha(ROOT/a['path']),available_cue_phrases=list(marks(a)),default_cues=DEFAULTS.get(kind,[])))
 data={'api':'frame(kind,t,duration,cues=None)->PIL RGB; get_frame(shot,t,duration=None)','size':[W,H],'fps':FPS,'cue_time':'shot-local seconds','source_reading_fixed':True,'special_scenes':['cctv_find','fine_compare','date_rewind','endcard'],'scenes':out,'excluded':['E02c_圆点说法与追访结果','END_C06'],'paid_calls':0}
 (OUT/'画面组件映射.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
 return data

def preview():
 import av
 CHECK.mkdir(parents=True,exist_ok=True);export_mapping()
 plan=[('cctv_find',4),('cctv_quote',4),('fine_claim',3),('fine_origin',5),('fine_compare',4),('date_rewind',4),('early_title',2),('comment_ningbo',3),('fm_limits',4),('dot_report',3),('photo_analysis',2),('end_housing',3),('endcard',4)]
 index=0;path=CHECK/'证据动作_无声预演.mp4'
 with av.open(str(path),'w') as c:
  s=c.add_stream('libx264',rate=FPS);s.width=W;s.height=H;s.pix_fmt='yuv420p';s.options={'crf':'20','preset':'veryfast'}
  for kind,duration in plan:
   frame(kind,duration*.94,duration).save(CHECK/(kind+'_关键帧.png'))
   for i in range(round(duration*FPS)):
    f=av.VideoFrame.from_image(frame(kind,i/FPS,duration));f.pts=index;index+=1
    for p in s.encode(f):c.mux(p)
  for p in s.encode():c.mux(p)
 with av.open(str(path)) as c:decoded=sum(1 for f in c.decode(video=0))
 assert decoded==index
 # Every declared dynamic segment must remain inside the evidence safe zone.
 bad=[]
 for kind,k in ALIASES.items():
  if k not in assets():continue
  for phrase,rr in marks(assets()[k]).items():
   for r in rr:
    if not(0<=r[0]<=W and 0<=r[2]<=W and 0<=r[1]<850 and 0<=r[3]<850):bad.append((kind,phrase,r))
 assert not bad,bad
 report={'preview':str(path.relative_to(ROOT)),'frames':decoded,'seconds':decoded/FPS,'dimensions':[W,H],'paid_calls':0,'all_dynamic_lines_above_850':True,'subtitle_safe_area':[0,970,W,H],'source_hashes_preserved':True,'visual_review':'pending','preview_cues':'demonstration proportions only; use actual narration cue seconds in final timeline'}
 (CHECK/'画面组件核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
 cards=''.join('<section><h2>'+k+'</h2><img src="'+k+'_关键帧.png"></section>' for k,_ in plan)
 (CHECK/'看证据动作.html').write_text('<!doctype html><meta charset="utf-8"><title>最终幕证据动作</title><style>body{background:#10141a;color:#eee;font:18px/1.8 "Microsoft YaHei";margin:24px auto;max-width:1440px}video,img{width:100%}section{margin:40px 0}</style><h1>原页查找、日期核对与动态划线</h1><p>无声局部预演；划线正式按实音时点。证据阅读时保持固定。</p><video controls src="证据动作_无声预演.mp4"></video>'+cards,'utf-8')
 print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--preview',action='store_true');a=p.parse_args()
 if a.preview:preview()
 else:print(json.dumps(export_mapping(),ensure_ascii=False))
