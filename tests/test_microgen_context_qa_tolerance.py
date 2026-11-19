"""Meaning-first QA: harmless variation passes; wrong science/math still blocks."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile

import pytest

import microgen_autonomous_science_qa as sq
from microgen_context_qa_tolerance import (
    canonical_equivalent_text,provably_minor_scientific_issue,
    reclassify_proven_minor_scientific_issues,CONTRACT_VERSION,
)
from microgen_tts_acoustic_qa import mismatch_details
from test_microgen_autonomous_science_qa import make_stage,approved
from test_microgen_tts_acoustic_qa import build_verified,normalize
from microgen_tts_acoustic_qa import audit_with_recognizer


@pytest.mark.parametrize("source,observed",[
    ("multiply by", "multiplied by"),
    ("divided by","divide by"),
    ("is equal to","equals"),
    ("the diagram shows","the figure shows"),
    ("we see that","we observe that"),
    ("metres","meters"),
    ("therefore","thus"),
])
def test_minor_context_phrase_equivalence(source,observed):
    assert canonical_equivalent_text(
        source,nontechnical=True)==canonical_equivalent_text(
        observed,nontechnical=True)


@pytest.mark.parametrize("source,observed",[
    ("v divided by t", "v t"),
    ("v divided by t", "v multiplied by t"),
    ("the particle accelerates", "the particle decelerates"),
    ("velocity equals 5", "velocity equals 50"),
    ("positive x", "negative x"),
    ("force is not constant", "force is constant"),
    ("the x component", "the y component"),
    ("distance in meters", "distance in seconds"),
])
def test_math_and_scientific_contradictions_cannot_normalize(source,observed):
    assert canonical_equivalent_text(
        source,nontechnical=True)!=canonical_equivalent_text(
        observed,nontechnical=True)


def test_actual_scientific_stage_downgrades_minor_reported_error(tmp_path):
    stage=make_stage(tmp_path)
    item=json.loads((stage/"script_tts.json").read_text())
    item["slides"][0]["narration"]=item["slides"][0]["narration"].replace(
        "metres","meters")
    item["slides"][0]["tts_text"]=item["slides"][0]["narration"]
    (stage/"script_tts.json").write_text(json.dumps(item),encoding="utf8")
    script=(stage/"script.txt").read_text()
    (stage/"script.txt").write_text(script.replace("metres","meters"))
    original=sq._inputs(stage)
    issue={"field":"narration",
           "observed_quote":"The velocity is ten meters per second",
           "source_quote":"The velocity is ten metres per second",
           "suggested_replacement":"The velocity is ten metres per second"}
    row={"slide":1,"status":"error","issues":[issue]}
    result=sq.audit_stage(stage,reviewer=lambda *_:{"reviews":[row,approved(2)]})
    assert result["status"]=="SOURCE_GROUNDED_MODEL_SCREEN_PASSED"
    assert result["minor_meaning_preserving_advisory_slides"]==[1]
    assert result["advisory_slide_count"]==1
    assert result["qa_meaning_tolerance_contract"]==CONTRACT_VERSION
    assert sq._inputs(stage)==original
    assert sq.verify_receipt(stage)["slide_count"]==2


@pytest.mark.parametrize("observed,cited",[
    ("The velocity is five metres per second",
     "The velocity is ten metres per second"),
    ("The velocity is ten seconds",
     "The velocity is ten metres per second"),
    ("The velocity is not ten metres per second",
     "The velocity is ten metres per second"),
])
def test_source_bound_science_core_error_never_downgraded(observed,cited):
    issue={"field":"narration","observed_quote":observed,
           "source_quote":cited,"suggested_replacement":""}
    assert not provably_minor_scientific_issue(
        issue,cited,observed,observed)
    assert reclassify_proven_minor_scientific_issues(
        [{"slide":1,"status":"error","issues":[issue]}],
        [cited],["Velocity"],[observed])[0][0]["status"]=="error"


def test_no_grounding_or_mixed_safety_issue_can_be_waived():
    good={"field":"narration",
          "observed_quote":"The velocity is ten meters per second",
          "source_quote":"The velocity is ten metres per second",
          "suggested_replacement":""}
    bad=dict(good,observed_quote="The velocity is five meters per second")
    rows=[{"slide":1,"status":"error","issues":[good,bad]}]
    new,downgraded=reclassify_proven_minor_scientific_issues(
        rows,["The velocity is ten metres per second"],
        ["Velocity"],["The velocity is ten meters per second"])
    assert new[0]["status"]=="error"
    assert downgraded==[]


def test_acoustic_equivalent_math_inflection_without_false_repair(tmp_path):
    expect="The final velocity is multiplied by the time and equals ten meters per second."
    with tempfile.TemporaryDirectory() as directory:
        stage=Path(directory)
        build_verified(stage,[expect])
        same="The final velocity is multiply by the time and is equal to ten metres per second."
        report=audit_with_recognizer(
            stage,[expect],lambda _:expect,normalize,
            independent_recognizer=lambda _:same)
        assert report["review_required_slides"]==[]
        assert report["slides"][0]["assessment"]=="ASR_SCREEN_PASS_LISTENING_REQUIRED"


@pytest.mark.parametrize("heard",[
    "The acceleration equals velocity time minus zero.",
    "The acceleration equals velocity multiplied by time minus zero.",
    "The acceleration equals negative velocity divided by time minus zero.",
])
def test_acoustic_missing_operator_or_wrong_sign_still_blocks(tmp_path,heard):
    expect="The acceleration equals velocity divided by time minus zero."
    with tempfile.TemporaryDirectory() as directory:
        stage=Path(directory)
        build_verified(stage,[expect])
        report=audit_with_recognizer(
            stage,[expect],lambda _:expect,normalize,
            independent_recognizer=lambda _:heard)
        assert report["review_required_slides"]==[1]


def test_real_hp_serway_saved_gemini_variants_separate_minor_from_material():
    root=Path(os.environ.get("LOCALAPPDATA","/unavailable"))/"MicroGen_AI_Checkpoints"
    stage=root/"20261118_HP_G3_SERWAY27_TIMED_REPAIR_9B7_PRIVATE"/"2.7"
    path=list(stage.glob(".microgen_private_acoustic_failed_*.json"))
    if len(path)!=1:
        pytest.skip("Private real Gemini source-bound historical fixture absent")
    from microgen_autonomous_acoustic_gate import _normalized
    data=json.loads(path[0].read_text(encoding="utf8"))
    texts=_normalized(stage)
    original=data["slides"]
    assert mismatch_details(
        texts[6],original[6]["original_blind_transcripts"][1])[
        "sensitive_mismatches"]==0
    assert mismatch_details(
        texts[4],original[4]["original_blind_transcripts"][1])[
        "sensitive_mismatches"]>=1


def test_live_registry_has_real_safety_handler_and_no_unbounded_retry():
    from microgen_recovery_registry import classify_log_attempt,load_registry
    repo=Path(__file__).resolve().parents[1]
    recovered=classify_log_attempt(
        "science_qa",
        b"Traceback (most recent call last):\n"
        b"ScienceQAError: Unsupported or ungrounded scientific correction\n",
        registry_folder=repo)
    assert recovered is not None
    assert recovered["failure_id"]=="MGA-20261118-MEANING-PRESERVING-QA"
    assert recovered["max_unmodified_retries"]==0
    acoustic=classify_log_attempt(
        "acoustic_qa",
        b"Traceback (most recent call last):\n"
        b"OneSidedAcousticReplayError: "
        b"HISTORICAL_IDENTICAL_SENSITIVE_RETAKE_HOLD\n",
        registry_folder=repo)
    assert acoustic is not None
    assert acoustic["failure_id"]=="MGA-20261118-IDENTICAL-PAID-ASR-REJECTION"
    assert acoustic["max_unmodified_retries"]==0
