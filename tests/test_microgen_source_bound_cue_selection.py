"""Real Serway 2.7 selected measured cue: source math preserved and fault injected."""
import json
import os
from pathlib import Path
import shutil
import tempfile

import pytest

from microgen_source_bound_cue_selection import choose_material_operator_cues
from microgen_autonomous_acoustic_gate import _normalized
from microgen_tts_acoustic_qa import audit_with_recognizer
from microgen_timed_acoustic_repair import (
    prepare_timed_repair,TimedAcousticRepairError,
)
from microgen_tts_provenance import verify_manifest
from microgen_timed_highlight_contract import inspect_timed_highlights


@pytest.fixture
def genuine_math_case():
    root=Path(os.environ.get("LOCALAPPDATA","/unavailable"))/"MicroGen_AI_Checkpoints"
    stage=root/"20261118_HP_G3_SERWAY27_TIMED_REPAIR_9B7_PRIVATE"/"2.7"
    paths=list(stage.glob(".microgen_private_acoustic_failed_*.json"))
    if len(paths)!=1:
        pytest.skip("Private HP two-Gemini original source-bound evidence absent")
    trace=json.loads(paths[0].read_text(encoding="utf8"))
    texts=_normalized(stage)
    def asr(index):
        return lambda wav:trace["slides"][
            int(wav.stem.removeprefix("slide"))-1
        ]["original_blind_transcripts"][index]
    report=audit_with_recognizer(
        stage,texts,asr(0),lambda text:text,
        independent_recognizer=asr(1),
        recognition_models=tuple(trace["models"]))
    return stage,texts,report


def test_real_21_slide_math_dissent_selects_only_one_of_88_cues(genuine_math_case):
    stage,texts,report=genuine_math_case
    assert report["review_required_slides"]==[5]
    assert choose_material_operator_cues(stage,report,texts)=={5:[2]}


def test_real_source_selected_cue_replay_preserves_other_pcm_and_timing(
        genuine_math_case):
    stage,texts,report=genuine_math_case
    selected=choose_material_operator_cues(stage,report,texts)
    old=inspect_timed_highlights(stage)
    records=verify_manifest(stage,texts)["slides"]
    submitted=[]
    with tempfile.TemporaryDirectory(prefix="microgen-real-cue-test-") as tmp:
        scratch=Path(tmp)
        def synthesize(text,target,record):
            # This is an OFFLINE PCM structural/transaction test only.
            # Never counted as fresh TTS, acoustic acceptance or new science.
            submitted.append((text,target.name))
            shutil.copy2(stage/"highlight_chunks"/"slide5_cue2.wav",target)
        result=prepare_timed_repair(
            stage,[5],texts,records,scratch,synthesize,
            lambda candidate,expected: candidate.is_file() and expected==texts[4],
            selected_cues=selected)
        assert result["cue_count"]==1
        assert len(submitted)==1
        assert submitted[0][1]=="timed_slide5_cue2.wav"
        assert len(result["chunks"])==1
        assert list(result["chunks"])==["highlight_chunks/slide5_cue2.wav"]
        assert result["selected_cues"]=={"5":[2]}
        current=json.loads(
            (stage/".microgen_timed_highlights.json").read_text())
        candidate=json.loads(result["manifest"].read_text())
        for idx in (0,2,3):
            assert (candidate["slides"][4]["cues"][idx]["audio_chunk_sha256"]
                    ==current["slides"][4]["cues"][idx]["audio_chunk_sha256"])
        assert old["slide_count"]==21
        assert result["prepared"].is_dir()
        assert inspect_timed_highlights(result["prepared"])["slide_count"]==21
    # Read-only source and original PCM untouched.
    assert inspect_timed_highlights(stage)["slide_count"]==21


@pytest.mark.parametrize("selection",[
    {5:[0]}, {5:[2,2]}, {5:[1,8]}, {5:[]}, {3:[2]},
    {5:[True]}, {5:[2],6:[2]},
])
def test_invalid_selection_blocks_before_any_paid_synthesis(
        genuine_math_case,selection):
    stage,texts,_=genuine_math_case
    records=verify_manifest(stage,texts)["slides"]
    sent=[]
    with tempfile.TemporaryDirectory(prefix="microgen-cue-invalid-") as tmp:
        with pytest.raises(TimedAcousticRepairError):
            prepare_timed_repair(
                stage,[5],texts,records,Path(tmp),
                lambda *_:sent.append(1),
                lambda *_:True,selected_cues=selection)
    assert sent==[]


def test_candidate_rejected_does_not_modify_real_source(
        genuine_math_case):
    stage,texts,report=genuine_math_case
    records=verify_manifest(stage,texts)["slides"]
    selected=choose_material_operator_cues(stage,report,texts)
    from hashlib import sha256
    original=sha256((stage/"slide5.wav").read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="microgen-cue-rejected-") as tmp:
        def offline_copy(text,target,record):
            shutil.copy2(stage/"highlight_chunks"/"slide5_cue2.wav",target)
        with pytest.raises(TimedAcousticRepairError,match="reviewers rejected"):
            prepare_timed_repair(
                stage,[5],texts,records,Path(tmp),offline_copy,
                lambda *_:False,selected_cues=selected)
    assert sha256((stage/"slide5.wav").read_bytes()).hexdigest()==original


def test_wrong_or_unconfirmed_math_operator_not_auto_selected(genuine_math_case):
    stage,texts,report=genuine_math_case
    copied=json.loads(json.dumps(report))
    copied["slides"][4]["transcripts"][1]=texts[4].replace(
        "divided by","multiplied by")
    assert choose_material_operator_cues(stage,copied,texts)=={}
