"""Strictly bounded replay of previously obtained independent model evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from microgen_acoustic_math_transcript import canonical_math_transcript
from microgen_tts_acoustic_qa import mismatch_details
from microgen_verified_acoustic_replay import valid_trace, maybe_replay_verified_acoustic


@pytest.mark.parametrize("spoken,reviewer", [
    ("position ex at time tee equals b multiplied by tee cubed minus see multiplied by tee",
     "position, x of t, equal b multiplied by t cubed minus c multiplied by t"),
    ("position ex at time tee equals b multiplied by tee cubed minus see multiplied by tee",
     "position, x at time t, equals B multiplied by T cubed minus C multiplied by T"),
    ("acceleration ay sub ex of t", "acceleration a y sub x of t"),
])
def test_authentic_style_notation_equivalence_is_exact(spoken, reviewer):
    diff=mismatch_details(spoken,reviewer)
    assert diff["difference_fraction_upper_bound"] == 0, diff
    assert diff["sensitive_mismatches"] == 0


@pytest.mark.parametrize("spoken,wrong", [
    ("position ex at time tee equals b multiplied by tee cubed minus see multiplied by tee",
     "position x at time x equals b multiplied by t cubed minus c multiplied by t"),
    ("position ex at time tee equals b multiplied by tee cubed minus see multiplied by tee",
     "position x at time t equals b multiplied by t squared minus c multiplied by t"),
    ("position ex at time tee equals b multiplied by tee cubed minus see multiplied by tee",
     "position x at time t equals b multiplied by t cubed plus c multiplied by t"),
    ("position ex at time tee equals b multiplied by tee cubed minus see multiplied by tee",
     "position x at time t equals 4 multiplied by t cubed minus c multiplied by t"),
    ("position ex at time tee equals b multiplied by tee cubed minus see multiplied by tee",
     "position x at time t equals b multiplied by 4t cubed minus c multiplied by t"),
])
def test_changed_mathematics_never_passes(spoken, wrong):
    assert mismatch_details(spoken,wrong)["difference_fraction_upper_bound"]>0


def _trace(tmp_path: Path, *, changed=False):
    snap={"slide1.wav":"a"*64}
    expected="b"*64
    rows=[dict(slide=1,wav_sha256=snap["slide1.wav"],
               expected_spoken_sha256=expected,
               original_blind_transcripts=[
                   "The position x of t equals b t cubed minus c t.",
                   "The position x at time t equals b t cubed minus c t."],
               assessment="REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE",
               source_risk_codes=[])]
    if changed:
        rows[0]["wav_sha256"]="c"*64
    data=dict(schema_version=1,status="PRIVATE_FAILED_ASR_EVIDENCE_NOT_ACCEPTED",
              models=["gemini-a","gemini-b"],
              source_snapshot_sha256=snap,review_required_slides=[1],
              slides=rows,accepted_for_video=False,
              phonetic_accuracy_certified=False,publication_allowed=False)
    raw=json.dumps(data,sort_keys=True).encode()
    path=tmp_path/(".microgen_private_acoustic_failed_"+
                   hashlib.sha256(raw).hexdigest()[:20]+".json")
    path.write_bytes(raw)
    return path,snap


def test_saved_blind_trace_requires_exact_content_digest_and_wav_snapshot(tmp_path):
    path,snap=_trace(tmp_path)
    assert valid_trace(path,snap,1,("gemini-a","gemini-b"))
    assert valid_trace(path,snap,1,("gemini-a","gemini-c")) is None
    assert valid_trace(path,{**snap,"slide1.wav":"e"*64},1,
                       ("gemini-a","gemini-b")) is None
    path.write_bytes(path.read_bytes()+b" ")
    assert valid_trace(path,snap,1,("gemini-a","gemini-b")) is None


def test_saved_trace_rejects_changed_wav_even_if_checksum_renamed(tmp_path):
    path,snap=_trace(tmp_path,changed=True)
    assert valid_trace(path,snap,1,("gemini-a","gemini-b")) is None


def test_code_only_math_formatter_is_idempotent():
    for term in (
        "position x at time t equals b multiplied by t cubed",
        "position x of t equal b multiplied by tee cubed",
        "The tea is hot at time t.",
    ):
        once=canonical_math_transcript(term)
        assert canonical_math_transcript(once)==once


def test_direct_non_owner_replay_does_not_run_models(tmp_path):
    assert maybe_replay_verified_acoustic(tmp_path/"unrelated",["speech"]) is None
