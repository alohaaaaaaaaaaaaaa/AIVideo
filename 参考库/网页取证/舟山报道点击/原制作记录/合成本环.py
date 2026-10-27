"""调查后续：固定原页、实音动态红线与本地查阅动作。

只处理本幕媒体，不调用生成 API、不改预算/授权。以 timeline.json 为准；
生成源正常速度各一次；AI反例素材有独立明确标签。--frames-only/--only/--assemble 可分阶段复核。
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parents[1]
CACHE = BASE / '缓存'
OUT = BASE / '导出'
CHECK = BASE / '检查'
W, H, FPS = 1920, 1080, 25
FF = imageio_ffmpeg.get_ffmpeg_exe()
STATIC_KINDS = {'evidence', 'comment', 'dynamic_comment'}
KINDS = STATIC_KINDS | {'ai_video', 'video', 'animation', 'local_action'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_text(path, content, encoding='utf-8'):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(content, encoding=encoding)
    tmp.replace(path)


def write(path, data):
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def resolve(path):
    path = Path(path)
    return path if path.is_absolute() else BASE / path


@lru_cache(maxsize=1)
def component():
    spec = importlib.util.spec_from_file_location('followup_actions', BASE / '动画/制作查阅动作.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def assets():
    entries = read(BASE / '声画执行稿.json')['evidence_assets']
    result = {k: resolve(v['path'] if isinstance(v, dict) else v) for k, v in entries.items()}
    folder = BASE / '证据素材/走访与军事报道'
    result.update({
        'V01': folder / 'V01_民间报告标题_标注.png',
        'V02': folder / 'V02c_华东管理局完整答复_标注.png',
        'V02_visit': folder / 'V02b_七月十五日接待_标注.png',
        'V03': folder / 'V03_限于所获资料完整结语_标注.png',
        'V04': folder / 'V04_私人军用并列分析完整段_标注.png',
        'MIL11': BASE / '证据素材/军事评论/MIL11_网友称舟山演习_完整评论.png',
        'airport_report': BASE.parent / '完整开场/真实证据/D2_observation_full_focus.png',
    })
    result['L01'] = result['L01_news']
    result['L04'] = result['L04_roles']
    for row in comment_overrides().values():
        for key in [row['id'], *row.get('aliases', [])]:
            result[key] = resolve(row['path'])
    return result


@lru_cache(maxsize=1)
def comment_overrides():
    path = CHECK / '评论原页高光接线.json'
    rows = read(path)['assets'] if path.exists() else []
    return {row['id']: row for row in rows}


def comment_override(asset):
    for row in comment_overrides().values():
        if asset in [row['id'], *row.get('aliases', [])]:
            return row
    return None


@lru_cache(maxsize=1)
def videos():
    return {v['id']: {**v, 'path': resolve(v['path'])}
            for v in read(CHECK / '生成素材清单.json')['videos']}


@lru_cache(maxsize=48)
def evidence_image(path):
    im = Image.open(path).convert('RGB')
    if im.size != (W, H):
        raise ValueError(f'原页必须1920×1080，禁止隐式重新排版：{path} {im.size}')
    return im


@lru_cache(maxsize=1)
def timeline_data():
    return read(BASE / 'timeline.json')


def cue_matches(shot, cue):
    # Aliased L01/L04 shots share one contiguous original floor. Earlier strokes
    # remain, so a narration boundary cannot make the red marks disappear.
    if cue.get('asset') == shot.get('asset'):
        return True
    try:
        return assets().get(cue.get('asset')) == assets().get(shot.get('asset')) and assets().get(shot.get('asset')) is not None
    except KeyError:
        return False


def shot_cues(shot):
    own = shot.get('underline_cues')
    cues = own if own is not None else [c for c in timeline_data().get('underline_cues', []) if cue_matches(shot, c)]
    override = comment_override(shot.get('asset'))
    if override is None:
        return cues
    groups = {g['key']: g for g in override['underline_groups']}
    result = []
    for cue in cues:
        group = groups.get(cue['key'])
        if group is None:
            raise ValueError(f'新原页缺少红线坐标：{shot["asset"]}/{cue["key"]}')
        result.append({**cue, 'segments': group['segments'],
                       'width_px': group.get('width_px', cue.get('width_px', 5)),
                       'color_rgb': group.get('color_rgb', cue.get('color_rgb', [215, 42, 48]))})
    return result


@lru_cache(maxsize=1)
def comment_footers():
    path = CHECK / '评论来源脚注.json'
    rows = read(path)['assets'] if path.exists() else []
    result = {}
    for row in rows:
        for key in [row['id'], *row.get('aliases', [])]:
            result[key] = row
    return result


def add_comment_footer(im, asset):
    row = comment_footers().get(asset)
    if row is None:
        return
    # Original L04 and L05 full floors reach y886/890. A shared strip at894
    # preserves those bottom signatures and original table borders verbatim.
    override = comment_override(asset)
    top = override.get('footer_y', 894) if override else 894
    max_y = override.get('max_comment_y', row['max_comment_y']) if override else row['max_comment_y']
    if max_y >= top or (not override and row['footer_background_start_min'] > top):
        raise ValueError(f'来源带会覆盖完整原评论 {asset}')
    d = ImageDraw.Draw(im)
    d.rectangle((0, top, W, H), fill=(15, 20, 27))
    source_font, note_font = font(26), font(23)
    for text, f in [(row['source_line'], source_font), (row['note_line'], note_font)]:
        if d.textlength(text, font=f) > W - 64:
            raise ValueError(f'来源脚注超出一行 {asset}')
    d.text((32, top + 20), row['source_line'], font=source_font, anchor='lt', fill=(217, 222, 229))
    d.text((32, top + 62), row['note_line'], font=note_font, anchor='lt', fill=(164, 177, 195))


def draw_underline(im, cue, global_t):
    start = float(cue['start'])
    duration = float(cue.get('draw_duration', cue.get('end', start + .6) - start))
    p = min(1., max(0., (global_t - start) / max(1 / FPS, duration)))
    if p <= 0:
        return
    lines = cue['segments']
    lengths = [math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2 in lines]
    remaining = sum(lengths) * p
    draw = ImageDraw.Draw(im)
    color = tuple(cue.get('color_rgb', [215, 42, 48]))
    width = int(cue.get('width_px', 5))
    for line, length in zip(lines, lengths):
        amount = min(length, remaining)
        if amount <= 0:
            break
        x1, y1, x2, y2 = line
        ratio = amount / max(.0001, length)
        xe, ye = x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio
        draw.line((round(x1), round(y1), round(xe), round(ye)), fill=color, width=width)
        radius = width / 2
        draw.ellipse((xe - radius, ye - radius, xe + radius, ye + radius), fill=color)
        remaining -= amount


def normalized_progress(shot, t):
    p = np.clip(t / max(1 / FPS, shot['end'] - shot['start'] - 1 / FPS), 0, 1)
    lo, hi = shot.get('p_range', [0, 1])
    return float(lo + (hi - lo) * p)


def progress(shot, t):
    if 'progress_knots' in shot:
        knots = shot['progress_knots']
        return float(np.interp(t, [v[0] for v in knots], [v[1] for v in knots]))
    return normalized_progress(shot, t)


def animated_frame(shot, t):
    mod = component()
    if 'phase_sequence' in shot:
        phases = shot['phase_sequence']
        for i, phase in enumerate(phases):
            if t < phase['end'] or i == len(phases) - 1:
                p = np.clip((t - phase['start']) / max(1 / FPS, phase['end'] - phase['start']), 0, 1)
                return mod.frame(phase['phase'], p)
    if 'phase' in shot:
        return mod.frame(shot['phase'], progress(shot, t))
    asset = shot['asset']
    if asset == 'A01':
        return mod.frame_at('A01', t, shot['end'] - shot['start'])
    if asset == 'A02a':
        return mod.frame('notice_range', progress(shot, t))
    if asset == 'A02b':
        return mod.frame('separate_times', progress(shot, t))
    if asset == 'A02':
        return mod.frame_at('A02', t, shot['end'] - shot['start'])
    raise ValueError(f'未知本地动画 {asset}')


@lru_cache(maxsize=1)
def action_desktop():
    return component().craft.desk().convert('RGB').resize((W, H), Image.Resampling.LANCZOS)


@lru_cache(maxsize=32)
def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc', size)


def ease(p):
    p = max(0., min(1., float(p)))
    return p * p * (3 - 2 * p)


def cursor(im, x, y, click=0):
    d = ImageDraw.Draw(im)
    if click > 0:
        r = 8 + 24 * click
        d.ellipse((x - r, y - r, x + r, y + r), outline=(170, 66, 47), width=3)
    poly = [(x, y), (x + 8, y + 39), (x + 16, y + 27), (x + 28, y + 33), (x + 33, y + 25), (x + 20, y + 19), (x + 33, y + 11)]
    d.polygon(poly, fill=(245, 240, 227), outline=(40, 43, 40), width=2)


def wipe_to(source, destination, p):
    """A deliberate page-turn cut: no continuing camera drift in reading shots."""
    p = ease(p)
    if p <= 0:
        return source.copy()
    if p >= 1:
        return destination.copy()
    x = round(W * (1 - p))
    im = destination.copy()
    if x > 0:
        im.paste(source.crop((0, 0, x, H)), (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((max(0, x - 20), 0, x, H), fill=(218, 210, 187))
    d.line((x, 0, x, H), fill=(74, 66, 51), width=4)
    return im


def local_action(shot, t):
    asset = shot['asset']
    p = normalized_progress(shot, t)
    if asset == 'open_M01':
        im = evidence_image(str(assets()['M01_title'])).copy()
        x = 1710 - 570 * ease(p / .65)
        y = 760 - 395 * ease(p / .65)
        cursor(im, x, y, max(0, 1 - abs(p - .78) / .13))
        return im
    if asset == 'anonymous_gap':
        im = evidence_image(str(assets()['E04_quote'])).copy()
        # Underline only the existing anonymous attribution on its original row.
        draw_underline(im, {'start': 0, 'draw_duration': .7, 'segments': [[76, 424, 212, 424]]}, t)
        return im
    if asset == 'A03_return':
        old = evidence_image(str(assets()['OTH09'])).copy()
        prior_comment = next((s for s in reversed(timeline_data()['shots'])
                              if s.get('asset') == 'OTH09' and s['end'] <= shot['start']), None)
        if prior_comment:
            for cue in shot_cues(prior_comment):
                draw_underline(old, cue, prior_comment['end'])
        add_comment_footer(old, 'OTH09')
        report = evidence_image(str(assets()['airport_report']))
        title = evidence_image(str(assets()['V01']))
        if p < .12:
            return wipe_to(old, title, p / .12)
        if p < .48:
            return title.copy()
        if p < .60:
            return wipe_to(title, report, (p - .48) / .12)
        im = report.copy()
        # Read the saved account in its existing accepted layout. No extra
        # emphasis is timed independently of the narrator in this return shot.
        return im
    if asset == 'keep_open':
        # A source page is put aside; an empty calendar index advances months.
        # Month labels are navigation, not invented article dates or evidence.
        craft = component().craft
        desk = craft.desk().copy()
        sheet = evidence_image(str(assets()['airport_report'])).resize((960, 540), Image.Resampling.LANCZOS).convert('RGBA')
        q = ease(p / .24)
        x = 145 - 1030 * q
        craft.quad_image(desk, sheet, [(x, 106), (x + 960, 106), (x + 960, 646), (x, 646)])
        if p > .18:
            progress_month = np.clip((p - .18) / .52, 0, 1)
            months = [7, 8, 9, 10]
            idx = min(3, int(progress_month * 4))
            month = months[idx]
            d = ImageDraw.Draw(desk)
            for offset in [12, 8, 4]:
                d.rectangle((441 + offset, 143 + offset, 841 + offset, 566 + offset), fill=(169 + offset, 159 + offset, 133 + offset))
            d.rectangle((441, 143, 841, 566), fill=(235, 226, 203))
            d.rectangle((441, 143, 841, 203), fill=(114, 54, 41))
            craft.center(d, (641, 173), '2010', 29, (245, 235, 211), mono=True)
            craft.center(d, (641, 326), f'{month}月', 94, (50, 52, 45), bold=True)
            craft.center(d, (641, 465), '继续翻当年的报道', 25, (87, 86, 69))
            if p > .76:
                craft.center(d, (641, 615), '还有新的说法吗？', 27, (225, 199, 148))
        return desk.convert('RGB').resize((W, H), Image.Resampling.LANCZOS)
    if asset in assets():
        return evidence_image(str(assets()[asset])).copy()
    raise ValueError(f'未知查阅动作 {asset}')


def frame(shot, t):
    kind = shot['kind']
    if kind in STATIC_KINDS:
        im = evidence_image(str(assets()[shot['asset']])).copy()
        for cue in shot_cues(shot):
            draw_underline(im, cue, shot['start'] + t)
        add_comment_footer(im, shot['asset'])
        return im
    if kind == 'animation':
        return animated_frame(shot, t).convert('RGB')
    if kind == 'local_action':
        return local_action(shot, t).convert('RGB')
    raise ValueError(f'需要视频解码的类型 {kind}')


def ass_time(t):
    cs = round(t * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f'{h}:{m:02}:{s:02}.{cs:02}'


def srt_time(t):
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def subtitles(timeline):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,46,&H00F4F1E8,&H000000FF,&H00130E0A,&H900A0C10,0,0,0,0,100,100,1,0,1,2.7,1.0,2,70,70,39,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    rows, srt = [], []
    for i, sub in enumerate(timeline['subtitles'], 1):
        caption = sub['text'].rstrip('，。').replace('\n', r'\N')
        rows.append(f"Dialogue: 0,{ass_time(sub['start'])},{ass_time(sub['end'])},Default,,0,0,0,,{caption}")
        srt.append(f"{i}\n{srt_time(sub['start'])} --> {srt_time(sub['end'])}\n{sub['text']}")
    ass = OUT / '调查后续_字幕.ass'
    atomic_text(ass, header + '\n'.join(rows) + '\n', 'utf-8-sig')
    atomic_text(OUT / '调查后续_字幕.srt', '\n\n'.join(srt) + '\n')
    return ass


def run(args, log):
    with Path(log).open('w', encoding='utf-8') as stream:
        result = subprocess.run([FF, '-y', '-hide_banner', *map(str, args)], stdout=stream, stderr=stream)
    if result.returncode:
        raise RuntimeError(f'FFmpeg失败，见 {log}')


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(shot):
    payload = json.dumps(shot, ensure_ascii=False, sort_keys=True).encode() + Path(__file__).read_bytes()
    if shot['kind'] in STATIC_KINDS:
        payload += bytes.fromhex(sha256_file(assets()[shot['asset']]))
        payload += json.dumps(shot_cues(shot), sort_keys=True).encode()
        payload += json.dumps(comment_footers().get(shot['asset']), ensure_ascii=False, sort_keys=True).encode()
    elif shot['kind'] in {'video', 'ai_video'}:
        payload += bytes.fromhex(sha256_file(videos()[shot.get('source_id', shot['asset'])]['path']))
    else:
        payload += (BASE / '动画/制作查阅动作.py').read_bytes()
        if shot['kind'] == 'local_action':
            for key in ['OTH09', 'airport_report', 'V01', 'E04_quote', 'M01_title']:
                payload += bytes.fromhex(sha256_file(assets()[key]))
            payload += json.dumps(comment_overrides(), ensure_ascii=False, sort_keys=True).encode()
            payload += json.dumps(timeline_data().get('underline_cues', []), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_timeline(timeline):
    if (timeline.get('width', W), timeline.get('height', H), timeline.get('fps', FPS)) != (W, H, FPS):
        raise ValueError('本幕固定1920×1080@25fps')
    ids, sources, end = set(), set(), 0.
    for shot in timeline['shots']:
        sid, kind = shot['id'], shot['kind']
        duration = shot['end'] - shot['start']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', sid) or sid in ids:
            raise ValueError(f'重复或不安全镜号 {sid}')
        ids.add(sid)
        if kind not in KINDS or duration <= 0 or abs(shot['start'] - end) > 1e-5:
            raise ValueError(f'镜头类型/连续时码异常 {sid}')
        if abs(round(duration * FPS) - duration * FPS) > 1e-4:
            raise ValueError(f'镜头时长未对齐25fps {sid}')
        end = shot['end']
        if kind in {'video', 'ai_video'}:
            source_id = shot.get('source_id', shot['asset'])
            if source_id in sources or float(shot.get('speed', 1)) != 1:
                raise ValueError(f'生成视频重复或变速 {sid}')
            sources.add(source_id)
            record = videos()[source_id]
            if not record['accepted_for_final'] or duration + shot.get('source_in', 0) > record['duration'] + .001:
                raise ValueError(f'生成源未认可或补长 {sid}')
            if sha256_file(record['path']) != record['sha256']:
                raise ValueError(f'生成源哈希变更 {source_id}')
            if source_id == 'N15_giant_contrast':
                if (shot.get('video_role') != 'ai_exaggeration_counterexample'
                        or shot.get('label') != 'AI夸张演绎'
                        or shot.get('label_secondary') != '并非历史影像'):
                    raise ValueError('巨物反例必须持续标示AI夸张演绎、并非历史影像。')
    if abs(end - timeline['duration']) > 1e-5:
        raise ValueError('镜头总时长与duration不符')
    expected = {'N10', 'N13', 'N14'}
    if timeline.get('visual_revision', {}).get('enabled') is True:
        expected.add('N15_giant_contrast')
    if sources != expected:
        raise ValueError(f'生成视频必须按当前已启用编排各一次 {sources}')


def render_one(shot, target):
    count = round((shot['end'] - shot['start']) * FPS)
    if shot['kind'] in {'video', 'ai_video'}:
        source = videos()[shot.get('source_id', shot['asset'])]['path']
        label = CACHE / (shot['id'] + '_情境标签.txt')
        is_counterexample = shot.get('video_role') == 'ai_exaggeration_counterexample'
        atomic_text(label, 'AI夸张演绎' if is_counterexample else 'AI情境示意')
        labelpath = label.resolve().as_posix().replace(':', r'\:').replace("'", r"\'")
        if is_counterexample:
            secondary = CACHE / (shot['id'] + '_非历史影像.txt')
            atomic_text(secondary, '并非历史影像')
            secondary_path = secondary.resolve().as_posix().replace(':', r'\:').replace("'", r"\'")
            vf = ("fps=25,scale=1920:1080,setsar=1,drawbox=x=28:y=23:w=340:h=119:color=black@0.78:t=fill,"
                  "drawtext=fontfile='C\\:/Windows/Fonts/msyhbd.ttc':"
                  f"textfile='{labelpath}':fontsize=40:fontcolor=0xFFDA8A:x=47:y=35,"
                  "drawtext=fontfile='C\\:/Windows/Fonts/msyh.ttc':"
                  f"textfile='{secondary_path}':fontsize=29:fontcolor=white:x=49:y=92")
        else:
            vf = ("fps=25,scale=1920:1080,setsar=1,drawtext=fontfile='C\\:/Windows/Fonts/msyh.ttc':"
                  f"textfile='{labelpath}':fontsize=27:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10:x=45:y=36")
        run(['-ss', shot.get('source_in', 0), '-i', source, '-an', '-vf', vf, '-frames:v', count,
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
             '-video_track_timescale', '12800', '-movflags', '+faststart', target], CACHE / (shot['id'] + '.log'))
        return
    if shot['kind'] == 'evidence' and not shot_cues(shot):
        run(['-loop', '1', '-framerate', FPS, '-i', assets()[shot['asset']], '-frames:v', count,
             '-an', '-c:v', 'libx264', '-preset', 'fast', '-tune', 'stillimage', '-crf', '18',
             '-pix_fmt', 'yuv420p', '-video_track_timescale', '12800', '-movflags', '+faststart', target], CACHE / (shot['id'] + '.log'))
        return
    cmd = [FF, '-y', '-hide_banner', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
           '-video_track_timescale', '12800', '-movflags', '+faststart', str(target)]
    with (CACHE / (shot['id'] + '.log')).open('w', encoding='utf-8') as stream:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=stream, stderr=stream)
        try:
            for i in range(count):
                im = frame(shot, i / FPS)
                if im.size != (W, H) or im.mode != 'RGB':
                    raise ValueError(f'组件格式错误 {shot["id"]}')
                proc.stdin.write(im.tobytes())
            proc.stdin.close()
            if proc.wait():
                raise RuntimeError(f'{shot["id"]}编码失败')
        finally:
            if proc.poll() is None:
                proc.terminate()


def assemble(timeline, ass, paths):
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f'尚未渲染 {path}')
    concat = CACHE / 'concat.txt'
    atomic_text(concat, '\n'.join("file '" + p.resolve().as_posix().replace("'", "'\\''") + "'" for p in paths) + '\n')
    raw = CACHE / '调查后续_无字幕.mp4'
    run(['-f', 'concat', '-safe', '0', '-i', concat, '-c', 'copy', raw], CACHE / '拼接.log')
    assfilter = ass.resolve().as_posix().replace(':', r'\:').replace("'", r"\'")
    out = OUT / '调查后续_无BGM_1080p.mp4'
    run(['-i', raw, '-i', resolve(timeline['audio']), '-vf', f"ass='{assfilter}'", '-map', '0:v:0', '-map', '1:a:0',
         '-t', timeline['duration'], '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', out], CACHE / '封装.log')
    print('ASSEMBLED', out, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', nargs='+')
    parser.add_argument('--assemble', action='store_true')
    parser.add_argument('--frames-only', action='store_true')
    args = parser.parse_args()
    for folder in [CACHE, OUT, CHECK]:
        folder.mkdir(parents=True, exist_ok=True)
    tl = timeline_data()
    validate_timeline(tl)
    ass = subtitles(tl)
    paths = []
    for shot in tl['shots']:
        target = CACHE / (shot['id'] + '.mp4')
        paths.append(target)
        if args.assemble or (args.only and shot['id'] not in args.only):
            continue
        if shot['kind'] not in {'video', 'ai_video'}:
            frame(shot, (shot['end'] - shot['start']) * .65).save(CHECK / (shot['id'] + '_合成前.png'))
        if args.frames_only:
            continue
        sig = fingerprint(shot)
        stamp = target.with_suffix('.stamp')
        if target.exists() and stamp.exists() and stamp.read_text() == sig:
            continue
        print('RENDER', shot['id'], round(shot['end'] - shot['start'], 2), flush=True)
        render_one(shot, target)
        atomic_text(stamp, sig)
    if not args.only and not args.frames_only:
        assemble(tl, ass, paths)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
