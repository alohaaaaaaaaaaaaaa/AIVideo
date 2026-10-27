"""Capture unchanged source HTML with genuine available CSS, fixed readable crops."""
from pathlib import Path
import concurrent.futures
import hashlib
import html
import json
import math
import re
import sys
import urllib.request
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
BASE=ROOT/"10_重新策划/调查后续"
RAW=OUT/"原始截图"
STYLES=OUT/"原站样式"
RAW.mkdir(exist_ok=True)
STYLES.mkdir(exist_ok=True)
FONT=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",25)
SMALL=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc",22)
FIND=r'''phrase=>{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;const nodes=[];let text='';while(n=w.nextNode()){if(n.parentElement.closest('script,style'))continue;nodes.push({n,start:text.length});text+=n.textContent;}const result=[];let start=text.indexOf(phrase);while(start>=0){const a=nodes.findLast(v=>v.start<=start);const end=start+phrase.length;const b=nodes.findLast(v=>v.start<end);const r=document.createRange();r.setStart(a.n,start-a.start);r.setEnd(b.n,end-b.start);result.push(...Array.from(r.getClientRects()).filter(v=>v.width>0&&v.height>0).map(q=>({x:q.x+scrollX,y:q.y+scrollY,width:q.width,height:q.height})));start=text.indexOf(phrase,end);}return result;}'''


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def normalize_url(url): return re.sub(r"^https?://web\.archive\.org/web/\d+(?:[a-z_]+)?/","",url).split("?")[0].replace("https://","http://")
def norm(s):return re.sub(r"\s+","",html.unescape(re.sub("<[^>]+>","",s)))
def bounds(rr):
    x=min(r["x"] for r in rr);y=min(r["y"] for r in rr)
    return dict(x=x,y=y,width=max(r["x"]+r["width"] for r in rr)-x,height=max(r["y"]+r["height"] for r in rr)-y)
def trans(r,c):
    k=1920/c["width"]
    return dict(x=(r["x"]-c["x"])*k,y=(r["y"]-c["y"])*k,width=r["width"]*k,height=r["height"]*k)


def fetch_css(job):
    original,filename,requests=job
    path=STYLES/filename
    record=dict(original_url=original,file=filename,success=False,attempts=[])
    if path.exists():
        return dict(original_url=original,file=filename,success=True,used_cache=True,sha256=sha(path),public_fetch_candidates=requests)
    for url in requests:
        row=dict(url=url)
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=12) as response:
                data=response.read();row.update(final_url=response.url,status=response.status,content_type=response.headers.get("Content-Type"))
            if len(data)<50 or b"<html" in data[:500].lower():raise ValueError("not CSS")
            path.write_bytes(data)
            row["success"]=True;record.update(success=True,sha256=sha(path),bytes=len(data))
            record["attempts"].append(row)
            return record
        except Exception as exc:
            row.update(success=False,error=str(exc));record["attempts"].append(row)
    return record


