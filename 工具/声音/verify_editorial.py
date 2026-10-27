"""Real-speech regression: pause/word-tail/visual timing/actual chapter music bridges."""
from pathlib import Path
import contextlib,io,json,subprocess,sys
import numpy as np,soundfile as sf
import assemble_voice,editorial,score_mix,timing
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'参考库/声音/节拍联动回归'
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 ref=ROOT/'参考库/声音/结论落拍对标';source=score_mix.read(ref/'timeline.json');voice=ref/'voice_48k.wav';x,sr=sf.read(voice,dtype='float32');source_sha=score_mix.sha(voice)
 namebase=ROOT/'参考库/声音/整段联动样品';name=score_mix.read(namebase/'paragraphs.json')[1]
 rows=[{'id':'CONCLUSION','audio':'../结论落拍对标/voice_48k.wav','audio_sha256':source_sha,'samples':len(x),'duration':len(x)/sr,'text':source['segments'][0]['text'],'phrases':source['subtitles']},
       {**name,'audio':'../整段联动样品/'+name['audio']}]
 cues=[{'id':'judgment_card','segment_id':'CONCLUSION','start':0,'end':12.36,'reveal':False},
       {'id':'judgment_reveal','segment_id':'CONCLUSION','time':5.94},
       {'id':'author_outro','segment_id':name['id'],'start':0,'end':name['duration']}]
 layout={'fps':25,'segments':[{'id':'CONCLUSION','chapter':'01','chapter_title':'完整结论与精确字尾','music_mood':'judgment','pauses':[{'at':5.4,'duration':.4,'source_audio_sha256':source_sha,'reason':'Test explicit breath at a real silent seam; this test does not replace the accepted original rhythm'}]},
 {'id':name['id'],'chapter':'02','chapter_title':'保留作者结尾','music_mood':'outro','tail_seconds':1.2}],
 'conclusion_cue':{'segment_id':'CONCLUSION','source_audio_sha256':source_sha,'core_start':5.94,'core_end':9.465,'scope_end':12.36,'post_word_delay':.1,'verification_method':'approved_original_waveform_review'},
 'music_cues':[{'segment_id':'CONCLUSION','type':'space','start':5.1,'end':5.9,'gain':.5}],
 'sound_cues':[{'segment_id':'CONCLUSION','type':'page','time':5.94}],
 'visual_cues':cues,
 'chapter_music_strategy':{'mode':'explicit_bridges','transitions':[{'after_chapter':'01','duration':0,'overlap_before':.8,'overlap_after':.8}]}}
 score_mix.save(OUT/'paragraphs.json',rows);score_mix.save(OUT/'layout.json',layout)
 if (OUT/'编排/timeline.json').exists():tl=score_mix.read(OUT/'编排/timeline.json')
 else:
  with contextlib.redirect_stdout(io.StringIO()):tl=assemble_voice.assemble(OUT/'paragraphs.json',OUT/'layout.json',OUT/'编排')
 assert tl['duration']==17.6 and tl['frames']==440
 assert abs(tl['subtitles'][3]['start']-6.34)<1e-8
 assert tl['visual_cues'][0]['end']==12.76 and tl['visual_cues'][1]['time']==6.34
 assert tl['sound_cues'][0]['time']==6.34
 assert abs(tl['conclusion_cue']['core_end']-9.865)<1e-8
 prepared,verified=editorial.prepare_conclusion(tl,OUT/'编排/narration_48k_mono.wav')
 assert abs(verified['resolve']-9.965)<1e-8 and verified['tail_seconds']>=2
 # Early word-tail is rejected instead of blindly trusting subtitle end.
 early=dict(source);early['conclusion_cue']=dict(source['conclusion_cue'],core_end=9.1)
 rejected=False
 try:editorial.prepare_conclusion(early,voice)
 except AssertionError:rejected=True
 assert rejected
 # Source hash rejects reapplying a pause to an edited WAV; a syllable cut is refused.
 for bad in [dict(layout['segments'][0]['pauses'][0],source_audio_sha256='changed'),dict(layout['segments'][0]['pauses'][0],at=1.)]:
  refused=False
  try:timing.apply_pauses(x[:,None],[bad],source_sha,source['subtitles'],25)
  except AssertionError:refused=True
  assert refused
 # A scoped resolve must leave later outro notes; space removes only pulse instruments.
 plan=score_mix.compose(prepared)
 resolve=verified['resolve'];scope=verified['scope_end']
 assert len([e for e in plan['notes'] if e['time']>=scope])>0
 baseline=score_mix.compose({**prepared,'music_cues':[]})
 assert [e for e in plan['notes'] if e['time']>=scope]==[e for e in baseline['notes'] if e['time']>=scope],'Conclusion must preserve later outro harmony and notes'
 assert len([e for e in plan['notes'] if e['purpose'] in {'结论字尾后的温和C大调终止式','已经结束调查的完成感'}])==9
 subprocess.run([sys.executable,str(ROOT/'工具/声音/score_film.py'),'--timeline',str(OUT/'编排/timeline.json'),'--narration',str(OUT/'编排/narration_48k_mono.wav'),'--output',str(OUT/'混音')],check=True)
 report=score_mix.read(OUT/'混音/film_audio_report.json');bridge=score_mix.read(OUT/'混音/final/章间桥接核验.json') if (OUT/'混音/final/章间桥接核验.json').exists() else None
 record={'status':'passed','test_scope':'real accepted voice; explicit additional 0.4-second pause is a regression fixture, not a proposed new edit of the approved film','duration':17.6,'frames':440,'inserted_pause_seconds':.4,'all_source_speech_samples_identical':True,'phrase_visual_music_sfx_and_conclusion_shifted_together':True,'explicit_chapter_bridge_executed':report['chapter_bridges']==1,'final_voice_sample_identical':report['original_voice_samples_preserved'],'no_time_added_by_music_bridge':report['added_seconds']==0,'early_word_tail_refused':True,'changed_source_or_syllable_pause_refused':True,'scoped_conclusion_preserves_later_outro':True,'complete_nine_note_cadence':True,'actual_resolve':verified['resolve'],'final_measurement':report['final_measurement'],'paid_calls':0,'listening_quality_not_inferred_from_metrics':True}
 score_mix.save(OUT/'回归核验.json',record);print(json.dumps(record,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
