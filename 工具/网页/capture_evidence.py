#!/usr/bin/env python3
"""Capture genuine public/archived HTML and DOM text-range coordinates.
No login state, source-text rewrite, CSS injection, paywall or challenge bypass.
Run: python capture_evidence.py config.json --output evidence_directory
"""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
import argparse,hashlib,json,math,os,re,shutil
from playwright.sync_api import sync_playwright

FIND=r'''arg=>{
 const scope=document.querySelector(arg.selector||'body'); if(!scope)throw new Error('Missing selector '+arg.selector);
 const walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT);let n,text='',nodes=[];
 while(n=walker.nextNode()){
  const p=n.parentElement;if(!p||p.closest('script,style,noscript,template'))continue;
  const cs=getComputedStyle(p);if(cs.display==='none'||cs.visibility==='hidden')continue;
  nodes.push({n,start:text.length});text+=n.textContent;
 }
 const matches=[];let at=text.indexOf(arg.quote);
 while(at>=0){
  const end=at+arg.quote.length,a=nodes.findLast(x=>x.start<=at),b=nodes.findLast(x=>x.start<end);
  const range=document.createRange();range.setStart(a.n,at-a.start);range.setEnd(b.n,end-b.start);
  const rects=Array.from(range.getClientRects()).filter(r=>r.width>0&&r.height>0).map(r=>[r.x+scrollX,r.y+scrollY,r.right+scrollX,r.bottom+scrollY]);
  if(rects.length){const parent=(range.commonAncestorContainer.nodeType===1?range.commonAncestorContainer:range.commonAncestorContainer.parentElement);const context=parent.closest('p,article,section,td')||parent;
   matches.push({quote:range.toString(),start:at,end,rects,context_text:context.innerText,context_tag:context.tagName});}
  at=text.indexOf(arg.quote,Math.max(end,at+1));
 }
 return {matches,scope_text:text};
}'''

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def safe_id(s):
 if not re.fullmatch(r'[A-Za-z0-9_-]+',s):raise ValueError('id 使用英文字母、数字、下划线或短横线')
 return s

def browser_path(explicit=None):
 if explicit:return str(Path(explicit).expanduser().resolve())
 # Prefer Playwright-managed browser; this fallback is only for a preinstalled cache.
 roots=[Path.home()/'Library/Caches/ms-playwright',Path.home()/'.cache/ms-playwright']
 for root in roots:
  matches=sorted(list(root.glob('chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell'))+list(root.glob('chromium_headless_shell-*/chrome-linux/headless_shell')),reverse=True)
  if matches:return str(matches[0])
 return None

