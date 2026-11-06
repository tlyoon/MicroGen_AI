"""Regression: highlighted fragments must not reuse static caches or ignore cue audio."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest

from test_microgen_timed_highlight_contract import stage
from microgen_timed_highlight_contract import (
    _hash, inspect_timed_highlights, video_segment_cache_key,
)
import microgen_autonomous_video_parts as parts


def test_static_cache_keys_remain_byte_for_byte_compatible():
    with TemporaryDirectory() as temp:
        s=stage(Path(temp))
        pdf=s/"slide1.pdf"
        wav=s/"slide1.wav"
        expected=hashlib.sha256(
            f"{_hash(pdf)}:{_hash(wav)}:gen_video_v22_cache_v2".encode()
        ).hexdigest()
        assert video_segment_cache_key(pdf,wav)==expected
        timed=inspect_timed_highlights(s)
        other=video_segment_cache_key(pdf,wav,timed["manifest_sha256"])
        assert other != expected
        assert len(other)==64


def test_video_checkpoint_fingerprint_tracks_timing_manifest_changes():
    from microgen_quality import dependency_fingerprint
    with TemporaryDirectory() as temp:
        s=stage(Path(temp))
        for name in ("gen_video_v22.py","microgen_autonomous_video_parts.py",
                     "microgen_timed_highlight_contract.py"):
            (s/name).write_text("isolated code input",encoding="utf8")
        original=dependency_fingerprint(s,"video")
        manifest=s/".microgen_timed_highlights.json"
        content=json.loads(manifest.read_text(encoding="utf8"))
        content["slides"][0]["cues"][0]["element_id"]="same_source_new_element_id"
        manifest.write_text(json.dumps(content),encoding="utf8")
        changed=dependency_fingerprint(s,"video")
        assert original != changed
        manifest.unlink()
        static=dependency_fingerprint(s,"video")
        assert static not in (original,changed)


def test_timed_parts_refuse_cached_static_video_and_bind_all_chunks():
    with TemporaryDirectory() as temp:
        s=stage(Path(temp))
        (s/"source.pdf").write_bytes(b"immutable isolated source fixture")
        (s/"slides.mp4").write_bytes(b"not a released video")
        bound=inspect_timed_highlights(s)
        old=s/".microgen_video_cache"
        old.mkdir()
        for i in range(1,3):
            static=old/f"slide{i}.mp4"
            static.write_bytes(b"previous good static segment")
            (old/f"slide{i}.json").write_text(json.dumps({
                "key":video_segment_cache_key(s/f"slide{i}.pdf",s/f"slide{i}.wav"),
                "sha256":_hash(static),
            }),encoding="utf8")
        with mock.patch.object(parts,"check_video",return_value={"seconds":1.4}):
            with pytest.raises(parts.AutoPartsError,match="Missing or unsafe"):
                parts._cache_segments(s,2)
        assert all((old/f"slide{i}.mp4").is_file() for i in (1,2))
        keys=parts._keys(s,2)
        assert ".microgen_timed_highlights.json" in keys
        assert "highlight_chunks/slide1_cue1.wav" in keys
        assert "highlight_chunks/slide2_cue2.wav" in keys
        new=s/f".microgen_video_cache_timed_{bound['manifest_sha256'][:12]}"
        new.mkdir()
        for i in range(1,3):
            video=new/f"slide{i}.mp4"
            video.write_bytes(b"independently highlighted video segment")
            (new/f"slide{i}.json").write_text(json.dumps({
                "key":video_segment_cache_key(
                    s/f"slide{i}.pdf",s/f"slide{i}.wav",
                    bound["manifest_sha256"]),
                "sha256":_hash(video),
            }),encoding="utf8")
        with mock.patch.object(parts,"check_video",return_value={"seconds":1.4}):
            active=parts._cache_segments(s,2)
        assert [x.parent for x in active]==[new,new]
        assert all((old/f"slide{i}.mp4").read_bytes()==
                   b"previous good static segment" for i in (1,2))
