"""Normal-path, non-billable recovery of final learner reflection on quizzes.

Never fabricate a scientific source anchor, waive numerical checks, or treat
Gemini's refusal as success. The visible question + options are independently
validated at the voice preflight boundary.
"""
import json
import os
from pathlib import Path
import fitz
import pytest

from microgen_timed_cue_planner import (
    QUESTION_REFLECTION_ROLE, _pdf_text_blocks, _lexical_match,
    question_reflection_source_block, prepare_slide_pages,
    write_verified_plan, sha,
)
from microgen_timed_cue_tts import PLAN_FILE, CueTTSError, _verified_plan


REFLECTION = (
    "Think about how velocity and acceleration vectors relate to direction "
    "and speed before advancing."
)


def make_stage(tmp_path):
    stage=tmp_path/"source"
    stage.mkdir()
    pdf=fitz.open()
    page=pdf.new_page(width=700,height=420)
    for y,line in (
        (45,"Concept Check: Quick Quiz 2.6"),
        (95,"Question: Which one of the following statements is true?"),
        (145,"(a) If a car is traveling eastward, its acceleration must be eastward."),
        (195,"(b) If a car is slowing down, its acceleration must be negative."),
        (245,"(c) A particle with constant acceleration can never stop and stay stopped."),
    ):
        page.insert_text((25,y),line)
    pdf.save(stage/"slides.pdf")
    pdf.close()
    narration=(
        "Now consider this Concept Check from Quick Quiz 2 point 6. "
        "The question asks: Which one of the following statements is true? "
        "If a car is slowing down, its acceleration must be negative. "
        + REFLECTION
    )
    (stage/"script_tts.json").write_text(json.dumps({
        "slides":[{"slide":1,"narration":narration,"tts_text":narration}]
    }),encoding="utf8")
    prepare_slide_pages(stage)
    return stage


def no_gemini(*args):
    pytest.fail("Source-grounded quiz reflection must not call Gemini")


def test_real_quiz_reflection_runs_normal_planner_without_model(tmp_path):
    stage=make_stage(tmp_path)
    before={p.name:sha(p) for p in stage.iterdir() if p.is_file()}
    write_verified_plan(stage,semantic_resolver=no_gemini)
    plan,fragments=_verified_plan(stage)
    assert len(fragments)==4
    assert plan["semantic_assist_applied"] is False
    assert plan["total_cues"]==4
    context=plan["slides"][0]["cues"][-1]
    assert context["question_context_role"]==QUESTION_REFLECTION_ROLE
    assert "Which one" in context["pdf_text"]
    assert context["spoken_text"]==REFLECTION
    assert plan["publication_allowed"] is False
    assert {p.name:sha(p) for p in stage.iterdir()
            if p.is_file() and p.name in before}==before


@pytest.mark.parametrize("text",[
    "Think about how moonlight affects plant metabolism before advancing.",
    "Think about how acceleration equals 999 before advancing.",
    "Acceleration causes a new force to appear.",
    "Think about how velocity changes because of the moon.",
    "Think about how velocity and acceleration relate before advancing? ",
])
def test_unrelated_or_assertive_content_remains_unresolved(text,tmp_path):
    stage=make_stage(tmp_path)
    with fitz.open(stage/"slides.pdf") as doc:
        blocks=_pdf_text_blocks(doc[0])
    assert question_reflection_source_block(text,4,4,blocks) is None


def test_nonfinal_prompt_and_missing_quiz_options_never_auto_anchor(tmp_path):
    stage=make_stage(tmp_path)
    with fitz.open(stage/"slides.pdf") as doc:
        blocks=_pdf_text_blocks(doc[0])
    assert question_reflection_source_block(REFLECTION,3,4,blocks) is None
    assert question_reflection_source_block(REFLECTION,4,4,blocks[:3]) is None
    assert question_reflection_source_block(REFLECTION,4,4,blocks[1:]) is None
    assert question_reflection_source_block(REFLECTION,4,4,blocks + blocks[1:2]) is None


@pytest.mark.parametrize("tamper",["remove_role","wrong_role","other_bbox","other_label"])
def test_independent_voice_plan_preflight_rejects_forged_provenance(
        tmp_path,tamper):
    stage=make_stage(tmp_path)
    write_verified_plan(stage,semantic_resolver=no_gemini)
    plan_path=stage/PLAN_FILE
    plan=json.loads(plan_path.read_text(encoding="utf8"))
    last=plan["slides"][0]["cues"][-1]
    first=plan["slides"][0]["cues"][0]
    if tamper=="remove_role":
        last.pop("question_context_role")
    elif tamper=="wrong_role":
        last["question_context_role"]="trusted_without_evidence"
    elif tamper=="other_bbox":
        last["pdf_bbox"]=first["pdf_bbox"]
    else:
        last["pdf_text"]=first["pdf_text"]
    plan_path.write_text(json.dumps(plan),encoding="utf8")
    with pytest.raises(CueTTSError,
                       match="(reflection|grounded|Element)"):
        _verified_plan(stage)


@pytest.mark.skipif(not os.environ.get("MICROGEN_REAL_G3_SECTION26_STAGE"),
                    reason="Use genuine private section 2.6 source on HP only")
def test_authentic_section_26_slide10_clears_without_model(tmp_path):
    original=Path(os.environ["MICROGEN_REAL_G3_SECTION26_STAGE"])
    stage=tmp_path/"real_section_cue"
    stage.mkdir()
    with fitz.open(original/"slides.pdf") as deck:
        doc=fitz.open()
        doc.insert_pdf(deck,from_page=9,to_page=9)
        doc.save(stage/"slides.pdf")
        doc.close()
    row=json.loads((original/"script_tts.json").read_text(
        encoding="utf8"))["slides"][9]
    real_row={"slide":1,"narration":row["narration"],"tts_text":row["tts_text"]}
    (stage/"script_tts.json").write_text(
        json.dumps({"slides":[real_row]},ensure_ascii=False),encoding="utf8")
    prepare_slide_pages(stage)
    write_verified_plan(stage,semantic_resolver=no_gemini)
    report,cues=_verified_plan(stage)
    assert len(cues)==6
    assert report["slides"][0]["cues"][-1]["question_context_role"]==QUESTION_REFLECTION_ROLE
