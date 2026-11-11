"""Avoid paid semantic mapping of numbers absent from the visible PDF.

This test suite reproduces the family seen on a private real lecture:
correctly calculated quantities are not automatically PDF-visible cues.
The normal private batch preflight and direct planner must both refuse before
a semantic provider request. No source excerpts or credentials are stored.
"""
import json

import fitz
import pytest

from microgen_batch import preflight_private_timed_acceptance
from microgen_timed_cue_planner import (
    CuePlanningError,
    prepare_slide_pages,
    propose_plan,
)


def build_stage(tmp_path, *, show_computed_number: bool):
    deck = fitz.open()
    page = deck.new_page()
    page.insert_text(
        (72, 70),
        "Given velocity v = 40 - 5t2 from t = 0 to t = 2.0 seconds",
    )
    if show_computed_number:
        page.insert_text((72, 105), "At t = 2.0, velocity equals 20 m/s.")
    deck.save(tmp_path / "slides.pdf")
    deck.close()
    spoken = (
        "The initial velocity is 40 meters per second, and at 2.0 seconds "
        "the calculated velocity becomes 20 meters per second."
    )
    (tmp_path / "script_tts.json").write_text(
        json.dumps({"slides": [
            {"slide": 1, "narration": spoken, "tts_text": spoken}
        ]}), encoding="utf8",
    )
    prepare_slide_pages(tmp_path)
    return tmp_path


def test_normal_private_acceptance_preflight_blocks_unsourced_numeric_claim(
    tmp_path, monkeypatch,
):
    stage = build_stage(tmp_path, show_computed_number=False)
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "1")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "4")
    with pytest.raises(CuePlanningError, match="UNATTESTED_VISIBLE_NUMERIC_CUE"):
        preflight_private_timed_acceptance(stage)
    assert not (stage / ".microgen_timed_cue_plan.json").exists()
    assert not (stage / ".microgen_tts_provenance.json").exists()


def test_direct_planner_does_not_contact_semantic_resolver_on_impossible_claim(
    tmp_path,
):
    stage = build_stage(tmp_path, show_computed_number=False)
    calls = []

    def fake_resolver(*args):
        calls.append(args)
        raise AssertionError("Should fail before semantic model request")

    with pytest.raises(CuePlanningError, match="UNATTESTED_VISIBLE_NUMERIC_CUE"):
        propose_plan(stage, semantic_resolver=fake_resolver)
    assert calls == []


def test_number_visible_on_slide_is_not_automatically_rejected(
    tmp_path, monkeypatch,
):
    stage = build_stage(tmp_path, show_computed_number=True)
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "1")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "4")
    admitted = preflight_private_timed_acceptance(stage)
    assert admitted["mode"] == "semantic_budget_admitted"
    assert admitted["pages"] == 1


def test_generator_instructions_prevent_off_slide_calculated_values(monkeypatch):
    import gen_script_v13 as narrator

    monkeypatch.setattr(
        narrator, "_read_prompt", lambda _: "Use original source exactly",
    )
    prompt = narrator._compose_prompt(
        [{"id": "slide_01", "title": "Velocity", "onscreen": ["v(t)"]}],
        [{"id": "source_1", "page": 1, "text": "A source-backed formula"}],
    )
    assert "derived" in prompt
    assert "ABSENT from the fixed slide" in prompt
    assert "do not narrate that result" in prompt
    assert "actually visible in the PDF text" in prompt


def test_formula_coefficients_and_decimal_notation_have_exact_literal_equivalence():
    from microgen_cue_semantic_mapping import numbers

    # Mathematical text extracted from PDF may not include spaces or powers.
    visible = numbers("vx = 40 -5t2, from t = 0 to t = 2.0 s")
    assert {"40", "5", "2", "0"}.issubset(visible)
    assert numbers("2") == numbers("2.0") == numbers("02.000")
    # Literal extraction is NOT an unproved arithmetic evaluator.
    assert "20" not in visible
    assert "10" not in visible
