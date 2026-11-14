"""Regression for exact original-PDF numeric context immediately above a heading.

Source-free synthetic physics text; no Gemini calls; numeric, lexical, quote
and PDF geometry validators are NEVER waived.
"""
import copy
import json
from pathlib import Path
import fitz
import pytest
from microgen_cue_semantic_mapping import (
    SemanticMappingError, repair_preceding_numeric_context_heading,
    validate_matches,
)

BLOCKS = [
    ([35, 30, 590, 90],
     "Problem: A moving particle has a time interval from t = 0 to t = 2.0 s.",
     set()),
    ([35, 115, 300, 138], "Evaluate Velocities:", set()),
    ([35, 150, 550, 178], "The velocity is 40 metres per second.", set()),
]
CUE = "To evaluate velocities across the interval from t equals 0 to t equals 2.0 seconds."
MISSING = [(1, CUE)]
WRONG = [{"cue": 1, "block": 2, "quote": "Evaluate Velocities:"}]


def test_exact_adjacent_source_time_values_recover_heading_without_new_text():
    saved=copy.deepcopy(WRONG)
    with pytest.raises(SemanticMappingError,match="Numerical claim"):
        validate_matches(saved,MISSING,BLOCKS)
    fixed=repair_preceding_numeric_context_heading(saved,MISSING,BLOCKS)
    assert fixed == [{"cue": 1, "blocks": [1, 2],
                      "quotes": [BLOCKS[0][1], "Evaluate Velocities:"]}]
    assert validate_matches(fixed,MISSING,BLOCKS)[1][0]==(0,1)
    assert saved==WRONG


@pytest.mark.parametrize("spoken,source,heading,quote", [
    ("Evaluate velocities at t equals 0 only.",
     BLOCKS[0][1], "Evaluate Velocities:", "Evaluate Velocities:"),
    ("Evaluate velocities from x equals 0 to x equals 2.0 seconds.",
     BLOCKS[0][1], "Evaluate Velocities:", "Evaluate Velocities:"),
    ("Compare displacement from t equals 0 to t equals 2.0 seconds.",
     BLOCKS[0][1], "Evaluate Velocities:", "Evaluate Velocities:"),
    ("Evaluate velocities from t equals 0 to t equals 2.00 seconds.",
     BLOCKS[0][1], "Evaluate Velocities:", "Evaluate Velocities:"),
    (CUE, "Problem: Use t = 0 for the experiment.",
     "Evaluate Velocities:", "Evaluate Velocities:"),
    (CUE, BLOCKS[0][1], "Evaluate Velocity", "Evaluate Velocity"),
    (CUE, BLOCKS[0][1], "Evaluate Velocities:", "Invented Heading:"),
])
def test_unverified_context_does_not_recover(spoken,source,heading,quote):
    blocks=[
        (BLOCKS[0][0],source,set()),
        (BLOCKS[1][0],heading,set()),
        BLOCKS[2],
    ]
    wrong=[{"cue":1,"block":2,"quote":quote}]
    assert repair_preceding_numeric_context_heading(
        wrong,[(1,spoken)],blocks)==wrong


def test_duplicate_heading_cannot_choose_which_problem_statement():
    blocks=BLOCKS+[
        ([35,200,330,225],"Evaluate Velocities:",set())]
    assert repair_preceding_numeric_context_heading(
        WRONG,MISSING,blocks)==WRONG


def test_already_multi_block_source_citation_is_not_edited():
    multi=[{"cue":1,"blocks":[1,2],
            "quotes":[BLOCKS[0][1],BLOCKS[1][1]]}]
    assert repair_preceding_numeric_context_heading(
        multi,MISSING,BLOCKS)==multi


def test_normal_timed_cue_planner_rechecks_real_pdf_geometry(
    tmp_path,monkeypatch,
):
    import microgen_timed_cue_planner as planner
    stage=tmp_path/"2.5"
    stage.mkdir()
    with fitz.open() as pdf:
        page=pdf.new_page(width=650,height=410)
        page.insert_textbox(fitz.Rect(35,35,605,100),BLOCKS[0][1],
                            fontsize=12)
        page.insert_text((35,144),"Evaluate Velocities:",fontsize=12)
        page.insert_text((35,195),"Other relevant discussion follows.",fontsize=12)
        pdf.save(stage/"slides.pdf")
    (stage/"script_tts.json").write_text(
        json.dumps({"slides":[{"slide":1,"narration":CUE,"tts_text":CUE}]}),
        encoding="utf8")
    planner.prepare_slide_pages(stage)
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES","1")
    monkeypatch.setattr(planner,"_lexical_match",
        lambda slide_no,units,blocks,allow_unanchored=False:
        ([None],[(1,CUE)]))
    def source_only_model(slide_no,missing,blocks):
        assert slide_no==1 and missing==MISSING
        candidates=[(i,b) for i,b in enumerate(blocks,1)
                    if b[1].strip()=="Evaluate Velocities:"]
        assert len(candidates)==1
        return [{"cue":1,"block":candidates[0][0],
                 "quote":"Evaluate Velocities:"}]
    plan=planner.propose_plan(stage,semantic_resolver=source_only_model)
    assert plan["total_cues"]==1
    actual=plan["slides"][0]["cues"][0]
    assert len(actual["pdf_bboxes"])==2
    assert len(actual["semantic_source_quotes"])==2
    assert "t = 2.0 s" in actual["pdf_text"]
    assert actual["semantic_source_quotes"][1]=="Evaluate Velocities:"
