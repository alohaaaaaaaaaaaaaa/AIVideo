"""Sample-exact editorial pauses with explicit coordinate conversion.
A pause has original source time, source WAV hash, and a whole-frame duration.
No syllable cuts, phrase-spanning cuts, or implicit image-time guesses.
"""
import math
import numpy as np
SR=48000
TIME_KEYS=('start','end','time','core_start','core_end','scope_end')
def shifted(t,events,end=False):
 t=float(t)
 return t+sum(e['duration'] for e in events if e['at']<t-1e-9 or (not end and abs(e['at']-t)<=1e-9))
def apply_pauses(x,requested,source_sha,phrases,fps):
 events=[];last=-1;spans=[];parts=[];offset=0;previous=0
 for item in requested:
  e=dict(item);a=float(e['at']);d=float(e['duration'])
  assert math.isfinite(a) and math.isfinite(d) and 0<a<len(x)/SR and 0<d<=3
  assert a>last and abs(d*fps-round(d*fps))<1e-7,'Pauses must be ordered, unique and whole-frame durations'
  assert e.get('source_audio_sha256')==source_sha,'Pause anchor WAV changed or was already edited; re-review the original source'
  assert str(e.get('reason','')).strip(),'Pause needs an editorial reason'
  at=round(a*SR);n=round(d*SR);a=at/SR;d=n/SR
  edge=x[max(0,at-240):min(len(x),at+240)];peak=float(np.max(np.abs(edge)))
  assert peak<1e-4,'Pause point is not within a verified silent gap'
  assert all(not(p['start']<a-1e-9 and a<p['end']-1e-9) for p in phrases),'Pause bisects a subtitle phrase; review and split the real phrase boundaries first'
  parts.extend([x[previous:at],np.zeros((n,x.shape[1]),np.float32)])
  spans.append({'source_start_sample':previous,'source_end_sample':at,'edited_start_sample':previous+offset,'edited_end_sample':at+offset})
  events.append({**e,'at':a,'duration':d,'inserted_samples':n,'edge_peak':peak,'source_sample':at,'edited_insert_sample':at+offset})
  offset+=n;previous=at;last=a
 parts.append(x[previous:]);spans.append({'source_start_sample':previous,'source_end_sample':len(x),'edited_start_sample':previous+offset,'edited_end_sample':len(x)+offset})
 y=np.concatenate(parts) if events else x
 for s in spans:assert np.array_equal(x[s['source_start_sample']:s['source_end_sample']],y[s['edited_start_sample']:s['edited_end_sample']])
 return y,events,spans
def translate(cue,segment):
 c=dict(cue);events=segment.get('internal_pauses',[])
 for k in TIME_KEYS:
  if k in c:
   end=k in ('end','core_end','scope_end');c[k]=round(segment['start']+shifted(c[k],events,end=end),9)
 return c
