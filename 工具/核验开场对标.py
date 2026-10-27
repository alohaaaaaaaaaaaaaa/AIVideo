from pathlib import Path
import json,hashlib
import av,numpy as np
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];B=R/'参考库/原片同段对标/开场29秒';O=R/'检查/本轮对标/连续开场';O.mkdir(exist_ok=True)
f=ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc',25)
def frame(p,t):
 with av.open(str(p)) as c:
  st=c.streams.video[0];c.seek(int(t/st.time_base),stream=st,backward=True)
  for fr in c.decode(st):
   if float(fr.time)>=t-.015:return fr.to_image()
imgs=[];rows=[]
for t in [0.4,1.4,3.6,4.8,7.,10.8,12.,14.8,17.6,20.4,21.8,23.,25.,28.8,29.28]:
 orig=frame(B/'原片_开场29秒.mp4',t);new=frame(B/'导出/clean.mp4',t);wm=frame(B/'导出/bili.mp4',t)
 if t==4.8:
  new.save(B/'首镜_修复后.png');orig.save(B/'首镜_原片.png')
 if t in [4.8,7.,14.8,17.6,20.4,23.,28.8]:
  img=Image.new('RGB',(1920,1120),'#142229');img.paste(orig.resize((960,540)),(0,40));img.paste(new.resize((960,540)),(960,40));None
  d=ImageDraw.Draw(img);d.text((10,5),f'原片 {t:.2f}s',font=f);d.text((970,5),'新工作室同段',font=f)
  img=img.crop((0,0,1920,580));img.save(O/f'{t:05.2f}_原片与新片.jpg');imgs.append(img.resize((960,290)))
 a=np.array(orig).astype(float);b=np.array(new).astype(float)
 rows.append({'time':t,'mean_abs_rgb_difference':round(float(np.abs(a-b).mean()),3),'new_edge_luma_left':round(float(b[430:600,:20].mean()),2),'old_edge_luma_left':round(float(a[430:600,:20].mean()),2)})
 new.resize((960,540)).save(O/f'{t:05.2f}_clean.jpg');wm.resize((960,540)).save(O/f'{t:05.2f}_bili.jpg')
out=Image.new('RGB',(960,len(imgs)*290))
for i,im in enumerate(imgs):out.paste(im,(0,290*i))
out.save(O/'七处同段对照.jpg');(O/'样帧差异.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print('sampled',len(rows),'timepoints')
