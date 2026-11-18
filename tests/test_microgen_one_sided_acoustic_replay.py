"""Real private two-Gemini failed review, independent offline replay tests.
Fixtures retain source audio through same-device hardlinks; no paid calls.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import pytest

from microgen_one_sided_acoustic_replay import (
    find_source_identical_failed_review,replay_with_one_sided_rechecks,
    verify_one_sided_replay,OneSidedAcousticReplayError,RECEIPT,
)
from microgen_autonomous_acoustic_gate import _normalized
from microgen_verified_acoustic_replay import sha


@pytest.fixture
def campaign(tmp_path,monkeypatch):
    actual=Path(os.environ["LOCALAPPDATA"])/"MicroGen_AI_Checkpoints"/(
        "20261118_HP_G3_SERWAY27_TIMED_REPAIR_9B7_PRIVATE")/"2.7"
    if not actual.is_dir():
        pytest.skip("Real Serway 2.7 failed private acoustic review unavailable")
    root=tmp_path/"MicroGen_AI_Checkpoints"
    old=root/"prior-failed"/"2.7"
    new=root/"new-source-campaign"/"2.7"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    repo=Path(__file__).resolve().parents[1]
    for name in ["source.pdf","slides.pdf","script_tts.json",
                 "script.txt",".microgen_tts_provenance.json"]:
        for stage in (old,new):
            os.link(actual/name,stage/name)
    for n in range(1,22):
        for stage in (old,new):
            os.link(actual/f"slide{n}.wav",stage/f"slide{n}.wav")
    shutil.copy2(actual/"microgen_autonomous_acoustic_gate.py",
                 old/"microgen_autonomous_acoustic_gate.py")
    shutil.copy2(repo/"microgen_autonomous_acoustic_gate.py",
                 new/"microgen_autonomous_acoustic_gate.py")
    for pattern in (".microgen_acoustic_blocked_*.json",
                    ".microgen_private_acoustic_failed_*.json"):
        for source in actual.glob(pattern):
            shutil.copy2(source,old/source.name)
    revision="a"*40
    for directory,stamp in ((old.parent,"9b7b31eea04300463442a12fdc046f2f1fdb5a84"),
                            (new.parent,revision)):
        grant={
            "publication_authorized":False,
            "scope":{
                "host":"hp","source_sha256":sha(new/"source.pdf"),
                "work_root":str(directory),"stop_after":"acceptance",
                "code_revision":stamp
            }
        }
        (directory/".microgen_bounded_provider_authorization.json").write_text(
            json.dumps(grant),encoding="utf8")
        dest=directory/"2.7"
        (dest/".microgen_checkpoint.json").write_text(
            json.dumps({"package_commit":stamp,"completed":{"tts":"2026-11-18T07:00Z"}}),
            encoding="utf8")
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    return old,new


def test_real_failed_dual_gemini_trace_is_found_on_exactly_matching_pcm(campaign):
    old,new=campaign
    found=find_source_identical_failed_review(new,_normalized(new))
    assert found is not None
    assert found["old"]==old
    assert found["retakes"]==[(5,1)]
    assert found["models"]==("gemini-3.5-flash","gemini-3.8-flash")


def test_source_wav_hash_drift_blocks_historical_replay(campaign):
    old,new=campaign
    target=new/"slide7.wav"
    target.unlink()
    target.write_bytes(b"NEW DIFFERENT AUDIO")
    assert find_source_identical_failed_review(new,_normalized(new)) is None


def test_offline_fake_retake_strict_replay_acceptance_and_reverify(campaign):
    from microgen_autonomous_acoustic_gate import _verify
    old,new=campaign
    source=_normalized(new)
    calls=[]
    def supplier():
        def first(path):
            raise AssertionError("Original source-exact first model must never be rebilled")
        def second(path):
            slide=int(path.stem.removeprefix("slide"))
            calls.append(slide)
            assert slide==5
            return source[slide-1]  # SYNTHETIC! not an independent Gemini verdict
        return first,second,("gemini-3.5-flash","gemini-3.8-flash")
    replay=replay_with_one_sided_rechecks(new,source,provider_factory=supplier)
    assert replay is not None
    assert replay["report"]["review_required_slides"]==[]
    assert calls==[5]
    assert (new/RECEIPT).is_file()
    _verify(new,replay["report"],source)
    receipt={
        "slide_count":21,
        "recognition_models":list(replay["report"]["recognition_models"]),
        "repaired_audio_slides":0,
        "independent_report":replay["report"],
        "verified_one_sided_historical_asr":replay["evidence"],
    }
    verify_one_sided_replay(new,receipt)
    assert replay_with_one_sided_rechecks(
        new,source,provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("No provider needed after confirmed retake")
        )
    )["report"]["review_required_slides"]==[]


def test_uncertain_paid_retake_never_reissues_after_process_loss(campaign):
    old,new=campaign
    source=_normalized(new)
    calls=[]
    class InjectedProcessDeath(BaseException):pass
    def supplier():
        def first(path):raise AssertionError("No first reviewer")
        def second(path):
            calls.append(int(path.stem.removeprefix("slide")))
            raise InjectedProcessDeath("crash after paid request")
        return first,second,("gemini-3.5-flash","gemini-3.8-flash")
    with pytest.raises(InjectedProcessDeath):
        replay_with_one_sided_rechecks(new,source,provider_factory=supplier)
    assert calls==[5]
    before=(new/RECEIPT).read_bytes()
    with pytest.raises(OneSidedAcousticReplayError,match="UNCERTAIN_PAID"):
        replay_with_one_sided_rechecks(
            new,source,provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("Must not call provider")
            )
        )
    assert before==(new/RECEIPT).read_bytes()


@pytest.mark.parametrize("failure,expected",[
    ("UNCERTAIN_PAID_ONE_SIDED_ASR_HOLD: no trusted reply",
     "MGA-20261118-UNCERTAIN-ONE-SIDED-ASR"),
    ("ONE_SIDED_SENSITIVE_MATHEMATICS_HOLD: contrary retake",
     "MGA-20261118-ONE-SIDED-ASR-MATH-HOLD"),
    ("UNVERIFIABLE_RETAKE_RESERVATION_HOLD",
     "MGA-20261118-ONE-SIDED-ASR-GENERAL-HOLD"),
])
def test_executable_recovery_registry_prioritizes_specific_failure(failure,expected):
    from microgen_recovery_registry import classify_log_attempt
    repo=Path(__file__).resolve().parents[1]
    log=("Traceback (most recent call last):\n"
         "  File \"microgen_one_sided_acoustic_replay.py\", line 1\n"
         f"OneSidedAcousticReplayError: {failure}\n").encode()
    decision=classify_log_attempt("acoustic_qa",log,registry_folder=repo)
    assert decision["failure_id"]==expected
    assert decision["max_unmodified_retries"]==0
    assert decision["disposition"] in (
        "DETERMINISTIC_HOLD","UNRESOLVED_EXTERNAL_EFFECT_HOLD")


def test_single_slot_retake_does_not_trigger_paid_key_pool_fanout(monkeypatch):
    import sys
    import types
    import microgen_autonomous_acoustic_gate as gate
    monkeypatch.setitem(sys.modules,"gemini_keys",types.SimpleNamespace(
        get_gemini_api_keys=lambda:["offline-key-A","offline-key-B"]
    ))
    monkeypatch.setenv("MICROGEN_GEMINI_PREFERRED_KEY_INDEX","2")
    attempted=[]
    def fake_recognizer(key,*,model):
        def run(path):
            attempted.append((key,model))
            if key=="offline-key-B":
                raise RuntimeError("injected preferred key fails")
            return "Synthetic source blind transcript"
        return run
    monkeypatch.setattr(gate,"gemini_audio_recognizer",fake_recognizer)
    first,second,names=gate._providers(single_slot_only=True)
    with pytest.raises(gate.AutonomousAcousticError):
        second(Path("synthetic-slide.wav"))
    assert attempted==[("offline-key-B",names[1])]
    attempted.clear()
    _,second_normal,_=gate._providers()
    assert second_normal(Path("synthetic-slide.wav")).startswith("Synthetic")
    assert len(attempted)==2
    assert [x[0] for x in attempted]==["offline-key-B","offline-key-A"]


def test_prior_rejected_identical_paid_retake_never_rebilled_in_new_campaign(campaign):
    """Historical two-Gemini disagreement survives new SHA-pinned code revision."""
    old,new=campaign
    found=find_source_identical_failed_review(new,_normalized(new))
    assert found and found["retakes"]==[(5,1)]
    prior=new.parent.parent/"older-rejected-private"/"2.7"
    prior.mkdir(parents=True)
    owner={
        "publication_authorized":False,
        "scope":{"host":"hp","work_root":str(prior.parent),
                 "source_sha256":sha(new/"source.pdf")}
    }
    (prior.parent/".microgen_bounded_provider_authorization.json").write_text(
        json.dumps(owner),encoding="utf8")
    record={
        "schema_version":1,
        "status":"FINITE_ASR_RETAKE_STARTED",
        "publication_allowed":False,
        "source_binding":{
            "source_sha256":sha(new/"source.pdf"),
            "input_snapshot_sha256":found["trace"]["source_snapshot_sha256"],
            "original_private_trace_sha256":sha(found["trace_path"]),
            "old_campaign":found["old"].parent.name,
            "models":list(found["models"]),
            "retake_slides":[{"slide":5,"reviewer_index":1}],
        },
        "attempts":[{"slide":5,"reviewer_index":1,"status":"REJECTED",
                     "transcript":"Source-blind model omitted the operator"}],
    }
    (prior/RECEIPT).write_text(json.dumps(record),encoding="utf8")
    with pytest.raises(OneSidedAcousticReplayError,
                       match="HISTORICAL_IDENTICAL_SENSITIVE_RETAKE_HOLD"):
        replay_with_one_sided_rechecks(
            new,_normalized(new),
            provider_factory=lambda: (_ for _ in ()).throw(
                AssertionError("Repeated paid request must never be sent")))
    assert not (new/RECEIPT).exists()
