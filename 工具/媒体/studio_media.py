#!/usr/bin/env python3
"""Portable manifest-based film assembly. No network, credentials, TTS, or publication."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import av
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
KINDS = {"image", "video", "ai", "animation"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def require_expected_hash(actual, expected, label):
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-fA-F]{64}", expected),
            f"{label}: expected SHA256必须是64位十六进制字符串")
    require(actual == expected.lower(), f"{label}: 编译后输入已变化；重新审定分镜并编译，禁止直接渲染旧manifest")


def run(args, log, cwd=None):
    with Path(log).open("w", encoding="utf-8") as f:
        result = subprocess.run([FF, "-hide_banner", "-nostdin", "-y", *map(str, args)],
                                cwd=cwd, stdout=f, stderr=f)
    if result.returncode:
        raise RuntimeError(f"FFmpeg 失败，详见 {log}")


def media_info(path):
    with av.open(str(path)) as c:
        v = next(iter(c.streams.video), None)
        a = next(iter(c.streams.audio), None)
        result = {}
        if v:
            require(v.duration is not None, f"视频缺少时长，请先规范封装：{path}")
            result["video"] = dict(width=v.width, height=v.height,
                                   fps=float(v.average_rate), duration=float(v.duration * v.time_base),
                                   frames=v.frames)
        if a:
            duration = float(a.duration * a.time_base) if a.duration is not None else c.duration / av.time_base
            result["audio"] = dict(duration=duration, sample_rate=a.sample_rate, channels=a.channels)
        return result


def ass_time(t):
    n = round(t * 100)
    h, n = divmod(n, 360000)
    m, n = divmod(n, 6000)
    s, n = divmod(n, 100)
    return f"{h}:{m:02}:{s:02}.{n:02}"


def srt_time(t):
    n = round(t * 1000)
    h, n = divmod(n, 3600000)
    m, n = divmod(n, 60000)
    s, n = divmod(n, 1000)
    return f"{h:02}:{m:02}:{s:02},{n:03}"


def ass_text(text):
    # Literal brackets/backslashes must never be interpreted as ASS commands.
    return str(text).replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", "\\N")


class Film:
    def __init__(self, manifest):
        self.path = Path(manifest).resolve()
        self.base = self.path.parent
        self.studio = Path(__file__).resolve().parents[2]
        self.visual_path = self.studio / "默认配置/视觉.json"
        self.visual = read(self.visual_path)
        self.m = read(self.path)
        self.fps = self.m.get("fps", 25)
        self.w = self.m.get("width", 1920)
        self.h = self.m.get("height", 1080)
        self.out = self.resolve(self.m.get("output_dir", "导出"))
        self.cache = self.out / "缓存"
        self.check = self.out / "检查"
        self.versions = self.m.get("versions", [
            {"id": "clean", "label": "无水印版", "watermark": False},
            {"id": "bili", "label": "B站水印版", "watermark": True},
        ])
        self.shots = []

    def font_info(self):
        config = self.visual["font"]
        primary = Path(config["primary_system_file"])
        fallback = self.studio/config["fallback_workspace_file"]
        selected = primary if primary.is_file() else fallback
        require(selected.is_file(), "主字体与工作室回退字体均不可用")
        selected_hash=digest(selected)
        exact=selected==primary and selected_hash==config.get("verified_primary_sha256")
        return {"family":config["primary_family"] if selected==primary else config["fallback_family"],
                "file":str(selected),"sha256":selected_hash,"exact_reference_face":exact,
                "notice":None if exact else (config["fallback_notice"] if selected!=primary else "系统同名字体版本hash与参考不同，需重新核验字形")}

    def subtitle_style(self, row=None):
        scale = self.h/self.visual["reference_resolution"][1]
        inherited = self.visual["subtitle"]
        style = {k:(v*scale if isinstance(v,(int,float)) else v) for k,v in inherited.items()}
        style["font"] = self.font_info()["family"]
        def merge(override):
            profile = override.get("profile")
            if profile:
                require(profile in self.visual["profiles"], f"未知字幕profile: {profile}")
                style.update({k:v*scale for k,v in self.visual["profiles"][profile].items()})
            style.update({k:v for k,v in override.items() if k!="profile"})
        merge({"profile":"main"})
        merge(self.m.get("subtitle_style",{}))
        if row:
            shot = next((s for s in self.shots if s["start"]<=row["start"]<s["end"]),None)
            if shot:
                merge(shot.get("subtitle_style",{}))
            merge(row.get("style",{}))
        return style

    def layout_filter(self, shot):
        layout=shot["layout"];mode=layout["mode"]
        if mode=="fullframe":
            # A composed frame is already the design. Never shrink it because it has a footer.
            geometry=f"scale={self.w}:{self.h}:flags=lanczos"
        elif mode=="contain":
            geometry=f"scale={self.w}:{self.h}:force_original_aspect_ratio=decrease:flags=lanczos,pad={self.w}:{self.h}:(ow-iw)/2:(oh-ih)/2:color=0x10141a"
        else:
            x,y,cw,ch=layout["crop"]
            dx,dy,dw,dh=layout["destination"]
            geometry=f"crop={cw}:{ch}:{x}:{y},scale={dw}:{dh}:force_original_aspect_ratio=decrease:flags=lanczos,pad={dw}:{dh}:(ow-iw)/2:(oh-ih)/2:color=0x10141a,pad={self.w}:{self.h}:{dx}:{dy}:color=0x10141a"
        return f"fps={self.fps}:eof_action=pass,{geometry},setsar=1,format=yuv420p"

    def resolve(self, p):
        p = Path(p)
        require(not p.is_absolute(), f"manifest 采用相对路径，便于整个工作室迁移：{p}")
        return (self.base / p).resolve()

    def watermark(self, version):
        if not version.get("watermark", False):
            return None
        mark = {**self.m.get("watermark", {}), **version.get("watermark_override", {})}
        if version.get("watermark_path"):
            mark["path"] = version["watermark_path"]
        return mark

    def validate_editorial_binding(self):
        if "editorial_binding" not in self.m:
            return None
        binding = self.m["editorial_binding"]
        require(isinstance(binding, dict), "editorial_binding必须为对象")
        checked = {}
        for name in ("plan", "timeline", "visual_cues", "narration"):
            pk, hk = name+"_path", name+"_sha256"
            required = name in ("plan", "timeline")
            if not required and pk not in binding and hk not in binding:
                continue
            require(pk in binding and hk in binding, f"导演绑定 {name}: 路径与SHA256必须成对提供")
            require(isinstance(binding[pk], str) and binding[pk].strip(), f"导演绑定 {name}: 路径不能为空")
            path = self.resolve(binding[pk])
            require(path.is_file(), f"导演绑定 {name}: 文件不存在 {path}")
            actual = digest(path)
            require_expected_hash(actual, binding[hk], "导演绑定 "+name)
            checked[pk], checked[hk] = binding[pk], actual
        return checked

    def validate(self):
        require(self.m.get("schema_version", 1) == 1, "不支持的 schema_version")
        require(type(self.fps) is int and 1 <= self.fps <= 60, "fps 必须为 1–60 整数；默认25")
        require(all(type(n) is int and n > 0 and n % 2 == 0 for n in (self.w, self.h)), "宽高必须为正偶数")
        require(self.m.get("shots"), "shots 不能为空")
        editorial_binding = self.validate_editorial_binding()
        checked_expected_hashes = 0
        self.out.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(exist_ok=True)
        self.check.mkdir(exist_ok=True)
        ids, frames, assets, video_ranges = set(), 0, {}, {}
        self.shots = []
        for source in self.m["shots"]:
            s = dict(source)
            sid = s.get("id", "")
            require(re.fullmatch(r"[A-Za-z0-9_\-]+", sid) is not None and sid not in ids, f"镜头 id 需唯一安全英文编号：{sid}")
            ids.add(sid)
            require(s.get("kind") in KINDS, f"{sid}: kind 必须为 {KINDS}")
            require(isinstance(s.get("native_label", False), bool), f"{sid}: native_label 必须是布尔值")
            duration, start_in = float(s["duration"]), float(s.get("in", 0))
            count = round(duration * self.fps)
            require(count > 0 and abs(count / self.fps - duration) < 1e-6, f"{sid}: duration 必须对齐整帧")
            require(start_in >= 0, f"{sid}: in 不能为负")
            require(s.get("speed", 1) == 1 and not s.get("loop", False), f"{sid}: 禁止变速和循环，先审定独立新素材")
            note = s.get("source_note", "")
            require(not note or (s["kind"] == "image" and not s.get("native_label")), f"{sid}: 仅无原生备注的静态截图可新增底部来源；视频/动画不加第二层")
            require(not note or 1 <= len(note.splitlines()) <= 2, f"{sid}: source_note 仅支持1–2行")
            if s["kind"] == "ai":
                require(s.get("native_label") is True, f"{sid}: AI片段请先在素材内做好一处情景示意标识，核验后设置 native_label:true")
            path = self.resolve(s["path"])
            require(path.is_file(), f"{sid}: 素材不存在 {path}")
            if str(path) not in assets:
                if s["kind"] == "image":
                    with Image.open(path) as im:
                        dimensions = [im.width,im.height]
                        im.verify()
                    info = {"image": True,"width":dimensions[0],"height":dimensions[1]}
                else:
                    info = media_info(path)
                    require("video" in info, f"{sid}: 素材不含视频流")
                assets[str(path)] = {"sha256": digest(path), **info}
            info = assets[str(path)]
            if editorial_binding is not None:
                require("expected_sha256" in s, f"{sid}: 导演编译的镜头缺少expected_sha256，不能退回未绑定素材")
            if "expected_sha256" in s:
                require_expected_hash(info["sha256"], s["expected_sha256"], "镜头 "+sid)
                checked_expected_hashes += 1
            if s["kind"]=="image":
                # Older manifests/checks may predate stored image dimensions.
                with Image.open(path) as im:sw,sh=im.size
            else:sw,sh=info["video"]["width"],info["video"]["height"]
            layout={**self.visual["default_layout"],**s.get("layout",{})}
            require(layout["mode"] in {"fullframe","contain","evidence_region"},f"{sid}: 未知layout.mode")
            if layout["mode"]=="fullframe":
                require(abs(sw/sh-self.w/self.h)<.002, f"{sid}: fullframe需要已构图的同宽高比画面；原始长网页请先设计阅读区域，禁止自动缩小或fill裁切")
                require(not note or s.get("source_note_safe_area") is True,f"{sid}: 请确认y870以下不含需保留的正文，再设置source_note_safe_area:true；工具不会缩小整图")
            elif layout["mode"]=="contain":
                require(bool(layout.get("reason")), f"{sid}: contain会产生留边，必须说明经审定的用途；不作为默认修补")
            else:
                require(s["kind"]=="image",f"{sid}: evidence_region仅用于真实静态原页")
                for key,limit in [("crop",(sw,sh)),("destination",(self.w,self.h))]:
                    rect=layout.get(key,[])
                    require(len(rect)==4 and all(type(v)is int for v in rect),f"{sid}: {key}必须是像素[x,y,width,height]")
                    x,y,rw,rh=rect
                    require(x>=0 and y>=0 and rw>0 and rh>0 and x+rw<=limit[0] and y+rh<=limit[1],f"{sid}: {key}越界")
                if note:require(layout["destination"][1]+layout["destination"][3]<=round(self.visual["source_footer"]["top"]*self.h/1080),f"{sid}: 证据阅读区域与来源底栏重叠")
            s["layout"]=layout
            if s["kind"] != "image":
                require(start_in + duration <= info["video"]["duration"] + 1e-6, f"{sid}: 请求超出素材时长；禁止末帧补足或循环")
                if s["kind"] == "ai":
                    # Same generated footage must not be repeated disguised as multiple shots.
                    source_key = info["sha256"]
                    for lo, hi, prior in video_ranges.get(source_key, []):
                        require(min(hi, start_in + duration) - max(lo, start_in) < 1e-6, f"{sid}: AI源区间与 {prior} 重复")
                    video_ranges.setdefault(source_key, []).append((start_in, start_in + duration, sid))
            elif start_in:
                raise ValueError(f"{sid}: 静态图无 in 点")
            s.update(start=frames / self.fps, end=(frames + count) / self.fps,
                     frame_count=count, absolute_path=str(path), **{"in": start_in})
            self.shots.append(s)
            frames += count
        self.frames, self.duration = frames, frames / self.fps
        audio_path = self.resolve(self.m["audio"]["path"])
        require(audio_path.is_file(), f"全片混音不存在：{audio_path}")
        audio_hash = digest(audio_path)
        if editorial_binding is not None:
            require("expected_sha256" in self.m["audio"], "导演编译的混音缺少expected_sha256，不能退回未绑定音频")
        if "expected_sha256" in self.m["audio"]:
            require_expected_hash(audio_hash, self.m["audio"]["expected_sha256"], "全片混音")
            checked_expected_hashes += 1
        audio = media_info(audio_path).get("audio")
        require(audio is not None, "audio.path 不含音频")
        require(audio["sample_rate"] == 48000 and audio["channels"] == 2, "交付混音必须是48kHz双声道；先在声音流程规范")
        require(abs(audio["duration"] - self.duration) <= 1 / self.fps + .001, f"混音 {audio['duration']:.3f}s 与镜头 {self.duration:.3f}s 不齐，须回到时间线修正")
        previous = 0
        for row in self.m.get("subtitles", []):
            require(isinstance(row.get("text"), str) and row["text"].strip(), "字幕文字不能为空")
            require(previous <= row["start"] < row["end"] <= self.duration + 1e-6, f"字幕重叠、逆序或越界：{row}")
            require(len(row["text"].splitlines()) <= 2, "字幕最多两行，长句应重新切句")
            previous = row["end"]
        chapters = self.m.get("chapters", [])
        previous = -1
        for c in chapters:
            require(previous < c["start"] < self.duration and c["start"] >= 0 and c["title"].strip(), "章节逆序、重复或越界")
            previous = c["start"]
        require(not chapters or chapters[0]["start"] == 0, "第一章从0秒开始")
        version_ids = set()
        require(self.versions, "versions 不能为空")
        for v in self.versions:
            require(re.fullmatch(r"[A-Za-z0-9_-]+", v["id"]) is not None and v["id"] not in version_ids, "版本 id 需唯一安全英文编号")
            version_ids.add(v["id"])
            mark = self.watermark(v)
            if mark is None:
                continue
            require(mark.get("path"), f"{v['id']}: 缺少 watermark.path")
            with Image.open(self.resolve(mark["path"])) as im:
                mw = int(mark.get("width", im.width))
                mh = round(im.height * mw / im.width)
            require(mw > 0 and 0 < float(mark.get("opacity", 1)) <= 1, "水印尺寸/透明度无效")
            for s in self.shots:
                pos = s.get("watermark_position", [mark.get("x", self.w - mw - 32), mark.get("y", 32)])
                require(len(pos) == 2 and all(type(n) in (int, float) for n in pos), "水印位置必须为两个固定数字；禁止镜头内动画")
                require(0 <= pos[0] <= self.w - mw and 0 <= pos[1] <= self.h - mh, f"{s['id']}: 水印越界")
        report = {"status": "validated", "manifest_sha256": digest(self.path), "duration": self.duration,
                  "frames": self.frames, "shots": self.shots, "assets": assets,
                  "audio": {"path": str(audio_path), "sha256": audio_hash, **audio},
                  "subtitle_count": len(self.m.get("subtitles", [])), "chapter_count": len(chapters),
                  "native_label_policy": "preserve_only; manual native label verification required",
                  "ai_original_speed_no_repeated_ranges": True, "within_shot_watermark_motion": False}
        report["visual_config_sha256"]=digest(self.visual_path)
        report["resolved_font"]=self.font_info()
        report["editorial_binding"] = editorial_binding
        report["expected_input_hashes_checked"] = checked_expected_hashes
        save(self.check / "输入核验.json", report)
        return report

    def sidecars(self):
        scale = self.h / 1080
        style = self.subtitle_style()
        font = style['font']
        require("," not in font and "\n" not in font, "字幕字体名不能包含逗号/换行")
        source = self.visual['source_footer']
        source_font = self.font_info()['family']
        def n(value): return f'{float(value):g}'
        subtitle_def = ','.join(["Main",font,n(style['font_size']),style['primary_colour'],style['secondary_colour'],style['outline_colour'],style['back_colour'],"0","0","0","0","100","100","0","0","1",n(style['outline']),n(style['shadow']),"2",str(round(style['margin_l'])),str(round(style['margin_r'])),str(round(style['margin_v'])),"1"])
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.w}
PlayResY: {self.h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: {subtitle_def}
Style: Source,{source_font},{round(source['font_sizes'][0]*scale)},&H00F4EBE6,&H00FFFFFF,&H001A1410,&H001A1410,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events, srt, subtitle_rows = [], [], []
        face_file=self.font_info()['file']
        for i, row in enumerate(self.m.get("subtitles", []), 1):
            actual=self.subtitle_style(row)
            face=ImageFont.truetype(face_file,round(actual['font_size']))
            require(all(face.getlength(line)<=self.w-actual['margin_l']-actual['margin_r'] for line in row['text'].splitlines()),f"字幕过宽，请按语义切句：{row['text']}")
            overrides=''
            if actual['font']!=font:overrides+=r'\fn'+actual['font']
            if actual['font_size']!=style['font_size']:overrides+=r'\fs'+n(actual['font_size'])
            if overrides:overrides='{'+overrides+'}'
            margin=round(actual['margin_v'])
            events.append(f"Dialogue: 0,{ass_time(row['start'])},{ass_time(row['end'])},Main,,0,0,{margin},,{overrides}{ass_text(row['text'])}")
            srt.append(f"{i}\n{srt_time(row['start'])} --> {srt_time(row['end'])}\n{row['text']}\n")
            subtitle_rows.append({'start':row['start'],'end':row['end'],'margin_v':margin,'font':actual['font'],'font_size':actual['font_size']})
        source_count = 0
        for shot in self.shots:
            if not shot.get("source_note"):
                continue
            source_count += 1
            a,b=ass_time(shot['start']),ass_time(shot['end'])
            y=round(source['top']*scale)
            events.append(f"Dialogue: -2,{a},{b},Source,,0,0,0,,{{\\an7\\pos(0,{y})\\p1\\c{source['background_ass']}}}m 0 0 l {self.w} 0 {self.w} {self.h-y} 0 {self.h-y}{{\\p0}}")
            for i,line in enumerate(shot['source_note'].splitlines()):
                font_size=round(source['font_sizes'][i]*scale)
                face=ImageFont.truetype(face_file,font_size)
                require(face.getlength(line)<=source['safe_width']*scale,f"{shot['id']}: 来源文字超出安全宽度，请精简或分两行")
                x=round(source['x']*scale);text_y=round((source['first_y']+i*source['line_step'])*scale)
                events.append(f"Dialogue: -1,{a},{b},Source,,0,0,0,,{{\\an7\\pos({x},{text_y})\\fs{font_size}\\c{source['colours_ass'][i]}}}{ass_text(line)}")
        (self.out / "subtitles.ass").write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
        (self.out / "subtitles.srt").write_text("\n".join(srt), encoding="utf-8-sig")
        def esc(s):
            return s.replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", " ")
        meta = [";FFMETADATA1", "title=" + esc(self.m.get("title", "啊子牙"))]
        chapters = self.m.get("chapters", [])
        for i, c in enumerate(chapters):
            end = chapters[i+1]["start"] if i+1 < len(chapters) else self.duration
            meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={round(c['start']*1000)}", f"END={round(end*1000)}", "title=" + esc(c["title"])]
        (self.out / "chapters.ffmetadata").write_text("\n".join(meta)+"\n", encoding="utf-8")
        save(self.check / "字幕与标注核验.json", {"subtitle_count": len(srt), "source_footer_count": source_count,
             "added_video_or_animation_labels": 0, "subtitle_style": style, "subtitle_rows": subtitle_rows, "resolved_font": self.font_info(), "source_footer": source,
             "ass_sha256": digest(self.out / "subtitles.ass"), "srt_sha256": digest(self.out / "subtitles.srt")})

    def render(self):
        input_report = self.validate()
        archive = self.out / "历史" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        existing = [self.out/(v["id"]+".mp4") for v in self.versions]
        existing += [self.out/name for name in ("subtitles.ass", "subtitles.srt", "chapters.ffmetadata", "播放成片.html")]
        if any(p.exists() for p in existing):
            archive.mkdir(parents=True)
            for p in existing:
                if p.exists():
                    shutil.copy2(p, archive/p.name)
        self.sidecars()
        clips = []
        for index, s in enumerate(self.shots):
            target = self.cache / (s["id"] + ".mp4")
            vf = self.layout_filter(s)
            args = []
            if s["kind"] == "image":
                args += ["-loop", "1", "-framerate", self.fps]
            else:
                args += ["-ss", s["in"]]
            args += ["-i", s["absolute_path"], "-vf", vf, "-an", "-frames:v", s["frame_count"],
                     "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-threads", "2",
                     "-video_track_timescale", self.fps * 512, target]
            run(args, self.check / f"shot_{s['id']}.log")
            info = media_info(target)["video"]
            require(info["frames"] == s["frame_count"], f"{s['id']}: 编码帧数不足，拒绝自动补帧")
            clips.append(target)
            print(f"镜头 {index+1}/{len(self.shots)} {s['id']}", flush=True)
        listing = self.cache / "shots.ffconcat"
        listing.write_text("ffconcat version 1.0\n" + "\n".join("file '" + str(p).replace("'", "'\\''") + "'" for p in clips) + "\n", encoding="utf-8")
        picture = self.cache / "picture.mp4"
        run(["-f", "concat", "-safe", "0", "-i", listing, "-map", "0:v:0", "-c:v", "copy", "-an", picture], self.check / "concat.log")
        # Encode audio once; version exports copy identical AAC packets.
        shared_audio = self.cache / "mix.m4a"
        run(["-i", self.resolve(self.m["audio"]["path"]), "-t", self.duration, "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2", shared_audio], self.check / "audio.log")
        render_outputs = []
        for v in self.versions:
            args = ["-filter_complex_threads", "2", "-i", picture, "-i", shared_audio,
                    "-f", "ffmetadata", "-i", "chapters.ffmetadata"]
            mark = self.watermark(v)
            font_source = Path(__file__).resolve().parents[2]/"参考库/动画/字体"
            if font_source.exists():
                font_target = self.out/"fonts"
                font_target.mkdir(exist_ok=True)
                for font_file in font_source.glob("*.otf"):
                    shutil.copy2(font_file, font_target/font_file.name)
            graph = "[0:v]ass=subtitles.ass:fontsdir=fonts[captioned]" if font_source.exists() else "[0:v]ass=subtitles.ass[captioned]"
            if mark:
                with Image.open(self.resolve(mark["path"])) as im:
                    mw = int(mark.get("width", im.width))
                def expression(axis):
                    positions = [s.get("watermark_position", [mark.get("x", self.w-mw-32), mark.get("y",32)])[axis] for s in self.shots]
                    expr = str(positions[-1])
                    for s, pos in zip(reversed(self.shots[:-1]), reversed(positions[:-1])):
                        expr = f"if(lt(t,{s['end']:.6f}),{pos},{expr})"
                    return expr
                args += ["-i", self.resolve(mark["path"])]
                graph += f";[3:v]scale={mw}:-1,format=rgba,colorchannelmixer=aa={mark.get('opacity',1)}[logo];[captioned][logo]overlay=x='{expression(0)}':y='{expression(1)}':eval=frame:format=auto,format=yuv420p[video]"
            else:
                graph += ";[captioned]format=yuv420p[video]"
            graph_path = self.out / f"filter_{v['id']}.txt"
            graph_path.write_text(graph, encoding="utf-8")
            target = self.out / (v["id"] + ".mp4")
            partial = self.out / (v["id"] + "_处理中.mp4")
            args += ["-filter_complex_script", graph_path.name, "-map", "[video]", "-map", "1:a:0", "-map_metadata", "2", "-map_chapters", "2",
                     "-c:v", "libx264", "-crf", self.m.get("crf",17), "-preset", "fast", "-threads", "3",
                     "-pix_fmt", "yuv420p", "-video_track_timescale", self.fps*512, "-c:a", "copy", "-t", self.duration,
                     "-movflags", "+faststart", partial]
            run(args, self.check / f"encode_{v['id']}.log", cwd=self.out)
            partial.replace(target)
            font_selections=[]
            for line in (self.check/f"encode_{v['id']}.log").read_text(errors="replace").splitlines():
                if "fontselect:" in line and " -> " in line:
                    selected=line.split(" -> ",1)[1]
                    parts=selected.rsplit(", ",2)
                    actual_path=Path(parts[0])
                    font_selections.append({"selection":selected,"file_sha256":digest(actual_path) if actual_path.is_file() else None})
            render_outputs.append({"id": v["id"], "path": target.name, "sha256": digest(target),"actual_libass_font_selections":font_selections})
            print(f"导出完成 {v['id']}", flush=True)
        save(self.check / "渲染记录.json", {"manifest_sha256": digest(self.path), "duration": self.duration,
             "input_assets": input_report["assets"], "audio_sha256": input_report["audio"]["sha256"],
             "visual_config_sha256": digest(self.visual_path), "resolved_font": self.font_info(),
             "ass_sha256": digest(self.out/"subtitles.ass"), "srt_sha256": digest(self.out/"subtitles.srt"),
             "outputs": render_outputs})

    def verify(self):
        current_input = self.validate()
        render_record = read(self.check / "渲染记录.json")
        require(render_record["manifest_sha256"] == digest(self.path), "manifest 已变化，请重新 render，不能验证旧输出")
        require(render_record.get("visual_config_sha256")==digest(self.visual_path), "视觉默认配置已变化，请重新render，不能用旧成片冒充新规范")
        # Paths may change when the complete studio is moved; hashes + media properties must not.
        asset_signature = lambda rows: sorted(json.dumps(value, sort_keys=True) for value in rows.values())
        require(asset_signature(render_record["input_assets"]) == asset_signature(current_input["assets"]) and render_record["audio_sha256"] == current_input["audio"]["sha256"], "素材或混音在渲染后已变化，请重新 render")
        require(render_record["ass_sha256"] == digest(self.out/"subtitles.ass") and render_record["srt_sha256"] == digest(self.out/"subtitles.srt"), "字幕侧录文件在渲染后已变化")
        samples = {min(self.frames-1, round((s["start"] + (s["end"]-s["start"])*.5)*self.fps)): s["id"] for s in self.shots}
        for s in self.shots:
            if s["kind"] in {"ai", "animation"}:
                samples[round(s["start"]*self.fps)] = s["id"] + "_首"
                samples[round(s["end"]*self.fps)-1] = s["id"] + "_尾"
        outputs = []
        for v in self.versions:
            path = self.out / (v["id"] + ".mp4")
            expected_hash = next(r["sha256"] for r in render_record["outputs"] if r["id"] == v["id"])
            require(digest(path) == expected_hash, f"{path}: 输出在渲染后变化")
            folder = self.check / (v["id"] + "_抽帧")
            folder.mkdir(exist_ok=True)
            count, contacts = 0, []
            with av.open(str(path)) as c:
                stream = c.streams.video[0]
                require((stream.width, stream.height) == (self.w, self.h) and stream.average_rate == self.fps, "输出规格不符")
                stream.thread_type = "AUTO"
                for frame in c.decode(stream):
                    require(abs(frame.time - count/self.fps) < 1e-5, f"{v['id']}: 视频PTS不连续@{count}")
                    if count in samples:
                        im = frame.to_image()
                        im.save(folder / f"{count:08}_{samples[count]}.jpg", quality=92)
                        contacts.append((count/self.fps, im.resize((384,round(384*self.h/self.w)))))
                    count += 1
                require(count == self.frames, f"{v['id']}: 帧数 {count} != {self.frames}")
            peak, clipped, audio_samples, packets = 0., 0, 0, hashlib.sha256()
            with av.open(str(path)) as c:
                a = c.streams.audio[0]
                require(a.sample_rate == 48000 and a.channels == 2, "音频规格不符")
                audio_duration = float(a.duration * a.time_base)
                for packet in c.demux(a):
                    if packet.size:
                        packets.update(bytes(packet))
                        packets.update(str((packet.pts, packet.dts, packet.duration)).encode())
                    for frame in packet.decode():
                        values = frame.to_ndarray()
                        audio_samples += frame.samples
                        peak = max(peak, float(np.abs(values).max()))
                        clipped += int(np.count_nonzero(np.abs(values) >= 1))
                require(audio_samples > 0 and abs(audio_duration-self.duration) <= .05, "音频缺失或音画时长不齐")
                require(clipped == 0, "AAC有满幅/削波采样，请调混音余量")
            meta = subprocess.run([FF,"-v","error","-i",str(path),"-map_chapters","0","-map_metadata","0","-f","ffmetadata","-"], capture_output=True, text=True, check=True).stdout
            require(meta.count("[CHAPTER]") == len(self.m.get("chapters", [])), "封装章节数不符")
            for expected, section in zip(self.m.get("chapters", []), meta.split("[CHAPTER]")[1:]):
                actual = dict(line.split("=",1) for line in section.splitlines() if "=" in line and not line.startswith(";"))
                n, den = map(int, actual["TIMEBASE"].split("/"))
                require(abs(int(actual["START"])*n/den-expected["start"])<=.002, "章节实际起点不符")
                title = expected["title"].replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", " ")
                require(actual["title"]==title, "章节标题不符")
            loudness_scan = subprocess.run([FF,"-hide_banner","-nostdin","-i",str(path),"-vn","-af","loudnorm=I=-16:TP=-1:LRA=11:print_format=json","-f","null","-"], capture_output=True, text=True, check=True)
            blocks = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', loudness_scan.stderr, flags=re.S)
            require(bool(blocks), "最终AAC响度扫描未返回结果")
            loudness = json.loads(blocks[-1])
            integrated_lufs, true_peak_dbtp = float(loudness["input_i"]), float(loudness["input_tp"])
            loudness_record = {"integrated_lufs": integrated_lufs if math.isfinite(integrated_lufs) else None,
                               "true_peak_dbtp": true_peak_dbtp if math.isfinite(true_peak_dbtp) else None,
                               "recommended_max_dbtp": -1.0, "true_peak_pass": true_peak_dbtp <= -1.0,
                               "measurement": "FFmpeg loudnorm input measurement on actual final AAC; no audio mutation"}
            save(self.check/f"{v['id']}_最终AAC响度.json", loudness_record)
            require(true_peak_dbtp <= -1.0, f"{v['id']}: 最终AAC真峰值 {true_peak_dbtp:.2f} dBTP 高于 -1 dBTP；需降低混音/调整限幅后重导，详见响度报告")
            for begin in range(0, len(contacts), 12):
                group = contacts[begin:begin+12]
                tile_h = group[0][1].height + 26
                sheet = Image.new("RGB", (1152, math.ceil(len(group)/3)*tile_h), "#101820")
                draw = ImageDraw.Draw(sheet)
                for i, (t, im) in enumerate(group):
                    x, y = (i%3)*384, (i//3)*tile_h
                    sheet.paste(im,(x,y))
                    draw.text((x+6,y+im.height+5), f"{t:.2f}s", fill="white")
                sheet.save(folder / f"联系表_{begin//12+1:03}.jpg",quality=90)
            outputs.append({"id":v["id"],"sha256":digest(path),"decoded_frames":count,"duration":self.duration,
                            "decoded_audio_samples":audio_samples,"audio_duration":audio_duration,
                            "audio_packet_sha256":packets.hexdigest(),"peak_dbfs":20*math.log10(max(peak,1e-12)),
                            "loudness":loudness_record,
                            "clipped_samples":clipped,"complete_decode":True})
        require(len({x["audio_packet_sha256"] for x in outputs}) == 1, "多个版本音轨不一致")
        save(self.check / "交付核验.json", {"status":"technical_pass_manual_review_required",
            "manifest_sha256":digest(self.path),"same_audio":True,"outputs":outputs,
            "manual_review":["逐镜头核验字幕遮挡、原文高光与来源真实性", "AI/动画原生标识首中尾可读且仅一处", "水印不遮挡证据并在镜头内静止", "试听专名及停顿，核对音乐落点", "抽帧不等于完整视听审片"]})
        print("完整视频/音频解码、帧数、PTS、音轨一致性、章节数核验通过；仍须实际视听审片。",flush=True)

    def player(self):
        self.validate()
        require(all((self.out/(v["id"]+".mp4")).exists() for v in self.versions), "请先 render")
        from urllib.parse import quote
        versions = [{"id":v["id"],"label":v.get("label",v["id"]),"url":quote(v["id"]+".mp4")} for v in self.versions]
        data = json.dumps({"versions":versions,"chapters":self.m.get("chapters",[]),"duration":self.duration}, ensure_ascii=False).replace("</", "<\\/")
        title = html.escape(self.m.get("title", "啊子牙 · 成片审阅"))
        page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>body{background:#0b1018;color:#e5edf8;font:16px system-ui;margin:0 auto;max-width:1200px;padding:24px}h1{font-size:23px}video{width:100%;max-height:78vh;background:#000;border-radius:12px}button{background:#223246;color:#edf5ff;border:1px solid #45617e;border-radius:7px;padding:10px 14px;margin:5px;cursor:pointer}.controls{margin:12px 0}p{color:#a8b8ca}</style><h1>__TITLE__</h1><video id="v" controls playsinline></video><div id="versions" class="controls"></div><div class="controls"><button id="back">后退10秒</button><button id="forward">前进10秒</button></div><div id="chapters" class="controls"></div><p id="status"></p><script>
const data=__DATA__,v=document.getElementById('v');
function load(version){const time=v.currentTime||0,playing=!v.paused;v.src=version.url;v.onloadedmetadata=()=>{v.currentTime=Math.min(time,v.duration);if(playing)v.play().catch(()=>{});};document.getElementById('status').textContent=version.label+' · '+Math.floor(data.duration/60)+'分'+(data.duration%60).toFixed(2)+'秒';}
data.versions.forEach(x=>{const b=document.createElement('button');b.textContent=x.label;b.onclick=()=>load(x);document.getElementById('versions').append(b)});
data.chapters.forEach(x=>{const b=document.createElement('button');b.textContent=x.title;b.onclick=()=>{v.currentTime=x.start;v.play().catch(()=>{})};document.getElementById('chapters').append(b)});
document.getElementById('back').onclick=()=>v.currentTime=Math.max(0,v.currentTime-10);document.getElementById('forward').onclick=()=>v.currentTime=Math.min(v.duration,v.currentTime+10);load(data.versions[0]);
</script></html>'''.replace("__TITLE__",title).replace("__DATA__",data)
        (self.out / "播放成片.html").write_text(page, encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate","render","verify","player","all"])
    parser.add_argument("manifest", type=Path)
    args=parser.parse_args()
    film=Film(args.manifest)
    if args.action=="all":
        film.render();film.verify();film.player()
    else:
        getattr(film,args.action)()


if __name__=="__main__":
    main()
