"""Fail-closed tests for source-bound full-lesson offline word cue proposals."""
import json
from pathlib import Path
import pytest
from microgen_full17_provisional_cues import prepare_full17_cues,WholeLectureError

def test_missing_original_evidence_is_not_accepted(tmp_path):
    with pytest.raises((FileNotFoundError,WholeLectureError)):
        prepare_full17_cues(tmp_path/"missing",tmp_path/"asr.json",tmp_path/"cues.json")
    assert not (tmp_path/"cues.json").exists()

@pytest.mark.parametrize("confidence",[0,.5,1.1,-1])
def test_confidence_floor_must_be_conservative(tmp_path,confidence):
    with pytest.raises((FileNotFoundError,WholeLectureError)):
        prepare_full17_cues(tmp_path/"missing",tmp_path/"asr.json",
                            tmp_path/"cues.json",minimum_confidence=confidence)
    assert not (tmp_path/"cues.json").exists()

def test_existing_output_cannot_be_overwritten(tmp_path):
    out=tmp_path/"report.json";out.write_text("original")
    with pytest.raises((FileNotFoundError,WholeLectureError)):
        prepare_full17_cues(tmp_path/"missing",tmp_path/"asr.json",out)
    assert out.read_text()=="original"
