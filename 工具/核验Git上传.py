"""Audit files Git would include without initializing/staging the real workspace.
Never prints secret values; known private credential values are compared in memory.
"""
from pathlib import Path
import subprocess,tempfile,json,re
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
R=Path(__file__).resolve().parents[1]
def main():
 with tempfile.TemporaryDirectory(prefix='aziyah-git-audit-') as td:
  gd=Path(td)/'repo.git'
  subprocess.run(['git','init','--bare','--quiet',str(gd)],check=True,capture_output=True)
  cmd=['git','--git-dir='+str(gd),'--work-tree='+str(R)]
  data=subprocess.run(cmd+['ls-files','--others','--exclude-standard','-z'],cwd=R,capture_output=True,check=True).stdout
  paths=[R/x.decode() for x in data.split(b'\0') if x]
  refs=['工具/声音/tts.py','参考库/声音/音源/GeneralUser-GS_LICENSE.txt','参考库/品牌/B站/字体/Yozai-OFL.txt','参考库/网页取证/央视原页滚动/输入/保存原始.html','参考库/原片同段对标/开场29秒/导出/bili.mp4']
  included={str(p.relative_to(R)) for p in paths};assert all(x in included for x in refs)
 known=[]
 cred=Path.home()/'Library/Application Support/啊子牙视频工作室/credentials.json'
 if cred.is_file():
  obj=json.loads(cred.read_text());known=[v.encode() for k,v in obj.items() if isinstance(v,str) and len(v)>=16 and any(w in k.upper() for w in ('KEY','TOKEN','SECRET'))]
 findings=[];total=0;text_checked=0;largest=[]
 patterns=[('private_key',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),('jwt',rb'eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}'),('bearer_literal',rb'(?i)Bearer\s+[A-Za-z0-9_.-]{32,}')]
 text_ext={'.md','.txt','.json','.py','.html','.css','.js','.yml','.yaml','.toml','.ini','.cfg','.ass','.srt','.xml','.csv','.log'}
 for p in paths:
  if p.is_symlink():findings.append({'path':str(p.relative_to(R)),'kind':'symlink_review'});continue
  n=p.stat().st_size;total+=n;largest.append((n,str(p.relative_to(R))))
  if p.suffix.lower() in text_ext or p.name.startswith('.'):
   b=p.read_bytes();text_checked+=1
   if any(k in b for k in known):findings.append({'path':str(p.relative_to(R)),'kind':'known_credential_value'})
   for label,pat in patterns:
    if re.search(pat,b):findings.append({'path':str(p.relative_to(R)),'kind':label})
 report={'checked_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'scope':'private Git upload candidates using current .gitignore; no real repo initialized/staged/pushed','candidate_files':len(paths),'candidate_bytes':total,'text_files_scanned':text_checked,'known_credential_value_check_available':bool(known),'secret_values_logged':False,'findings':findings,'files_over_50MiB':[{'path':p,'bytes':n} for n,p in sorted(largest,reverse=True) if n>50*2**20],'essential_examples_included':refs,'lfs_installed':subprocess.run(['git','lfs','version'],capture_output=True).returncode==0,'limits':'Known credential and selected token patterns only; no claim of exhaustive secret detection. Private remote not yet selected.'}
 report['status']='passed' if not findings else 'needs_review'
 (R/'检查/Git上传准备.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
 if findings:raise SystemExit(2)
if __name__=='__main__':main()
