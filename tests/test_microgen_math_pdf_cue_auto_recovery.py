"""Real-path source-PDF mathematical cue recovery; no model calls.

Correctly printed math may contain few/no 4-letter words, so a lexical-only
filter must not throw it away. Deterministic auto-match is intentionally
restricted to unique complete literal source evidence.
"""
import json

import fitz
import pytest

from microgen_cue_semantic_mapping import exact_math_source_block
from microgen_timed_cue_planner import (
    _lexical_match, _pdf_text_blocks, prepare_slide_pages,
    write_verified_plan, CuePlanningError, propose_plan,
)
from microgen_timed_cue_tts import _verified_plan


def source_math_block(formula, box=(25., 30., 310., 60.)):
    from microgen_timed_cue_planner import salient
    return (list(box), formula, salient(formula))


def test_math_only_pdf_text_is_kept_and_page_counter_is_excluded():
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((45, 45), "13 / 17", fontsize=11)
    page.insert_text((45, 90), "vxi = 40 -5(0)2 = 40 m/s, vxf = 40 -5(2)2 = 20 m/s",
                     fontsize=10)
    retained = _pdf_text_blocks(page)
    assert len(retained) == 1
    assert "vxf" in retained[0][1]
    assert "20 m/s" in retained[0][1]
    pdf.close()


def test_initial_final_computation_automatically_maps_exact_unique_pdf_block():
    spoken = ("Evaluating initial velocity at 40 meters per second and final "
              "velocity at 2.0 seconds gives 20 meters per second.")
    blocks = [
        source_math_block("Given v = 40 -5t2 at t = 2.0 s"),
        source_math_block("vxi = 40 -5(0)2 = 40 m/s; vxf = 40 -5(2.0)2 = 20 m/s"),
        source_math_block("Average acceleration is the slope of velocity"),
    ]
    assert exact_math_source_block(spoken, blocks) == 1
    cues, unresolved = _lexical_match(3, [spoken], blocks, allow_unanchored=True)
    assert unresolved == []
    assert cues[0]["pdf_text"] == blocks[1][1]


def test_limit_sign_and_variable_have_two_exact_source_anchors():
    spoken = ("Dividing by delta t and taking the limit as delta t approaches zero "
              "gives a sub x equals negative 10 t.")
    blocks = [
        source_math_block("vxf = 40 - 5(t+Delta t)2 = 40 - 5t2 -10t Delta t"),
        source_math_block("Take the limit as Delta t approaches 0"),
        source_math_block("Δt→0(-10t -5 Δt) = −10t"),
        source_math_block("At t = 2, ax = -10(2) = -20 m/s2"),
    ]
    assert exact_math_source_block(spoken, blocks) == 2
    cues, missing = _lexical_match(4, [spoken], blocks, allow_unanchored=True)
    assert missing == []
    assert cues[0]["pdf_text"] == blocks[2][1]


def test_ambiguous_or_inaccurate_math_is_not_auto_recovered():
    spoken = ("The initial velocity of 40 meters per second gives a final "
              "velocity of 20 meters per second at 2 seconds.")
    correct = source_math_block("vxi = 40 m/s, vxf = 20 m/s at t = 2 s")
    assert exact_math_source_block(spoken, [correct, correct]) is None
    assert exact_math_source_block(spoken, [
        source_math_block("vxi = 40 m/s, vxf = 30 m/s at t = 2 s"),
    ]) is None
    assert exact_math_source_block(spoken, [
        source_math_block("vxi = 40 km/h, vxf = 20 km/h at t = 2 s"),
    ]) is None

    limit = ("The limit as delta t approaches zero equals negative 10 t")
    assert exact_math_source_block(limit, [
        source_math_block("Δt→0(10t +5Δt) = +10t"),
    ]) is None
    assert exact_math_source_block(limit, [
        source_math_block("Δt→0(-10t) = −10x"),
    ]) is None
    assert exact_math_source_block(limit, [
        source_math_block("Δt→0(-10t) = −10t"),
        source_math_block("Δt→0(-10t) = −10t"),
    ]) is None


