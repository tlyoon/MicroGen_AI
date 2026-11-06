"""Decode actual MP4 cues and reject missing, persistent, or drifted highlights.

No paid models, source-PDF edits or publication. This reuses the established
PR209 ROI-difference QA and current source/PCM verification.
"""
import json
import os
import shutil
from unittest.mock import patch
from pathlib import Path

import pytest

from test_microgen_timed_highlight_contract import stage
from gen_video_v22 import main as render
from microgen_measured_highlight_video_qa import (
    RECEIPT, MeasuredVisualQAError, inspect_visual_timing,
    audit_stage,verify_receipt,
)


@pytest.fixture
def local_ffmpeg():
    ffmpeg=os.environ.get("MICROVID_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg or not Path(ffmpeg).is_file():
        pytest.skip("Local FFmpeg required for opt-in visual integration")
    return Path(ffmpeg)


def make_video(tmp_path,monkeypatch,ffmpeg):
    s=stage(tmp_path)
    monkeypatch.setenv("MICROVID_FFMPEG",str(ffmpeg))
    monkeypatch.chdir(s)
    render()
    return s


@pytest.mark.skipif(os.environ.get("MICROGEN_MEDIA_INTEGRATION_TEST")!="1",
                    reason="Opt-in real H.264/AAC frame verification")
def test_source_pcm_cue_visual_receipt_and_revalidation(
        tmp_path,monkeypatch,local_ffmpeg):
    s=make_video(tmp_path,monkeypatch,local_ffmpeg)
    result=audit_stage(s,ffmpeg=local_ffmpeg)
    assert result["cue_count"]==4
    assert result["slide_count"]==2
    assert result["visual_highlight_rendering_verified"] is True
    assert result["spoken_word_to_element_alignment_verified"] is False
    assert result["publication_allowed"] is False
    assert len(result["checked_cues"])==4
    assert (s/RECEIPT).is_file()
    assert verify_receipt(s,ffmpeg=local_ffmpeg)==result
    with pytest.raises(MeasuredVisualQAError,match="Untrusted"):
        amended=json.loads((s/RECEIPT).read_text(encoding="utf8"))
        amended["spoken_word_to_element_alignment_verified"]=True
        (s/RECEIPT).write_text(json.dumps(amended),encoding="utf8")
        verify_receipt(s,ffmpeg=local_ffmpeg)


@pytest.mark.skipif(os.environ.get("MICROGEN_MEDIA_INTEGRATION_TEST")!="1",
                    reason="Opt-in real H.264/AAC frame verification")
def test_static_slide_video_does_not_pass_cue_highlight_audit(
        tmp_path,monkeypatch,local_ffmpeg):
    s=stage(tmp_path)
    manifest=s/".microgen_timed_highlights.json"
    source=manifest.read_bytes()
    manifest.unlink()
    monkeypatch.setenv("MICROVID_FFMPEG",str(local_ffmpeg))
    monkeypatch.chdir(s)
    render()
    manifest.write_bytes(source)
    with pytest.raises(MeasuredVisualQAError,match="no independently visible"):
        inspect_visual_timing(s,ffmpeg=local_ffmpeg)
    assert not (s/RECEIPT).exists()


@pytest.mark.skipif(os.environ.get("MICROGEN_MEDIA_INTEGRATION_TEST")!="1",
                    reason="Opt-in real H.264/AAC frame verification")
def test_changed_cue_audio_invalidates_previous_visual_receipt(
        tmp_path,monkeypatch,local_ffmpeg):
    s=make_video(tmp_path,monkeypatch,local_ffmpeg)
    assert audit_stage(s,ffmpeg=local_ffmpeg)["cue_count"]==4
    chunk=s/"highlight_chunks"/"slide1_cue1.wav"
    raw=bytearray(chunk.read_bytes())
    raw[-2:]=b"\x12\x34"
    chunk.write_bytes(raw)
    with pytest.raises(Exception):
        verify_receipt(s,ffmpeg=local_ffmpeg)


@pytest.mark.skipif(os.environ.get("MICROGEN_MEDIA_INTEGRATION_TEST")!="1",
                    reason="Opt-in actual media safety regression")
def test_bad_timed_candidate_does_not_replace_previous_static_video(
        tmp_path,monkeypatch,local_ffmpeg):
    from microgen_quality import sha256
    stage_dir=stage(tmp_path)
    manifest=stage_dir/".microgen_timed_highlights.json"
    source=manifest.read_bytes()
    manifest.unlink()
    monkeypatch.setenv("MICROVID_FFMPEG",str(local_ffmpeg))
    monkeypatch.chdir(stage_dir)
    render()
    original=sha256(stage_dir/"slides.mp4")
    manifest.write_bytes(source)
    static_filter=("scale=1920:1080:force_original_aspect_ratio=decrease,"
                   "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white")
    with patch("microgen_timed_highlight_contract.ffmpeg_highlight_filter",
               return_value=static_filter):
        with pytest.raises(MeasuredVisualQAError,match="no independently visible"):
            render()
    assert sha256(stage_dir/"slides.mp4")==original
    assert not (stage_dir/RECEIPT).exists()
