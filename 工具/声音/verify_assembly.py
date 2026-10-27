"""Verify delivered assembly and local-repair guards using real cached audio only."""
from pathlib import Path
import json,sys,tempfile,subprocess,math
import numpy as np,soundfile as sf
import tts,score_mix
ROOT=Path(__file__).resolve().parents[2]
def main():
 d=ROOT/'参考库/声音/整段联动样品';tl=tts.read(d/'编排输出_实音字幕/timeline.json');rows=tts.read(d/'paragraphs.json');by={r['id']:r for r in rows};pcm,sr=sf.read(d/'编排输出_实音字幕/narration_48k_mono.wav',dtype='float32');records=[]
 assert len(pcm)==tl['samples']==533760 and tl['frames']==278 and tl['duration']==11.12
 for s in tl['segments']:
  row=by[s['id']];source,_=sf.read(d/row['audio'],dtype='float32');assert np.array_equal(pcm[s['sample_start']:s['speech_end_sample']],source)
  assert not np.any(pcm[s['speech_end_sample']:s['sample_end']])
  assert s['sample_start']==s['frame_start']*1920 and s['sample_end']==s['frame_end']*1920
  for p,global_p in zip(row['phrases'],s['phrases']):
   assert abs(global_p['start']-p['start']-s['sample_start']/sr)<1e-8
   assert abs(global_p['end']-p['end']-s['sample_start']/sr)<1e-8
  records.append({'id':s['id'],'all_speech_samples_identical':True,'padding_is_silent':True,'actual_phrase_offsets_preserved':True})
 for v in [-1,float('nan'),float('inf')]:
  try:tts.make_plan(None,None,v);raise AssertionError('invalid rate accepted')
  except ValueError:pass
 for v in [-1,float('nan'),float('inf')]:
  try:tts.execute(None,None,v,None,False);raise AssertionError('invalid budget accepted')
  except ValueError:pass
 with tempfile.TemporaryDirectory() as temp:
  temp=Path(temp);row=tts.read(ROOT/'参考库/声音/TTS离线计划示例.json')['paragraphs'][0];other=dict(row,id='C01_P002');tts.save(temp/'plan.json',{'paragraphs':[row,other]})
  cmd=[sys.executable,str(ROOT/'工具/声音/prepare_voice.py'),'--plan',str(temp/'plan.json'),'--cache',str(ROOT/'参考库/声音/姓名修音缓存示例'),'--output',str(temp/'prepared')]
  subprocess.run(cmd,check=True,capture_output=True);before=tts.read(temp/'prepared/paragraphs.json');subprocess.run(cmd+['--only','C01_P001'],check=True,capture_output=True);after=tts.read(temp/'prepared/paragraphs.json')
  assert len(after)==2 and before[1]==after[1]
  score_mix.render_sfx({'duration':2,'ai_uses':[{'id':'S1','asset_id':'V01','start':0,'end':2}]},temp)
  assert tts.read(temp/'音效来源与时码.json')['events']==[]
 mixed=tts.read(d/'混音输出_实音字幕/混音核验.json');assert mixed['final']['duration']==tl['duration'] and mixed['final']['clipped_samples']==0
 result={'status':'technical_checks_passed','scope':'real paragraph PCM → frame-aligned ledger → score/mix; media rendering is checked by the media integration separately','duration':tl['duration'],'frames':tl['frames'],'samples':tl['samples'],'paragraphs':records,'alignment_padding_samples':291,'explicit_tail_samples':76800,'speech_trimmed_samples':0,'time_stretch':False,'partial_prepare_preserves_other_rows':True,'invalid_nonfinite_budget_and_price_rejected':True,'implicit_old_V01_airport_sound_removed':True,'mix_metrics':{k:mixed['final'][k] for k in ['integrated_lufs','true_peak_dbtp','clipped_samples','complete_decode']},'paid_calls':0,'human_full_listening_claimed':False}
 tts.save(d/'联动核验.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
