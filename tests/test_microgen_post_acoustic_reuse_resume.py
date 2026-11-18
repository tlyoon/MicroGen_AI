"""Production checkpoint recovery: no extra Gemini after true acoustic PASS."""
import json
import os
from pathlib import Path

import pytest

from microgen_post_acoustic_reuse_resume import (
    reconcile_verified_audio_receipt,
    PostAcousticResumeError,
)
from microgen_batch import stage_valid
from microgen_quality import dependency_fingerprint


RELEASE="bcf192d607b77a78ba126e99005c283935d6027c"
PATCH="a"*40
ALLOWED=[
    "microgen_batch.py",
    "microgen_verified_tts_reuse.py",
    "microgen_recovery_registry_v6.json",
    "microgen_post_acoustic_reuse_resume.py",
]


@pytest.fixture
def genuine_accepted_hp_stage(monkeypatch):
    root=Path(os.environ.get("LOCALAPPDATA","/missing"))/"MicroGen_AI_Checkpoints"
    stage=root/"20261118_HP_G3_SERWAY27_OPERATOR_BCF_PRIVATE"/"2.7"
    cp_path=stage/".microgen_checkpoint.json"
    if not cp_path.is_file():
        pytest.skip("Private real HP G3 source unavailable")
    cp=json.loads(cp_path.read_text(encoding="utf8"))
    if cp.get("package_commit")!=RELEASE:
        pytest.skip("Historical pre-migration checkpoint already advanced")
    assert cp["completed"]["acoustic_qa"]
    monkeypatch.setenv("MICROGEN_TIMED_CUES","1")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST","1")
    return root/"G2_SERWAY24_RC_CODE_20261107",stage,cp,Path(
        "G:/My Drive/Serway/Serway_1_7/2/2.7")


def test_real_21_slide_accepted_recovery_read_only(genuine_accepted_hp_stage):
    repo,stage,cp,dest=genuine_accepted_hp_stage
    before=(stage/".microgen_checkpoint.json").read_bytes()
    accepted=reconcile_verified_audio_receipt(
        repo,stage,cp,RELEASE,PATCH,stage_valid,
        dependency_fingerprint,dest,git_diff=lambda *args:ALLOWED)
    assert accepted["status"]==(
        "SOURCE_BOUND_ONE_CUE_AUDIO_CHECKPOINT_RECONCILED")
    assert set(accepted["fingerprints"])=={
        "science_qa","tts","acoustic_qa"}
    assert accepted["new_paid_requests"] is False
    assert accepted["publication_allowed"] is False
    assert (stage/".microgen_checkpoint.json").read_bytes()==before
    assert cp["dependency_fingerprints"]["tts"]==accepted[
        "fingerprints"]["tts"]


@pytest.mark.parametrize("diff",[
    ["gen_script_v13.py",*ALLOWED],
    ["microgen_tts_provenance.py",*ALLOWED],
    ["microgen_autonomous_science_qa.py",*ALLOWED],
    ["microgen_flash_tts.py",*ALLOWED],
    ["microgen_batch.py"],
    [],
    ["microgen_batch.py","microgen_batch.py"],
])
def test_source_or_policy_diff_forbids_rekey_before_checks(
        genuine_accepted_hp_stage,diff):
    repo,stage,cp,dest=genuine_accepted_hp_stage
    invoked=[]
    with pytest.raises(PostAcousticResumeError):
        reconcile_verified_audio_receipt(
            repo,stage,cp,RELEASE,PATCH,
            lambda *_:invoked.append("STAGE"),
            lambda *_:invoked.append("FINGERPRINT"),
            dest,git_diff=lambda *args:diff)
    assert invoked==[]


