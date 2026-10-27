#!/usr/bin/env python3
"""One-time read-only comparison against an explicitly supplied adopted film project."""
from pathlib import Path
import argparse,json,sys,wave,re
import av,numpy as np
from PIL import Image,ImageDraw,ImageFont
from studio_media import Film,save,digest

def sample(p,t):
 with av.open(str(p)) as c:
  s=c.streams.video[0];c.seek(int(t/s.time_base),stream=s,backward=True)
  for f in c.decode(s):
   if f.time>=t-1e-5:return f.to_image().convert('RGB')
 raise ValueError((p,t))
def sec(s):
 h,m,s=map(float,s.split(':'));return h*3600+m*60+s

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reference',type=Path,required=True);a=ap.parse_args();old=a.reference.resolve();root=Path(__file__).resolve().parents[2];out=root/'检查/本轮对标/媒体';out.mkdir(parents=True,exist_ok=True)
 tl=json.loads((old/'timeline.json').read_text());assert tl['duration']==1319.96,'只接受本次指定的已采用21:59.96版'
 original=old/'导出/萧山机场事件_叙事优化版_无水印_1080p.mp4';master=old/'缓存/全片_无字幕无声_1080p.mp4'
 with av.open(str(original)) as c:assert abs(float(c.streams.video[0].duration*c.streams.video[0].time_base)-1319.96)<.001
 subs=[]
 for line in (old/'导出/subtitle_burn.ass').read_text('utf-8-sig').splitlines():
  if line.startswith('Dialogue:'):
   r=line.split(',',9);subs.append({'start':sec(r[1]),'end':sec(r[2]),'margin_v':int(r[7]),'text':r[9]})
 credits=[r for folder in ['前半','后半'] for r in json.loads((old/f'素材/{folder}/source_credits.json').read_text())['records'] if r['status']=='add']
 checks=[('comment',3.60),('science',320.00),('source_two_lines',685.00),('endcard',1312.00)]
 manifest={'schema_version':1,'title':'原采用版同画面对标','fps':25,'width':1920,'height':1080,'output_dir':'导出','shots':[],'audio':{'path':'test_mix.wav'},'subtitles':[],'chapters':[{'start':0,'title':'同画面对标'}],'subtitle_style':{'profile':'main'},'versions':[{'id':'clean','label':'对标无水印','watermark':False}]}
 reference=[]
 for i,(sid,t) in enumerate(checks):
  t=round(t*25)/25;raw=sample(master,t);raw.save(out/(sid+'_source.png'));sample(original,t).save(out/(sid+'_原采用.png'))
  s={'id':sid,'path':sid+'_source.png','kind':'image','duration':1,'native_label':False,'layout':{'mode':'fullframe'}}
  source=next((r for r in credits if r['start']<=t<r['end']),None)
  if source:s.update(source_note=source['text'],source_note_safe_area=True)
  active=[x for x in subs if x['start']<=t<x['end']]
  for row in active:manifest['subtitles'].append({'start':i,'end':i+1,'text':row['text'],'style':{'profile':'science' if row['margin_v']==74 else 'main'}})
  manifest['shots'].append(s);reference.append({'id':sid,'reference_time':t,'active_subtitles':active,'source_note':source['text'] if source else None})
 n=48000*len(checks);t=np.arange(n)/48000;vals=.02*np.sin(2*np.pi*220*t);stereo=np.stack((vals,vals),axis=1)
 with wave.open(str(out/'test_mix.wav'),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(48000);w.writeframes((stereo*32767).astype('<i2').tobytes())
 save(out/'manifest.json',manifest);film=Film(out/'manifest.json');film.render();film.verify()
 font=ImageFont.truetype('/System/Library/Fonts/Hiragino Sans GB.ttc',24);results=[]
 for i,row in enumerate(reference):
  sid=row['id'];old_im=Image.open(out/(sid+'_原采用.png')).convert('RGB');new=sample(out/'导出/clean.mp4',i+.52);new.save(out/(sid+'_新渲.png'))
  a,b=np.asarray(old_im).astype(float),np.asarray(new).astype(float)
  subtitle=(slice(960,1050),slice(120,1800));ma=np.all(a[subtitle]>230,axis=2);mb=np.all(b[subtitle]>230,axis=2)
  union=np.count_nonzero(ma|mb);iou=np.count_nonzero(ma&mb)/union if union else None
  error=float(np.abs(a-b).mean());source_error=float(np.abs(a[870:960]-b[870:960]).mean());upper_error=float(np.abs(a[:870]-b[:870]).mean())
  sheet=Image.new('RGB',(1920,1160),'#10141a');sheet.paste(old_im.resize((960,540)),(0,40));sheet.paste(new.resize((960,540)),(960,40));d=ImageDraw.Draw(sheet);d.text((20,5),'左：原采用成片 '+str(row['reference_time'])+'s',font=font,fill='white');d.text((980,5),'右：新工作室同画面重渲',font=font,fill='white');sheet.paste(old_im.crop((300,940,1620,1080)).resize((1320,140)),(20,610));sheet.paste(new.crop((300,940,1620,1080)).resize((1320,140)),(20,790));d.text((1360,630),'原字幕',font=font,fill='white');d.text((1360,810),'新字幕',font=font,fill='white');sheet.save(out/(sid+'_同画面对照.jpg'),quality=94)
  results.append({**row,'whole_frame_mae_0_255':error,'upper_picture_mae':upper_error,'source_footer_mae':source_error,'subtitle_bright_glyph_iou':iou,'composition_same':upper_error<2,'contact_sheet':str((out/(sid+'_同画面对照.jpg')).relative_to(root))})
 # Regression reproduces the user's screenshot shrink: edge content must survive fullframe with footer.
 scene=film.shots[0];assert 'pad=' not in film.layout_filter(scene) and '1920:864' not in film.layout_filter(scene)
 baseline=Film(out/'manifest.json');baseline.validate();assert baseline.subtitle_style()['margin_v']==42 and baseline.subtitle_style({'start':1.2,'style':{'profile':'science'}})['margin_v']==74
 for invalid in [{'mode':'fullframe'},{'mode':'contain'}]:
  bad=json.loads(json.dumps(manifest));bad['shots'][0]['layout']=invalid
  if invalid['mode']=='fullframe':bad['shots'][0].pop('source_note_safe_area',None)
  save(out/'invalid.json',bad)
  try:Film(out/'invalid.json').validate()
  except ValueError:pass
  else:raise AssertionError('layout guard missing')
 (out/'invalid.json').unlink();film.validate()
 r={'status':'passed' if all(x['composition_same'] and (x['subtitle_bright_glyph_iou'] is None or x['subtitle_bright_glyph_iou']>.90) for x in results) else 'needs_visual_review','reference_duration':1319.96,'reference_final_sha256':digest(original),'visual_defaults_sha256':digest(root/'默认配置/视觉.json'),'reference_main_ass_style':next(x for x in (old/'导出/subtitle_burn.ass').read_text('utf-8-sig').splitlines() if x.startswith('Style: Main')),'current_main_ass_style':next(x for x in (out/'导出/subtitles.ass').read_text('utf-8-sig').splitlines() if x.startswith('Style: Main')),'font':film.font_info(),'results':results,'fixes':['去掉source_note隐式缩图，fullframe全幅不加边不裁切','字体恢复Hiragino并记录实际libass选择和字体hash','主字幕42/科学74按profile；描边阴影颜色左右边距对齐原片','来源底栏870/884/926位置、27/23字体和原配色恢复','来源与字幕文字检查实际字宽，防静默出屏','原页长图显式evidence_region，contain必须用途说明'],'paid_calls':0,'limits':['同画面使用原无字幕母片冻结帧，仅比较布局字形与编码误差，不代替运动/声音审片','系统Hiragino不复制分发；跨机Noto回退必须披露为不同字形']}
 save(root/'检查/本轮对标/媒体视觉差异.json',r);print(json.dumps({'status':r['status'],'results':results},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