def select_match(page,quote,selector='body',occurrence=None,within=None):
 found=page.evaluate(FIND,{'quote':quote,'selector':selector})['matches']
 if within:
  # Scope to the actual matched source paragraph, not a same-word appearance elsewhere.
  found=[m for m in found if m['start']>=within['start'] and m['end']<=within['end']]
 if occurrence is None:
  if len(found)!=1:raise ValueError(f'原文匹配必须唯一：{quote!r}，找到 {len(found)} 处；请给 selector/context 或显式 occurrence')
  return found[0]
 if not 0<=occurrence<len(found):raise ValueError(f'匹配序号超范围：{quote!r}')
 return found[occurrence]

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('config',type=Path);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--browser');a=ap.parse_args()
 config=a.config.resolve();cfg=json.loads(config.read_text('utf-8-sig'));base=config.parent;out=a.output.resolve()
 if out.exists():raise FileExistsError('保留已有证据目录，请换新输出目录或先作明确版本归档')
 out.mkdir(parents=True);(out/'原始资源').mkdir();(out/'原始截图').mkdir()
 mode=cfg['mode'];assert mode in ['archived_html','public_url']
 url=cfg['url'];assert urlsplit(url).scheme in ['http','https']
 render_url=cfg.get('archive_render_url',url) if mode=='archived_html' else url
 assert urlsplit(render_url).scheme in ['http','https']
 viewport=cfg.get('viewport',[1440,1080]);dpr=cfg.get('device_scale_factor',2)
 assert len(viewport)==2 and all(isinstance(x,int) and 320<=x<=4096 for x in viewport) and dpr in [1,2,3]
 js=cfg.get('javascript_enabled',False);request_log=[];resources=[];response_log=[];pending=[]
 stamp=datetime.now(timezone.utc).isoformat()
 manifest={'schema_version':1,'status':'capturing','captured_at_utc':stamp,'mode':mode,'requested_url':url,'viewport_css':viewport,'device_scale_factor':dpr,'scripts_enabled':js,'logged_in_profile_used':False,'source_text_rewritten':False,'css_override_injected':False,'network_requests_sent':0,'resources':resources,'requests':request_log,'regions':[],'limitations':cfg.get('limitations',[])}
 manifest['archive_render_url']=render_url if mode=='archived_html' else None
 manifest['archive_render_origin_differs_from_source']=render_url!=url
 dump(out/'capture_config.json',cfg)
 try:
  with sync_playwright() as pw:
   opts={'headless':True,'args':['--disable-background-networking']}
   exe=browser_path(a.browser) if a.browser else None if Path(pw.chromium.executable_path).exists() else browser_path()
   if exe:opts['executable_path']=exe
   browser=pw.chromium.launch(**opts);ctx=browser.new_context(viewport={'width':viewport[0],'height':viewport[1]},device_scale_factor=dpr,java_script_enabled=js,locale=cfg.get('locale','zh-CN'),service_workers='block',accept_downloads=False)
   page=ctx.new_page();mapping={}
   if mode=='archived_html':
    source=(base/cfg['html']).resolve();data=source.read_bytes();name='main_original.html';(out/'原始资源'/name).write_bytes(data)
    main={'url':url,'path':'原始资源/'+name,'sha256':sha(out/'原始资源'/name),'content_type':cfg.get('content_type','text/html; charset=utf-8'),'bytes':len(data),'role':'unchanged_saved_main_html'};resources.append(main);mapping[render_url]=(data,main)
    for i,r in enumerate(cfg.get('resources',[]),1):
     p=(base/r['path']).resolve();data=p.read_bytes();name=f'{i:03d}_{p.name}';(out/'原始资源'/name).write_bytes(data)
     rec={'url':r['url'],'path':'原始资源/'+name,'sha256':sha(out/'原始资源'/name),'content_type':r['content_type'],'bytes':len(data),'role':'saved_resource'};resources.append(rec);mapping[r['url']]=(data,rec)
    def route(req):
     u=req.request.url
     if u in mapping:
      data,rec=mapping[u];req.fulfill(status=200,content_type=rec['content_type'],body=data);request_log.append({'url':u,'action':'fulfilled_from_unchanged_saved_bytes','sha256':rec['sha256']})
     else:req.abort();request_log.append({'url':u,'action':'blocked_unavailable_archived_resource'})
   else:
    def route(req):
     r=req.request
     if r.method not in ['GET','HEAD'] or urlsplit(r.url).scheme not in ['http','https']:
      req.abort();request_log.append({'url':r.url,'method':r.method,'action':'blocked_non_read_only_request'})
     else:
      manifest['network_requests_sent']+=1;request_log.append({'url':r.url,'method':r.method,'action':'public_read_without_login'});req.continue_()
    page.on('response',lambda r:pending.append(r))
   page.route('**/*',route)
   response=page.goto(render_url,wait_until='load',timeout=cfg.get('timeout_ms',30000));page.evaluate('document.fonts.ready')
   if cfg.get('wait_selector'):page.locator(cfg['wait_selector']).first.wait_for(state='visible',timeout=10000)
   if mode=='public_url':
    if response is None or response.status in [401,403,407,429]:raise RuntimeError('页面拒绝访问/鉴权/限流；停止，不尝试绕过')
    visible=page.locator('body').inner_text()
    if re.search(r'(verify you are human|checking your browser|access denied|验证码|安全验证)',visible[:1600],re.I):raise RuntimeError('出现验证或访问挑战，停止，不绕过')
    for i,r in enumerate(pending):
     if r.request.resource_type not in ['document','stylesheet','image','font']:continue
     ct=r.headers.get('content-type','application/octet-stream');rec={'url':r.url,'status':r.status,'content_type':ct,'role':r.request.resource_type}
     try:
      data=r.body()
      if len(data)>cfg.get('max_resource_bytes',20000000):raise ValueError('resource above configured archival size limit')
      extension='.html' if 'html' in ct else '.css' if 'css' in ct else '.bin';name=f'network_{i:04d}'+extension;(out/'原始资源'/name).write_bytes(data)
      rec.update(path='原始资源/'+name,sha256=sha(out/'原始资源'/name),bytes=len(data));resources.append(rec)
     except Exception as exc:rec.update(body_saved=False,error=str(exc))
     response_log.append(rec)
   manifest.update(resolved_url=page.url,title=page.title(),browser=browser.version,http_status=response.status if response else None)
   size=page.evaluate('({width:Math.max(document.documentElement.scrollWidth,innerWidth),height:Math.max(document.documentElement.scrollHeight,innerHeight)})')
   if size['height']>cfg.get('max_document_height',40000):raise ValueError('文档过高，需另行分段设计，不静默截断上下文')
   manifest['document_size_css']=size
   (out/'visible_full_text.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
   (out/'rendered_dom.html').write_text(page.content(),encoding='utf-8')
   page.screenshot(path=str(out/'原始截图/viewport.png'),animations='disabled',scale='device')
   page.screenshot(path=str(out/'原始截图/full_page.png'),full_page=True,animations='disabled',scale='device')
   manifest['page_metadata']={}
   for key,selector in cfg.get('metadata_selectors',{}).items():
    loc=page.locator(selector);manifest['page_metadata'][key]={'selector':selector,'count':loc.count(),'text':loc.first.inner_text() if loc.count() else None}
   for region in cfg['regions']:
    ident=safe_id(region['id']);selector=region.get('selector','body');match=select_match(page,region['quote'],selector,region.get('occurrence'))
    bounds=[min(r[0] for r in match['rects']),min(r[1] for r in match['rects']),max(r[2] for r in match['rects']),max(r[3] for r in match['rects'])]
    view=region.get('view')
    if view:
     x=float(view.get('x',max(0,(bounds[0]+bounds[2]-view['width'])/2)));y=max(0,(bounds[1]+bounds[3]-view['height'])/2+view.get('y_offset',0));width=float(view['width']);height=float(view['height'])
    else:
     pad=region.get('padding',[32,90]);x=max(0,math.floor(bounds[0]-pad[0]));y=max(0,math.floor(bounds[1]-pad[1]));width=min(size['width']-x,math.ceil(bounds[2]+pad[0]-x));height=min(size['height']-y,math.ceil(bounds[3]+pad[1]-y))
    clip={'x':x,'y':y,'width':width,'height':height}
    assert x>=0 and y>=0 and x+width<=size['width']+.01 and y+height<=size['height']+.01
    assert x<=bounds[0] and y<=bounds[1] and bounds[2]<=x+width and bounds[3]<=y+height,f'选区不能裁断引用全文：region={ident}, quote_bounds={bounds}, clip={clip}'
    image=out/'原始截图'/f'{ident}.png';page.screenshot(path=str(image),clip=clip,full_page=True,animations='disabled',scale='device')
    def mapped(rect):return [round((rect[0]-x)*dpr,4),round((rect[1]-y)*dpr,4),round((rect[2]-x)*dpr,4),round((rect[3]-y)*dpr,4)]
    marks=[]
    for item in region.get('marks',[]):
     m=select_match(page,item['quote'],selector,item.get('occurrence'),within=match)
     marks.append({'id':safe_id(item['id']),'quote':m['quote'],'rects_css_document':m['rects'],'rects_image_pixels':[mapped(r) for r in m['rects']]})
    rec={'id':ident,'quote':match['quote'],'quote_text_sha256':hashlib.sha256(match['quote'].encode()).hexdigest(),'selector':selector,'context_text':match['context_text'],'image':str(image.relative_to(out)),'image_sha256':sha(image),'clip_css':clip,'quote_rects_css_document':match['rects'],'quote_rects_image_pixels':[mapped(r) for r in match['rects']],'focus_rect_image_pixels':mapped(bounds),'marks':marks,'source_url':url,'capture_mode':mode}
    manifest['regions'].append(rec)
   ctx.close();browser.close()
  manifest.update(status='captured_coordinate_audit_required',responses=response_log,source_kind='current_browser_rendering_of_unchanged_saved_html' if mode=='archived_html' else 'current_public_web_capture',current_capture_not_historical_screenshot=True,paid_api_calls=0,authentication_bypassed=False)
  manifest['files']=[{'path':str(p.relative_to(out)),'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file() and p.name!='capture.json']
  dump(out/'capture.json',manifest);print(json.dumps({'status':manifest['status'],'output':str(out),'regions':[r['id'] for r in manifest['regions']],'network_requests_sent':manifest['network_requests_sent']},ensure_ascii=False))
 except Exception as exc:
  manifest.update(status='failed_do_not_use_as_complete_evidence',error=str(exc));dump(out/'capture.json',manifest);raise

if __name__=='__main__':main()
