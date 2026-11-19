"""One sensitive-model edit versus exact independent reviewer: finite recheck.

Includes the real HP Serway 2.7 SHA-bound failed dual Gemini transcripts.
All retakes in this offline test are synthetic, NOT new Gemini decisions.
"""
from __future__ import annotations
import os
from pathlib import Path
import pytest

from microgen_one_sided_acoustic_recheck import (
    source_exact_vs_one_sensitive,recheck_one_sided_sensitive
)


def test_one_source_exact_against_one_sensitive_edit_only():
    # One changed variable in a *long* otherwise exact lecture script;
    # a one-in-seven change in a short sentence must NOT qualify.
    short="Acceleration along the x axis equals zero."
    expect=("A particle is moving steadily in a laboratory frame with "
            "an initial velocity measured in meters per second and "
            "the motion is described by the following equation. "
            "The source diagram is measured against the same fixed coordinate "
            "system in each repeated experiment without introducing another force. "
            "Acceleration along the x axis equals zero.")
    dissent=expect.replace("equals zero","equals one")
    assert source_exact_vs_one_sensitive(expect,expect,dissent)==1
    assert source_exact_vs_one_sensitive(expect,dissent,expect)==0
    assert source_exact_vs_one_sensitive(expect,expect,expect) is None
    assert source_exact_vs_one_sensitive(
        short,short,short.replace("x axis","y axis")) is None
    assert source_exact_vs_one_sensitive(
        expect,expect,dissent.replace("x axis","y axis")) is None
    assert source_exact_vs_one_sensitive(
        expect,expect,dissent.replace("axis equals","axis does not equal")) is None
    assert source_exact_vs_one_sensitive(expect,expect,"[inaudible]") is None


def real_failure():
    from microgen_verified_acoustic_replay import valid_trace
    from microgen_autonomous_acoustic_gate import _normalized,_input_snapshot
    root=Path(os.environ.get("LOCALAPPDATA","/unavailable"))/"MicroGen_AI_Checkpoints"
    stage=root/"20261118_HP_G3_SERWAY27_TIMED_REPAIR_9B7_PRIVATE"/"2.7"
    if not stage.is_dir():
        pytest.skip("Owner private HP source not present")
    source=_normalized(stage)
    paths=list(stage.glob(".microgen_private_acoustic_failed_*.json"))
    if len(paths)!=1:pytest.skip("Exact one original failure trace required")
    models=("gemini-3.5-flash","gemini-3.8-flash")
    trace=valid_trace(paths[0],_input_snapshot(stage,len(source)),len(source),models)
    assert trace is not None
    assert trace["review_required_slides"]==[5,7]
    return stage,source,trace,models


def test_real_21_slide_failed_dual_model_replay_requires_only_two_rechecks():
    from microgen_autonomous_acoustic_gate import _transcripts,_verify
    stage,texts,trace,models=real_failure()
    # Exactly the authentic original independent transcripts are replayed.
    # At most 2 candidate retakes; the test callback is intentionally fake
    # and never creates a real acceptance receipt or billed Gemini request.
    transcripts=[r["original_blind_transcripts"] for r in trace["slides"]]
    hits=[]
    def recognizer(index):
        def run(wav):
            number=int(wav.stem.removeprefix("slide"))
            hits.append((index,number))
            if hits.count((index,number))>1:
                return texts[number-1]  # SYNTHETIC source-matching retake
            return transcripts[number-1][index]
        return run
    engines=(recognizer(0),recognizer(1))
    memo={}
    initial=_transcripts(stage,texts,engines,models,memo=memo)
    assert initial["review_required_slides"]==[5]
    result=recheck_one_sided_sensitive(stage,initial,texts,engines,memo)
    assert result["review_required_slides"]==[]
    assert result["independent_one_sided_sensitive_rechecks"]["resolved_slides"]==[5]
    assert len(hits)==43 # 42 original blind reads plus one source-risk retake
    assert [x for x in hits[42:]]==[(1,5)]
    _verify(stage,result,texts)
    assert not (stage/".microgen_autonomous_acoustic_qa.json").exists()


def test_real_failed_asr_remains_blocked_if_sensitive_mismatch_repeats():
    from microgen_autonomous_acoustic_gate import _transcripts
    stage,texts,trace,models=real_failure()
    originals=[r["original_blind_transcripts"] for r in trace["slides"]]
    def recognizer(index):
        def run(wav):
            return originals[int(wav.stem.removeprefix("slide"))-1][index]
        return run
    engines=(recognizer(0),recognizer(1))
    memo={}
    initial=_transcripts(stage,texts,engines,models,memo=memo)
    result=recheck_one_sided_sensitive(stage,initial,texts,engines,memo)
    assert result["review_required_slides"]==[5]
    assert result["independent_one_sided_sensitive_rechecks"]["resolved_slides"]==[]
    assert result["independent_one_sided_sensitive_rechecks"]["attempted_slides"]==[5]
