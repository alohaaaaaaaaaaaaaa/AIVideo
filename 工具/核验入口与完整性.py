"""Check current authored entry links and syntax without scanning external archived pages."""
from pathlib import Path
from urllib.parse import urlparse,unquote
from html.parser import HTMLParser
import hashlib,json,re,py_compile,ast
R=Path(__file__).resolve().parents[1]
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ('href','src','poster') and v:self.links.append(v)
def main():
 files=[R/'00_从这里开始.md',R/'AGENTS.md',R/'打开工作室.html',R/'制作技能/aziyah-video/SKILL.md',R/'检查/本轮对标/差异与修复.md',*sorted((R/'文档').glob('*.md'))]
 files += [R/p for p in ['参考库/原片同段对标/开场29秒/看同段对照.html','参考库/原片同段对标/开场29秒/导出/播放成片.html','参考库/网页取证/看网页参考.html','参考库/AI生成/本轮实测/看真实接口样片.html','参考库/声音/试听默认声音.html']]
 missing=[];count=0
 for p in files:
  s=p.read_text()
  if p.suffix=='.html':parser=Links();parser.feed(s);links=parser.links
  else:links=re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',s)
  for raw in links:
   raw=raw.strip('<>');u=urlparse(raw)
   if u.scheme or not u.path:continue
   path=(p.parent/unquote(u.path)).resolve();count+=1
   if not path.exists():missing.append({'file':str(p.relative_to(R)),'link':raw})
 python=[];hardcoded=[]
 for p in (R/'工具').rglob('*.py'):
  if any(x in ('历史','__pycache__') for x in p.parts):continue
  py_compile.compile(str(p),doraise=True);python.append(str(p.relative_to(R)))
  if p.name=='audit_portability.py':continue
  if re.search(r'/Users/[^\s"\']+/xsufo',p.read_text()):hardcoded.append(str(p.relative_to(R)))
 credential_names=[str(p.relative_to(R)) for p in R.rglob('*') if p.is_file() and not any(x in ('.venv','历史','__pycache__') for x in p.parts) and (p.name in ('credentials.json','ky.json') or p.name.startswith('.env'))]
 report={'status':'passed' if not (missing or hardcoded or credential_names) else 'failed','checked_links':count,'missing_links':missing,'syntax_checked_python_files':len(python),'runtime_hardcoded_old_root':hardcoded,'credential_files_in_project':credential_names,'credential_contents_not_read':True,'scope':'authored entry/docs/player links; vendor archived HTML intentionally excluded'}
 (R/'检查/入口与文件完整性.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
 assert report['status']=='passed'
if __name__=='__main__':main()
