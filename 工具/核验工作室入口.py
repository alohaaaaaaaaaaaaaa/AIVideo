"""Check actual local homepage, same-time comparison and exported player."""
from pathlib import Path
import json
from urllib.parse import unquote,urlparse
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'检查/入口核验'
BASE=ROOT/'参考库/原片同段对标/开场29秒'
def main():
 OUT.mkdir(parents=True,exist_ok=True);errors=[];rows=[]
 with sync_playwright() as p:
  cached=sorted((Path.home()/'Library/Caches/ms-playwright').glob('chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell'),reverse=True)
  browser=p.chromium.launch(headless=True,**({'executable_path':str(cached[0])} if cached else {}))
  page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto((ROOT/'打开工作室.html').as_uri(),wait_until='load');page.wait_for_function('document.querySelector("video").readyState>=1')
  assert page.locator('h1').inner_text().startswith('下一条视频')
  page.locator('footer').scroll_into_view_if_needed();page.wait_for_function('Array.from(document.images).every(x=>x.complete&&x.naturalWidth>0)')
  missing=[]
  for url in page.locator('a[href]').evaluate_all('(xs)=>xs.map(x=>x.href)'):
   u=urlparse(url)
   if u.scheme=='file' and not Path(unquote(u.path)).exists():missing.append(url)
  assert not missing,missing
  meta=page.locator('video').evaluate('v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,error:v.error?.message||null})')
  assert meta['width']==1920 and meta['height']==1080 and abs(meta['duration']-29.36)<.05 and not meta['error'];rows.append({'homepage_media':meta,'missing_links':missing})
  page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/'工作室首页_桌面.png'),full_page=True)
  page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1');page.screenshot(path=str(OUT/'工作室首页_手机.png'),full_page=True);rows.append({'mobile_horizontal_overflow':False})
  page.set_viewport_size({'width':1440,'height':1000});page.goto((BASE/'看同段对照.html').as_uri());page.wait_for_function('document.querySelector("#v").readyState>=1')
  page.locator('#v').evaluate('v=>{v.muted=true;v.currentTime=3.6}');page.wait_for_function('!document.querySelector("#v").seeking')
  for i in [2,1,0]:
   page.locator('#versions button').nth(i).click();page.wait_for_function('(()=>{const v=document.querySelector("#v");return v.readyState>=2&&!v.seeking&&Math.abs(v.currentTime-3.6)<.08})()')
  rows.append({'three_way_reference_switch_preserves_time':True});page.screenshot(path=str(OUT/'同段对照播放器.png'),full_page=True)
  page.goto((BASE/'导出/播放成片.html').as_uri());page.wait_for_function('document.querySelector("#v").readyState>=1');assert page.locator('#versions button').count()==2
  page.locator('#v').evaluate('v=>{v.muted=true;v.currentTime=8}');page.wait_for_function('!document.querySelector("#v").seeking');page.locator('#versions button').nth(1).click()
  page.wait_for_function('(()=>{const v=document.querySelector("#v");return v.readyState>=2&&!v.seeking&&v.currentSrc.endsWith("clean.mp4")&&Math.abs(v.currentTime-8)<.05})()');rows.append({'bili_clean_switch_preserves_time':True})
  page.locator('#chapters button').first.click();page.locator('#v').evaluate('v=>v.pause()');page.screenshot(path=str(OUT/'验收播放器.png'),full_page=True)
  web=ROOT/'参考库/网页取证/看网页参考.html';page.goto(web.as_uri());videos=page.locator('video');assert videos.count()>=2
  for i in range(videos.count()):
   v=videos.nth(i);v.evaluate('v=>v.load()');v.evaluate('(v)=>new Promise((resolve,reject)=>{if(v.readyState>=1)return resolve();v.onloadedmetadata=resolve;v.onerror=()=>reject(v.error?.message)})');assert v.evaluate('v=>v.videoWidth>0&&v.duration>0')
  rows.append({'web_example_videos_readable':videos.count()});page.screenshot(path=str(OUT/'网页参考页.png'),full_page=True)
  assert not errors,errors;browser.close()
 report={'status':'passed','checks':rows,'javascript_errors':errors,'method':'actual local pages in headless Chromium','audio_review':'playability only, not human listening','paid_calls':0};(OUT/'浏览器核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
