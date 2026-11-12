"""Standing owner authorization for finite private development and measured TTS.

No model, Cloud service or network calls. Real batch entrypoint and the
actual one-engine, source-PDF-bound cue TTS producer are exercised offline.
"""
from contextlib import nullcontext
import json
import os
from pathlib import Path
from unittest.mock import patch
import sys

import pytest

import microgen_batch as batch
import microgen_campaign_authorization as auth
import microgen_private_dev_policy as policy
import microgen_flash_tts as flash
from microgen_timed_cue_tts import produce_measured_cue_audio
from microgen_tts_provenance import verify_manifest
from test_microgen_timed_cue_tts import input_stage, sample_wav


@pytest.fixture
def private_scope(tmp_path, monkeypatch):
    with patch.dict(os.environ, {}, clear=False):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setattr(policy.socket, "gethostname", lambda: "HP")
        monkeypatch.setattr(auth, "_revision", lambda repo: "d" * 40)
        root = tmp_path / "MicroGen_AI_Checkpoints"
        root.mkdir()
        (root / policy.OWNER_CONSENT_FILE).write_text(
            json.dumps(policy.OWNER_CONSENT_RECORD), encoding="utf8")
        repo = root / "G2_SERWAY24_RC_CODE_20261107"
        repo.mkdir()
        (repo / "microgen_batch.py").write_text("verified production runner")
        (repo / "microgen_flash_tts.py").write_text("verified production TTS")
        source_root = tmp_path / "MyResearchSource"
        source = source_root / "2" / "2.5" / "source.pdf"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"%PDF-1.4\nprivate source test\n")
        work = root / "G2_NEW_PRIVATE_WORK"
        opts = dict(repo=repo, source_root=source_root, work_root=work,
                    source_file=source, stop_after="acceptance",
                    stage_retries=0, multipart=False)
        policy.freeze_standing_environment()
        yield opts


def test_automatic_private_owner_grant_ledger_and_resume(private_scope):
    opts = private_scope
    created = auth.authorize_or_resume(
        **opts, explicit_authorization=False,
        standing_private_development=True)
    assert created["status"] == "FROZEN_STANDING_PRIVATE_DEVELOPMENT_SCOPE"
    record_path = opts["work_root"] / auth.RECEIPT
    frozen = record_path.read_bytes()
    record = json.loads(frozen)
    assert record["publication_authorized"] is False
    assert record["scope"]["provider_environment"][
        "MICROGEN_TTS_ENABLE_CLOUD_FALLBACK"] == "1"
    assert record["scope"]["provider_environment"][
        "MICROGEN_TTS_VOICE"] == "Kore"
    assert record["scope"]["provider_environment"][
        "MICROGEN_TTS_CLOUD_FALLBACK_MAX_CHARACTERS"] == "40000"
    resumed = auth.authorize_or_resume(
        **opts, explicit_authorization=False,
        standing_private_development=True)
    assert resumed["status"] == "REUSED_EXACT_BOUNDED_PROVIDER_SCOPE"
    assert record_path.read_bytes() == frozen
    # New name cannot restart the same source+revision and incur new cost.
    new_name = opts | {
        "work_root": opts["work_root"].with_name("ANOTHER_BILLABLE_ATTEMPT")
    }
    with pytest.raises(auth.BoundedCampaignAuthorizationError,
                       match="STANDING_CAMPAIGN_ALREADY_USED"):
        auth.authorize_or_resume(
            **new_name, explicit_authorization=False,
            standing_private_development=True)
    assert not (new_name["work_root"] / auth.RECEIPT).exists()