def capture(page,source,cid,phrases,width=720,rectangles=None,notes=None):
    per=[]
    for q in phrases:
        rr=page.evaluate(FIND,q)
        assert rr,(cid,q)
        # Duplicate linked article titles sometimes occur outside the main body.
        per.append(dict(phrase=q,rectangles=rr))
    required=rectangles or [r for p in per for r in p["rectangles"]]
    b=bounds(required)
    width=math.ceil(max(width,b["width"]+30,b["height"]*1920/720)/16)*16
    pw=page.evaluate("Math.max(document.documentElement.scrollWidth,document.body.scrollWidth)")
    if width>pw and b["width"] <= math.floor(pw/16)*16:
        # A full-width original paragraph may leave no additional margin;
        # retain every text pixel, reducing only optional outer padding.
        width=math.floor(pw/16)*16
    height=width*1080/1920
    assert width<=pw,(cid,width,pw,b)
    crop=dict(x=max(0,min(math.floor(b["x"]+b["width"]/2-width/2),pw-width)),
              y=max(0,math.floor(b["y"]+b["height"]/2-height*.40)),width=width,height=height)
    transformed=[trans(r,crop) for r in required]
    assert all(r["x"]>=0 and r["y"]>=0 and r["x"]+r["width"]<=1920.1 and r["y"]+r["height"]<850 for r in transformed),(cid,transformed)
    raw=RAW/(cid+".png")
    page.screenshot(path=str(raw),clip=crop,full_page=True,scale="device",animations="disabled")
    im_raw=Image.open(raw)
    assert im_raw.size==(int(width*3),int(height*3)),(cid,im_raw.size,width,height)
    im=im_raw.convert("RGB").resize((1920,1080),Image.Resampling.LANCZOS)
    plain=OUT/(cid+"_原页裁切.png");im.save(plain)
    dim=Image.blend(im.filter(ImageFilter.GaussianBlur(10)),Image.new("RGB",im.size,(27,32,37)),.30)
    mask=Image.new("L",im.size,0);draw=ImageDraw.Draw(mask)
    for r in transformed:
        draw.rectangle((max(0,r["x"]-5),max(0,r["y"]-4),min(1920,r["x"]+r["width"]+5),min(1080,r["y"]+r["height"]+4)),fill=255)
    out=Image.composite(im,dim,mask.filter(ImageFilter.GaussianBlur(1)))
    draw=ImageDraw.Draw(out);draw.rectangle((0,870,1920,1080),fill=(16,20,26))
    draw.text((32,883),source["label"],font=FONT,fill=(225,230,237))
    draw.text((32,925),source["limit"],font=SMALL,fill=(172,185,202))
    final=OUT/(cid+"_标注.png");out.save(final)
    asset=dict(id=cid,path=final.name,plain_path=plain.name,sha256=sha(final),dimensions=[1920,1080],
               raw_path="原始截图/"+raw.name,raw_sha256=sha(raw),raw_dimensions=list(im_raw.size),clip_css=crop,
               source_id=source["id"],source_sha256=source["sha256"],original_url=source["original_url"],source_url=source["url"],
               complete_quotes=phrases,required_source_rectangles_css=required,required_source_rectangles_px=transformed,
               all_required_source_rectangles_inside_frame_and_above_850=True,source_text_modified=False,
               source_label=source["label"],source_limit=source["limit"],notes=notes or [],fixed_pixels_no_motion=True)
    print(cid,flush=True)
    return asset