def test_complete_source_pdf_plan_succeeds_offline_without_semantic_model(tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "0")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((42, 65),
                     "vxi = 40 - 5(0)2 = 40 m/s; vxf = 40 -5(2)2 = 20 m/s",
                     fontsize=10)
    pdf.save(tmp_path / "slides.pdf")
    pdf.close()
    speech = ("At 2 seconds the initial velocity is 40 meters per second "
              "and the final velocity is 20 meters per second.")
    (tmp_path / "script_tts.json").write_text(
        json.dumps({"slides": [{
            "slide": 1, "narration": speech, "tts_text": speech,
        }]}), encoding="utf8",
    )
    prepare_slide_pages(tmp_path)
    plan_path = write_verified_plan(tmp_path)
    assert plan_path.is_file()
    verified, cues = _verified_plan(tmp_path)
    assert verified["total_cues"] == 1
    assert cues == [speech]
    assert verified["slides"][0]["cues"][0]["pdf_bbox"]


def test_no_provider_call_when_unverifiable_or_ambiguous(tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "0")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((42, 65), "vxi = 40 m/s, vxf = 30 m/s", fontsize=10)
    pdf.save(tmp_path / "slides.pdf")
    pdf.close()
    speech = "The initial velocity is 40 meters per second, final velocity is 20 meters per second at 2 seconds."
    (tmp_path / "script_tts.json").write_text(
        json.dumps({"slides": [{"slide": 1, "narration": speech,
                                "tts_text": speech}]}), encoding="utf8",
    )
    prepare_slide_pages(tmp_path)
    with pytest.raises(CuePlanningError, match="UNATTESTED_VISIBLE_NUMERIC_CUE"):
        propose_plan(tmp_path)



def test_numbered_title_and_distant_formula_are_split_without_rewriting_speech(
    tmp_path, monkeypatch,
):
    from microgen_timed_cue_planner import source_grounded_speech_units, normalized
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "1")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "4")
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((42, 55),
                     "Example 2.6: Average Acceleration (Part A)", fontsize=12)
    page.insert_text((42, 480),
                     "Given vx = 40 - 5t2, find average acceleration.",
                     fontsize=11)
    pdf.save(tmp_path / "slides.pdf")
    pdf.close()
    spoken = (
        "In Part A of Example 2.6, we find the average acceleration "
        "for a particle with velocity 40 minus 5 t squared."
    )
    (tmp_path / "script_tts.json").write_text(json.dumps({
        "slides": [{"slide": 1, "narration": spoken, "tts_text": spoken}],
    }), encoding="utf8")
    prepare_slide_pages(tmp_path)
    with fitz.open(tmp_path / "slides.pdf") as check:
        blocks = _pdf_text_blocks(check[0])
        units = source_grounded_speech_units(spoken, blocks)
    assert len(units) == 2
    assert "Example 2.6" in units[0]
    assert "40 minus 5" in units[1]
    assert normalized(" ".join(units)) == normalized(spoken)
    seen = []

    def source_quoted_candidate(slide, missing, blocks):
        seen.append(slide)
        assert slide == 1
        return [
            {"cue": cue, "block": 1 if "Example 2.6" in sentence else 2,
             "quote": blocks[(0 if "Example 2.6" in sentence else 1)][1][:85]}
            for cue, sentence in missing
        ]

    plan_path = write_verified_plan(tmp_path,
                                    semantic_resolver=source_quoted_candidate)
    verified, fragments = _verified_plan(tmp_path)
    assert plan_path.is_file()
    assert verified["total_cues"] == 2
    assert fragments == units
    assert seen == [1]
    # Distant title/formula source boxes were never combined into one huge
    # fabricated highlight rectangle.
    boxes = [cue["pdf_bbox"] for cue in verified["slides"][0]["cues"]]
    assert boxes[0][3] < boxes[1][1]


def test_lexical_word_overlap_does_not_ignore_wrong_value_in_selected_block():
    spoken = ("The velocity and acceleration indicate a result of "
              "20 meters per second.")
    blocks = [
        source_math_block("The velocity and acceleration show 30 m/s."),
        source_math_block("The correct number 20 belongs to a separate label"),
    ]
    cues, missing = _lexical_match(1, [spoken], blocks,
                                   allow_unanchored=True)
    # One block has the right words but a wrong number; the other has 20
    # without the necessary wording or unit. Neither is automatically
    # accepted as the source of the whole spoken claim.
    assert cues == [None]
    assert missing == [(1, spoken)]