def test_standing_mode_refuses_terminal_replay_or_modified_provider(private_scope):
    opts = private_scope
    auth.authorize_or_resume(**opts, explicit_authorization=False,
                             standing_private_development=True)
    stage = opts["work_root"] / "2.5"
    stage.mkdir()
    (stage / ".microgen_checkpoint.json").write_text(
        json.dumps({"last_error": {"stage": "tts", "type": "RuntimeError"}}))
    with pytest.raises(auth.BoundedCampaignAuthorizationError,
                       match="PRIOR_STAGE_FAILURE_HOLD"):
        auth.authorize_or_resume(
            **opts, explicit_authorization=False,
            standing_private_development=True)
    with patch.dict(os.environ, {"MICROGEN_TTS_VOICE": "OtherVoice"}):
        with pytest.raises(auth.BoundedCampaignAuthorizationError,
                           match="scope changed"):
            auth.authorize_or_resume(
                **opts, explicit_authorization=False,
                standing_private_development=True)


def test_missing_or_tampered_local_owner_consent_never_authorizes_costs(
    private_scope,
):
    opts=private_scope
    marker=opts["work_root"].parent / policy.OWNER_CONSENT_FILE
    marker.unlink()
    with pytest.raises(auth.BoundedCampaignAuthorizationError,
                       match="STANDING_PRIVATE_DEVELOPMENT_SCOPE_INVALID"):
        auth.authorize_or_resume(
            **opts, explicit_authorization=False,
            standing_private_development=True)
    assert not opts["work_root"].exists()
    marker.write_text('{"publication_allowed":true}', encoding="utf8")
    with pytest.raises(auth.BoundedCampaignAuthorizationError,
                       match="STANDING_PRIVATE_DEVELOPMENT_SCOPE_INVALID"):
        auth.authorize_or_resume(
            **opts, explicit_authorization=False,
            standing_private_development=True)
    assert not opts["work_root"].exists()


def test_host_scope_and_retry_budget_rejected_without_side_effects(private_scope):
    opts = private_scope
    assert policy.eligible_private_development(
        **{k: opts[k] for k in (
            "repo", "source_root", "work_root", "stop_after",
            "stage_retries", "multipart")})
    with patch.object(policy.socket, "gethostname", return_value="Dell-115"):
        with pytest.raises(auth.BoundedCampaignAuthorizationError,
                           match="STANDING_PRIVATE_DEVELOPMENT_SCOPE_INVALID"):
            auth.authorize_or_resume(
                **opts, explicit_authorization=False,
                standing_private_development=True)
    with pytest.raises(auth.BoundedCampaignAuthorizationError,
                       match="STANDING_PRIVATE_DEVELOPMENT_SCOPE_INVALID"):
        auth.authorize_or_resume(
            **(opts | {"stage_retries": 1}),
            explicit_authorization=False,
            standing_private_development=True)
    assert not opts["work_root"].exists()


def test_normal_batch_owner_grant_without_any_approval_flag(
    private_scope, monkeypatch,
):
    opts = private_scope
    argv = ["microgen_batch.py",
            "--repo", str(opts["repo"]),
            "--source-root", str(opts["source_root"]),
            "--work-root", str(opts["work_root"]),
            "--targets", "2.5", "--stop-after", "acceptance"]
    with patch.object(sys, "argv", argv), \
         patch.object(batch.quality, "require_scratch_space",
                      return_value={"free_gb": 20, "required_gb": 8}), \
         patch.object(batch, "resolve_docling_python",
                      return_value=sys.executable), \
         patch.object(batch, "preflight") as preflight, \
         patch.object(batch, "subchapter_ownership",
                      return_value=nullcontext(None)), \
         patch.object(batch, "process_one") as process:
        assert batch.main() == 0
        assert process.call_count == 1
        assert preflight.call_count == 1
    receipt = json.loads(
        (opts["work_root"] / auth.RECEIPT).read_text(encoding="utf8"))
    assert receipt["scope"]["stop_after"] == "acceptance"
    assert receipt["max_stage_retries"] == 0
    assert receipt["publication_authorized"] is False


