"""Regression: a stale narration cut/asset/cue must not silently render."""
from pathlib import Path
import copy,contextlib,io,json,tempfile,hashlib,os
from compile_storyboard import compile_plan,sha
R=Path(__file__).resolve().parents[2];B=R/'参考库/原片同段对标/开场29秒';P=json.loads((B/'声画任务.json').read_text())
results={}
with tempfile.TemporaryDirectory(prefix='导演绑定_') as td:
 D=Path(td)
 for k in ('timeline','audio'):P[k]=str((B/P[k]).resolve())
 for s in P['shots']:
  for k in ('path','acceptance_record'):
   if k in s:s[k]=str((B/s[k]).resolve())
 def run(name,edit,expected):
  p=copy.deepcopy(P);edit(p);file=D/(name+'.json');file.write_text(json.dumps(p));error=None
  try:
   with contextlib.redirect_stdout(io.StringIO()):compile_plan(file,D/(name+'_manifest.json'))
  except (ValueError,KeyError,FileNotFoundError) as e:error=str(e)
  if expected is None:assert error is None,error
  else:assert error and expected in error,(name,error)
  results[name]={'passed':True,'blocked_reason':error}
 run('valid_adopted_opening',lambda p:None,None)
 logo=R/'参考库/品牌/B站/透明PNG/啊子牙_悠哉_B站无账号_1080p.png'
 def mark_paths(p):p['delivery'].update(watermark={'path':str(logo)},versions=[{'id':'bili','watermark':True,'watermark_path':str(logo),'watermark_override':{'path':str(logo)}}])
 run('custom_mark_paths',mark_paths,None)
 marked=json.loads((D/'custom_mark_paths_manifest.json').read_text())
 for rel in [marked['watermark']['path'],marked['versions'][0]['watermark_path'],marked['versions'][0]['watermark_override']['path']]:assert not Path(rel).is_absolute() and (D/rel).resolve()==logo.resolve()

 def smaller(p):
  p['delivery'].update(width=1280,height=720)
  for shot in p['shots']:shot.pop('watermark_position',None)
 run('scaled_default_mark',smaller,None)
 small=json.loads((D/'scaled_default_mark_manifest.json').read_text());mark=small['watermark']
 assert mark['x']>=0 and mark['x']+mark['width']<=1280 and mark['y']<720
 run('stale_timeline',lambda p:p.update(timeline_sha256='0'*64),'实音时间线已改变')
 run('asset_replaced',lambda p:p['shots'][0].update(asset_sha256='0'*64),'素材换版')
 run('shot_gap',lambda p:p['shots'][0].update(start_offset=.04),'空洞或重叠')
 run('no_viewer_task',lambda p:p['shots'][0].update(viewer_task=''),'观众')
 run('video_too_short',lambda p:p['shots'][3].update(end_offset=4),'视频不足')
 run('ai_acceptance_old',lambda p:p['shots'][1].update(acceptance_record='missing.json'),'验收记录丢失')
 narration=R/'参考库/声音/开场连续29秒对标/voice_48k.wav'
 cues={'timeline_sha256':P['timeline_sha256'],'narration_sha256':sha(narration),'cues':[{'id':'H01','time':.6667}]}
 cp=D/'cues.json';cp.write_text(json.dumps(cues))
 receipt={'asset_sha256':P['shots'][0]['asset_sha256'],'visual_cues_sha256':sha(cp),'cue_ids':['H01']};rp=D/'render_receipt.json';rp.write_text(json.dumps(receipt))
 def add_cues(p):p.update(visual_cues=str(cp),narration=str(narration));p['shots'][0].update(cue_ids=['H01'],cue_render_receipt=str(rp))
 run('current_cue_bound',add_cues,None)
 receipt['visual_cues_sha256']='0'*64;rp.write_text(json.dumps(receipt))
 run('stale_animation',add_cues,'尚未用当前触发点')
 cues['timeline_sha256']='0'*64;cp.write_text(json.dumps(cues))
 run('stale_cues',add_cues,'旧时间线')
out=R/'检查/本轮对标/导演分镜绑定核验.json';out.write_text(json.dumps({'status':'passed','checks':results,'scope':'actual opening plan with deliberately stale inputs; no aesthetic claim'},ensure_ascii=False,indent=2)+'\n');print(out)
