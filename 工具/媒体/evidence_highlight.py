#!/usr/bin/env python3
"""Animate genuine screenshot pixels and timed underlines, with one source footer."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config", type=Path)
    args = ap.parse_args()
    cfg = args.config.resolve()
    d = json.loads(cfg.read_text("utf-8-sig"))
    base = cfg.parent
    source = (base / d["image"]).resolve()
    output = (base / d.get("output", "原文高光.mp4")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    w, h, fps, duration = d.get("width",1920), d.get("height",1080), d.get("fps",25), d.get("duration",8)
    assert w%2==0 and h%2==0 and duration>0 and abs(duration*fps-round(duration*fps))<1e-6
    original = Image.open(source).convert("RGB")
    crop = d.get("crop", [0,0,original.width,original.height])
    assert 0<=crop[0]<crop[2]<=original.width and 0<=crop[1]<crop[3]<=original.height
    raw = original.crop(crop)
    scale = min(w*.94/raw.width, h*.70/raw.height)
    shown = raw.resize((round(raw.width*scale),round(raw.height*scale)), Image.Resampling.LANCZOS)
    x, y = (w-shown.width)//2, round((h*.79-shown.height)/2)
    bg = Image.new("RGB",(w,h),"#101820")
    bg.paste(shown,(x,y))
    default_font = Path("/System/Library/Fonts/Hiragino Sans GB.ttc")
    if not default_font.exists():
        default_font = Path(__file__).resolve().parents[2]/"参考库/动画/字体/NotoSansCJKsc-Regular.otf"
    font_path = d.get("font_path", str(default_font))
    font_path = str((base/font_path).resolve()) if not Path(font_path).is_absolute() else font_path
    font = ImageFont.truetype(font_path,round(27*h/1080))
    small = ImageFont.truetype(font_path,round(23*h/1080))
    foot = d["source_note"].splitlines()
    assert 1<=len(foot)<=2, "底部来源限两行"
    draw = ImageDraw.Draw(bg)
    for i,line in enumerate(foot):
        face = font if i==0 else small
        assert draw.textlength(line,font=face)<w*.94, "来源过长，请分行或精简显示名称；完整URL放证据台账"
        draw.text((round(w*.03),round(h*.815)+i*round(38*h/1080)),line,font=face,fill="#e6edf5" if i==0 else "#b1bdcc")
    # All ROI coordinates refer to original screenshot pixels; quoted text is never redrawn.
    highlights=[]
    for mark in d.get("highlights",[]):
        rect=mark["rect"]
        assert len(rect)==4 and crop[0]<=rect[0]<rect[2]<=crop[2] and crop[1]<=rect[1]<rect[3]<=crop[3]
        assert 0<=mark["start"]<mark.get("end",duration)<=duration
        highlights.append({**mark,"mapped":[x+(rect[0]-crop[0])*scale,y+(rect[1]-crop[1])*scale,x+(rect[2]-crop[0])*scale,y+(rect[3]-crop[1])*scale]})
    partial=output.with_name(output.stem+"_处理中.mp4")
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    with output.with_suffix(".log").open("w") as log:
        p=subprocess.Popen([ff,"-hide_banner","-nostdin","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{w}x{h}","-r",str(fps),"-i","-","-an","-c:v","libx264","-crf","17","-preset","fast","-threads","2","-pix_fmt","yuv420p","-movflags","+faststart",str(partial)],stdin=subprocess.PIPE,stdout=log,stderr=log)
        try:
            for frame in range(round(duration*fps)):
                t=frame/fps
                im=bg.copy().convert("RGBA")
                overlay=Image.new("RGBA",(w,h))
                pen=ImageDraw.Draw(overlay)
                for mark in highlights:
                    if not mark["start"]<=t<mark.get("end",duration):
                        continue
                    left,top,right,bottom=mark["mapped"]
                    progress=min(1,(t-mark["start"])/mark.get("draw_duration",.36))
                    progress=progress*progress*(3-2*progress)
                    end=left+(right-left)*progress
                    pen.rectangle((left,top,end,bottom),fill=(255,212,89,32))
                    pen.line((left,bottom+2,end,bottom+2),fill=(223,69,51,235),width=max(2,round(4*h/1080)))
                im=Image.alpha_composite(im,overlay).convert("RGB")
                if frame in {0,round(duration*fps)//2,round(duration*fps)-1}:
                    im.save(output.with_name(output.stem+f"_检查{frame:05}.png"))
                p.stdin.write(im.tobytes())
        finally:
            p.stdin.close()
        if p.wait()!=0:
            raise RuntimeError(f"编码失败，查看 {output.with_suffix('.log')}")
    partial.replace(output)
    report={"source_image":str(source),"source_sha256":sha(source),"source_url":d.get("source_url"),
            "output_sha256":sha(output),"source_pixels_rewritten":False,"source_text_retyped":False,
            "crop_original_coordinates":crop,"highlight_coordinates":"original screenshot pixels",
            "native_label":True,"footer_count":1,"top_editorial_badge_added":False,
            "frames":round(duration*fps),"duration":duration,"note":"裁切/缩放/色彩高光不等于网页原件；原件、URL、原文与截取记录均须保留。"}
    output.with_suffix(".json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(output)


if __name__=="__main__":
    main()
