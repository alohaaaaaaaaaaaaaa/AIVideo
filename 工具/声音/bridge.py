"""章间音乐桥：原旁白逐样本保留，既有章节音轨只移动、不变速。

python bridge.py --timeline old_timeline.json --transitions transitions.json --output 独立目录 [--plan-only]
输入 timeline 是已完成段内停顿、尚未加入章间停顿的版本。对应各章BGM须先重混。
transitions JSON:
 {"transitions":[{"after_chapter":"01","duration":1.2,"overlap_before":0.8,"overlap_after":0.8},...],
  "new_duration":61.2,
  "pause_events":[{"start":20.0,"end":21.2,"gain_db":-3.0,"reason":"曝光前留拍"}]}
所有接缝必须全列，duration允许0。pause_events使用输入timeline时间，先移位再执行。
仅写入--output；不改原timeline、各章stem或现有全片混音。仅本地SF2生成，无付费调用。
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,re,subprocess
import numpy as np
import soundfile as sf
from scipy import ndimage,signal
import imageio_ffmpeg

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
PALETTE=ROOT/'参考库/声音/音源'
SR=48000
NAMES={'voice':'voice_48k_stereo.wav','music':'music_48k_stereo.wav','sfx':'sfx_48k_stereo.wav','mix':'mix_48k_stereo.wav'}

def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def count(t):return round(float(t)*SR)
def db(v):return float(20*np.log10(max(float(v),1e-12)))
def peak(a):return float(np.max(np.abs(a))) if a.size else 0.
def rms(a):return float(np.sqrt(np.mean(np.square(a,dtype=np.float64)))) if a.size else 0.
def raised(q):return .5-.5*np.cos(np.pi*np.clip(q,0,1))
def slices(path,start,end):
 with sf.SoundFile(path) as f:
  assert f.samplerate==SR and f.channels==2
  f.seek(start);x=f.read(end-start,dtype='float32',always_2d=True)
 assert len(x)==end-start
 return x

def make_plan(tl,supplied):
 chapters=tl['chapters'];assert len(chapters)>=2
 assert len({str(c['id']).zfill(2) for c in chapters})==len(chapters)
 cursor=0.
 for c in chapters:
  assert str(c['id']).isdigit() and abs(float(c['start'])-cursor)<.001 and float(c['end'])>float(c['start'])
  cursor=float(c['end'])
 assert abs(cursor-float(tl['duration']))<.001
 raw=supplied.get('transitions',supplied.get('records',[]))
 by={str(r.get('after_chapter',r.get('chapter',''))).zfill(2):r for r in raw}
 assert set(by)=={str(c['id']).zfill(2) for c in chapters[:-1]},'逐一列明所有接缝（不加时处duration=0）'
 gap_sum=0.;schedule=[];trans=[]
 for i,c in enumerate(chapters):
  duration=float(c['end'])-float(c['start']);new_start=float(c['start'])+gap_sum;new_end=new_start+duration
  schedule.append({**c,'old_start':c['start'],'old_end':c['end'],'start':new_start,'end':new_end,'duration':duration})
  if i==len(chapters)-1:break
  r=by[str(c['id']).zfill(2)];gap=float(r['duration']);before=float(r.get('overlap_before',.8));after=float(r.get('overlap_after',.8))
  assert 0<=gap<=6 and .5<=before<=1.0 and .5<=after<=1.0
  if 'new_start' in r:assert abs(float(r['new_start'])-new_end)<.02
  if 'new_end' in r:assert abs(float(r['new_end'])-(new_end+gap))<.02
  trans.append({**r,'after_chapter':str(c['id']).zfill(2),'before_chapter':str(chapters[i+1]['id']).zfill(2),'old_boundary':c['end'],'start':new_end,'end':new_end+gap,'duration':gap,'overlap_before':before,'overlap_after':after})
  gap_sum+=gap
 duration=float(tl['duration'])+gap_sum
 if 'new_duration' in supplied:assert abs(duration-float(supplied['new_duration']))<.001
 def shift(t):return float(t)+sum(x['duration'] for x in trans if x['old_boundary']<=float(t)+1e-8)
 pauses=[]
 for e in supplied.get('pause_events',[]):
  a,b=float(e['start']),float(e['end']);assert 0<=a<b<=float(tl['duration'])
  assert all(not(a<x['old_boundary']<b) for x in trans),'观察降乐窗口不得跨章，须分为两项'
  pauses.append({**e,'old_start':a,'old_end':b,'start':shift(a),'end':shift(b),'gain_db':float(e.get('gain_db',-3))})
  assert -12<=pauses[-1]['gain_db']<=0
 return {'input_duration':tl['duration'],'duration':duration,'fps':25,'added_seconds':gap_sum,'chapters':schedule,'transitions':trans,'pause_events':pauses}

def write_stems(plan,out,bgm_root):
 outputs={k:out/v for k,v in NAMES.items()};records=[]
 with sf.SoundFile(outputs['voice'],'w',samplerate=SR,channels=2,subtype='FLOAT') as ov, sf.SoundFile(outputs['music'],'w',samplerate=SR,channels=2,subtype='FLOAT') as om, sf.SoundFile(outputs['sfx'],'w',samplerate=SR,channels=2,subtype='FLOAT') as os:
  for c in plan['chapters']:
   ident=str(c['id']).zfill(2);p=bgm_root/f'C{ident}';sources={'voice':Path(c['narration']),'music':p/'music_48k_stereo.wav','sfx':p/'sfx_48k_stereo.wav'}
   n=count(c['duration']);h=hashlib.sha256()
   for kind,dst in [('voice',ov),('music',om),('sfx',os)]:
    with sf.SoundFile(sources[kind]) as src:
     assert src.samplerate==SR and src.frames==n,(sources[kind],src.frames,n)
     for b in src.blocks(blocksize=SR*5,dtype='float32',always_2d=True):
      if kind=='voice' and b.shape[1]==1:b=np.repeat(b/np.sqrt(2),2,axis=1).astype(np.float32)
      assert b.shape[1]==2
      if kind=='voice':h.update(b.tobytes())
      dst.write(b)
   gap=next((x for x in plan['transitions'] if x['after_chapter']==ident),None)
   if gap:
    zeros=np.zeros((count(gap['duration']),2),np.float32)
    for dst in (ov,om,os):dst.write(zeros)
   records.append({'chapter':ident,'narration_source':str(sources['voice']),'narration_source_sha256':sha(sources['voice']),'source_stereo_samples_sha256':h.hexdigest(),'source_frames':n,'output_start_sample':count(c['start']),'music_source':str(sources['music']),'music_source_sha256':sha(sources['music'])})
 # Confirm complete original samples in order at their shifted positions.
 for r in records:
  audio=slices(outputs['voice'],r['output_start_sample'],r['output_start_sample']+r['source_frames'])
  assert hashlib.sha256(audio.tobytes()).hexdigest()==r['source_stereo_samples_sha256'];r['narration_sample_identical']=True
 for p in outputs.values():
  if p.exists():
   with sf.SoundFile(p) as f:assert f.frames==count(plan['duration'])
 return outputs,records

def bridge_pitches(prev,next_plan):
 # The original composer adds a C cadence; use the common tones of the
 # actual last bar and next first bar, favouring C/E if that overlap exists.
 palette=module('bridge_chords',BASE/'score_mix.py')
 last=prev['bars'][-1]['chord'];first=next_plan['bars'][0]['chord']
 a={p%12 for p in palette.CHORDS[last][0]};b={p%12 for p in palette.CHORDS[first][0]};common=a&b
 preferred=[0,4,7,9,2,5,11]
 pcs=[x for x in preferred if x in common]
 if not pcs:pcs=[x for x in preferred if x in b][:2]
 return [60+x for x in pcs[:2]],last,first

def synthesize_bridge(rec,bgm_root,sampler,font):
 before,after,gap=rec['overlap_before'],rec['overlap_after'],rec['duration'];length=before+gap+after;n=count(length);sampler.N=n;sampler.DURATION=length
 prev=read(bgm_root/f"C{rec['after_chapter']}"/'编曲执行计划.json');nxt=read(bgm_root/f"C{rec['before_chapter']}"/'编曲执行计划.json')
 pitches,last,first=bridge_pitches(prev,nxt);audio=np.zeros((n,2),np.float32);events=[]
 for j,pitch in enumerate(pitches):
  at=.025*j;y=font.note(48,pitch,23,max(.35,length-.65-at));start=count(at);take=min(len(y),n-start);audio[start:start+take]+=y[:take]*.45
  events.append({'instrument':'strings','pitch':pitch,'time':at,'duration':length-.65-at,'velocity':23})
 # One fresh quiet response, no rhythmic pulse or sampled-waveform repeat.
 if gap>=1.20:
  at=before+gap*.48;pitch=pitches[-1]+(12 if int(rec['after_chapter'])%2==0 else 0);y=font.note(0,pitch,22,max(.25,min(.9,length-at-.2)));start=count(at);take=min(len(y),n-start);audio[start:start+take]+=y[:take]*.35
  events.append({'instrument':'piano','pitch':pitch,'time':at,'duration':min(.9,length-at-.2),'velocity':22})
 audio=signal.sosfilt(signal.butter(2,105,btype='highpass',fs=SR,output='sos'),audio,axis=0)
 audio=signal.sosfilt(signal.butter(2,4200,fs=SR,output='sos'),audio,axis=0)
 audio-=signal.sosfilt(signal.butter(2,[1300,3700],btype='bandpass',fs=SR,output='sos'),audio,axis=0)*.35
 audio=sampler.reverb(audio,1.1,.13,seed=501+int(rec['after_chapter']))
 return audio.astype(np.float32),{'previous_last_chord':last,'next_first_chord':first,'common_tone_pitches':pitches,'notes':events,'waveform_looped':False}

def protect_bridge(bridge,voice,old_peak,local_target):
 # Level is set to the two nearby already-ducked music stems; never above
 # their maximum. Only the new bridge receives this detector envelope.
 level_gain=local_target/max(rms(bridge),1e-12);bridge*=level_gain
 frame=480;mono=np.mean(voice,axis=1);pad=(-len(mono))%frame;frames=np.sqrt(np.mean(np.pad(mono,(0,pad)).reshape(-1,frame)**2,axis=1));active=ndimage.maximum_filter1d((frames>10**(-43/20)).astype(float),size=13,mode='nearest');env=np.zeros_like(active)
 for i,targ in enumerate(active):
  prior=env[i-1] if i else targ;alpha=np.exp(-.01/(.035 if targ>prior else .48));env[i]=targ+(prior-targ)*alpha
 duck=np.interp(np.arange(len(bridge))/SR,(np.arange(len(env))+.5)*.01,1-.75*env).astype(np.float32);bridge*=duck[:,None]
 # 250ms local guard, smoothed, prevents bridge from masking quiet words.
 window=12000;cap=np.ones(math.ceil(len(bridge)/window),np.float32)
 for i in range(len(cap)):
  v=voice[i*window:(i+1)*window];b=bridge[i*window:(i+1)*window];vr=rms(v);br=rms(b)
  if vr>10**(-38/20):cap[i]=min(1,vr*10**(-18/20)/max(br,1e-12))
 cap=ndimage.minimum_filter1d(cap,size=3,mode='nearest');bridge*=np.interp(np.arange(len(bridge))/SR,(np.arange(len(cap))+.5)*.25,cap).astype(np.float32)[:,None]
 final_gain=min(1,old_peak/max(peak(bridge),1e-12));bridge*=final_gain
 return bridge,{'initial_level_gain':level_gain,'peak_cap_gain':final_gain,'reference_local_rms_dbfs':db(local_target),'reference_peak_dbfs':db(old_peak),'new_bridge_peak_dbfs':db(peak(bridge)),'duck_attack_ms':35,'duck_release_ms':480,'lookahead_ms':60}

def add_bridges(plan,paths,out,bgm_root):
 sampler=module('bridge_sampler',BASE/'sampler.py');font=sampler.Font(PALETTE/'GeneralUser-GS.sf2');records=[]
 for rec in plan['transitions']:
  a=count(rec['start']-rec['overlap_before']);b=count(rec['end']+rec['overlap_after']);old=slices(paths['music'],a,b);voice=slices(paths['voice'],a,b)
  # Nearby 4-second context, excluding the inserted silent interval.
  pa=slices(paths['music'],max(0,count(rec['start']-4)),count(rec['start']));pb=slices(paths['music'],count(rec['end']),min(count(plan['duration']),count(rec['end']+4)));ref=np.concatenate([pa,pb]);old_peak=peak(ref);target=max(rms(pa),rms(pb))*10**(-1.5/20)
  generated,score=synthesize_bridge(rec,bgm_root,sampler,font);assert len(generated)==len(old)
  generated,levels=protect_bridge(generated,voice,old_peak,target)
  t=np.arange(len(old))/SR;w=np.ones(len(old),np.float32);before,after,gap=rec['overlap_before'],rec['overlap_after'],rec['duration'];front=t<before;back=t>before+gap;w[front]=raised(t[front]/before);w[back]=1-raised((t[back]-before-gap)/after)
  mixed=old*(1-w[:,None])+generated*w[:,None];assert peak(mixed)<=max(old_peak,peak(old))+1e-6
  with sf.SoundFile(paths['music'],'r+') as f:f.seek(a);f.write(mixed)
  sf.write(out/f"桥接_{rec['after_chapter']}_{rec['before_chapter']}.wav",generated,SR,subtype='FLOAT')
  records.append({**rec,**score,**levels,'region_start':a/SR,'region_end':b/SR,'mixed_peak_dbfs':db(peak(mixed)),'original_music_peak_dbfs':db(old_peak),'crossfade':'raised-cosine convex (weights sum to 1); original voice is not faded','boundary_sample_step_start':float(np.max(np.abs(mixed[0]-old[0]))),'boundary_sample_step_end':float(np.max(np.abs(mixed[-1]-old[-1])))})
 return records

def apply_pause_ducks(plan,paths):
 records=[]
 for e in plan['pause_events']:
  attack=float(e.get('attack',.35));release=float(e.get('release',.55));a=max(0,count(e['start']-attack));b=min(count(plan['duration']),count(e['end']+release));old=slices(paths['music'],a,b);t=np.arange(len(old))/SR+a/SR;level=10**(e['gain_db']/20)
  w=np.interp(t,[e['start']-attack,e['start'],e['end'],e['end']+release],[1,level,level,1]).astype(np.float32)
  with sf.SoundFile(paths['music'],'r+') as f:f.seek(a);f.write(old*w[:,None])
  records.append({**e,'region_start':a/SR,'region_end':b/SR,'attack':attack,'release':release,'voice_changed':False})
 return records

def mix_stream(plan,paths):
 stats={'frames':0,'clipped_samples':0,'sample_peak':0.,'nonvoice_safety_gain_min':1.}
 with sf.SoundFile(paths['voice']) as v,sf.SoundFile(paths['music'],'r+') as m,sf.SoundFile(paths['sfx'],'r+') as s,sf.SoundFile(paths['mix'],'w',samplerate=SR,channels=2,subtype='FLOAT') as o:
  while True:
   voice=v.read(SR*5,dtype='float32',always_2d=True)
   if not len(voice):break
   pos=m.tell();music=m.read(len(voice),dtype='float32',always_2d=True);sfx=s.read(len(voice),dtype='float32',always_2d=True);nonvoice=music+sfx;headroom=.94-np.abs(voice);assert headroom.min()>0;valid=np.abs(nonvoice)>1e-9;gain=min(1,float(np.min(headroom[valid]/np.abs(nonvoice[valid]))) if valid.any() else 1.)
   if gain<1:
    music*=gain;sfx*=gain;m.seek(pos);m.write(music);s.seek(pos);s.write(sfx)
   audio=voice+music+sfx;o.write(audio);stats['frames']+=len(audio);stats['clipped_samples']+=int(np.count_nonzero(np.abs(audio)>=1));stats['sample_peak']=max(stats['sample_peak'],peak(audio));stats['nonvoice_safety_gain_min']=min(stats['nonvoice_safety_gain_min'],gain)
 assert stats['frames']==count(plan['duration']) and stats['clipped_samples']==0
 stats['sample_peak_dbfs']=db(stats.pop('sample_peak'));return stats

def loudness(path):
 p=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-nostdin','-i',str(path),'-af','loudnorm=I=-17:TP=-2:LRA=11:print_format=json','-f','null','-'],capture_output=True)
 assert p.returncode==0,p.stderr.decode(errors='replace')[-3000:]
 hits=re.findall(r'\{[^{}]*"input_i"[^{}]*\}',p.stderr.decode(errors='replace'),re.S);assert hits
 d=json.loads(hits[-1]);return {'integrated_lufs':float(d['input_i']),'true_peak_dbtp':float(d['input_tp']),'loudness_range_lu':float(d['input_lra']),'complete_decode':True}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--timeline',type=Path,required=True);ap.add_argument('--transitions',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--bgm-root',type=Path,required=True);ap.add_argument('--plan-only',action='store_true');args=ap.parse_args()
 assert args.output.resolve() not in [(BASE/'声音').resolve(),args.bgm_root.resolve()],'必须输出到独立目录'
 tl=read(args.timeline)
 for c in tl['chapters']:
  p=Path(c['narration']);c['narration']=str(p if p.is_absolute() else args.timeline.resolve().parent/p)
 supplied=read(args.transitions);plan=make_plan(tl,supplied);args.output.mkdir(parents=True,exist_ok=True);save(args.output/'音乐桥执行计划.json',plan)
 if args.plan_only:print(json.dumps({'duration':plan['duration'],'added_seconds':plan['added_seconds'],'bridges':len(plan['transitions'])},ensure_ascii=False));return
 paths,voice_checks=write_stems(plan,args.output,args.bgm_root);bridges=add_bridges(plan,paths,args.output,args.bgm_root);ducks=apply_pause_ducks(plan,paths);stats=mix_stream(plan,paths);stats.update(loudness(paths['mix']));assert stats['true_peak_dbtp']<-1
 report={'status':'technical_checks_passed','input_timeline':str(args.timeline),'input_timeline_sha256':sha(args.timeline),'transitions_file':str(args.transitions),'duration':plan['duration'],'bridges':bridges,'observation_ducks':ducks,'narration_checks':voice_checks,'voice_unstretched':True,'voice_sample_identical':all(x['narration_sample_identical'] for x in voice_checks),'music_waveform_looped':False,'paid_calls':0,'outputs':{k:{'path':str(p),'sha256':sha(p)} for k,p in paths.items()},'verification':stats,'listening_review':'技术核验；不声称已人工听完整片'};save(args.output/'衔接配乐核验.json',report);print(json.dumps({'duration':plan['duration'],'bridges':len(bridges),'verification':stats},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
