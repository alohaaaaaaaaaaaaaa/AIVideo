"""Production music runner: compose each chapter, then apply explicit music bridges.
No time is added here: all editorial breathing must already exist in the ledger.
"""
from pathlib import Path
import argparse,copy,json,subprocess,sys
import soundfile as sf
import numpy as np
import score_mix,editorial
BASE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--timeline',type=Path,required=True);p.add_argument('--narration',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);tl,check=editorial.prepare_conclusion(score_mix.read(a.timeline),a.narration)
    chapters=tl.get('chapters',[])
    assert chapters and abs(chapters[0]['start'])<1e-8 and abs(chapters[-1]['end']-tl['duration'])<1e-8
    if len(chapters)>1:
        strategy=tl.get('chapter_music_strategy',{});assert strategy.get('mode')=='explicit_bridges','Choose and record chapter_music_strategy before full-film mix'
        transitions=strategy.get('transitions',[]);assert len(transitions)==len(chapters)-1
        assert all(float(e['duration'])==0 for e in transitions),'Music runner must not change picture/subtitle time; put all pauses into assemble ledger first'
    with sf.SoundFile(a.narration) as f:
        assert f.samplerate==48000 and f.frames==round(tl['duration']*48000),'Master narration differs from ledger'
    records=[];cursor=0
    for c in chapters:
        start,end=float(c['start']),float(c['end']);out=a.output/'chapters'/('C'+str(c['id']).zfill(2));out.mkdir(parents=True,exist_ok=True)
        assert abs(start-cursor)<1e-8 and end>start,'Chapters must be contiguous';cursor=end
        voice=out/'narration.wav'
        with sf.SoundFile(a.narration) as f:
            assert f.samplerate==48000;f.seek(round(start*48000));x=f.read(round((end-start)*48000),dtype='float32',always_2d=True)
        sf.write(voice,x,48000,subtype='FLOAT')
        sections=[]
        for s in tl['music_sections']:
            lo,hi=max(start,s['start']),min(end,s['end'])
            if lo<hi:sections.append({**s,'start':round(lo-start,8),'end':round(hi-start,8)})
        cues=[]
        for cue in tl.get('music_cues',[]):
            if cue['type']=='space':
                lo,hi=max(start,cue['start']),min(end,cue['end'])
                if lo<hi:cues.append({**cue,'start':round(lo-start,8),'end':round(hi-start,8)})
            elif start<=cue['time']<end:cues.append({**cue,'time':round(cue['time']-start,8),'scope_end':min(end,cue.get('scope_end',end))-start})
        sounds=[]
        for cue in tl.get('sound_cues',[]):
            when=cue.get('time',cue.get('start',0))
            if start<=when<end:sounds.append({**cue,'time':when-start,'duration':min(cue.get('duration',.16),end-when)})
        local={'duration':end-start,'music_sections':sections,'music_cues':cues,'sound_cues':sounds}
        if 'silent_music_rms_dbfs' in c:local['silent_music_rms_dbfs']=c['silent_music_rms_dbfs']
        plan=score_mix.compose(local);score_mix.save(out/'timeline.json',local);score_mix.save(out/'编曲执行计划.json',plan)
        from midi_export import write_midi
        write_midi(plan,out/'score.mid')
        music=score_mix.render_score(plan,out);sfx=score_mix.render_sfx(local,out);report=score_mix.mixdown(local,voice,None,music,sfx,out)
        records.append({'id':str(c['id']).zfill(2),'start':start,'end':end,'narration':str(voice.resolve()),'report':report})
    if len(chapters)>1:
        score_mix.save(a.output/'bridge_timeline.json',{'duration':tl['duration'],'chapters':records})
        score_mix.save(a.output/'bridge_plan.json',{'transitions':transitions,'new_duration':tl['duration'],'pause_events':tl.get('observation_music_ducks',[])})
        subprocess.run([sys.executable,str(BASE/'bridge.py'),'--timeline',str(a.output/'bridge_timeline.json'),'--transitions',str(a.output/'bridge_plan.json'),'--bgm-root',str(a.output/'chapters'),'--output',str(a.output/'final')],check=True)
        final=a.output/'final/mix_48k_stereo.wav'
    else:final=a.output/'chapters'/('C'+str(chapters[0]['id']).zfill(2))/'mix_48k_stereo.wav'
    final_voice=final.with_name('voice_48k_stereo.wav')
    original,sr=sf.read(a.narration,dtype='float32',always_2d=True);delivered,_=sf.read(final_voice,dtype='float32',always_2d=True)
    expected=np.repeat(original/np.sqrt(2),2,axis=1).astype(np.float32) if original.shape[1]==1 else original
    assert np.array_equal(expected,delivered),'Master speech samples changed during chapter mixing'
    measured=score_mix.inspect(final);assert measured['clipped_samples']==0 and measured['true_peak_dbtp']<=-1
    score_mix.save(a.output/'film_audio_report.json',{'duration':tl['duration'],'chapters':len(chapters),'chapter_bridges':len(chapters)-1,'added_seconds':0,'conclusion':check,'final_mix':str(final.resolve()),'final_mix_sha256':score_mix.sha(final),'paid_calls':0,'original_voice_samples_preserved':True,'timeline_sha256':score_mix.sha(a.timeline),'final_measurement':measured})
    print(final)
if __name__=='__main__':main()
