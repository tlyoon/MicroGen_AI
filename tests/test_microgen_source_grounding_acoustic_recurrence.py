"""Normal-path prevention of sparse title and math-coordinate ASR false alarms.

No provider requests, private source, audio inference or release waivers.
"""
import json
from unittest.mock import patch

import fitz
import pytest

from microgen_timed_cue_planner import (
    _lexical_match, prepare_slide_pages, propose_plan,
    write_verified_plan, salient,
)
from microgen_timed_cue_tts import _verified_plan
from microgen_tts_acoustic_qa import mismatch_details
from microgen_autonomous_acoustic_gate import _classify_review_blocker


def _title_stage(tmp_path, phrase):
    doc = fitz.open()
    slide = doc.new_page()
    slide.insert_text((72, 72), "2.5 Geometrical", fontsize=16)
    doc.save(tmp_path / "slides.pdf")
    doc.close()
    (tmp_path / "script_tts.json").write_text(json.dumps({
        "slides": [{"slide": 1, "tts_text": phrase}]
    }), encoding="utf8")
    prepare_slide_pages(tmp_path)
    return tmp_path


def test_one_term_verbatim_numbered_title_is_source_grounded_in_normal_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "0")
    stage = _title_stage(tmp_path, "2.5 Geometrical.")
    proposal = propose_plan(stage)
    assert proposal["total_cues"] == 1
    assert proposal["planning_method"] == "source_pdf_overlap_conservative"
    write_verified_plan(stage)
    verified, fragments = _verified_plan(stage)
    assert verified["total_cues"] == 1
    assert fragments == ["2.5 Geometrical."]


def test_single_block_does_not_admit_new_numerical_claim(tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "0")
    stage = _title_stage(tmp_path, "2.5 Geometrical; claim of 7 additional results.")
    from microgen_timed_cue_planner import CuePlanningError
    with pytest.raises(CuePlanningError, match="insufficient"):
        propose_plan(stage)


def test_multiblock_or_paraphrased_one_word_cue_not_silently_matched():
    one = ([10.,20.,200.,45.], "2.5 Geometrical", salient("2.5 Geometrical"))
    other = ([10.,55.,200.,80.], "Different illustrative topic", salient("Different illustrative topic"))
    spoken = "2.5 Geometrical."
    cues, missing = _lexical_match(1, [spoken], [one, other], allow_unanchored=True)
    assert cues == [None]
    assert missing == [(1, spoken)]
    cues, missing = _lexical_match(1, ["2.5 We study something else."], [one],
                                   allow_unanchored=True)
    assert missing


def test_narration_generation_prompt_prevents_unanchored_paraphrase():
    import gen_script_v13 as narration
    with patch.object(narration, "_read_prompt", return_value="fixture"), \
         patch.object(narration, "_available_figures", return_value=[]):
        prompt = narration._compose_prompt(
            [{"id": "slide_01", "title": "Example", "text": "Visible example"}],
            [{"id": "source1", "page": 1, "text": "Original source"}],
        )
    assert "SOURCE-ANCHORED TIMED NARRATION" in prompt
    assert "two distinctive" in prompt
    assert "mathematical" in prompt
    assert "downstream offline grounding" in prompt


@pytest.mark.parametrize("expected,heard", [
    ("Position ex of tee changes.", "Position X of T changes."),
    ("Position why of tee changes.", "Position y of t changes."),
    ("The ex of tee value rises.", "The x of tee value rises."),
])
def test_coordinate_time_asr_homophone_spelling_is_not_a_tts_defect(expected, heard):
    match = mismatch_details(expected, heard)
    assert match["difference_fraction_upper_bound"] == 0
    assert match["sensitive_mismatches"] == 0


@pytest.mark.parametrize("expected,heard", [
    ("The why axis increases.", "The yay axis increases."),
    ("The value is see.", "The value is circa."),
    ("Position ex of tee is positive.", "Position x of T is negative."),
    ("The t variable is positive.", "The tee variable is positive."),
])
def test_genuine_sensitive_or_out_of_scope_differences_remain_visible(expected, heard):
    assert mismatch_details(expected, heard)["difference_fraction_upper_bound"] > 0


def test_source_math_risk_stays_on_independent_hold_not_waived():
    review = {"slides": [{
        "slide": 1, "assessment": "REVIEW_REQUIRED_SOURCE_PRONUNCIATION_RISK",
        "source_pronunciation_risks": [{"code": "coordinate_of_time"}]
    }], "review_required_slides": [1], "unavailable_recognizer_passes": []}
    classification = _classify_review_blocker(review)
    assert classification["root_cause_family"] == "SOURCE_PRONUNCIATION_RISK_HOLD"
    assert not classification["safe_auto_repair"]
