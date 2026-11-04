"""Offline PR270 tests: exact Web Flash-Lite voice/model, failover and no paid calls."""
from __future__ import annotations

import array
import base64
import hashlib
import io
import json
import math
from pathlib import Path
import wave

import pytest

import microgen_flash_tts as flash
import microgen_tts_provider_policy as policy


def wav_data(pitch=330):
    samples = array.array("h", [
        int(5200*math.sin(2*math.pi*pitch*i/24000))
        for i in range(24000)
    ])
    memory = io.BytesIO()
    with wave.open(memory, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(samples.tobytes())
    return memory.getvalue()


def never_network(*args, **kwargs):
    raise AssertionError("Unexpected provider/network request")


def test_original_web_model_and_voice_are_exact_defaults():
    assert flash.DEFAULT_PROVIDER == "gemini"
    assert flash.DEFAULT_MODEL == "gemini-3.8-flash-lite-tts"
    assert flash.FALLBACK_MODEL == "gemini-3.8-flash-tts"
    assert flash.DEFAULT_VOICE == "Kore"
    assert [s["model"] for s in flash.provider_specs()] == [
        "gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]
    assert [s["provider"] for s in flash.provider_specs()] == [
        "gemini_flash_lite_tts", "gemini_flash_tts"]


def test_web_chirp_cloud_is_only_third_fallback_and_kore_voice_name():
    specs=flash.provider_specs(enable_cloud=True)
    assert [(x["provider"],x["model"],x["voice"]) for x in specs] == [
        ("gemini_flash_lite_tts","gemini-3.8-flash-lite-tts","Kore"),
        ("gemini_flash_tts","gemini-3.8-flash-tts","Kore"),
        ("google_cloud_chirp3","chirp3-hd","en-US-Chirp3-HD-Kore"),
    ]
    with pytest.raises(flash.FlashTTSError):
        flash.provider_specs("")


def test_api_project_defaults_to_gemini_without_cloud_or_key_file(tmp_path):
    empty=tmp_path/"private"
    empty.mkdir()
    assert policy.selected_formal_provider({"MICROVID_CONFIG_DIR":str(empty)}) == "gemini"
    assert policy.require_formal_provider({"MICROVID_CONFIG_DIR":str(empty)}) == "gemini"
    assert policy.selected_formal_provider({
        "MICROVID_CONFIG_DIR":str(empty),
        "MICROGEN_FORMAL_TTS_PROVIDER":"google_cloud",
    }) == "google_cloud"
    for disabled in ("unconfigured","", "off"):
        assert policy.selected_formal_provider({
            "MICROVID_CONFIG_DIR":str(empty),
            "MICROGEN_FORMAL_TTS_PROVIDER":disabled,
        })=="unconfigured"


def test_parses_complete_wav_from_inline_model_response_not_legacy_pcm():
    class Obj:
        def __init__(self,**kwargs):
            self.__dict__.update(kwargs)
    sample=wav_data()
    r=Obj(candidates=[Obj(content=Obj(parts=[
        Obj(inline_data=Obj(data=sample))
    ]))])
    assert flash._response_wav(r)==sample
    r.candidates[0].content.parts[0].inline_data.data=base64.b64encode(sample).decode()
    assert flash._response_wav(r)==sample
    r.candidates[0].content.parts[0].inline_data.data=b"not WAV"
    with pytest.raises(flash.FlashTTSError):
        flash._response_wav(r)


def test_sentence_aware_chunking_and_pcm_wave_merge():
    chunks=flash._split_tts_text("First sentence. Second phrase here. Third.", max_chars=28)
    assert " ".join(chunks) == "First sentence. Second phrase here. Third."
    merged=flash._merge_wavs([wav_data(330),wav_data(440)])
    with wave.open(io.BytesIO(merged),"rb") as sound:
        assert sound.getnchannels()==1
        assert sound.getsampwidth()==2
        assert sound.getframerate()==24000
        assert sound.getnframes()==48000


def test_atomic_full_batch_gemini_lite_primary_never_enters_cloud(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    calls=[]
    def fake(text,spec):
        calls.append((text,spec["model"]))
        return wav_data(330)
    target=tmp_path/"complete"
    result=flash.render_batch(["Physics narration A.","Physics narration B."],
                              target,speak=fake)
    assert result["engine"]=="gemini_flash_lite_tts"
    assert result["model"]==flash.DEFAULT_MODEL
    assert result["voice"]=="Kore"
    assert not result["fallback_used"]
    assert result["publication_allowed"] is False
    assert [x[1] for x in calls]==[flash.DEFAULT_MODEL]*2
    assert len(list(target.glob("slide*.wav")))==2
    assert (target/flash.BATCH_RECEIPT).is_file()
    for row in result["slides"]:
        assert hashlib.sha256((target/row["wav_filename"]).read_bytes()).hexdigest()==row["wav_sha256"]


def test_primary_failure_regenerates_entire_batch_in_flash_not_mixed(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    calls=[]
    def fake(text,spec):
        calls.append((text,spec["model"]))
        if spec["model"]==flash.DEFAULT_MODEL and "B" in text:
            raise RuntimeError("mock primary outage")
        return wav_data(460 if spec["model"]==flash.FALLBACK_MODEL else 300)
    target=tmp_path/"complete"
    result=flash.render_batch(["A","B"],target,speak=fake)
    assert result["engine"]=="gemini_flash_tts"
    assert result["fallback_used"] is True
    assert result["fallback_mode"]=="whole_batch_single_voice"
    assert calls == [
        ("A",flash.DEFAULT_MODEL),("B",flash.DEFAULT_MODEL),
        ("A",flash.FALLBACK_MODEL),("B",flash.FALLBACK_MODEL),
    ]
    assert (target/"slide01.wav").read_bytes() == wav_data(460)
    assert (target/"slide02.wav").read_bytes() == wav_data(460)


def test_both_gemini_models_fail_and_cloud_is_disabled_by_default(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    attempts=[]
    def fake(text,spec):
        attempts.append(spec["provider"])
        raise RuntimeError("offline no provider")
    target=tmp_path/"uncommitted"
    with pytest.raises(flash.FlashTTSError,match="all authorized"):
        flash.render_batch(["One"],target,speak=fake)
    assert attempts==["gemini_flash_lite_tts","gemini_flash_tts"]
    assert not target.exists()
    assert not list(tmp_path.glob(".microgen-flash-batch-*"))


@pytest.mark.parametrize("flag,ceiling",[
    ("0","1000"),("1",""),("1","1"),("1","not-a-number"),
])
def test_cloud_fallback_refuses_missing_owner_budget_optin_before_api(
        tmp_path,monkeypatch,flag,ceiling):
    monkeypatch.setenv(flash.CLOUD_FALLBACK_ENV,flag)
    monkeypatch.setenv(flash.CLOUD_MAX_CHARS_ENV,ceiling)
    with pytest.raises(flash.FlashTTSError,match="not budget/owner authorized"):
        flash.render_batch(["longish sentence"],tmp_path/"would_bill",
                           allow_cloud=True,speak=never_network)
    assert not (tmp_path/"would_bill").exists()


def test_opted_in_cloud_only_after_both_gemini_fail_one_coherent_batch(
        tmp_path,monkeypatch):
    monkeypatch.setenv(flash.CLOUD_FALLBACK_ENV,"1")
    monkeypatch.setenv(flash.CLOUD_MAX_CHARS_ENV,"100")
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    calls=[]
    def fake(text,spec):
        calls.append((spec["provider"],spec["voice"]))
        if spec["provider"]!="google_cloud_chirp3":
            raise RuntimeError("Gemini unavailable")
        return wav_data(420)
    result=flash.render_batch(["A","B"],tmp_path/"cloud_only",
                              allow_cloud=True,speak=fake)
    assert result["engine"]=="google_cloud_chirp3"
    assert result["voice"]=="en-US-Chirp3-HD-Kore"
    assert [provider for provider,voice in calls] == [
        "gemini_flash_lite_tts","gemini_flash_tts",
        "google_cloud_chirp3","google_cloud_chirp3",
    ]
    assert all(voice=="en-US-Chirp3-HD-Kore" for provider,voice in calls
               if provider=="google_cloud_chirp3")
    assert result["publication_allowed"] is False


def test_broken_last_slide_aborts_full_batch_without_wav_publish(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    target=tmp_path/"should_not_exist"
    def fake(text,spec):
        if text=="broken":
            return b"broken"
        return wav_data()
    with pytest.raises(flash.FlashTTSError):
        flash.render_batch(["good","broken"],target,speak=fake)
    assert not target.exists()
    assert not list(tmp_path.glob(".microgen-flash-batch-*"))


def test_reject_existing_output_preserves_user_files(tmp_path):
    path=tmp_path/"keep"
    path.mkdir()
    (path/"my_file.txt").write_text("preserve")
    with pytest.raises(flash.FlashTTSError):
        flash.render_batch(["Hello."],path,speak=never_network)
    assert (path/"my_file.txt").read_text()=="preserve"


def test_api_module_direct_synthesize_routes_to_flash_and_writes_no_cloud(
        tmp_path,monkeypatch):
    import text_to_speech_v25 as api
    monkeypatch.setenv("MICROGEN_FORMAL_TTS_PROVIDER","gemini")
    monkeypatch.delenv(flash.CLOUD_FALLBACK_ENV,raising=False)
    monkeypatch.setattr(flash,"_speak",lambda text,spec:wav_data(400))
    out=tmp_path/"slide1.wav"
    provider=api.synthesize("The variable c. Next, integrate.",out)
    assert provider=="gemini_flash_lite_tts"
    assert out.read_bytes()==wav_data(400)
    assert list(tmp_path.glob("*.partial"))==[]


def test_explicit_cloud_legacy_path_unchanged_and_not_default(tmp_path,monkeypatch):
    import text_to_speech_v25 as api
    monkeypatch.setenv("MICROGEN_FORMAL_TTS_PROVIDER","google_cloud")
    calls=[]
    def fake(spoken,target):
        calls.append(spoken)
        target.write_bytes(wav_data())
        return "google_cloud_chirp3"
    monkeypatch.setattr(api,"_google_synthesize",fake)
    result=api.synthesize("Let x equal 2.",tmp_path/"explicit_cloud.wav")
    assert result=="google_cloud_chirp3"
    assert calls==["Let x equal 2."]
    assert (tmp_path/"explicit_cloud.wav").exists()


def test_google_genai_call_matches_web_tts_schema(monkeypatch):
    from types import SimpleNamespace as NS
    import gemini_keys
    calls=[]
    class FakeModels:
        def generate_content(self,**kwargs):
            calls.append(kwargs)
            return NS(candidates=[NS(content=NS(parts=[
                NS(inline_data=NS(data=wav_data()))
            ]))])
    def invoke(factory,callback,**kwargs):
        assert kwargs["max_retries"]==0
        return callback(NS(models=FakeModels()))
    monkeypatch.setattr(gemini_keys,"call_with_client_failover",invoke)
    monkeypatch.setattr(flash,"_load_gemini_keys_from_microvid",lambda:None)
    result=flash._gemini_api("Explain momentum.",flash.DEFAULT_MODEL,flash.DEFAULT_VOICE)
    assert result==wav_data()
    assert len(calls)==1
    assert calls[0]["model"]=="gemini-3.8-flash-lite-tts"
    assert calls[0]["contents"]==[{"role":"user","parts":[{
        "text":"Explain momentum.","speech_metadata":{"style":flash.STYLE},
    }]}]
    assert calls[0]["config"]=={
        "response_modalities":["AUDIO"],
        "speech_config":{"voice_config":{"voice":"Kore"}},
    }


def test_legacy_api_batch_entrypoint_uses_web_flash_default_without_cloud(
        tmp_path,monkeypatch):
    import os
    import text_to_speech_v25 as api
    from microgen_tts_provenance import verify_manifest
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MICROGEN_FORMAL_TTS_PROVIDER","gemini")
    monkeypatch.delenv(flash.CLOUD_FALLBACK_ENV,raising=False)
    items=[
        {"narration":"Momentum is conserved.","tts_text":"Momentum is conserved."},
        {"narration":"The acceleration is constant.","tts_text":"The acceleration is constant."},
    ]
    calls=[]
    def mocked_render(texts,directory,**kwargs):
        assert kwargs["voice"]=="Kore"
        assert kwargs["allow_cloud"] is False
        assert texts==[x["tts_text"] for x in items]
        calls.append(texts)
        directory.mkdir()
        for i in range(1,len(texts)+1):
            (directory/f"slide{i:02}.wav").write_bytes(wav_data(300+i*40))
        return {"model":flash.DEFAULT_MODEL,"engine":"gemini_flash_lite_tts",
                "voice":"Kore","slide_count":len(texts)}
    monkeypatch.setattr(flash,"render_batch",mocked_render)
    api._run_flash_batch(items)
    report=verify_manifest(tmp_path,[x["tts_text"] for x in items])
    assert report["provider"]=="gemini_flash_lite_tts"
    assert report["voice_name"]=="Kore"
    assert report["technical_provenance_verified"] is True
    assert report["listening_qa_verified"] is False
    assert (tmp_path/"slide1.wav").is_file()
    assert (tmp_path/"slide2.wav").is_file()
    assert (tmp_path/".microgen_tts_cache"/"slide1.json").is_file()
    api._run_flash_batch(items)
    assert len(calls)==1


def test_gemini_batch_rejects_broken_sound_before_replacing_existing_wavs(
        tmp_path,monkeypatch):
    import text_to_speech_v25 as api
    monkeypatch.chdir(tmp_path)
    prior=wav_data(500)
    (tmp_path/"slide1.wav").write_bytes(prior)
    def broken_output(texts,directory,**kwargs):
        directory.mkdir()
        (directory/"slide01.wav").write_bytes(wav_data())
        (directory/"slide02.wav").write_bytes(b"broken")
        return {"model":flash.DEFAULT_MODEL,"engine":"gemini_flash_lite_tts",
                "voice":"Kore","slide_count":2}
    monkeypatch.setattr(flash,"render_batch",broken_output)
    with pytest.raises(Exception):
        api._run_flash_batch([
            {"tts_text":"A clean start.","narration":"A clean start."},
            {"tts_text":"Another clean sentence.","narration":"Another clean sentence."},
        ])
    assert (tmp_path/"slide1.wav").read_bytes()==prior
    assert not (tmp_path/"slide2.wav").exists()
    assert not (tmp_path/".microgen_tts_provenance.json").exists()


def test_cloud_character_ceiling_counts_failed_attempts_without_retry_billing(
        tmp_path,monkeypatch):
    monkeypatch.setenv(flash.CLOUD_FALLBACK_ENV,"1")
    monkeypatch.setenv(flash.CLOUD_MAX_CHARS_ENV,"2")
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","3")
    attempts=[]
    def fail(text,spec):
        if spec["provider"]=="google_cloud_chirp3":
            attempts.append(len(text))
        raise RuntimeError("deliberately unavailable mock provider")
    with pytest.raises(flash.FlashTTSError):
        flash.render_batch(["X"],tmp_path/"no_paid_output",
                           allow_cloud=True,speak=fail)
    assert sum(attempts)<=2
    assert not (tmp_path/"no_paid_output").exists()
