"""Offline checks on delivered real audio and paid-call safeguards; no API calls."""
from pathlib import Path
import hashlib,importlib.metadata,json,tempfile
import numpy as np,soundfile as sf
import tts
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ref=ROOT/'参考库/声音';demo=ref/'离线复现样品';result={'status':'technical_checks_passed','paid_calls':0,'human_full_listening_claimed':False,'checks':[]}
 src,sr=sf.read(demo/'voice_48k_mono.wav',dtype='float32');expected=np.repeat(src[:,None]/np.sqrt(2),2,axis=1).astype(np.float32)
 voice,_=sf.read(demo/'输出/voice_48k_stereo.wav',dtype='float32');assert np.array_equal(voice,expected)
 mix,_=sf.read(demo/'输出/mix_48k_stereo.wav',dtype='float32');music,_=sf.read(demo/'输出/music_48k_stereo.wav',dtype='float32');sfx,_=sf.read(demo/'输出/sfx_48k_stereo.wav',dtype='float32')
 residual=float(np.max(np.abs(mix.astype(np.float64)-music-sfx-voice)));assert residual<1e-7 and np.isfinite(mix).all() and np.max(np.abs(mix))<1
 result['checks'].append({'check':'actual_render_voice_samples_preserved_equal_power','passed':True,'samples':len(src),'duration':len(src)/sr,'pcm_mix_residual_peak':residual})
 record=tts.read(demo/'输出/混音核验.json');assert record['final']['complete_decode'] and record['final']['clipped_samples']==0 and record['final']['true_peak_dbtp']<-1
 result['mix_measurement']={k:record['final'][k] for k in ['duration','sample_peak_dbfs','clipped_samples','integrated_lufs','true_peak_dbtp','loudness_range_lu','complete_decode']}
 bridge=tts.read(demo/'桥接输出/衔接配乐核验.json');assert bridge['voice_sample_identical'] and bridge['verification']['clipped_samples']==0
 result['bridge_measurement']=bridge['verification'];result['checks'].append({'check':'actual_chapter_bridge_preserved_original_voice','passed':True})
 name=tts.read(ref/'姓名离线复现/C01_P001.json');assert name['text'].startswith('我是啊子牙。') and name['phrases'][0]['tts_text']=='我是阿子牙。' and not name['time_stretch']
 result['checks'].append({'check':'real_cached_name_audio_provider_alignment','passed':True,'duration':name['duration'],'samples':name['samples'],'new_tts_calls':0})
 font=ref/'音源/GeneralUser-GS.sf2';cfg=tts.read(ROOT/'默认配置/声音.json');assert sha(font)==cfg['music']['soundfont_sha256']
 result['checks'].append({'check':'actual_soundfont_sha_matches_approved_reference','passed':True,'sha256':sha(font)})
 midi=(demo/'输出/score.mid').read_bytes();assert midi.startswith(b'MThd') and midi.count(b'MTrk')==5
 result['checks'].append({'check':'four_instrument_smf_plus_tempo_track','passed':True})
 # Simulate denied networking: a regression must fail before any network call.
 def forbidden_session():raise AssertionError('Network must never run in this verification')
 prior=tts.requests.Session;tts.requests.Session=forbidden_session
 try:
  tts.execute(ref/'TTS离线计划示例.json',ref/'姓名修音缓存示例',0,['C01_P001'],False)
  with tempfile.TemporaryDirectory() as d:
   tmp=Path(d);raised=False
   try:tts.execute(ref/'TTS离线计划示例.json',tmp,0,None,False)
   except RuntimeError as e:raised='Budget cap exceeded' in str(e)
   assert raised
  with tempfile.TemporaryDirectory() as d:
   tmp=Path(d);row=tts.read(ref/'TTS离线计划示例.json')['paragraphs'][0]
   tts.save(tmp/'receipts'/(row['cache_key']+'.json'),{'status':'submission_uncertain_requires_reconciliation','estimated_cost_cny':row['estimated_cost_cny']})
   raised=False
   try:tts.execute(ref/'TTS离线计划示例.json',tmp,10,['C01_P001'],False)
   except RuntimeError as e:raised='reconcile' in str(e)
   assert raised
 finally:tts.requests.Session=prior
 result['checks'].append({'check':'paid_call_guards_no_network','cache_hit':True,'budget_exceeded_stops_before_submit':True,'uncertain_submit_blocks_retry':True,'passed':True})
 result['dependencies']={k:importlib.metadata.version(k) for k in ['numpy','scipy','soundfile','imageio-ffmpeg','requests']};result['libsndfile']=sf.__libsndfile_version__
 tts.save(ref/'技术核验.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
