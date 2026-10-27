"""Explicit real-audio conclusion anchors. No inference from topic or wording."""
from pathlib import Path
import copy,hashlib,math
import numpy as np,soundfile as sf
SR=48000
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare_conclusion(timeline,narration):
    tl=copy.deepcopy(timeline);anchor=tl.get('conclusion_cue')
    if not anchor:
        if any(c.get('type')=='resolve' for c in tl.get('music_cues',[])):
            raise ValueError('A production resolve needs conclusion_cue bound to the actual narration WAV; subtitle end alone is insufficient')
        return tl,None
    assert anchor.get('narration_sha256')==sha(narration),'Conclusion anchor audio changed; review actual edited WAV'
    assert anchor.get('verification_method') in ['waveform_and_independent_asr','waveform_and_listening','approved_original_waveform_review']
    a,b=float(anchor['core_start']),float(anchor['core_end']);delay=float(anchor.get('post_word_delay',.10));duration=float(tl['duration']);scope_end=float(anchor.get('scope_end',duration))
    assert all(math.isfinite(x) for x in [a,b,delay,scope_end]) and 0<=a<b<scope_end<=duration and .08<=delay<=.25
    with sf.SoundFile(narration) as f:
        assert f.samplerate==SR
        begin=round(a*SR);finish=min(f.frames,round((b+.12)*SR));f.seek(begin);x=f.read(finish-begin,dtype='float32',always_2d=True).mean(axis=1)
    hop=240;energy=np.sqrt(np.mean(np.pad(x,(0,(-len(x))%hop)).reshape(-1,hop)**2,axis=1));hits=np.flatnonzero(energy>10**(-43/20));assert len(hits),'No audible conclusion core'
    observed=(begin+(int(hits[-1])+1)*hop)/SR
    assert observed<=b+.08,('Audible voice continues past claimed word tail',b,observed)
    resolve=b+delay;assert scope_end-resolve>=2,'Conclusion needs >=2 seconds of musical tail'
    cues=[c for c in tl.get('music_cues',[]) if c.get('type')!='resolve' and c.get('role')!='conclusion_duck']
    cues.extend([{'type':'space','role':'conclusion_duck','start':max(0,a-.35),'end':b,'gain':10**(-2.5/20),'reason':'Let the complete core judgment finish before the cadence'},
      {'type':'resolve','time':resolve,'scope_end':scope_end,'core_start':a,'core_end':b,'audio_verified':True,'reason':'Resolve after actual word tail; preserve music in later sections'}])
    tl['music_cues']=cues
    record={'core_start':a,'core_end':b,'rms_last_active_seconds':observed,'rms_window_ms':5,'rms_threshold_dbfs':-43,'resolve':resolve,'word_to_resolve_seconds':delay,'scope_end':scope_end,'tail_seconds':scope_end-resolve,'narration_sha256':sha(narration),'verification_method':anchor['verification_method'],'subtitle_end_used_as_word_tail':False,'narration_changed':False}
    tl['conclusion_verification']=record
    return tl,record
