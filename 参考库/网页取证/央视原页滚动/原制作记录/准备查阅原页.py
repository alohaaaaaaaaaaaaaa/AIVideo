"""Render unchanged saved news HTML for the one-off search/scroll action."""
from pathlib import Path
import json,hashlib
from playwright.sync_api import sync_playwright

BASE=Path(__file__).resolve().parents[2]
ROOT=BASE.parents[1]
OUT=BASE/'制作/画面/查阅原页'
OUT.mkdir(parents=True,exist_ok=True)
SRC=ROOT/'06_原始资料/新闻/E06_央视经济半小时_新浪转载.html'
URL='http://news.sina.com.cn/c/sd/2010-11-19/065721497404.shtml'
STYLES=ROOT/'10_重新策划/调查后续/证据素材/走访与军事报道/原站样式'
FIND=r'''phrase=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;const ns=[];let s='';while(n=w.nextNode()){if(n.parentElement.closest('script,style'))continue;ns.push({n,start:s.length});s+=n.textContent;}const out=[];let i=s.indexOf(phrase);while(i>=0){const a=ns.findLast(x=>x.start<=i),end=i+phrase.length,b=ns.findLast(x=>x.start<end);const r=document.createRange();r.setStart(a.n,i-a.start);r.setEnd(b.n,end-b.start);out.push(...Array.from(r.getClientRects()).filter(x=>x.width>0&&x.height>0).map(x=>({x:x.x+scrollX,y:x.y+scrollY,width:x.width,height:x.height})));i=s.indexOf(phrase,end);}return out;}'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
 ctx=browser.new_context(viewport={'width':1440,'height':1080},device_scale_factor=3,java_script_enabled=False,locale='zh-CN')
 page=ctx.new_page();blocked=[];styles=[]
 def route(r):
  u=r.request.url
  if u==URL:r.fulfill(status=200,content_type='text/html; charset=gb18030',body=SRC.read_bytes())
  elif u.endswith('/master.css'):
   f=STYLES/'sina_master.css';r.fulfill(status=200,content_type='text/css; charset=gb18030',body=f.read_bytes());styles.append(str(f.relative_to(ROOT)))
  elif u.endswith('/theme_standard.css'):
   f=STYLES/'sina_theme.css';r.fulfill(status=200,content_type='text/css; charset=gb18030',body=f.read_bytes());styles.append(str(f.relative_to(ROOT)))
  else:blocked.append(u);r.abort()
 page.route('**/*',route);page.goto(URL,wait_until='load',timeout=20000);page.evaluate('document.fonts.ready')
 phrases=['央视《经济半小时》：低空开放可淘金？','2010年7月7日','杭州萧山机场','小型私人飞机','典型的“黑飞”事件']
 points={q:page.evaluate(FIND,q) for q in phrases}
 assert all(points.values()),points
 clip={'x':200,'y':0,'width':720,'height':850}
 out=OUT/'E06_原页连续查阅条.png';page.screenshot(path=str(out),clip=clip,full_page=True,animations='disabled')
 data={'source':str(SRC.relative_to(ROOT)),'source_sha256':sha(SRC),'path':str(out.relative_to(ROOT)),'sha256':sha(out),'clip_css':clip,'device_scale_factor':3,'viewport':[1440,1080],'phrases':points,'styles':styles,'blocked_resources':len(blocked),'network_requests_sent':0,'source_text_changed':False}
 (OUT/'查阅坐标.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
 browser.close()
 print(json.dumps({'path':str(out),'coordinates':points},ensure_ascii=False))
