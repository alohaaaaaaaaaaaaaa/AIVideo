"""Capture intact saved CCTV/Sina paragraphs; no source text or DOM rewriting."""
from pathlib import Path
import hashlib, json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[5]
OUT = ROOT / '10_重新策划/全片终版/叙事优化制作/素材/后半'
SRC = ROOT / '06_原始资料/新闻/E06_央视经济半小时_新浪转载.html'
STYLE = ROOT / '10_重新策划/调查后续/证据素材/走访与军事报道/原站样式'
URL = 'http://news.sina.com.cn/c/sd/2010-11-19/065721497404.shtml'
BROWSER = Path('/Users/elton/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell')
FONT = '/System/Library/Fonts/STHeiti Medium.ttc'
FIND = r'''phrase=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;const ns=[];let s='';while(n=w.nextNode()){if(n.parentElement.closest('script,style'))continue;ns.push({n,start:s.length});s+=n.textContent;}const out=[];let i=s.indexOf(phrase);while(i>=0){const a=ns.findLast(x=>x.start<=i),end=i+phrase.length,b=ns.findLast(x=>x.start<end);const r=document.createRange();r.setStart(a.n,i-a.start);r.setEnd(b.n,end-b.start);out.push(...Array.from(r.getClientRects()).filter(x=>x.width>0&&x.height>0).map(x=>({x:x.x+scrollX,y:x.y+scrollY,width:x.width,height:x.height})));i=s.indexOf(phrase,end);}return out;}'''
PARA = '记者了解到，今年4月27日九龙旅游度假山庄为了筹划飞行俱乐部做了一次飞行表演，在未经军民航批准的情况下，飞行员擅自驾驶直升机升空飞行10分钟，结果造成了上海浦东、虹桥国际机场航班大面积延误，目前相关监管部门对此事件正在处理之中。'
CONTEXT = '记者在浙江嘉兴平湖九龙旅游度假山庄同样看到停放着两架飞机，一架小型固定翼飞机，一架蜂鸟260L型直升机，工作人员介绍由于是在上海世博会期间，所以私人飞行活动被取消，这些飞机被相关监管部门监控不得使用。'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=str(BROWSER),headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':1080},device_scale_factor=3,java_script_enabled=False,locale='zh-CN')
        page=ctx.new_page(); blocked=[]
        def route(r):
            u=r.request.url
            if u==URL:r.fulfill(status=200,content_type='text/html; charset=gb18030',body=SRC.read_bytes())
            elif u.endswith('/master.css'):r.fulfill(status=200,content_type='text/css; charset=gb18030',body=(STYLE/'sina_master.css').read_bytes())
            elif u.endswith('/theme_standard.css'):r.fulfill(status=200,content_type='text/css; charset=gb18030',body=(STYLE/'sina_theme.css').read_bytes())
            else:blocked.append(u);r.abort()
        page.route('**/*',route);page.goto(URL,wait_until='load');page.evaluate('document.fonts.ready')
        for ident,paragraph,phrases in [
            ('pinghu_context',CONTEXT,['浙江嘉兴平湖九龙旅游度假山庄']),
            ('pinghu_quote',PARA,['4月27日','未经军民航批准','直升机升空飞行10分钟','上海浦东、虹桥国际机场航班大面积延误'])]:
            rects=page.evaluate(FIND,paragraph);assert rects,ident
            x=min(r['x'] for r in rects)-24;y=min(r['y'] for r in rects)-7
            right=max(r['x']+r['width'] for r in rects)+24;bottom=max(r['y']+r['height'] for r in rects)+7
            clip={'x':x,'y':y,'width':right-x,'height':bottom-y}
            raw=OUT/(ident+'_原页原像素.png');page.screenshot(path=str(raw),clip=clip,full_page=True,animations='disabled')
            # Keep the actual page around the cited paragraph, matching the
            # already-approved evidence treatment. The focused pixels remain
            # at their true page coordinates; only surrounding pixels blur.
            view={'x':200,'y':(y+bottom)/2-163.125,'width':720,'height':326.25}
            page_raw=OUT/(ident+'_原页环境.png')
            page.screenshot(path=str(page_raw),clip=view,full_page=True,animations='disabled')
            page_im=Image.open(page_raw).convert('RGB').resize((1920,870),Image.Resampling.LANCZOS)
            scale=1920/view['width']
            focus=(round((x-view['x'])*scale),round((y-view['y'])*scale),round((right-view['x'])*scale),round((bottom-view['y'])*scale))
            background=Image.blend(page_im.filter(ImageFilter.GaussianBlur(8.5)),Image.new('RGB',(1920,870),(16,20,26)),.36)
            background.paste(page_im.crop(focus),focus[:2])
            im=Image.new('RGB',(1920,1080),(16,20,26));im.paste(background,(0,0));d=ImageDraw.Draw(im)
            d.text((32,885),'新浪转载央视《经济半小时》实录 | 2010-11-19 06:57 | 节目播出：11月18日',font=ImageFont.truetype(FONT,26),fill=(230,235,244))
            d.text((32,927),'另一宗事件：2010年4月27日 · 浙江嘉兴平湖',font=ImageFont.truetype(FONT,23),fill=(173,187,205))
            target=OUT/(ident+'.png');im.save(target)
            marks={}
            for phrase in phrases:
                found=page.evaluate(FIND,phrase)
                found=[r for r in found if y<=r['y']<bottom]
                assert found,phrase
                marks[phrase]=[[(r['x']-view['x'])*scale,(r['y']+r['height']-view['y'])*scale+4,(r['x']+r['width']-view['x'])*scale,(r['y']+r['height']-view['y'])*scale+4] for r in found]
            records.append({'id':'new:'+ident,'path':str(target.relative_to(ROOT)),'raw_path':str(raw.relative_to(ROOT)),'environment_raw_path':str(page_raw.relative_to(ROOT)),'source':str(SRC.relative_to(ROOT)),'source_sha256':sha(SRC),'sha256':sha(target),'source_url':URL,'quote':paragraph,'marks':marks,'clip_css':clip,'view_css':view,'focus_rect':focus,'treatment':'actual source page; blur surrounding page; intact sharp original paragraph; actual-speech redlines','source_pixels_rewritten':False,'network_requests_sent':0})
        browser.close()
    (OUT/'pinghu_sources.json').write_text(json.dumps({'assets':records,'paid_calls':0,'source_text_changed':False,'network_requests_sent':0},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'captured':[x['id'] for x in records]},ensure_ascii=False))

if __name__=='__main__':main()
