"""Assemble real paragraph PCM to one sample/frame ledger; tail padding only.
No network, no regenerated speech, no time stretching or implicit editing pauses.
All segment local timestamps are translated by the actual sample start offset.
"""
from pathlib import Path
import argparse,hashlib,json,math
import numpy as np,soundfile as sf
from timing import apply_pauses,shifted,translate
SR=48000
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def srt_time(t):
 n=round(t*1000);hh,n=divmod(n,3600000);mm,n=divmod(n,60000);ss,n=divmod(n,1000);return f'{hh:02}:{mm:02}:{ss:02},{n:03}'
def assemble(paragraphs_path,layout_path,out):
 rows=read(paragraphs_path);layout=read(layout_path);fps=layout.get('fps',25)
 assert type(fps) is int and 1<=fps<=60 and SR%fps==0,'fps must divide 48000 for exact sample/frame boundaries'
 samples_per_frame=SR//fps;by={r['id']:r for r in rows};assert len(by)==len(rows),'Duplicate paragraph id'
 order=layout['segments'];assert order and len({r['id'] for r in order})==len(order),'Each paragraph must be placed once; use distinct ids for intentional rerecording'
 assert {r['id'] for r in order}==set(by),'Layout must include exactly all supplied paragraphs; pass an explicit subset paragraphs file for excerpts'
 out=Path(out);out.mkdir(parents=True,exist_ok=True);target=out/'narration_48k_mono.wav'
 assert not target.exists(),'Use a new output directory for a new adopted assembly'
 cursor=0;segments=[];phrases=[];chapters=[];sections=[];seen_chapters=set();records=[]
 with sf.SoundFile(target,'w',samplerate=SR,channels=1,subtype='FLOAT') as dst:
  for e in order:
   row=by[e['id']];src=Path(paragraphs_path).resolve().parent/row['audio'];assert src.is_file() and sha(src)==row['audio_sha256']
   x,sr=sf.read(src,dtype='float32',always_2d=True);assert sr==SR and x.shape[1]==1 and np.isfinite(x).all()
   n=len(x);assert n>0 and row['samples']==n and abs(row['duration']-n/SR)<1/SR,'Paragraph metadata does not match actual PCM'
   tail=e.get('tail_seconds',0);assert finite(tail) and 0<=tail<=30,'tail_seconds must be an explicit finite 0..30 seconds'
   assert abs(tail*fps-round(tail*fps))<1e-7,'Explicit tail must be whole frames'
   edited,pause_events,source_spans=apply_pauses(x,e.get('pauses',[]),sha(src),row['phrases'],fps)
   edited_n=len(edited);speech_frames=math.ceil(edited_n/samples_per_frame);padding=speech_frames*samples_per_frame-edited_n;tail_samples=round(tail*SR);allocated=edited_n+padding+tail_samples
   start=cursor/SR;end=(cursor+allocated)/SR;cid=str(e['chapter']).zfill(2);assert cid.isdigit() and e.get('chapter_title') and e.get('music_mood')
   assert e['music_mood'] in ['discovery','trace','mismatch','early','comments','window','recap','judgment','resolved','coda','outro']
   if not chapters or chapters[-1]['id']!=cid:
    assert cid not in seen_chapters,'Chapter segments must be contiguous';seen_chapters.add(cid)
    chapters.append({'id':cid,'title':e['chapter_title'],'start':start,'end':end,'sample_start':cursor,'sample_end':cursor+allocated,'frame_start':cursor//samples_per_frame,'frame_end':(cursor+allocated)//samples_per_frame})
   else:
    assert chapters[-1]['title']==e['chapter_title'],'Chapter title must stay consistent'
    chapters[-1].update(end=end,sample_end=cursor+allocated,frame_end=(cursor+allocated)//samples_per_frame)
   if 'silent_music_rms_dbfs' in e:
    level=e['silent_music_rms_dbfs'];assert finite(level) and -50<=level<=-20
    assert chapters[-1].get('silent_music_rms_dbfs',level)==level,'A silent chapter needs one consistent music level'
    chapters[-1]['silent_music_rms_dbfs']=level
   local=[];last=0.
   for p in row['phrases']:
    assert finite(p['start']) and finite(p['end']) and last<=p['start']<p['end']<=n/SR+1/SR
    last=p['end'];q={**p,'start':round(start+shifted(p['start'],pause_events),9),'end':round(start+shifted(min(n/SR,p['end']),pause_events,end=True),9),'segment_id':e['id']};phrases.append(q);local.append(q)
   seg={'id':e['id'],'chapter':cid,'text':row['text'],'source_audio':str(src.relative_to(Path(paragraphs_path).resolve().parent)),'source_sha256':sha(src),'start':start,'end':end,'natural_duration':n/SR,'sample_start':cursor,'speech_end_sample':cursor+n,'sample_end':cursor+allocated,'source_samples':n,'frame_start':cursor//samples_per_frame,'frame_end':(cursor+allocated)//samples_per_frame,'alignment_padding_samples':padding,'explicit_tail_samples':tail_samples,'explicit_tail_seconds':tail,'phrases':local,'time_stretch':False}
   seg.update(speech_end_sample=cursor+edited_n,edited_samples=edited_n,internal_pause_samples=edited_n-n,internal_pauses=pause_events,source_identity_spans=source_spans)
   segments.append(seg)
   if sections and sections[-1]['music_mood']==e['music_mood'] and sections[-1]['chapter']==cid:sections[-1]['end']=end
   else:sections.append({'id':f'M{len(sections)+1:03}','chapter':cid,'title':e.get('music_title',e['chapter_title']),'music_mood':e['music_mood'],'start':start,'end':end})
   dst.write(edited);dst.write(np.zeros((padding+tail_samples,1),np.float32));records.append({'id':e['id'],'sample_start':cursor,'samples':edited_n,'original_samples':n,'inserted_pause_samples':edited_n-n,'pcm_sha256':hashlib.sha256(edited.tobytes()).hexdigest(),'source_spans':source_spans,'source_pcm_sha256':hashlib.sha256(x.tobytes()).hexdigest()});cursor+=allocated
 # Read actual written PCM; checks include every speech sample, not only length.
 with sf.SoundFile(target) as f:
  assert f.frames==cursor
  for rec in records:
   f.seek(rec['sample_start']);pcm=f.read(rec['samples'],dtype='float32',always_2d=True)
   assert hashlib.sha256(pcm.tobytes()).hexdigest()==rec['pcm_sha256']
   restored=np.concatenate([pcm[s['edited_start_sample']:s['edited_end_sample']] for s in rec['source_spans']]);assert hashlib.sha256(restored.tobytes()).hexdigest()==rec['source_pcm_sha256'];rec['sample_identical']=True
 # Export chapter WAVs, directly usable by bridge.py after per-chapter score_mix.
 with sf.SoundFile(target) as source:
  for c in chapters:
   chapter_dir=out/'chapters';chapter_dir.mkdir(exist_ok=True);name='chapter_'+c['id']+'_48k_mono.wav'
   assert all(ch.isalnum() or ch in '_-' for ch in c['id']),'Unsafe chapter id'
   source.seek(c['sample_start']);n=c['sample_end']-c['sample_start'];sf.write(chapter_dir/name,source.read(n,dtype='float32'),SR,subtype='FLOAT');c['narration']='chapters/'+name
 def resolve_cue(cue):
  cue=dict(cue);sid=cue.pop('segment_id',None)
  if sid:
   s=next(s for s in segments if s['id']==sid)
   cue=translate(cue,s)
   cue['anchor_segment_id']=sid
  elif any(s.get('internal_pauses') for s in segments):
   raise ValueError('With internal pauses, every cue must use segment_id and original source-local times')
  return cue
 tl={'schema_version':1,'time_basis':'seconds derived from actual 48000Hz sample ledger','sample_rate':SR,'fps':fps,'samples_per_frame':samples_per_frame,'duration':cursor/SR,'samples':cursor,'frames':cursor//samples_per_frame,'narration':'narration_48k_mono.wav','segments':segments,'subtitles':phrases,'chapters':chapters,'music_sections':sections,'music_cues':[resolve_cue(c) for c in layout.get('music_cues',[])],'sound_cues':[resolve_cue(c) for c in layout.get('sound_cues',[])],'source_paragraphs_sha256':sha(paragraphs_path),'layout_sha256':sha(layout_path)}
 tl['narration_sha256']=sha(target)
 if layout.get('chapter_music_strategy'):tl['chapter_music_strategy']=layout['chapter_music_strategy']
 if layout.get('conclusion_cue'):
  anchor=dict(layout['conclusion_cue']);sid=anchor.get('segment_id');assert sid,'Assembly conclusion must be anchored to a segment'
  seg=next(s for s in segments if s['id']==sid);assert anchor.pop('source_audio_sha256',None)==seg['source_sha256'],'Conclusion source WAV changed; review actual word tail'
  tl['conclusion_cue']={**resolve_cue(anchor),'narration_sha256':sha(target)}
 for k in ('visual_cues','observation_music_ducks'):
  tl[k]=[resolve_cue(c) for c in layout.get(k,[])]
 if any(s.get('internal_pauses') for s in segments):
  assert tl['visual_cues'],'Any internal pause requires explicit visual_cues for synchronised picture timing'
 save(out/'timeline.json',tl);save(out/'visual_cues.json',{'timeline_sha256':sha(out/'timeline.json'),'narration_sha256':sha(target),'duration':tl['duration'],'cues':tl['visual_cues']});save(out/'subtitles.json',[{k:p[k] for k in ['start','end','text']} for p in phrases]);save(out/'media_chapters.json',[{k:c[k] for k in ['start','title']} for c in chapters])
 (out/'subtitles.srt').write_text('\n'.join(f'{i+1}\n{srt_time(p["start"])} --> {srt_time(p["end"])}\n{p["text"]}\n' for i,p in enumerate(phrases)),'utf-8')
 report={'status':'sample_identical_all_paragraphs','samples':cursor,'frames':cursor//samples_per_frame,'duration':cursor/SR,'time_stretch':False,'speech_trimmed_samples':0,'padding_samples':sum(s['alignment_padding_samples'] for s in segments),'explicit_tail_samples':sum(s['explicit_tail_samples'] for s in segments),'paragraph_checks':records,'narration_sha256':sha(target),'paid_calls':0}
 report.update(internal_pause_samples=sum(s['internal_pause_samples'] for s in segments),all_source_samples_preserved=True,subtitles_and_visual_cues_use_same_shift_map=True)
 save(out/'assembly_verification.json',report);print(json.dumps(report,ensure_ascii=False,indent=2));return tl
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--paragraphs',type=Path,required=True);p.add_argument('--layout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assemble(a.paragraphs,a.layout,a.output)
