"""啊子牙默认声音：按实际时间线编曲、轻量音效与旁白避让混音。

不调用服务；不循环旧录音；不改时间线、字幕、旁白源文件或任何旧成片。
使用方法见 ../../文档/03_默认配音与配乐.md。全部时码为本幕内的秒数。
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys

import imageio_ffmpeg
import numpy as np
from scipy import ndimage, signal
from scipy.io import wavfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
PALETTE = ROOT / "参考库/声音/音源"
SR = 48000
FF = imageio_ffmpeg.get_ffmpeg_exe()
CHORDS = {
    "Am9": ([57, 60, 64, 71], 45), "Fmaj9": ([57, 60, 64, 67], 41),
    "Dm9": ([57, 60, 62, 65], 50), "Cmaj7": ([55, 59, 60, 64], 48),
    "Am7": ([55, 57, 60, 64], 45), "Em7": ([55, 59, 62, 64], 47),
    "Esus": ([57, 59, 64, 69], 47), "G6": ([55, 59, 62, 64], 43),
    "C6": ([55, 60, 64, 69], 48), "C": ([55, 60, 64, 67], 48),
}
ROLES = {
    "discovery": (84, ["Am9", "Cmaj7", "Fmaj9", "C6", "Dm9", "G6"], .87),
    "trace": (90, ["Am7", "Dm9", "Am9", "Em7", "Fmaj9", "Esus"], .92),
    "mismatch": (80, ["Esus", "Am7", "Dm9", "Em7"], .64),
    "early": (86, ["Am9", "Fmaj9", "Dm9", "Cmaj7", "Em7"], .83),
    "comments": (88, ["Cmaj7", "Fmaj9", "Am7", "Dm9", "G6"], .78),
    "window": (76, ["Am9", "Fmaj9", "Em7", "Dm9"], .65),
    "recap": (86, ["Am9", "Fmaj9", "Dm9", "Em7", "Cmaj7", "G6"], .91),
    "judgment": (82, ["Fmaj9", "Dm9", "G6", "Cmaj7"], .90),
    "resolved": (82, ["C", "Fmaj9", "C6", "G6", "C"], .78),
    "coda": (90, ["C6", "Fmaj9", "Cmaj7", "G6", "C"], .74),
    "outro": (86, ["Fmaj9", "G6", "C6", "C"], .72),
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda: f.read(2**20), b""):
            h.update(part)
    return h.hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def run(args):
    p = subprocess.run([FF, "-hide_banner", "-y", *map(str, args)], capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode("utf-8", errors="replace")[-5000:])
    return p


def db(x):
    return 20 * np.log10(np.maximum(x, 1e-12))


def preserve_prefix(array, source, duration, fade=0.):
    """精确保留认可前段；交叉淡化只能发生在新尾部内部。"""
    rate, prior = wavfile.read(source, mmap=True)
    count = round(duration*SR)
    cross = round(fade*SR)
    assert rate == SR and prior.shape[1:] == array.shape[1:]
    assert count+cross <= min(len(prior), len(array)), "前段/过渡超出音轨长度"
    array[:count] = prior[:count]
    if cross:
        weight = (1-np.cos(np.linspace(0, np.pi, cross)))*.5
        if array.ndim == 2:
            weight = weight[:, None]
        array[count:count+cross] = prior[count:count+cross]*(1-weight)+array[count:count+cross]*weight
    exact = bool(np.array_equal(array[:count].astype(np.float32), prior[:count]))
    assert exact
    return {"source": str(source), "prefix_seconds": duration, "prefix_samples": count,
            "prefix_sample_identical": exact, "crossfade_inside_new_tail_seconds": fade}


def norm(text):
    return re.sub(r"[\W_]+", "", str(text)).lower()


def phrases(tl):
    items = tl.get("subtitles", [])
    if not items:
        items = [p for s in tl.get("segments", []) for p in s.get("phrases", [])]
    return sorted([{"start": float(p["start"]), "end": float(p["end"]), "text": p["text"]}
                   for p in items], key=lambda p: p["start"])


def locate(tl, token):
    """可以跨字幕边界，返回真实片语的范围；不按字数猜时码。"""
    items, target = phrases(tl), norm(token)
    for i, item in enumerate(items):
        joined = ""
        boundaries = []
        for j in range(i, min(i + 4, len(items))):
            if j > i and items[j]["start"] - items[j - 1]["end"] > 2:
                break
            joined += norm(items[j]["text"])
            boundaries.append(len(joined))
            if target in joined:
                offset = joined.index(target)
                first = next(k for k, edge in enumerate(boundaries) if edge > offset)
                last = next(k for k, edge in enumerate(boundaries) if edge >= offset+len(target))
                return {"start": items[i+first]["start"], "end": items[i+last]["end"], "text": token}
    return None


def prepare(tl):
    """Explicit editorial music roles and real measured cues; never infer topic."""
    duration = float(tl["duration"])
    assert duration >= 1
    raw = tl.get("music_sections") or []
    assert raw, "Provide music_sections with an explicit music_mood"
    sections = []
    cursor = 0.0
    for i, sec in enumerate(raw):
        start, end = float(sec["start"]), float(sec["end"])
        role = sec["music_mood"]
        assert role in ROLES, f"Unsupported music_mood: {role}"
        assert abs(start-cursor) < .0001 and start < end <= duration+.0001
        sections.append({"id":str(sec.get("id",f"S{i+1:02}")), "title":sec.get("title",""), "start":start,"end":end,"role":role})
        cursor = end
    assert abs(cursor-duration)<.0001, "Music sections must cover the complete timeline"
    cues = list(tl.get("music_cues",[]))
    assert sum(c["type"]=="resolve" for c in cues)<=1, "Use one final cadence per render"
    for c in cues:
        assert c["type"] in ("space","resolve")
        if c["type"]=="space": assert 0<=c["start"]<c["end"]<=duration and 0<=c.get("gain",.5)<=1
        else: assert 0<=c["time"]<=duration-2, "Leave at least 2 seconds for the cadence"
    return sections, cues


def compose(tl):
    duration = float(tl["duration"])
    sections, cues = prepare(tl)
    events, bars = [], []
    rng = np.random.default_rng(201007071118)
    resolution_cue = next((c for c in cues if c["type"] == "resolve"), None)
    resolution = float(resolution_cue["time"]) if resolution_cue else None
    resolution_end = float(resolution_cue.get("scope_end",duration)) if resolution_cue else None

    def note(track, at, pitch, length, velocity, purpose):
        if at < 0 or at >= duration - .8:
            return
        if track in ("pizz", "vibes") and any(c["type"] == "space" and c["start"] <= at < c["end"] for c in cues):
            return
        events.append({"track": track, "time": round(at, 5), "pitch": int(pitch),
                       "duration": round(min(length, duration-at-.05), 5),
                       "velocity": int(np.clip(velocity, 1, 100)), "purpose": purpose})

    for sec in sections:
        role = sec["role"]
        bpm, progression, strength = ROLES[role]
        coda_variant = 0
        if role == "coda":
            # 五个彩蛋分别写尾奏小节，换和声起点、音区和问答密度。
            coda_variant = int(sec.get("variant",0)) % 5
            coda_progressions = [
                ["C6", "Fmaj9", "G6", "Cmaj7"],
                ["Fmaj9", "C6", "Dm9", "G6"],
                ["Cmaj7", "G6", "Fmaj9", "C6"],
                ["Am7", "Fmaj9", "Cmaj7", "G6"],
                ["Fmaj9", "G6", "C6", "C"],
            ]
            progression = coda_progressions[coda_variant]
            bpm = [88, 84, 92, 86, 88][coda_variant]
        beat = 60 / bpm
        count = math.ceil((sec["end"] - sec["start"]) / (4 * beat))
        for b in range(count):
            at = sec["start"] + .12 + b * beat * 4
            if at >= sec["end"]-.1:
                continue
            resolved = resolution is not None and resolution <= at < resolution_end and role in ("judgment", "resolved", "outro")
            local_progression = ROLES["resolved"][1] if resolved else progression
            chord = local_progression[b % len(local_progression)]
            voicing, bass = CHORDS[chord]
            bars.append({"time": round(at, 4), "section": sec["id"], "role": role,
                         "chord": chord, "bpm": bpm, "resolved": resolved,
                         "coda_variant": coda_variant if role == "coda" else None})
            quiet = role in ("window", "mismatch")
            # 每4小节留一个薄段，减少长篇旁白下无休止的脉冲。
            sparse = b % 4 == 3 or quiet
            if not (quiet and b % 3 == 1):
                for j, pitch in enumerate(voicing):
                    note("strings", at+j*.025, pitch, min(4.05*beat, sec["end"]-at),
                         round((24 if quiet else 29)*strength), "延展和声，避免压迫人声")
            if b % (4 if quiet else 2) == 0:
                note("piano", at+.035, bass+12, beat*2.5, 34*strength, "稀疏低音支点")
            if role in ("coda", "comments", "outro"):
                patterns = [[(.8, 72), (2.5, 76)], [(1.0, 74), (2.8, 71)],
                            [(.9, 69), (2.65, 72)], [(1.3, 74)]]
                if role == "coda":
                    patterns = [
                        [[(.65, 72), (2.5, 76)], [(1.1, 74), (2.8, 71)], [(.8, 69), (2.4, 72)], [(1.5, 67)]],
                        [[(1.1, 76), (3.0, 72)], [(1.5, 74)], [(.9, 72), (2.7, 69)], [(1.3, 71)]],
                        [[(.75, 72), (1.8, 76), (3.15, 74)], [(1.0, 71), (2.5, 72)], [(.65, 76), (2.4, 72)], [(1.7, 67)]],
                        [[(.9, 76), (2.6, 72)], [(1.2, 74), (2.8, 69)], [(.8, 72), (2.7, 67)], [(1.5, 71)]],
                        [[(.75, 69), (2.5, 72)], [(1.0, 74), (2.7, 76)], [(.8, 72), (2.4, 67)], [(1.3, 72)]],
                    ][coda_variant]
            elif quiet:
                patterns = [[(1.3, 71)], [(2.1, 76)], [(1.8, 74)], [(2.2, 69)]]
            elif resolved:
                patterns = [[(.6, 72), (2.1, 76)], [(1.2, 67), (2.7, 72)],
                            [(.8, 69), (2.4, 76)], [(1.2, 72)]]
            elif role in ("trace", "recap"):
                patterns = [[(.7, 76), (1.9, 71), (3.15, 72)], [(.9, 74), (2.6, 69)],
                            [(.65, 72), (1.9, 74), (3.25, 71)], [(1.5, 76)]]
            else:
                patterns = [[(.8, 76), (2.25, 71)], [(1.0, 74), (2.7, 69)],
                            [(1.1, 72), (2.7, 76)], [(1.8, 71)]]
            for j, (offset, pitch) in enumerate(patterns[b % 4]):
                onset = at+offset*beat+float(rng.uniform(-.008, .008))
                if onset < sec["end"]-.22:
                    note("piano", onset, pitch, beat*(1.6 if quiet else 1.2),
                         (37+j%2*3)*strength, "已认可问句动机的逐段发展")
            pulses = [] if quiet else ([1.1] if sparse else [.5, 1.75, 3.05])
            if role == "coda" and not sparse:
                pulses = [[.5, 1.75, 3.0], [1.0, 3.0], [.5, 1.5, 2.75], [1.0, 2.65], [.75, 2.5]][coda_variant]
            if role in ("judgment", "resolved"):
                pulses = [2.7] if b % 2 == 0 else []
            for j, offset in enumerate(pulses):
                onset = at+offset*beat
                if onset < sec["end"]-.2:
                    pitch = voicing[(j+b)%4] + (12 if role in ("comments", "coda") else 0)
                    note("pizz", onset, pitch, beat*.4, 29*strength, "查阅推进或轻巧尾奏")
            if b % 6 == 2 and not quiet:
                note("vibes", min(sec["end"]-.3, at+3*beat), voicing[2]+12, beat*1.4, 21,
                     "少量色彩，不做发现音效")
    if resolution is not None:
        # 和声完成在句后，不鼓掌、不警报、不盖住结论关键词。
        for j, pitch in enumerate([48, 60, 64, 67, 72]):
            note("piano", resolution+j*.055, pitch, 2.4, 38 if j else 34, "结论字尾后的温和C大调终止式")
        for j, pitch in enumerate([55, 60, 64, 67]):
            note("strings", resolution+j*.02, pitch, 3.1, 27, "已经结束调查的完成感")
    if duration > 4 and (resolution is None or resolution_end < duration-.001):
        for j, pitch in enumerate([60, 64, 67, 72]):
            note("piano", duration-2.9+j*.055, pitch, 1.35, 29, "片尾自然落定")
    if resolution is not None:
        cadence = {"结论字尾后的温和C大调终止式", "已经结束调查的完成感"}
        events = [e for e in events if e["time"] < resolution or e["time"] >= resolution_end or e["purpose"] in cadence]
        landed=[e for e in events if e["purpose"] in cadence]
        assert len(landed)==9,"Conclusion must retain complete 5 piano + 4 string cadence"
    events.sort(key=lambda e: (e["time"], e["track"], e["pitch"]))
    return {"duration": duration, "sections": sections, "music_cues": cues, "bars": bars,
            "notes": events, "old_waveform_loop_used": False, "paid_api_calls": 0}


def render_score(plan, out, preserve=None):
    duration, n = plan["duration"], round(plan["duration"]*SR)
    sampler = module("final_score_sampler", BASE / "sampler.py")
    sampler.N, sampler.DURATION = n, duration
    font_path = PALETTE / "GeneralUser-GS.sf2"
    font = sampler.Font(font_path)
    calibration = read(PALETTE / "音源校准.json")
    configs = {"piano": (0, .90, 4200), "strings": (48, .31, 2400),
               "pizz": (45, .55, 3600), "vibes": (11, .20, 4600)}
    times = np.arange(n, dtype=np.float32)/SR
    env = np.minimum(1, times/.40)*np.clip((duration-times)/1.5, 0, 1)
    for cue in plan["music_cues"]:
        if cue["type"] == "space":
            a, b, gain = cue["start"], cue["end"], cue.get("gain", .5)
            env *= np.interp(times, [a-.20, a, b, b+.35], [1, gain, gain, 1]).astype(np.float32)
    full = np.zeros((n, 2), np.float32)
    metrics = {}
    for track, (program, gain, cutoff) in configs.items():
        stem = np.zeros((n, 2), np.float32)
        chosen = [e for e in plan["notes"] if e["track"] == track]
        for e in chosen:
            y = font.note(program, e["pitch"], e["velocity"], e["duration"])
            start = round(e["time"]*SR)
            take = min(len(y), n-start)
            stem[start:start+take] += y[:take]
        stem = signal.sosfilt(signal.butter(2, cutoff, fs=SR, output="sos"), stem, axis=0).astype(np.float32)
        stem = signal.sosfilt(signal.butter(2, 110, btype="highpass", fs=SR, output="sos"), stem, axis=0).astype(np.float32)
        stem = sampler.reverb(stem, 1.4 if track == "strings" else 1.1,
                              .23 if track == "piano" else .13, seed=program+14).astype(np.float32)
        stem *= .065/calibration["stems"][track]["raw_rms"]*gain
        stem -= signal.sosfilt(signal.butter(2, [1300, 3700], btype="bandpass", fs=SR, output="sos"), stem, axis=0).astype(np.float32)*.23
        stem *= env[:, None]
        prefix_check = None
        if preserve:
            prefix_check = preserve_prefix(stem, preserve["directory"]/f"分轨_{track}_48k_float.wav",
                                           preserve["duration"], preserve["fade"])
        full += stem
        path = out/f"分轨_{track}_48k_float.wav"
        wavfile.write(path, SR, stem)
        metrics[track] = {"program": program, "notes": len(chosen), "path": str(path), "sha256": sha(path),
                          "preserved_prefix": prefix_check}
        print(f"{track}: {len(chosen)} notes rendered", flush=True)
        del stem
    gain = min(1., 10**(-7/20)/max(float(np.max(np.abs(full))), 1e-12))
    full *= gain
    prefix_check = None
    if preserve:
        prefix_check = preserve_prefix(full, preserve["directory"]/"music_score_48k_stereo.wav",
                                       preserve["duration"], preserve["fade"])
    target = out/"music_score_48k_stereo.wav"
    wavfile.write(target, SR, full)
    record = plan | {"sample_rate": SR, "master_gain": gain, "stems": metrics,
                     "preserved_prefix": prefix_check,
                     "output": str(target), "output_sha256": sha(target),
                     "soundfont": str(font_path), "soundfont_sha256": sha(font_path),
                     "license": str(PALETTE/"GeneralUser-GS_LICENSE.txt"),
                     "license_source_url": "https://schristiancollins.com/generaluser.php",
                     "composition": "本幕按实音重新编曲；沿用已认可乐器音源和两音问句动机，不复制或循环已有音乐录音。"}
    save(out/"编曲记录.json", record)
    return target


def render_sfx(tl, out, preserve=None):
    """仅非历史录音的后期提示和环境氛围；有对应画面时码才生成。"""
    n = round(float(tl["duration"])*SR)
    audio = np.zeros((n, 2), np.float32)
    rng = np.random.default_rng(710880)
    events = []
    supplied = tl.get("sound_cues")
    cues = list(supplied or [])
    for cue in cues:
        kind = cue["type"]
        assert kind in ("page", "search", "cabin", "airport"), f"未知音效类型: {kind}"
        at = float(cue.get("time", cue.get("start", 0)))
        default_len = {"page": .16, "search": .08, "cabin": 6.5, "airport": 6.0}[kind]
        duration = min(float(cue.get("duration", default_len)), float(tl["duration"])-at)
        assert 0 <= at < float(tl["duration"]) and duration > 0
        size = round(duration*SR)
        t = np.arange(size)/SR
        noise = rng.normal(0, 1, size).astype(np.float32)
        if kind == "page":
            y = signal.sosfilt(signal.butter(2, [600, 3200], btype="bandpass", fs=SR, output="sos"), noise)
            y *= np.sin(np.pi*t/duration)**2
            level = -39
        elif kind == "search":
            y = signal.sosfilt(signal.butter(2, [650, 1700], btype="bandpass", fs=SR, output="sos"), noise)
            y *= np.exp(-t/0.014)*np.minimum(1, t/.002)
            level = -40
        else:
            hi = 750 if kind == "cabin" else 1100
            y = signal.sosfilt(signal.butter(3, [70, hi], btype="bandpass", fs=SR, output="sos"), noise)
            if kind == "cabin":
                y += np.sin(2*np.pi*92*t)*.08 + np.sin(2*np.pi*137*t)*.025
            y *= np.minimum(1, t/.55)*np.minimum(1, (duration-t)/.8)
            level = -38 if kind == "cabin" else -42
        gain_db = float(cue.get("gain_db", level))
        y *= 10**(gain_db/20)/max(np.sqrt(np.mean(y*y)), 1e-9)
        stereo = np.stack([y/np.sqrt(2), y/np.sqrt(2)], axis=1).astype(np.float32)
        start = round(at*SR)
        audio[start:start+size] += stereo[:n-start]
        events.append(cue | {"time": at, "duration": duration, "rms_gain_db": gain_db,
                             "source": "本地程序合成，后期氛围/查阅音效，非当年现场录音"})
    path = out/"音效_48k_stereo.wav"
    prefix_check = None
    if preserve:
        prefix_check = preserve_prefix(audio, preserve["directory"]/"音效_48k_stereo.wav", preserve["duration"])
    wavfile.write(path, SR, audio)
    save(out/"音效来源与时码.json", {"events": events, "output": str(path), "sha256": sha(path),
                                  "preserved_prefix": prefix_check, "paid_api_calls": 0})
    return path


def inspect(path):
    decoded = run(["-v", "error", "-i", path, "-vn", "-ar", SR, "-ac", 2, "-f", "f32le", "pipe:1"])
    audio = np.frombuffer(decoded.stdout, dtype="<f4").reshape(-1, 2)
    peak = float(np.max(np.abs(audio)))
    report = run(["-i", path, "-af", "loudnorm=I=-17:TP=-2:LRA=11:print_format=json", "-f", "null", "-"])
    blocks = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', report.stderr.decode("utf-8", errors="replace"), re.S)
    if not blocks:
        raise RuntimeError("FFmpeg未返回响度数据")
    loud = json.loads(blocks[-1])
    return {"path": str(path), "sha256": sha(path), "duration": len(audio)/SR,
            "sample_peak_dbfs": float(db(peak)), "clipped_samples": int(np.sum(np.abs(audio) >= 1)),
            "integrated_lufs": float(loud["input_i"]), "true_peak_dbtp": float(loud["input_tp"]),
            "loudness_range_lu": float(loud["input_lra"]), "complete_decode": True}


def mixdown(tl, narration, detector_path, music_path, sfx_path, out, preserve=None):
    n, duration = round(float(tl["duration"])*SR), float(tl["duration"])
    mixer = module("final_approved_duck", BASE/"mix_helpers.py")
    mixer.N, mixer.DURATION = n, duration
    sr, native = wavfile.read(narration)
    assert sr == SR, "旁白应先由主时间线输出48kHz WAV"
    assert abs(len(native)-n) <= 2, f"旁白长度与时间线不同: {len(native)/SR} vs {duration}"
    original = mixer.decode(narration, 1)[:, 0]
    detector = mixer.decode(detector_path or narration, 1)[:, 0]
    if native.ndim == 1 or native.shape[1] == 1:
        dialogue = np.repeat(original[:, None]/np.sqrt(2), 2, axis=1)
    else:
        dialogue = mixer.decode(narration, 2)
    music = mixer.decode(music_path, 2, "highpass=f=105,equalizer=f=1800:t=q:w=0.65:g=-4.5,lowpass=f=7000")
    music -= np.mean(music, axis=0, keepdims=True)
    active = mixer.rms_frames(detector, 480) > 10**(-43/20)
    active = ndimage.maximum_filter1d(active.astype(float), size=13, mode="nearest")
    env = np.zeros_like(active)
    for i, target in enumerate(active):
        previous = env[i-1] if i else target
        alpha = np.exp(-.01/(.035 if target > previous else .48))
        env[i] = target+(previous-target)*alpha
    times = np.arange(n, dtype=np.float32)/SR
    duck = np.interp(times, (np.arange(len(env))+.5)*.01, 1-.75*env).astype(np.float32)
    music *= duck[:, None]
    window = 12000
    voice_rms = mixer.rms_frames(dialogue, window)
    det_rms = mixer.rms_frames(detector, window)
    music_rms = mixer.rms_frames(music, window)
    voiced = (det_rms > 10**(-38/20)) & (voice_rms > 10**(-35/20))
    ratios = music_rms[voiced]/np.maximum(voice_rms[voiced], 1e-12)
    silent_level = None
    if len(ratios):
        gain = 10**(-21/20)/max(np.median(ratios), 1e-12)
    else:
        silent_level = tl.get('silent_music_rms_dbfs')
        assert isinstance(silent_level,(int,float)) and math.isfinite(silent_level) and -50<=silent_level<=-20, '无旁白章节须显式设置 silent_music_rms_dbfs（-50至-20）；根据前后音乐实测选择，不伪造人声相对电平'
        gain = 10**(silent_level/20)/max(float(np.sqrt(np.mean(music.astype(np.float64)**2))),1e-12)
    caps = np.ones_like(music_rms)
    caps[voiced] = np.minimum(1, 10**(-14/20)/np.maximum(ratios*gain, 1e-12))
    vb, mb = mixer.rms_frames(mixer.band(dialogue), window), mixer.rms_frames(mixer.band(music), window)
    valid = voiced & (vb > 10**(-42/20))
    caps[valid] = np.minimum(caps[valid], 10**(-9/20)/np.maximum(mb[valid]/vb[valid]*gain, 1e-12))
    caps = ndimage.minimum_filter1d(caps, size=3, mode="nearest")
    music *= (gain*np.interp(times, (np.arange(len(caps))+.5)*window/SR, caps)).astype(np.float32)[:, None]
    sfx = mixer.decode(sfx_path, 2)
    sfx *= np.sqrt(duck)[:, None]
    # 声音余量不足时只降音乐/环境，不能自动压低旁白。
    nonvoice = music+sfx
    guard = np.abs(nonvoice) > 1e-9
    headroom = .94-np.abs(dialogue)
    assert np.min(headroom) > 0, "旁白自身峰值过高，应在旁白阶段先匹配认可听感"
    safety_gain = min(1., float(np.min(headroom[guard]/np.abs(nonvoice[guard]))) if np.any(guard) else 1.)
    music *= safety_gain
    sfx *= safety_gain
    prefix_checks = []
    if preserve:
        for name, array, fade in [("music_48k_stereo.wav", music, preserve["fade"]),
                                   ("sfx_48k_stereo.wav", sfx, preserve["fade"]),
                                   ("voice_48k_stereo.wav", dialogue, 0.)]:
            prefix_checks.append(preserve_prefix(array, preserve["directory"]/name, preserve["duration"], fade))
    mixed = dialogue+music+sfx
    if preserve:
        prefix_checks.append(preserve_prefix(mixed, preserve["directory"]/"mix_48k_stereo.wav",
                                             preserve["duration"]))
    assert np.max(np.abs(mixed)) <= .94001
    outputs = {"voice_48k_stereo.wav": dialogue, "music_48k_stereo.wav": music,
               "sfx_48k_stereo.wav": sfx, "mix_48k_stereo.wav": mixed}
    for name, array in outputs.items():
        wavfile.write(out/name, SR, array.astype(np.float32))
    final = out/"mix_48k_stereo.wav"
    run(["-i", final, "-c:a", "libmp3lame", "-b:a", "192k", out/"mix_preview.mp3"])
    run(["-i", music_path, "-c:a", "libmp3lame", "-b:a", "192k", out/"music_preview.mp3"])
    ratio_db = db(mixer.rms_frames(music, window)[voiced]/voice_rms[voiced])
    measured = inspect(final)
    report = {"duration": duration, "narration": str(narration), "narration_sha256": sha(narration),
              "music_sha256": sha(music_path), "voice_processing": "单声道等功率居中；立体声输入保持；不归一化、不变速、不削人声",
              "music_eq": "HP105Hz; -4.5dB@1800Hz Q0.65; LP7000Hz",
              "duck_attack_ms": 35, "duck_release_ms": 480, "lookahead_ms": 60,
              "music_relative_db_median": float(np.median(ratio_db)) if len(ratio_db) else None, "music_relative_db_max": float(np.max(ratio_db)) if len(ratio_db) else None,
              "silent_music_rms_dbfs": silent_level,
              "dialogue_addition_residual_peak": float(np.max(np.abs(mixed-music-sfx-dialogue))),
              "nonvoice_safety_gain": safety_gain, "final": measured,
              "preserved_prefix_checks": prefix_checks,
              "loudness_near_accepted_reference": -18.5 <= measured["integrated_lufs"] <= -15.5,
              "new_paid_calls": 0, "listening_review": "技术核验；听感与画面结合由整片审阅确认"}
    save(out/"混音核验.json", report)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeline", type=Path, required=True)
    ap.add_argument("--narration", type=Path)
    ap.add_argument("--detector", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--music-only", action="store_true")
    ap.add_argument("--reuse-music", action="store_true")
    ap.add_argument("--adopted-score", type=Path, help="Validated note plan to re-render; no recomposition or old waveform looping")
    ap.add_argument("--preserve-prefix", type=Path, help="先前版本BGM目录，原样保留指定前段")
    ap.add_argument("--prefix-duration", type=float, default=0)
    ap.add_argument("--prefix-crossfade", type=float, default=.8, help="仅新尾部内的音乐过渡秒数")
    ap.add_argument("--verify-final", type=Path)
    args = ap.parse_args()
    assert args.prefix_duration >= 0
    args.output.mkdir(parents=True, exist_ok=True)
    tl = read(args.timeline)
    conclusion_check = None
    if not args.narration and not args.verify_final and (tl.get('conclusion_cue') or any(c.get('type')=='resolve' for c in tl.get('music_cues',[]))):
        raise ValueError('Conclusion music planning/rendering requires --narration for actual word-tail validation')
    if args.narration and not args.verify_final:
        from editorial import prepare_conclusion
        tl, conclusion_check = prepare_conclusion(tl,args.narration)
        if conclusion_check:save(args.output/"结论字尾核验.json",conclusion_check)
    if args.verify_final:
        check = inspect(args.verify_final)
        assert check["clipped_samples"] == 0
        assert abs(check["duration"]-float(tl["duration"])) <= .05
        save(args.output/"最终AAC核验.json", check | {"timeline_sha256": sha(args.timeline)})
        print(json.dumps(check, ensure_ascii=False, indent=2))
        return
    if args.adopted_score:
        plan=read(args.adopted_score)
        assert abs(float(plan['duration'])-float(tl['duration']))<1e-8,'Adopted score duration differs from current narration'
        assert plan.get('bars') and plan.get('sections') and plan.get('notes')
        for event in plan['notes']:
            assert event['track'] in ['piano','strings','pizz','vibes'] and 0<=event['time']<tl['duration'] and 0<event['duration']<=tl['duration']-event['time']+.0001
            assert 0<=event['pitch']<=127 and 1<=event['velocity']<=127
        if conclusion_check:
            resolve=next(c['time'] for c in plan.get('music_cues',[]) if c['type']=='resolve')
            assert abs(resolve-conclusion_check['resolve'])<.001,'Adopted cadence and measured word-tail cue differ; revise the explicit score'
        plan=plan|{'adopted_score_sha256':sha(args.adopted_score),'adopted_score_recomposed':False}
    else:plan=compose(tl)
    plan=plan|{'timeline':str(args.timeline),'timeline_sha256':sha(args.timeline),'conclusion_verification':conclusion_check}
    preserve = None
    if args.preserve_prefix:
        assert args.preserve_prefix.resolve() != args.output.resolve(), "保留源必须是独立备份目录"
        preserve = {"directory": args.preserve_prefix, "duration": args.prefix_duration, "fade": args.prefix_crossfade}
    from midi_export import write_midi
    write_midi(plan,args.output/"score.mid")
    save(args.output/"编曲执行计划.json", plan)
    if args.plan_only:
        print(json.dumps({"duration": plan["duration"], "notes": len(plan["notes"]),
                          "sections": plan["sections"], "cues": plan["music_cues"]}, ensure_ascii=False, indent=2))
        return
    music = args.output/"music_score_48k_stereo.wav"
    if args.reuse_music:
        assert read(args.output/"编曲记录.json")["timeline_sha256"] == sha(args.timeline), "时间线已变，须重新编曲"
    else:
        render_score(plan, args.output, preserve)
    sfx = render_sfx(tl, args.output, preserve)
    if not args.music_only:
        assert args.narration and args.narration.is_file(), "完整混音需要 --narration 48kHz WAV"
        report = mixdown(tl, args.narration, args.detector, music, sfx, args.output, preserve)
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
