"""按最终幕实音生成旁白、字幕、镜头与音乐接口；不生成、不变速、不改源音频。"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from scipy.io import wavfile

if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
BASE=Path(__file__).resolve().parents[1]
SR,FPS=48000,25
FRAME_SAMPLES=SR//FPS
AI_SECONDS=5.84

def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def write(p,d):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(t):return re.sub(r'[^a-z0-9\u3400-\u9fff]','',t.lower())
def q(t):return round(t*FPS)/FPS
def up(t):return math.ceil(t*FPS-1e-8)/FPS

def locate(phrases,text):
 target=norm(text);joined='';bounds=[]
 for p in phrases:
  joined+=norm(p['text']);bounds.append(len(joined))
 idx=joined.find(target)
 if idx<0:raise ValueError('实音短语中找不到：'+text)
 lo=next(i for i,end in enumerate(bounds) if end>idx)
 hi=next(i for i,end in enumerate(bounds) if end>=idx+len(target))
 return phrases[lo]['start'],phrases[hi]['end']

def safe_insert_sample(audio,begin,end):
 """只选已有低能量静音，保留两侧尾音；不切断辅音增加停顿。"""
 lo=max(0,round((begin+.015)*SR));hi=min(len(audio),round((end-.015)*SR))
 hop=480;centers=[]
 for i in range(lo,max(lo,hi-hop),hop):
  rms=float(np.sqrt(np.mean(audio[i:i+hop]**2)))
  if rms<.002:centers.append(i+hop//2)
 if not centers:return None
 midpoint=(lo+hi)//2
 return min(centers,key=lambda x:abs(x-midpoint))

def prepare_audio(row,aligned):
 path=BASE/aligned['leveled_wav'];rate,raw=wavfile.read(path)
 assert rate==SR and raw.ndim==1 and raw.dtype==np.float32,(row['id'],path)
 assert sha(Path(aligned['audio']))==aligned['audio_sha256'],row['id']
 phrases=copy.deepcopy(aligned['phrases'])
 assert all(p['matched'] and p['end']>p['start'] for p in phrases),row['id']
 changes=[];reviews=[];duration=len(raw)/SR
 for pause in row.get('pauses',{}).get('after_phrases',[]):
  _,end=locate(phrases,pause['after_text'])
  following=next((p['start'] for p in phrases if p['start']>=end-.001),duration)
  if following<end:following=duration
  target=up(float(pause['minimum_silence_seconds']))
  existing=max(0,following-end)
  need=max(0,up(target-existing))
  if need<=0:continue
  # 句末补在整个音频后，内部只在真实静音处插入。
  at=len(raw) if following==duration else safe_insert_sample(raw,end,following)
  if at is None:
   reviews.append(dict(after_text=pause['after_text'],reason='ASR间隔没有可安全插入的静音；保留原声连续性',requested=target,existing=existing));continue
  changes.append(dict(source_sample=at,add_samples=round(need*SR),reason=pause['reason'],after_text=pause['after_text']))
 changes.sort(key=lambda x:x['source_sample'])
 parts=[];prev=0;maps=[];cursor=0
 for event in changes:
  at=event['source_sample'];parts.append(raw[prev:at]);size=at-prev
  maps.append(dict(source_in_sample=prev,source_out_sample=at,destination_in_sample=cursor,destination_out_sample=cursor+size));cursor+=size
  parts.append(np.zeros(event['add_samples'],np.float32));cursor+=event['add_samples'];prev=at
 parts.append(raw[prev:]);maps.append(dict(source_in_sample=prev,source_out_sample=len(raw),destination_in_sample=cursor,destination_out_sample=cursor+len(raw)-prev))
 output=np.concatenate(parts)
 def shift(t):
  sample=round(t*SR)
  return (sample+sum(e['add_samples'] for e in changes if e['source_sample']<sample))/SR
 for p in phrases:
  p['source_start']=p['start'];p['source_end']=p['end'];p['start']=shift(p['start']);p['end']=shift(p['end'])
 return output,phrases,changes,reviews,maps,path

def srt_time(t):
 ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
 return f'{h:02}:{m:02}:{s:02},{ms:03}'
def ass_time(t):
 cs=round(t*100);h,cs=divmod(cs,360000);m,cs=divmod(cs,6000);s,cs=divmod(cs,100)
 return f'{h}:{m:02}:{s:02}.{cs:02}'
def export_subtitles(subs):
 out=BASE/'导出';out.mkdir(exist_ok=True)
 (out/'最后一幕_旁白字幕.srt').write_text('\n\n'.join(f'{i}\n{srt_time(p["start"])} --> {srt_time(p["end"])}\n{p["text"].replace(chr(10), "")}' for i,p in enumerate(subs,1))+'\n','utf-8')
 header='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Microsoft YaHei,44,&H00FFFFFF,&H00FFFFFF,&H0010141A,&H80000000,0,0,0,0,100,100,0,0,1,2.5,0,5,90,90,0,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
 lines=[]
 for p in subs:
  text=p['text'].replace('\n','').replace('{','｛').replace('}','｝')
  lines.append(f'Dialogue: 0,{ass_time(p["start"])},{ass_time(p["end"])},Default,,0,0,0,,{{\\pos(960,1012)}}{text}')
 (out/'最后一幕_字幕.ass').write_text(header+'\n'.join(lines)+'\n','utf-8-sig')

def make_shots(segments):
 """镜头切点从实际口播定位；资料阅读镜头不持续缩放。"""
 S={s['id']:s for s in segments};shots=[];ai_uses=[]
 def at(sid,text):return q(locate(S[sid]['phrases'],text)[0])
 def add(sid,scene,start=None,end=None,**extra):
  s=S[sid];start=s['start'] if start is None else q(start);end=s['end'] if end is None else q(end)
  if end-start<1/FPS:return
  shot=dict(id=f'SH{len(shots)+1:03}',segment=sid,start=start,end=end,duration=round(end-start,6),kind='evidence',scene=scene,cues=[],base_fixed=scene not in {'cctv_find','date_rewind','endcard'},task=s['scene']['task'])
  shot.update(extra)
  shots.append(shot);return shot
 def sequence(sid,scenes):
  for i,(scene,start) in enumerate(scenes):add(sid,scene,start,scenes[i+1][1] if i+1<len(scenes) else S[sid]['end'])
 def ai(sid,vid,start):
  selection_file=BASE/'AI视频'/'正式选用.json'
  selections=read(selection_file) if selection_file.exists() else {}
  selected=selections.get(vid)
  folder=BASE/'AI视频'/vid;files=[BASE/selected['source']] if selected else list(folder.glob('*.mp4'))
  if len(files)!=1:raise RuntimeError(f'{vid}须登记唯一的正式AI视频')
  if selected and sha(files[0])!=selected['source_sha256']:raise RuntimeError(f'{vid}选定素材哈希不符')
  end=q(start+AI_SECONDS)
  shot=add(sid,'ai_video',start,end,kind='ai_video',asset_id=vid,source=str(files[0].resolve()),source_sha256=sha(files[0]),source_in=0,source_out=AI_SECONDS,playback_rate=1,ai_label='AI情境示意',original_audio_used=False,loop=False,freeze_tail=False)
  ai_uses.append({k:shot[k] for k in ['id','segment','asset_id','source','source_sha256','start','end','duration','source_in','source_out','playback_rate','ai_label','loop','freeze_tail']})
 def contains(sid):return sid in S
 if contains('F01'):
  s=S['F01'];finding=max(s['start']+1.6,at('F01','这里写着')-2.8)
  sequence('F01',[('cctv_title',s['start']),('cctv_find',finding),('cctv_quote',at('F01','这里写着'))])
 for sid in ['F02','F21','F22','F23']:
  if contains(sid):add(sid,'conclusion' if sid in ['F21','F22','F23'] else 'cctv_quote')
 if contains('F03'):sequence('F03',[('named_report',S['F03']['start']),('fine_claim',at('F03','到第二年'))])
 if contains('F04'):sequence('F04',[('fine_claim',S['F04']['start']),('fine_origin',at('F04','可顺着'))])
 if contains('F05'):sequence('F05',[('fine_compare',S['F05']['start']),('fine_origin',at('F05','这笔能查到来历的罚款'))])
 if contains('F06'):add('F06','fine_origin')
 if contains('F07'):
  sequence('F07',[('date_rewind',S['F07']['start']),('early_title',at('F07','七月八号')),('early_quote',at('F07','已经说了')),('early_reprint',at('F07','第二天，其他报纸'))])
 if contains('F08'):sequence('F08',[('early_quote',S['F08']['start']),('comment_ningbo',at('F08','再往当天的评论里翻'))])
 for sid,scene in [('F09','comment_ningbo'),('F10','comment_ningbo'),('F11','comment_private'),('F12','comment_private'),('F13','fm_route'),('F15','fm_limits'),('F16','fm_limits'),('F18','dot_report'),('F25','end_train'),('F26','end_bus'),('F27','end_worldcup'),('F28','end_housing'),('F29','end_souvenir'),('F30','endcard')]:
  if contains(sid):add(sid,scene)
 if contains('F14'):
  s=S['F14'];begin=min(at('F14','往左舷前下方看'),s['end']-AI_SECONDS)
  add('F14','fm_observation',s['start'],begin);ai('F14','V01',begin);add('F14','fm_observation',begin+AI_SECONDS,s['end'])
 if contains('F17'):sequence('F17',[('dot_title',S['F17']['start']),('dot_report',at('F17','杭州日报'))])
 if contains('F19'):sequence('F19',[('photo',S['F19']['start']),('photo_analysis',at('F19','摄影分析')),('photo_relation',at('F19','照片和机场目标'))])
 if contains('F20'):sequence('F20',[('military_dates',S['F20']['start']),('military_search',at('F20','军方搜寻')),('cctv_quote',at('F20','再回头看央视'))])
 if contains('F24'):
  s=S['F24'];begin=q(s['end']-AI_SECONDS);add('F24','conclusion',s['start'],begin);ai('F24','V02',begin)
 shots.sort(key=lambda s:s['start'])
 for i,s in enumerate(shots,1):s['id']=f'SH{i:03}'
 # 将语音触发词映射到画面组件的真实原文关键词。
 phrase_map={
  'cctv_quote':[('这里写着','2010年7月7日'),('小型私人飞机','小型私人飞机'),('黑飞','典型的“黑飞”事件')],
  'named_report':[('许伟杰','许伟杰'),('未经登记','未经登记的喷气式直升机')],
  'fine_claim':[('因此被罚','许伟杰因此被处以2.9万元的行政处罚')],
  'fine_origin':[('四月二十三号','4月23日'),('温州乐清','温州乐清市坝头村')],
  'early_title':[('七月八号','2010年07月08日19:41')],
  'early_quote':[('很可能是私人飞机','很可能是私人飞机')],
  'early_reprint':[('第二天，其他报纸','很可能是私人飞机')],
  'comment_ningbo':[('机组人员跟他说','机组人员跟他说'),('不明飞机','不明飞机')],
  'comment_private':[('私人飞机','私人飞机'),('具体原因不清楚','具体原因不清楚'),('p.o.l.i.c.e','p.o.l.i.c.e')],
  'fm_route':[('FM808','FM808，澳门到上海的航班')],
  'fm_observation':[('他估计','我估计是到杭州上空了')],
  'fm_limits':[('第一次我就发现它是一架小型的飞机','第一次我就发现它是一架小型的飞机'),('不是同一架','两次看到的不是同一架飞机'),('他没看清','我就不能确定了'),('飞行没有异常','飞机飞行也没有异常')],
  'dot_report':[('据事后了解','据事后了解'),('一个圆点','一个圆点'),('一闪一闪','一闪一闪'),('很快消失','很快消失')],
  'photo_analysis':[('长曝光拖影','飞机长时间曝光拖影')],
  'military_dates':[('公开演习的时间','2010年6月30日至7月5日')],
  'military_search':[('军方搜寻','通知军方搜寻')],
  'conclusion':[('飞机','小型私人飞机'),('黑飞','典型的“黑飞”事件')],
  'end_train':[('只过路不停车','只过路不停车')],
  'end_bus':[('走错路了','走错路了')],
  'end_worldcup':[('中国为什么没有参加南非世界杯','中国为什么没有参加南非世界杯')],
  'end_housing':[('杭州这样的房价','杭州这样的房价'),('他们还不敢来呢','他们还不敢来呢')],
  'end_souvenir':[('带点地球的特产回去吧','带点地球的特产回去吧'),('低调点儿行不','低调点儿行不')],
 }
 for shot in shots:
  phrases=S[shot['segment']]['phrases']
  for trigger,source in phrase_map.get(shot['scene'],[]):
   try:start,end=locate(phrases,trigger)
   except ValueError:continue
   if shot['start']-.001<=start<shot['end']:
    shot['cues'].append(dict(phrase=source,start=round(start-shot['start'],4),draw_duration=.52,spoken_text=trigger,timing_basis='actual_ASR_phrase_bounds'))
  # 两段同框只强调已经听过的真实日期，避免组件默认比例时码。
  if shot['scene']=='fine_compare':
   shot['cues']=[dict(phrase='杭州萧山机场',scene='fine_claim',start=0,draw_duration=.48),dict(phrase='4月23日',scene='fine_origin',start=.35,draw_duration=.48),dict(phrase='温州乐清市坝头村',scene='fine_origin',start=.75,draw_duration=.48)]
 for use in ai_uses:use['id']=next(s['id'] for s in shots if s.get('asset_id')==use['asset_id'])
 return shots,ai_uses

def reuse_revision_shots(plan,segments):
 """删整段修订时沿用旧镜头ID和镜头内动效，不重排已认可画面。"""
 revision=plan.get('revision',{})
 old_path=BASE/revision['baseline_timeline']
 assert sha(old_path)==revision['baseline_timeline_sha256'],'修订基线时间线哈希不符'
 old=read(old_path);previous={s['id']:s for s in old['segments']};current={s['id']:s for s in segments}
 shots=[];mapping=[]
 for shot in old['shots']:
  sid=shot['segment']
  if sid not in current:continue
  assert abs(current[sid]['duration']-previous[sid]['duration'])<.001,sid+'非整段等速复用'
  delta=round(current[sid]['start']-previous[sid]['start'],6)
  new=copy.deepcopy(shot);new['start']=round(shot['start']+delta,6);new['end']=round(shot['end']+delta,6)
  if new.get('source_sha256'):assert sha(Path(new['source']))==new['source_sha256'],new['id']
  shots.append(new);mapping.append(dict(old_id=shot['id'],new_id=new['id'],segment=sid,scene=new['scene'],old_start=shot['start'],old_end=shot['end'],new_start=new['start'],new_end=new['end'],shift_seconds=delta,duration_unchanged=True,cues_local_unchanged=new.get('cues')==shot.get('cues')))
 ai_uses=[]
 for use in old['ai_uses']:
  if use['segment'] not in current:continue
  new=copy.deepcopy(use);delta=current[use['segment']]['start']-previous[use['segment']]['start']
  new['start']=round(new['start']+delta,6);new['end']=round(new['end']+delta,6);ai_uses.append(new)
 write(BASE/'检查/两评论修订_镜头映射.json',dict(baseline=str(old_path),baseline_sha256=sha(old_path),kept_ids_preserved=True,removed_segments=revision['removed_segments'],shots=mapping))
 return shots,ai_uses

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
 plan=read(BASE/'旁白分段.json');missing=[r['id'] for r in plan['voices'] if not (BASE/f"声音/{r['id']}_对齐.json").exists()]
 if missing:
  print(json.dumps(dict(ready=False,missing=missing),ensure_ascii=False));return
 if args.dry_run:
  print(json.dumps(dict(ready=True,segments=len(plan['voices']),outputs=['timeline.json','声音/旁白_48k.wav','导出/最后一幕_旁白字幕.srt','导出/最后一幕_字幕.ass']),ensure_ascii=False));return
 segments=[];subtitles=[];audio_parts=[];cursor=0;maps=[];pause_checks=[];source_hashes={}
 for row in plan['voices']:
  a=read(BASE/f"声音/{row['id']}_对齐.json")
  assert a.get('text_sha256')==row['text_sha256'],row['id']+'的对齐文本不是当前稿'
  audio,phrases,inserted,reviews,pieces,path=prepare_audio(row,a)
  lead=round(up(row.get('pauses',{}).get('lead_seconds',.12))*SR)
  tail=round(up(row.get('pauses',{}).get('tail_seconds',.24))*SR)
  length=math.ceil((lead+len(audio)+tail)/FRAME_SAMPLES)*FRAME_SAMPLES
  start=cursor/SR;end=(cursor+length)/SR;offset=(cursor+lead)/SR
  audio_parts.extend([np.zeros(lead,np.float32),audio,np.zeros(length-lead-len(audio),np.float32)])
  for p in phrases:
   p['local_start']=p['start'];p['local_end']=p['end'];p['start']=round(offset+p['start'],6);p['end']=round(offset+p['end'],6);p['segment']=row['id']
   subtitles.append(dict(segment=row['id'],start=p['start'],end=p['end'],text=p['text'],alignment_method='actual_ASR_word_bounds_with_silence_insertions'))
  segment=dict(id=row['id'],title=row['title'],section=row['section'],section_title=row['section_title'],start=start,end=end,duration=end-start,audio=str(path.resolve()),audio_sha256=sha(path),raw_audio=a['audio'],raw_audio_sha256=a['audio_sha256'],voice_offset=lead/SR,phrases=phrases,source_asset_ids=row['source_asset_ids'],scene=row['scene'],inserted_pauses=inserted,playback_rate=1,time_stretch=False)
  segments.append(segment);source_hashes[str(path)]=sha(path)
  for p in pieces:
   maps.append(dict(segment=row['id'],source=str(path),source_in=p['source_in_sample']/SR,source_out=p['source_out_sample']/SR,start=(cursor+lead+p['destination_in_sample'])/SR,end=(cursor+lead+p['destination_out_sample'])/SR))
  pause_checks.append(dict(segment=row['id'],inserted=inserted,review_notes=reviews));cursor+=length
 voice=np.concatenate(audio_parts).astype(np.float32);assert len(voice)==cursor
 voice_path=BASE/'声音/旁白_48k.wav';wavfile.write(voice_path,SR,voice)
 source_cache={}
 for piece in maps:
  if piece['source'] not in source_cache:source_cache[piece['source']]=wavfile.read(piece['source'])[1]
  original=source_cache[piece['source']][round(piece['source_in']*SR):round(piece['source_out']*SR)]
  assembled=voice[round(piece['start']*SR):round(piece['end']*SR)]
  assert np.array_equal(original,assembled),piece
 for a,b in zip(subtitles,subtitles[1:]):assert a['end']<=b['start']+.001,(a,b)
 shots,ai_uses=reuse_revision_shots(plan,segments) if plan.get('revision',{}).get('baseline_timeline') else make_shots(segments)
 for a,b in zip(shots,shots[1:]):assert abs(a['end']-b['start'])<.001,(a,b)
 assert shots[0]['start']==0 and abs(shots[-1]['end']-cursor/SR)<.001
 moods={1:'discovery',2:'trace',3:'early',4:'comments',5:'window',6:'recap',7:'judgment',8:'coda',9:'outro'}
 music=[]
 for sec in sorted({s['section'] for s in segments}):
  group=[s for s in segments if s['section']==sec];music.append(dict(id=f'M{sec:02}',title=group[0]['section_title'],start=group[0]['start'],end=group[-1]['end'],music_mood=moods[sec]))
 timeline=dict(schema_version=1,status='actual_narration_timeline_ready',duration=cursor/SR,fps=FPS,sample_rate=SR,width=1920,height=1080,audio=str(voice_path.resolve()),narration_mono=str(voice_path.resolve()),detector_mono=str(voice_path.resolve()),audio_sha256=sha(voice_path),segments=segments,subtitles=subtitles,shots=shots,ai_uses=ai_uses,music_sections=music,chapters=music,audio_pieces=maps,subtitle_safe_area=[0,970,1920,1080],subtitle_anchor=[960,1012],subtitle_font_size=44,time_stretch=False,playback_rate=1,ai_speed=1,ai_reuse_count={x['asset_id']:1 for x in ai_uses},source_plan='旁白分段.json',source_plan_sha256=sha(BASE/'旁白分段.json'),source_audio_hashes=source_hashes,paid_calls=0)
 revision_check=None
 if plan.get('revision',{}).get('baseline_timeline'):
  revision=plan['revision'];timeline['revision']=copy.deepcopy(revision)
  old=read(BASE/revision['baseline_timeline']);old_rate,old_voice=wavfile.read(BASE/revision['baseline_voice'])
  stop=revision['preserve_prefix_until'];assert old_rate==SR
  assert np.array_equal(voice[:round(stop*SR)],old_voice[:round(stop*SR)]),'前312.84秒旁白不一致'
  assert [s for s in shots if s['end']<=stop]==[s for s in old['shots'] if s['end']<=stop],'前312.84秒镜头定义不一致'
  assert [s for s in subtitles if s['end']<=stop]==[s for s in old['subtitles'] if s['end']<=stop],'前312.84秒字幕不一致'
  for sid,wanted in revision['expected_segment_starts'].items():
   s=next(s for s in segments if s['id']==sid);assert abs(s['start']-wanted)<.001,(sid,s['start'],wanted)
  assert abs(cursor/SR-revision['expected_duration'])<.001
  revision_check=dict(prefix_voice_sample_identical=True,prefix_shots_identical=True,prefix_subtitles_identical=True,preserved_prefix_seconds=stop,expected_segment_starts=revision['expected_segment_starts'],duration=cursor/SR,removed_segments=revision['removed_segments'],new_generations=0,asr_rerun=False)
 write(BASE/'timeline.json',timeline);export_subtitles(subtitles)
 write(BASE/'检查/时间线组装核验.json',dict(status='passed',duration=cursor/SR,frames=cursor//FRAME_SAMPLES,samples=cursor,segments=len(segments),shots=len(shots),subtitles=len(subtitles),AI_use_count=2,AI_each_seconds=AI_SECONDS,AI_normal_speed=True,source_audio_preserved=True,source_chunks_sample_identical=True,verified_source_chunks=len(maps),time_stretch=False,peak=float(np.max(np.abs(voice))),pause_checks=pause_checks,subtitle_anchor=[960,1012],revision_check=revision_check,requires_visual_and_listening_review=True))
 print(json.dumps(dict(ready=True,duration=cursor/SR,segments=len(segments),shots=len(shots),subtitles=len(subtitles),audio=str(voice_path),AI_seconds=AI_SECONDS),ensure_ascii=False))

if __name__=='__main__':main()
