"""PR270 exact original chapter handoff -> Gemini TTS -> PR269 -> PR268, all synthetic."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from microgen_flash_tts import DEFAULT_MODEL
from microgen_flash_chapter_tts import (
    FlashChapterTTSError, chapter_preflight, produce_private_chapter,
    main,
)
from microgen_private_chapter_audio_video import (
    audit_chapter_captured_audio, PrivateChapterMediaError,
)
from test_microgen_private_chapter_audio_video import _fixture, _make_audio
from microgen_pronunciation_closed_loop import sha_file


def prepared(tmp_path):
    bundle, filled, original = _fixture(tmp_path)
    plan = json.loads(filled.read_text())
    for row in plan["sections"]:
        row["audio_dir"] = None
        row["capture_manifest"] = None
    blank = tmp_path/"chapter_source_bound_blank.json"
    blank.write_text(json.dumps(plan),encoding="utf8")
    return bundle,blank,original


def wav_bytes(tmp_path,pitch=400):
    filename=tmp_path/f"synthetic_{pitch}.wav"
    _make_audio(filename,pitch)
    return filename.read_bytes()


def test_source_sha_bound_chapter_preflight_no_network_or_audio(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_FORMAL_TTS_PROVIDER","gemini")
    bundle,blank,_ = prepared(tmp_path)
    result, texts, frozen = chapter_preflight(bundle,blank)
    assert result["chapter_id"]=="1"
    assert result["slide_count"]==4
    assert result["section_count"]==2
    assert result["gemini_default_model"]=="gemini-3.8-flash-lite-tts"
    assert result["gemini_first_fallback"]=="gemini-3.8-flash-tts"
    assert result["voice"]=="Kore"
    assert result["paid_provider_calls"]==0
    assert result["publication_allowed"] is False
    assert len(texts)==4
    assert all(sha_file(path)==digest for path,digest in frozen.items())
    assert main(["--chapter-bundle",str(bundle),
                 "--blank-source-plan",str(blank)])==0


def test_paid_synthesis_requires_explicit_run_authorization(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_FORMAL_TTS_PROVIDER","gemini")
    bundle,blank,_=prepared(tmp_path)
    target=tmp_path/"must_not_exist"
    with pytest.raises(FlashChapterTTSError,match="authorize-paid"):
        produce_private_chapter(bundle,blank,target)
    assert not target.exists()


def test_full_synthetic_chapter_flash_to_pr269_to_pr268_real_video(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_FORMAL_TTS_PROVIDER","gemini")
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    bundle,blank,original=prepared(tmp_path)
    initial_source=[sha_file(Path(x["source_pdf"])) for x in original["cases"]]
    audio=wav_bytes(tmp_path)
    calls=[]
    def speak(text, spec):
        assert spec["model"]==DEFAULT_MODEL
        assert spec["voice"]=="Kore"
        calls.append(spec["provider"])
        return audio
    output=tmp_path/"PRIVATE_CHAPTER_AUDIO"
    result=produce_private_chapter(
        bundle,blank,output,authorized_paid_run=True,speak=speak)
    assert result["slide_count"]==4
    assert result["section_count"]==2
    assert result["provider_model"]=="gemini-3.8-flash-lite-tts"
    assert result["provider_voice"]=="Kore"
    assert result["publication_allowed"] is False
    assert len(calls)==4
    assert (output/"chapter_gemini_audio_receipt.json").is_file()
    plan=output/"verified_capture"/"capture_plan_ready.json"
    assert plan.is_file()
    parsed=json.loads(plan.read_text())
    assert all(Path(row["audio_dir"]).is_dir() and
               Path(row["capture_manifest"]).is_file()
               for row in parsed["sections"])
    assert len(list((output/"wav_root").rglob("*.wav")))==4
    assert [sha_file(Path(x["source_pdf"])) for x in original["cases"]]==initial_source
    videos=tmp_path/"PRIVATE_COMPLETE_VIDEO"
    media=audit_chapter_captured_audio(
        bundle,plan,videos,render_private_videos=True)
    assert media["videos_created"] is True
    assert media["slide_count"]==4
    assert media["section_count"]==2
    assert media["publication_allowed"] is False
    assert len(list((videos/"section_videos").glob("*.mp4")))==2
    assert all(x["every_slide_midpoint_frame_verified"] for x in media["sections"])


def test_original_source_changed_fails_before_paid_provider_request(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_FORMAL_TTS_PROVIDER","gemini")
    bundle,blank,orig=prepared(tmp_path)
    source=Path(orig["cases"][0]["source_pdf"])
    with source.open("ab") as f:
        f.write(b"forged-after-readiness")
    with pytest.raises((FlashChapterTTSError,PrivateChapterMediaError,ValueError)):
        produce_private_chapter(
            bundle,blank,tmp_path/"no_output",authorized_paid_run=True,
            speak=lambda *a:(_ for _ in ()).throw(AssertionError("never call")))
    assert not (tmp_path/"no_output").exists()


def test_owner_explicit_cloud_primary_remains_outside_default_pipeline(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_FORMAL_TTS_PROVIDER","google_cloud")
    bundle,blank,_=prepared(tmp_path)
    with pytest.raises(FlashChapterTTSError,match="not Gemini"):
        produce_private_chapter(
            bundle,blank,tmp_path/"no_cloud_primary",authorized_paid_run=True,
            speak=lambda *a: (_ for _ in ()).throw(AssertionError("network")))
    assert not (tmp_path/"no_cloud_primary").exists()


def test_existing_private_output_is_not_overwritten(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_FORMAL_TTS_PROVIDER","gemini")
    bundle,blank,_=prepared(tmp_path)
    target=tmp_path/"keep"
    target.mkdir()
    (target/"keep.txt").write_text("user file")
    with pytest.raises((PrivateChapterMediaError,FlashChapterTTSError)):
        produce_private_chapter(
            bundle,blank,target,authorized_paid_run=True,
            speak=lambda *a: (_ for _ in ()).throw(AssertionError("network")))
    assert (target/"keep.txt").read_text()=="user file"
