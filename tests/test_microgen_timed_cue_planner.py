"""Offline regression for source-exact earlier slide slicing and cue planning."""
import json
from pathlib import Path

import fitz
import pytest

from test_microgen_timed_cue_tts import input_stage
from microgen_timed_cue_planner import (
    PLAN_FILE,CuePlanningError,prepare_slide_pages,propose_plan,
    write_verified_plan,sha,
)
from microgen_timed_cue_tts import _verified_plan


def test_slicing_creates_missing_before_tts_without_drift(tmp_path):
    stage=input_stage(tmp_path)
    pdf1=stage/"slide1.pdf"
    pdf2=stage/"slide2.pdf"
    old=sha(pdf1)
    pdf2.unlink()
    paths=prepare_slide_pages(stage)
    assert len(paths)==2
    assert sha(pdf1)==old
    assert pdf2.is_file()
    after=sha(pdf2)
    prepare_slide_pages(stage)
    assert sha(pdf2)==after


def test_existing_mismatched_slide_never_overwritten(tmp_path):
    stage=input_stage(tmp_path)
    target=stage/"slide2.pdf"
    with fitz.open() as doc:
        doc.new_page().insert_text((40,70),"Unrelated fake content")
        doc.save(target.with_name("other.pdf"))
    fake=target.with_name("other.pdf")
    target.write_bytes(fake.read_bytes())
    before=sha(target)
    with pytest.raises(CuePlanningError,match="differs from source"):
        prepare_slide_pages(stage)
    assert sha(target)==before


def test_deterministic_source_proposal_is_complete_and_non_billing(tmp_path):
    stage=input_stage(tmp_path)
    existing=stage/PLAN_FILE
    existing.unlink()
    proposal=propose_plan(stage)
    assert proposal["total_cues"]==4
    assert proposal["publication_allowed"] is False
    assert proposal["semantic_mapping_certified"] is False
    saved=write_verified_plan(stage)
    assert saved==existing
    verified,fragments=_verified_plan(stage)
    assert len(fragments)==4
    assert verified==proposal


def test_unsupported_narration_mapping_fails_without_invented_cues(tmp_path):
    stage=input_stage(tmp_path)
    (stage/PLAN_FILE).unlink()
    script=stage/"script_tts.json"
    raw=json.loads(script.read_text(encoding="utf8"))
    raw["slides"][1]["tts_text"]="A completely unrelated topic about the history of poetry."
    script.write_text(json.dumps(raw),encoding="utf8")
    with pytest.raises(CuePlanningError,match="insufficient|no anchored terms"):
        propose_plan(stage)
    assert not (stage/PLAN_FILE).exists()
