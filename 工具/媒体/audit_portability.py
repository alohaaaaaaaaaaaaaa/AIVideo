#!/usr/bin/env python3
"""Copy owned modules to a temporary independent root and run only offline operations."""
from pathlib import Path
import json,os,re,shutil,subprocess,sys,tempfile,hashlib
ROOT=Path(__file__).resolve().parents[2]
def main():
 report={'status':'running','scope':['工具/媒体','工具/生成','文档/05_剪辑字幕标注与交付.md','文档/06_AI画面与任务管理.md','参考库/证据画面','参考库/AI生成'],'paid_calls':0,'api_generation_calls':0,'actual_credentials_read':False,'checks':[],'notes':[]}
 owned=[ROOT/'工具/媒体',ROOT/'工具/生成']
 hardcoded=[]
 for folder in owned:
  for path in folder.glob('*.py'):
   if path.resolve()==Path(__file__).resolve():continue  # scanner's literal detection patterns aren't runtime paths
   source=path.read_text('utf-8')
   for lineno,line in enumerate(source.splitlines(),1):
    if re.search(r'/Users/[^\s]+|D:\\\\|xsufo/',line):hardcoded.append({'file':str(path.relative_to(ROOT)),'line':lineno})
 report['runtime_old_root_paths']=hardcoded
 # Only filenames inspected for credential material; contents are deliberately not read.
 suspicious=[]
 for folder in [ROOT/'工具',ROOT/'参考库',ROOT/'默认配置']:
  for path in folder.rglob('*'):
   if path.is_file() and (path.name in {'ky.json','.env'} or path.suffix.lower() in {'.key','.pem','.p12','.pfx'}):suspicious.append(str(path.relative_to(ROOT)))
 report['credential_filenames_in_project']=suspicious
 broken=[];checked=[]
 md_paths=[ROOT/'文档/05_剪辑字幕标注与交付.md',ROOT/'文档/06_AI画面与任务管理.md']
 md_paths += [p for folder in owned for p in folder.glob('*.md')]
 for path in md_paths:
  for raw in re.findall(r'\[[^\]]+\]\(([^)]+)\)',path.read_text('utf-8')):
   if raw.startswith(('https:','http:','#')):continue
   target=(path.parent/raw.split('#')[0]).resolve();checked.append(str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else raw)
   if not target.exists():broken.append({'source':str(path.relative_to(ROOT)),'target':raw})
 report['markdown_link_targets_checked']=checked;report['broken_links']=broken
 critical=['工具/生成/video.py','工具/生成/label_context.py','工具/生成/shots.schema.json','工具/生成/shots.example.json','工具/生成/authorization.example.json','工具/生成/plan.example.json','参考库/AI生成/旧项目真实例/开场三个镜头_真实提示词与验收.json','参考库/AI生成/官方文档_20261026/fetch_log.json','参考库/证据画面/平湖原文高光/高光示例配置.json','参考库/动画/字体/NotoSansCJKsc-Regular.otf','参考库/品牌/B站/透明PNG/啊子牙_悠哉_B站无账号_1080p.png']
 report['critical_references']=[{'path':p,'exists':(ROOT/p).is_file()} for p in critical]
 env=os.environ.copy();env.pop('MINIMAX_API_KEY',None)
 with tempfile.TemporaryDirectory(prefix='aziya-independent-') as temp:
  moved=Path(temp)/'工作室 moved';moved.mkdir()
  for rel in ['工具/媒体','工具/生成','参考库/动画/字体','参考库/证据画面','默认配置']:
   shutil.copytree(ROOT/rel,moved/rel,ignore=shutil.ignore_patterns('__pycache__'))
  commands=[('moved_existing_exports_verify',['工具/媒体/studio_media.py','verify','工具/媒体/离线测试/manifest.json']),
            ('fresh_media_render_decode',['工具/媒体/smoke_test.py']),
            ('video_mock_state_machine',['工具/生成/test_video_offline.py']),
            ('context_label_without_symlinks',['工具/生成/label_context.py','--input','工具/生成/离线标签测试/raw.mp4','--output','工具/生成/离线标签测试/moved_label.mp4','--confirmed-unlabeled']),
            ('evidence_highlight_relative_paths',['工具/媒体/evidence_highlight.py','参考库/证据画面/平湖原文高光/高光示例配置.json'])]
  for name,args in commands:
   result=subprocess.run([sys.executable,*args],cwd=moved,env=env,capture_output=True,text=True)
   report['checks'].append({'name':name,'passed':result.returncode==0,'exit_code':result.returncode,'output_tail':result.stdout[-300:].replace(str(moved),'<MOVED_ROOT>'),'error_tail':result.stderr[-800:].replace(str(moved),'<MOVED_ROOT>')})
  report['relocation_test']='Actual independent copy under random temporary path with spaces and Chinese characters; no old-root symlink; MINIMAX_API_KEY removed from child environment'
 report['authorization_boundary']={'plan_offline':True,'submit_requires_plan_hash_bound_actual_authorization':True,'submit_requires_verified_current_price_evidence':True,'amount_and_task_caps':True,'uncertain_submission_never_auto_retried':True,'query_download_do_not_create_generation':'covered by offline mock','cdn_has_no_authorization':'covered by offline mock','mock_authorization_refused_for_real_api':True,'actual_provider_paid_availability':'not tested; current legacy price not verified'}
 report['notes']=['Archive source files may mention historical xsufo relative paths; these are provenance, not runtime imports.','Existing check reports may record absolute source paths; rerender regenerates them, and verify compares content hashes after relocation.','Windows lock and font fallbacks implemented but not executed on Windows in this macOS session.','Secrets scan checked suspicious filenames only, did not read credential contents.','Input examples intentionally contain not-yet-created episode asset placeholders; they are schema examples, not adopted manifests.']
 report['status']='passed' if not hardcoded and not suspicious and not broken and all(x['exists'] for x in report['critical_references']) and all(x['passed'] for x in report['checks']) else 'needs_review'
 path=ROOT/'检查/媒体独立性审查.json';path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'report':str(path),'status':report['status'],'checks':[(x['name'],x['passed']) for x in report['checks']]},ensure_ascii=False))
 if report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
