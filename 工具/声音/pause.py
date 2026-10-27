"""Insert quiet editorial breathing room without stretching speech.
Use actual waveform/word timestamps to choose --at. The caller must retime the
picture and subtitles by the emitted shift map; this tool never guesses it.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np,soundfile as sf
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--at',type=float,required=True);p.add_argument('--duration',type=float,required=True);a=p.parse_args()
 assert a.input.resolve()!=a.output.resolve();x,sr=sf.read(a.input,dtype='float32',always_2d=True);assert sr==48000 and 0<a.at<len(x)/sr and 0<a.duration<=3
 at=round(a.at*sr);n=round(a.duration*sr);edge=x[max(0,at-240):min(len(x),at+240)];quiet_peak=float(np.max(np.abs(edge)))
 assert quiet_peak<1e-4,'This cut is not in a verified silent gap; inspect real audio, do not cut a syllable'
 y=np.concatenate([x[:at],np.zeros((n,x.shape[1]),np.float32),x[at:]])
 assert np.array_equal(y[:at],x[:at]) and np.array_equal(y[at+n:],x[at:])
 a.output.parent.mkdir(parents=True,exist_ok=True);sf.write(a.output,y,sr,subtype='FLOAT')
 d={'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'old_duration':len(x)/sr,'new_duration':len(y)/sr,'insert_at':at/sr,'added_seconds':n/sr,'inserted_samples':n,'edge_peak':quiet_peak,'all_source_samples_preserved':True,'time_stretch':False,'shift_map':[{'from':at/sr,'shift':n/sr}],'required_follow_up':'Retiming of picture, subtitles, cues and music must use this shift map before export.'}
 a.output.with_suffix('.pause.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8');print(json.dumps(d,ensure_ascii=False))
if __name__=='__main__':main()
