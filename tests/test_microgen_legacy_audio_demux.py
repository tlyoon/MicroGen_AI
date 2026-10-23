"""Contract/adversarial tests for §2.5 legacy MP4 audio recovery.

A test MP4's slide scene metadata is synthetic; no word alignment is claimed.
"""
from __future__ import annotations
import json
import subprocess
import wave
from pathlib import Path

import pytest
import pymupdf as fitz
from microgen_quality import check_video
from microgen_source_safe_orchestrator import (
    create_workspace, stage_existing_root_wavs, source_bound_timeline, digest
)
import microgen_legacy_audio_demux as r


def build_synthetic_legacy(tmp_path):
    imageio_ffmpeg=pytest.importorskip("imageio_ffmpeg")
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    source=tmp_path/"lesson"
    source.mkdir()
    with fitz.open() as doc:
        for i in range(3):
            page=doc.new_page(width=640,height=360)
            page.insert_text((35,50),f"Slide {i+1}",fontsize=15)
        doc.save(source/"slides.pdf")
    (source/"script_tts.json").write_text(json.dumps({"slides":[
        {"slide":i,"tts_text":f"Physics slide {i}."} for i in range(1,4)]}),encoding="utf8")
    video=source/"slides.mp4"
    cmd=[ffmpeg,"-nostdin","-hide_banner","-loglevel","error",
        "-f","lavfi","-i","color=c=black:s=320x180:r=5:d=2.4",
        "-f","lavfi","-i","sine=frequency=500:sample_rate=16000:duration=2.4",
        "-t","2.4","-c:v","libx264","-pix_fmt","yuv420p",
        "-c:a","aac","-shortest","-y",str(video)]
    p=subprocess.run(cmd,capture_output=True,timeout=45)
    if p.returncode:
        pytest.skip("No bounded local H.264/AAC ffmpeg encoder: "+p.stderr.decode("utf8","replace")[-200:])
    media=check_video(video)
    report={"status":"VIDEO_CANDIDATE_PASS_NOT_PUBLISHED",
        "corrected_mp4_sha256":digest(video),"candidate_seconds":media["seconds"],
        "old_media_sha256":{"corrected_pdf":digest(source/"slides.pdf")},
        "source_provenance":{
            "narration_sidecar_sha256":digest(source/"script_tts.json"),"expected_pages":3},
        "video_slide_boundaries_seconds":[.7,1.5],
        "candidate_video_verification":{"corrected_scene_validation":[
            {"scene":i,"matching_pdf_page":i} for i in range(1,4)]}}
    evidence=source/".microgen_legacy_video_evidence.json"
    evidence.write_text(json.dumps(report),encoding="utf8")
    stage=tmp_path/"stage"
    create_workspace(source,stage)
    stage_existing_root_wavs(stage)
    return source,stage,ffmpeg


def test_scene_based_recovery_creates_all_staged_wavs(tmp_path):
    source,stage,ffmpeg=build_synthetic_legacy(tmp_path)
    before=digest(source/"slides.mp4")
    proof=r.inspect_legacy_scene_receipt(stage)
    assert proof["slide_count"]==3 and not proof["phonetic_accuracy_verified"]
    result=r.recover_legacy_scene_wavs(stage,ffmpeg=ffmpeg)
    assert result["wav_count"]==3 and not result["ready_for_publication"]
    assert digest(source/"slides.mp4")==before
    assert not (source/"slide1.wav").exists()
    with wave.open(str(stage/"audio"/"slide2.wav"),"rb") as wav:
        assert wav.getnchannels()==1 and wav.getframerate()==16000
        assert wav.getnframes()/wav.getframerate()==pytest.approx(.8,abs=.005)
    state=json.loads((stage/"legacy_mp4_audio_receipt.json").read_text())
    assert state["original_tts_wavs_recreated"] is False
    assert all(not c["phonemes_verified"] for c in state["clips"])
    timeline=source_bound_timeline(stage)
    assert timeline["slides"]==3
    with pytest.raises(r.LegacyRecoveryError):
        r.recover_legacy_scene_wavs(stage,ffmpeg=ffmpeg)


def test_video_mutation_rejected_before_materialization(tmp_path):
    source,stage,ffmpeg=build_synthetic_legacy(tmp_path)
    with (source/"slides.mp4").open("ab") as f:f.write(b"tampered")
    with pytest.raises(r.LegacyRecoveryError):
        r.recover_legacy_scene_wavs(stage,ffmpeg=ffmpeg)
    assert list((stage/"audio").iterdir())==[]


def test_corrupted_slide_boundaries_rejected_before_decode(tmp_path):
    source,stage,ffmpeg=build_synthetic_legacy(tmp_path)
    p=source/".microgen_legacy_video_evidence.json"
    obj=json.loads(p.read_text())
    obj["video_slide_boundaries_seconds"]=[1.5,.7]
    p.write_text(json.dumps(obj))
    with pytest.raises(r.LegacyRecoveryError):
        r.inspect_legacy_scene_receipt(stage)
    assert list((stage/"audio").iterdir())==[]


def test_mixed_wav_sources_refused(tmp_path):
    source,stage,ffmpeg=build_synthetic_legacy(tmp_path)
    with wave.open(str(stage/"audio"/"slide1.wav"),"wb") as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
        wav.writeframes(b"\0\0"*8000)
    with pytest.raises(r.LegacyRecoveryError):
        r.recover_legacy_scene_wavs(stage,ffmpeg=ffmpeg)


def test_bounded_extra_aac_tail_is_preserved_and_blocks_release(tmp_path,monkeypatch):
    source,stage,ffmpeg=build_synthetic_legacy(tmp_path)
    path=source/".microgen_legacy_video_evidence.json"
    obj=json.loads(path.read_text(encoding="utf8"))
    obj["candidate_seconds"]=1.85
    path.write_text(json.dumps(obj),encoding="utf8")
    # Simulate an MP4 container that reports less duration than its decoded
    # AAC track, reproducing the offset measured in the real Thomas lesson.
    monkeypatch.setattr(r,"check_video",lambda video:{"seconds":1.85})
    state=r.recover_legacy_scene_wavs(stage,ffmpeg=ffmpeg)
    assert state["wav_count"]==3
    assert state["audio_overhang_seconds"]==pytest.approx(.55,abs=.08)
    assert state["overhang_requires_listening_review"]
    assert state["overhang_acoustic_energy_present"]
    assert state["ready_for_publication"] is False
    receipt=json.loads((stage/"legacy_mp4_audio_receipt.json").read_text())
    assert receipt["audio_beyond_video_end"]["tail_sha256"]
    assert (stage/"audio"/"audio_after_video_end.wav").is_file()
