"""Offline exact reconstruction of the accepted opening from bundled voice and notes.
The next chapter's original four-second native stems are bridge context only.
"""
from pathlib import Path
import argparse,json,subprocess,sys
import numpy as np,soundfile as sf
import score_mix
ROOT=Path(__file__).resolve().parents[2]
REF=ROOT/'参考库/声音/开场连续29秒对标'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 chapter=a.output/'chapters/C01';chapter.mkdir(parents=True,exist_ok=True)
 subprocess.run([sys.executable,str(ROOT/'工具/声音/score_mix.py'),'--timeline',str(REF/'timeline.json'),'--narration',str(REF/'voice_48k.wav'),'--adopted-score',str(REF/'原C01逐音符.json'),'--output',str(chapter)],check=True)
 import shutil
 context=REF/'桥接上下文/C02';dest=a.output/'chapters/C02';dest.mkdir(exist_ok=True)
 for name in ['编曲执行计划.json','music_48k_stereo.wav','sfx_48k_stereo.wav','narration.wav']:shutil.copyfile(context/name,dest/name)
 tl={'duration':33.36,'chapters':[{'id':'01','start':0,'end':29.36,'narration':str((REF/'voice_48k.wav').resolve())},{'id':'02','start':29.36,'end':33.36,'narration':str((dest/'narration.wav').resolve())}]}
 score_mix.save(a.output/'bridge_timeline.json',tl)
 subprocess.run([sys.executable,str(ROOT/'工具/声音/bridge.py'),'--timeline',str(a.output/'bridge_timeline.json'),'--transitions',str(REF/'桥接接口.json'),'--bgm-root',str(a.output/'chapters'),'--output',str(a.output/'bridge')],check=True)
 n=round(29.36*48000);records={};final=a.output/'final';final.mkdir(exist_ok=True)
 for key in ['mix','voice','music','sfx']:
  x,sr=sf.read(a.output/'bridge'/f'{key}_48k_stereo.wav',dtype='float32',always_2d=True);x=x[:n];path=final/f'{key}_48k_stereo.wav';sf.write(path,x,sr,subtype='FLOAT')
  old=REF/f'old_{"voice_stereo" if key=="voice" else key}_48k.wav'
  if old.exists():
   y,_=sf.read(old,dtype='float32',always_2d=True);assert np.array_equal(x,y)
   records[key]={'sample_identical':True,'maximum_absolute_difference':0,'sha256':score_mix.sha(path)}
 score_mix.save(final/'reference_comparison.json',{'duration':29.36,'frames':734,'samples':n,'comparison':records,'old_project_required':False,'paid_calls':0,'music_from_notes':True,'original_C02_stems_used_only_for_bridge_context':True})
 print(final/'mix_48k_stereo.wav')
if __name__=='__main__':main()
