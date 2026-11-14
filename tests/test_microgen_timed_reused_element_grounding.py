"""Source-free replay of repeated-element narration within the normal timed planner.

An earlier cue's use of a PDF text element must not make a later,
independently grounded reference to that same element ungroundable.
This is NOT a waiver for paraphrases, unknown numbers, or one-word guesses.
"""
import json

import fitz

from microgen_timed_cue_planner import (
    _lexical_match, salient, prepare_slide_pages, propose_plan, write_verified_plan,
)
from microgen_timed_cue_tts import _verified_plan


def _block(label, x=10):
    return ([x, 20.0, x + 160.0, 40.0], label, salient(label))


def test_repeated_anchored_cue_can_reuse_same_visible_pdf_element():
    spoken = [
        "Faraday induction drives the transformer through a rotating magnetic apparatus.",
        "Faraday induction also explains the observed signal from surrounding components.",
    ]
    blocks = [_block("Faraday induction"), _block("Unrelated optical experiment", 200)]
    cues, missing = _lexical_match(1, spoken, blocks, allow_unanchored=False)
    assert missing == []
    assert [c["pdf_text"] for c in cues] == ["Faraday induction"] * 2
    assert cues[0]["element_id"] != cues[1]["element_id"]


def test_one_matching_source_term_does_not_justify_repeat():
    spoken = [
        "Faraday induction drives the transformer through a rotating magnetic apparatus.",
        "Faraday villages contain unfamiliar historical claims and disconnected theories.",
    ]
    cues, missing = _lexical_match(
        1, spoken, [_block("Faraday induction")], allow_unanchored=True
    )
    assert cues[0]["pdf_text"] == "Faraday induction"
    assert cues[1] is None
    assert missing == [(2, spoken[1])]


def test_unused_element_still_preferred_when_both_have_equal_source_evidence():
    spoken = [
        "Faraday induction causes complex electromagnetic behavior in the experiment.",
        "Faraday induction also appears in a different discussion about magnetic circuits.",
    ]
    cues, missing = _lexical_match(
        1, spoken, [_block("Faraday induction", 10), _block("Faraday induction", 210)],
        allow_unanchored=False
    )
    assert missing == []
    assert cues[0]["pdf_bbox"] != cues[1]["pdf_bbox"]


def test_normal_pdf_plan_and_verifier_accept_source_attested_repeat(tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "0")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Faraday induction", fontsize=16)
    doc.save(tmp_path / "slides.pdf")
    doc.close()
    narration = (
        "Faraday induction drives the transformer through a rotating magnetic apparatus. "
        "Faraday induction also explains the observed signal from surrounding components."
    )
    (tmp_path / "script_tts.json").write_text(
        json.dumps({"slides": [{"slide": 1, "tts_text": narration}]}),
        encoding="utf8",
    )
    prepare_slide_pages(tmp_path)
    proposal = propose_plan(tmp_path)
    assert proposal["total_cues"] == 2
    assert not proposal["semantic_assist_applied"]
    assert len(proposal["slides"][0]["cues"]) == 2
    write_verified_plan(tmp_path)
    verified, fragments = _verified_plan(tmp_path)
    assert verified["total_cues"] == 2
    assert len(fragments) == 2