def main():
    jobs=[
        ("http://news.sina.com.cn/iframe/87/new20080718/master.css","sina_master.css",["https://news.sina.com.cn/iframe/87/new20080718/master.css"]),
        ("http://news.sina.com.cn/iframe/87/20080708/theme_standard.css","sina_theme.css",["https://news.sina.com.cn/iframe/87/20080708/theme_standard.css"]),
        ("http://china.org.cn/article.css","china_article.css",["https://web.archive.org/web/20101129105302cs_/http://china.org.cn/article.css","https://www.china.org.cn/article.css"]),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        styles=list(pool.map(fetch_css,jobs))
    (STYLES/"fetch_log.json").write_text(json.dumps(styles,ensure_ascii=False,indent=2)+"\n","utf-8")
    stylemap={normalize_url(s["original_url"]):(STYLES/s["file"],s) for s in styles if s["success"]}
    report_lines=(ROOT/"06_原始资料/调查与论坛/ufocns_311.txt").read_text("utf-8").splitlines()
    notice_lines=(BASE/"来源缓存/M01_禁航报道.txt").read_text("utf-8").splitlines()
    drill_lines=(BASE/"来源缓存/M02_东海演练报道.txt").read_text("utf-8").splitlines()
    specs=[
        dict(id="VISIT",path="06_原始资料/调查与论坛/ufocns_311.html",url="https://www.ufocns.com/thread-311-1-1.html",original_url="http://www.ufocns.com/thread-311-1-1.html",encoding="utf-8",viewport=720,
             label="民间联合调查报告 · 2010年7月14—15日走访 · 保存论坛原页本地渲染",limit="报告转述接待答复与分析思路 · 不是机组原始笔录或政府结案文件"),
        dict(id="M01",path="10_重新策划/调查后续/来源缓存/M01_禁航报道.html",url="https://news.sina.com.cn/c/2010-06-29/051717723846s.shtml",original_url="https://news.sina.com.cn/c/2010-06-29/051717723846s.shtml",encoding="gb18030",viewport=1280,
             label="新浪转载 · 四川新闻网—成都商报 · 2010-06-29 05:17",limit="新闻转引训练通告 · 6月30日至7月5日的船舶禁航，不是萧山机场禁飞"),
        dict(id="M02",path="10_重新策划/调查后续/来源缓存/M02_东海演练报道.html",url="https://news.sina.com.cn/c/2010-07-07/070717766546s.shtml",original_url="https://news.sina.com.cn/c/2010-07-07/070717766546s.shtml",encoding="gb18030",viewport=1280,
             label="新浪转载 · 深圳特区报载新华社稿 · 2010-07-07 07:07",limit="正文时间为“7月初” · 7月7日是刊发日，不能据此延长公开演习日程"),
        dict(id="E04",path="06_原始资料/新闻/中国网英文_UFO remains a mystery_20100710.html",url="https://web.archive.org/web/20101129105302/http://china.org.cn/china/2010-07/10/content_20464734.htm",original_url="http://www.china.org.cn/china/2010-07/10/content_20464734.htm",encoding="utf-8",viewport=960,
             label="中国网转载 China Daily · 2010-07-10 · 2010-11-29网页归档",limit="未具名消息人士称与军事有关 · 未提供能核实当天活动的材料"),
    ]
    manifest=dict(dimensions=[1920,1080],paid_api_calls=0,sources=[],assets=[],visual_review="pending",
                  method="保存原HTML字节不变；Chrome禁脚本本地路由渲染，匹配原站CSS；固定原页像素裁切和外围虚化，编辑出处独立置于底栏。",
                  required_source_max_y=850,editorial_footer_y=870,subtitle_safe_area=[0,970,1920,1080])
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",headless=True)
        manifest["browser"]=browser.version
        for s in specs:
            path=ROOT/s["path"];data=path.read_bytes();s.update(sha256=sha(path),reused_styles=[],blocked_resources=[],source_bytes_unchanged=True,local_render_url=s["url"].replace("https://","http://",1))
            ctx=browser.new_context(viewport={"width":s["viewport"],"height":1080},device_scale_factor=3,java_script_enabled=False,locale="zh-CN")
            page=ctx.new_page()
            def route(r):
                u=r.request.url
                if u==s["local_render_url"]:
                    r.fulfill(status=200,content_type="text/html; charset="+s["encoding"],body=data)
                elif normalize_url(u) in stylemap:
                    style,record=stylemap[normalize_url(u)]
                    s["reused_styles"].append(dict(requested_url=u,path=style.relative_to(ROOT).as_posix(),sha256=sha(style),fetch_record=record))
                    r.fulfill(status=200,content_type="text/css; charset=utf-8",body=style.read_bytes())
                else:
                    s["blocked_resources"].append(dict(url=u,kind=r.request.resource_type));r.abort()
            page.route("**/*",route);page.goto(s["local_render_url"],wait_until="load",timeout=20000);page.evaluate("document.fonts.ready")
            s["page_title"]=page.title()
            assets=manifest["assets"]
            if s["id"]=="VISIT":
                title_rect=page.locator("#thread_subject").bounding_box()
                assets.append(capture(page,s,"V01_民间报告标题",["萧山机场UFO事件调查报告"],760,[title_rect],notes=["仅报告标题高光，转载作者和日期随外围原样虚化；论坛页面为2015转载载体，记载2010走访。不得把2015当走访时间。 "]))
                assets.append(capture(page,s,"V01b_调查组织与时间",[report_lines[3],"二、调查时间","2010年7月14-15日"],760))
                assets.append(capture(page,s,"V02a_七月十四日访问",["六、调查过程",report_lines[24],report_lines[25],report_lines[26]],760))
                assets.append(capture(page,s,"V02b_七月十五日接待",[report_lines[38],report_lines[39]],760))
                assets.append(capture(page,s,"V02c_华东管理局完整答复",[report_lines[44]],760))
                assets.append(capture(page,s,"V03_限于所获资料完整结语",[report_lines[56]],760))
                assets.append(capture(page,s,"V04_私人军用并列分析完整段",[report_lines[53],report_lines[55]],760,notes=["不排除、侧面了解、可能及私人/军用并列完整保留，非军机唯一论。中间第1项仍是原文外围，无删除或移位。 "]))
            elif s["id"]=="M01":
                heading=page.locator("#artibodyTitle").bounding_box();info=page.locator(".artInfo").bounding_box()
                assets.append(capture(page,s,"M01a_禁航报道标题日期",["解放军发禁航通告 将在东海实弹射击","2010年06月29日05:17","四川新闻网-成都商报"],900,[heading,info]))
                assets.append(capture(page,s,"M01b_日期海域船舶通告完整段",[notice_lines[34],notice_lines[35]],720))
            elif s["id"]=="M02":
                heading=page.locator("#artibodyTitle").bounding_box();info=page.locator(".artInfo").bounding_box()
                assets.append(capture(page,s,"M02a_演练报道标题日期",["东海舰队举行海空实弹大演练","2010年07月07日07:07","深圳特区报"],900,[heading,info]))
                assets.append(capture(page,s,"M02b_七月初舰艇战机完整段",drill_lines[38:41],760))
            else:
                title=page.locator("#title").bounding_box()
                sourcephrase="China Daily,  July 10, 2010"
                date=page.evaluate(FIND,sourcephrase)
                assets.append(capture(page,s,"E04a_标题稿源日期",["UFO remains a mystery",sourcephrase],760,[title]+date))
                quote="A source with knowledge of the matter, however, told China Daily earlier that the object had a military connection."
                assets.append(capture(page,s,"E04b_匿名军事关联完整句",[quote],760))
                boundary='"No conclusion has yet been drawn," Wang Jian, head of air traffic control with the Zhejiang branch of the Civil Aviation Administration of China (CAAC), was quoted by Xinhua News Agency as saying.'
                assets.append(capture(page,s,"E04c_七月当时尚无结论",[boundary],760))
            s["source_sha256_after_capture"]=sha(path)
            assert s["source_sha256_after_capture"]==s["sha256"]
            manifest["sources"].append(s);ctx.close()
        browser.close()
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n","utf-8")
    checks=dict(all_passed=True,paid_api_calls=0,source_bytes_unchanged=True,visual_review="pending",
                checks=[dict(id=a["id"],size=a["dimensions"],source_text_above_850=True,exact_capture_dimensions=True,rectangles=a["required_source_rectangles_px"]) for a in manifest["assets"]])
    (OUT/"bbox与安全区核验.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2)+"\n","utf-8")
    for start in range(0,len(manifest["assets"]),4):
        sheet=Image.new("RGB",(1920,1140),(16,20,26));draw=ImageDraw.Draw(sheet)
        for i,a in enumerate(manifest["assets"][start:start+4]):
            x,y=(i%2)*960,(i//2)*570
            sheet.paste(Image.open(OUT/a["path"]).resize((960,540),Image.Resampling.LANCZOS),(x,y))
            draw.text((x+12,y+540),a["id"],font=SMALL,fill=(220,227,237))
        sheet.save(OUT/("联系表"+str(start//4+1)+".jpg"),quality=95)
    print(json.dumps(dict(frames=len(manifest["assets"]),bbox_passed=True,paid_api_calls=0),ensure_ascii=False))


if __name__=="__main__":main()