def test_flash_3_8_primary_and_cloud_only_last_synthesized_fallback(
    tmp_path, monkeypatch,
):
    assert policy.PRIMARY_TTS_MODEL == flash.DEFAULT_MODEL
    assert policy.GEMINI_FALLBACK_TTS_MODEL == flash.FALLBACK_MODEL
    assert policy.DEFAULT_VOICE == flash.DEFAULT_VOICE == "Kore"
    assert policy.CLOUD_FALLBACK_PROVIDER == "google_cloud_chirp3"
    monkeypatch.setenv("MICROGEN_TIMED_CUES", "1")
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS", "1")
    monkeypatch.setenv("MICROGEN_TTS_ENABLE_CLOUD_FALLBACK", "1")
    monkeypatch.setenv("MICROGEN_TTS_CLOUD_FALLBACK_MAX_CHARACTERS", "40000")
    stage = input_stage(tmp_path)
    calls = []

    def synthesize(text, spec):
        calls.append((spec["provider"], spec["voice"]))
        if spec["provider"] != "google_cloud_chirp3":
            raise RuntimeError("Simulated Gemini outage")
        return sample_wav(text, spec)

    report = produce_measured_cue_audio(stage, speak=synthesize)
    assert report["provider"] == "google_cloud_chirp3"
    assert report["voice"] == "en-US-Chirp3-HD-Kore"
    assert calls[:2] == [
        ("gemini_flash_lite_tts", "Kore"),
        ("gemini_flash_tts", "Kore"),
    ]
    assert calls[2:] == [("google_cloud_chirp3", "en-US-Chirp3-HD-Kore")] * 4
    texts = json.loads((stage / "script_tts.json").read_text())["slides"]
    assert verify_manifest(
        stage, [t["tts_text"] for t in texts])["provider"] == "google_cloud_chirp3"


def test_insufficient_cloud_budget_never_blocks_authorized_gemini(tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS", "1")
    monkeypatch.setenv("MICROGEN_TTS_ENABLE_CLOUD_FALLBACK", "1")
    monkeypatch.setenv("MICROGEN_TTS_CLOUD_FALLBACK_MAX_CHARACTERS", "1")
    stage = input_stage(tmp_path)
    calls = []
    def synthesize(text, spec):
        calls.append(spec["provider"])
        return sample_wav(text,spec)
    report=produce_measured_cue_audio(stage,speak=synthesize)
    assert report["provider"]=="gemini_flash_lite_tts"
    assert calls==["gemini_flash_lite_tts"]*4
    assert (stage/"slide1.wav").is_file()


def test_malformed_cloud_fallback_budget_fails_before_any_paid_request(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("MICROGEN_TTS_ENABLE_CLOUD_FALLBACK", "1")
    monkeypatch.setenv("MICROGEN_TTS_CLOUD_FALLBACK_MAX_CHARACTERS", "unlimited")
    stage=input_stage(tmp_path)
    calls=[]
    with pytest.raises(Exception,match="finite source-bound budget"):
        produce_measured_cue_audio(stage,
            speak=lambda text,spec:calls.append(spec["provider"]))
    assert not calls



def test_normal_batch_exact_scope_resume_needs_no_second_approval(
    private_scope, monkeypatch,
):
    opts=private_scope
    argv=["microgen_batch.py","--repo",str(opts["repo"]),
          "--source-root",str(opts["source_root"]),
          "--work-root",str(opts["work_root"]),
          "--targets","2.5","--stop-after","acceptance"]
    for attempt in (1,2):
        with patch.object(sys,"argv",argv), \
             patch.object(batch.quality,"require_scratch_space",
                          return_value={"free_gb":20,"required_gb":8}), \
             patch.object(batch,"resolve_docling_python",
                          return_value=sys.executable), \
             patch.object(batch,"preflight"), \
             patch.object(batch,"subchapter_ownership",
                          return_value=nullcontext(None)), \
             patch.object(batch,"process_one") as dispatch:
            assert batch.main()==0
            dispatch.assert_called_once()
    receipt=opts["work_root"] / auth.RECEIPT
    assert receipt.is_file()
    assert len(list(
        (opts["work_root"].parent / policy.LEDGER_FOLDER).glob("*.json")
    ))==1