@pytest.mark.parametrize("corruption",[
    {"stage":"tts","type":"VerifiedTTSReuseError",
     "message":"Recovered WAV or cache integrity drift"},
    {"stage":"acoustic_qa","type":"InvalidError",
     "message":"Recovered WAV or cache integrity drift"},
    {"stage":"acoustic_qa","type":"VerifiedTTSReuseError",
     "message":"An unknown altered WAV"},
])
def test_no_checkpoint_migration_on_unrelated_failure(
        genuine_accepted_hp_stage,corruption):
    repo,stage,cp,dest=genuine_accepted_hp_stage
    cp["last_error"]=corruption
    accepted=reconcile_verified_audio_receipt(
        repo,stage,cp,RELEASE,PATCH,
        lambda *_:pytest.fail("No stage may be accepted"),
        lambda *_:pytest.fail("No fingerprints rekeyed"),
        dest,git_diff=lambda *_:pytest.fail("No git call allowed"))
    assert accepted is None


def test_failure_in_three_stage_preflight_keeps_old_checkpoint_intact(
        genuine_accepted_hp_stage):
    repo,stage,cp,dest=genuine_accepted_hp_stage
    before=json.dumps(cp,sort_keys=True)
    seen=[]
    def fails_at_tts(s,name,d):
        seen.append(name)
        return name!="tts"
    with pytest.raises(PostAcousticResumeError,match="Stale"):
        reconcile_verified_audio_receipt(
            repo,stage,cp,RELEASE,PATCH,fails_at_tts,
            lambda *args:"b"*64,dest,git_diff=lambda *_:ALLOWED)
    assert seen==["science_qa","tts"]
    assert json.dumps(cp,sort_keys=True)==before


def test_authorization_code_delta_returns_offline_only_never_paid(
        genuine_accepted_hp_stage,monkeypatch):
    from microgen_campaign_authorization import (
        _offline_verified_acoustic_continuation,
    )
    import microgen_post_acoustic_reuse_resume as module
    repo,stage,cp,dest=genuine_accepted_hp_stage
    root=stage.parent
    old=json.loads(
        (root/".microgen_bounded_provider_authorization.json"
         ).read_text(encoding="utf8"))["scope"]
    new={**old,"code_revision":PATCH}
    expected={"status":"SOURCE_BOUND_ONE_CUE_AUDIO_CHECKPOINT_RECONCILED",
              "source_accepted_reuse_receipt_sha256":"1"*64,
              "independent_acoustic_receipt_sha256":"2"*64}
    monkeypatch.setattr(
        module,"reconcile_verified_audio_receipt",
        lambda *args,**kwargs:expected)
    value=_offline_verified_acoustic_continuation(
        repo=repo,root=root,source_file=dest/"source.pdf",
        old_scope=old,proposed_scope=new,stage_retries=0)
    assert value["offline_continuation_only"] is True
    assert value["publication_authorized"] is False
    assert value["stage_retries"]==0
    assert json.loads((root/".microgen_bounded_provider_authorization.json"
        ).read_text())["scope"]==old
    for key,value in (
        ("provider_environment",{"MICROGEN_TTS_VOICE":"other"}),
        ("source_sha256","a"*64),
        ("host","other"),
        ("work_root","C:/stranger"),
        ("stop_after","published")):
        wrong=dict(new)
        wrong[key]=value
        assert _offline_verified_acoustic_continuation(
            repo=repo,root=root,source_file=dest/"source.pdf",
            old_scope=old,proposed_scope=wrong,stage_retries=0) is None


@pytest.mark.parametrize("stage_name",[
    "figure_mapping","slides","narration","science_qa","tts","acoustic_qa",
])
def test_offline_continuation_cannot_trigger_any_provider_stage(stage_name):
    from types import SimpleNamespace
    from microgen_batch import enforce_offline_provider_boundary
    with pytest.raises(RuntimeError,match="OFFLINE_ONLY_PROVIDER_STAGE_HOLD"):
        enforce_offline_provider_boundary(
            SimpleNamespace(offline_accepted_recovery_only=True),stage_name)
    assert enforce_offline_provider_boundary(
        SimpleNamespace(offline_accepted_recovery_only=False),stage_name) is None


@pytest.mark.parametrize("stage_name",[
    "figure_extraction","slide_slicing","video","acceptance",
])
def test_offline_continuation_permits_only_local_stages(stage_name):
    from types import SimpleNamespace
    from microgen_batch import enforce_offline_provider_boundary
    assert enforce_offline_provider_boundary(
        SimpleNamespace(offline_accepted_recovery_only=True),stage_name) is None
