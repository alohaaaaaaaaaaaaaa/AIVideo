#!/usr/bin/env python3
"""Reject changed reviewed inputs before any encoding; no network or API calls."""
from pathlib import Path
from copy import deepcopy
import json
import tempfile
import wave

from PIL import Image
import studio_media
from studio_media import Film, digest, save


def pcm(path, value):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(48000)
        f.writeframes(int(value).to_bytes(2, "little", signed=True) * 2 * 48000)


def main():
    result = {"status": "passed", "checks": {}, "network_calls": 0, "paid_calls": 0, "encoded_files": 0}
    def no_encoding(*args, **kwargs):
        raise AssertionError("A stale input reached FFmpeg")
    studio_media.run = no_encoding
    with tempfile.TemporaryDirectory(prefix="aziya-binding-") as tmp:
        base = Path(tmp) / "中文 空格项目"
        base.mkdir()
        Image.new("RGB", (160, 90), "#123456").save(base / "画面.png")
        pcm(base / "混音.wav", 0)
        pcm(base / "旁白.wav", 1)
        for name in ("分镜", "时间线", "动画触发"):
            save(base / (name+".json"), {"reviewed": True, "version": 1})
        m = {"schema_version": 1, "title": "binding regression only", "width": 1920, "height": 1080,
             "fps": 25, "output_dir": "输出", "versions": [{"id": "clean", "watermark": False}],
             "shots": [{"id": "S01", "path": "画面.png", "kind": "image", "duration": 1,
                        "expected_sha256": digest(base / "画面.png")}],
             "audio": {"path": "混音.wav", "expected_sha256": digest(base / "混音.wav")},
             "subtitles": [], "chapters": [], "editorial_binding": {}}
        for key, filename in (("plan", "分镜.json"), ("timeline", "时间线.json"),
                              ("visual_cues", "动画触发.json"), ("narration", "旁白.wav")):
            m["editorial_binding"].update({key+"_path": filename, key+"_sha256": digest(base/filename)})
        manifest = base / "manifest.json"
        save(manifest, m)
        valid = Film(manifest).validate()
        assert valid["expected_input_hashes_checked"] == 2
        assert len(valid["editorial_binding"]) == 8
        result["checks"]["all_hashes_match_and_unicode_relative_paths"] = True
        sentinel = base / "输出/clean.mp4"
        sentinel.write_bytes(b"EXISTING_OUTPUT_MUST_REMAIN")

        def rejects(name, expected_fragment):
            try:
                Film(manifest).render()
            except ValueError as exc:
                assert expected_fragment in str(exc), (name, str(exc))
                assert sentinel.read_bytes() == b"EXISTING_OUTPUT_MUST_REMAIN"
                assert not (base / "输出/历史").exists()
                result["checks"][name] = {"rejected_before_encoding": True, "reason": str(exc)}
            else:
                raise AssertionError("Stale binding accepted: "+name)

        mutations = [
            ("same_size_image_replaced", "画面.png", lambda p: Image.new("RGB", (160, 90), "#654321").save(p), "镜头 S01"),
            ("same_duration_mix_replaced", "混音.wav", lambda p: pcm(p, 50), "全片混音"),
            ("storyboard_changed", "分镜.json", lambda p: save(p, {"reviewed": False}), "导演绑定 plan"),
            ("timeline_changed", "时间线.json", lambda p: save(p, {"version": 2}), "导演绑定 timeline"),
            ("visual_cues_changed", "动画触发.json", lambda p: save(p, {"cue_time": 0.5}), "导演绑定 visual_cues"),
            ("same_duration_narration_replaced", "旁白.wav", lambda p: pcm(p, 75), "导演绑定 narration"),
        ]
        for name, filename, modify, fragment in mutations:
            path = base / filename
            original = path.read_bytes()
            try:
                modify(path)
                rejects(name, fragment)
            finally:
                path.write_bytes(original)

        bad = deepcopy(m)
        del bad["shots"][0]["expected_sha256"]
        save(manifest, bad)
        rejects("bound_manifest_cannot_drop_asset_hash", "缺少expected_sha256")
        bad = deepcopy(m)
        del bad["editorial_binding"]["narration_sha256"]
        save(manifest, bad)
        rejects("optional_binding_requires_path_hash_pair", "路径与SHA256必须成对")

        manual = deepcopy(m)
        del manual["editorial_binding"]
        del manual["shots"][0]["expected_sha256"]
        del manual["audio"]["expected_sha256"]
        save(manifest, manual)
        legacy = Film(manifest).validate()
        assert legacy["editorial_binding"] is None and legacy["expected_input_hashes_checked"] == 0
        result["checks"]["unbound_manual_manifest_remains_compatible"] = True

        manual["shots"][0]["expected_sha256"] = "0"*64
        save(manifest, manual)
        rejects("optional_asset_hash_alone_is_enforced", "镜头 S01")

    target = Path(__file__).with_name("导演绑定回归.json")
    save(target, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
