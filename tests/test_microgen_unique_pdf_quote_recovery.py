"""Regression for recycled PR #258 source-anchor recovery in real cue pipeline.

Source-free, no provider calls, no unsupported quote or numeric waiver.
"""
import json
from pathlib import Path

import pytest

from microgen_cue_semantic_mapping import (
    SemanticMappingError, repair_unique_verbatim_quote_location,
    source_quote_constrained_schema, persist_private_semantic_failure,
    validate_matches, SEMANTIC_RESPONSE_JSON_SCHEMA,
)

BLOCKS = [
    ([10, 10, 310, 35], "Overview of energy transfers in the system", set()),
    ([10, 40, 360, 70],
     "The momentum of the particle remains conserved in the collision", set()),
    ([10, 80, 390, 110],
     "Its speed changes by 12 meters per second along the horizontal axis", set()),
    ([10, 120, 390, 155], "The total impulse is 6 newton seconds", set()),
]
MISSING = [(1, "The particle momentum remains conserved during a collision.")]


def test_unique_exact_source_quote_relocates_wrong_selected_block():
    source = "The momentum of the particle remains conserved"
    wrong = [{"cue": 1, "block": 1, "quote": source}]
    with pytest.raises(SemanticMappingError, match="Quoted evidence"):
        validate_matches(wrong, MISSING, BLOCKS)
    fixed = repair_unique_verbatim_quote_location(wrong, MISSING, BLOCKS)
    assert fixed == [{"cue": 1, "block": 2, "quote": source}]
    assert validate_matches(fixed, MISSING, BLOCKS)[1][0] == (1,)
    assert wrong[0]["block"] == 1  # do not mutate model evidence


def test_wrong_selected_group_is_recovered_only_as_unique_ordered_original_blocks():
    cues = [(1, "The particle momentum remains conserved and its speed changes "
                "by 12 meters per second.")]
    wrong = [{"cue": 1, "blocks": [1, 2],
              "quotes": ["The momentum of the particle remains conserved",
                         "Its speed changes by 12 meters per second"]}]
    fixed = repair_unique_verbatim_quote_location(wrong, cues, BLOCKS)
    assert fixed[0]["blocks"] == [2, 3]
    assert validate_matches(fixed, cues, BLOCKS)[1][0] == (1, 2)


def test_valid_citation_is_never_modified():
    good = [{"cue": 1, "block": 2,
             "quote": "The momentum of the particle remains conserved"}]
    assert repair_unique_verbatim_quote_location(good, MISSING, BLOCKS) == good


@pytest.mark.parametrize("spoof", [
    "The momentum of the particle proves a fake result",
    "A source sentence that was never printed",
    "Momentum 999 newton meters",
])
def test_fabricated_or_unsupported_quote_cannot_be_repaired(spoof):
    wrong = [{"cue": 1, "block": 1, "quote": spoof}]
    assert repair_unique_verbatim_quote_location(wrong, MISSING, BLOCKS) == wrong
    with pytest.raises(SemanticMappingError):
        validate_matches(wrong, MISSING, BLOCKS)


def test_duplicate_quote_is_ambiguous_and_cannot_move():
    duplicate = BLOCKS + [([10, 160, 300, 190], BLOCKS[1][1], set())]
    wrong = [{"cue": 1, "block": 1,
              "quote": "The momentum of the particle remains conserved"}]
    assert repair_unique_verbatim_quote_location(wrong, MISSING, duplicate) == wrong


def test_no_lexical_corroboration_cannot_rescue_wrong_block():
    wrong = [{"cue": 1, "block": 1,
              "quote": "The momentum of the particle remains conserved"}]
    spoken = [(1, "A different idea with unrelated vocabulary appears.")]
    assert repair_unique_verbatim_quote_location(wrong, spoken, BLOCKS) == wrong


def test_unprinted_numerical_claim_remains_blocked_after_reanchor():
    wrong = [{"cue": 1, "block": 1,
              "quote": "The momentum of the particle remains conserved"}]
    spoken = [(1, "The particle momentum remains conserved at 999 meters.")]
    assert repair_unique_verbatim_quote_location(wrong, spoken, BLOCKS) == wrong


def test_out_of_order_relocated_group_fails_closed():
    wrong = [{"cue": 1, "blocks": [1, 2],
              "quotes": ["Its speed changes by 12 meters per second",
                         "The momentum of the particle remains conserved"]}]
    spoken = [(1, "The particle momentum remains conserved and its speed "
                  "changes by 12 meters per second.")]
    assert repair_unique_verbatim_quote_location(wrong, spoken, BLOCKS) == wrong


def test_native_schema_uses_only_original_exact_source_quote_candidates():
    from google.genai import types
    schema = source_quote_constrained_schema(BLOCKS)
    single, grouped = schema["properties"]["matches"]["items"]["anyOf"]
    expected = [b[1] for b in BLOCKS]
    assert single["properties"]["quote"]["enum"] == expected
    assert grouped["properties"]["quotes"]["items"]["enum"] == expected
    assert "enum" not in SEMANTIC_RESPONSE_JSON_SCHEMA[
        "properties"]["matches"]["items"]["anyOf"][0]["properties"]["quote"]
    config = types.GenerateContentConfig(
        temperature=0, response_mime_type="application/json",
        response_json_schema=schema,
    )
    assert config.response_json_schema["required"] == ["matches"]
    assert config.response_json_schema["properties"]["matches"][
        "items"]["anyOf"][0]["properties"]["quote"]["enum"] == expected


def test_schema_cap_preserves_original_validator_instead_of_unsafe_expansion():
    many = [([1, 2, 3, 4], "Verified unique source fragment number " + str(i), set())
            for i in range(90)]
    assert source_quote_constrained_schema(many) == SEMANTIC_RESPONSE_JSON_SCHEMA


def test_private_failure_evidence_keeps_original_reply_only_in_local_authorized_workroot(
    tmp_path, monkeypatch, capsys,
):
    import microgen_cue_semantic_mapping as mapping
    local = tmp_path / "AppData" / "Local"
    stage = local / "MicroGen_AI_Checkpoints" / "G2_FINITE_PRIVATE" / "2.5"
    stage.mkdir(parents=True)
    (stage.parent / ".microgen_bounded_provider_authorization.json").write_text("{}")
    (stage / "slides.pdf").write_bytes(b"PRIVATE PDF")
    (stage / "script_tts.json").write_text('{"slides":[]}')
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(mapping.socket if hasattr(mapping, "socket") else
                        __import__("socket"), "gethostname", lambda: "hp")
    model = [{"cue": 1, "block": 1, "quote": "NOT PRESENT IN THE SOURCE"}]
    error = SemanticMappingError("Quoted evidence not present in rendered PDF text")
    assert persist_private_semantic_failure(stage, 11, model, MISSING, BLOCKS, error)
    proof = stage / ".microgen_private_semantic_failed_slide_11.json"
    saved = json.loads(proof.read_text())
    assert saved["reason_code"] == "UNTRUSTED_SEMANTIC_QUOTE"
    assert saved["original_model_proposal"] == model
    assert saved["accepted_semantic_mapping"] is False
    assert saved["publication_allowed"] is False
    assert "NOT PRESENT IN THE SOURCE" not in capsys.readouterr().out
    assert not persist_private_semantic_failure(stage, 11, model, MISSING, BLOCKS, error)
    monkeypatch.setattr(__import__("socket"), "gethostname", lambda: "other-pc")
    assert not persist_private_semantic_failure(stage, 12, model, MISSING, BLOCKS, error)
    assert not (stage / ".microgen_private_semantic_failed_slide_12.json").exists()


def test_normal_real_pdf_cue_planner_reanchors_group_before_independent_verification(
    tmp_path, monkeypatch,
):
    import fitz
    from microgen_timed_cue_planner import prepare_slide_pages, propose_plan
    from microgen_timed_cue_tts import PLAN_FILE

    stage = tmp_path / "private"
    stage.mkdir()
    with fitz.open() as doc:
        page = doc.new_page(width=550, height=320)
        page.insert_text((30, 45), "Overview of the experiment", fontsize=12)
        page.insert_text((30, 90),
                         "Measured momentum equals 12 units for the system",
                         fontsize=12)
        page.insert_text((30, 140),
                         "Final speed becomes 6 units after the event", fontsize=12)
        doc.save(stage / "slides.pdf")
    narration = ("The measured momentum equals 12 units for the system "
                 "and the final speed becomes 6 units after the event.")
    (stage / "script_tts.json").write_text(json.dumps({
        "slides": [{"slide": 1, "tts_text": narration,
                    "narration": narration}]
    }), encoding="utf8")
    prepare_slide_pages(stage)
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "1")
    recorded = []

    def model(slide, missing, blocks):
        recorded.append((slide, len(missing), len(blocks)))
        assert slide == 1 and len(missing) == 1 and len(blocks) == 3
        # The original block/quote pairs are shifted by one. The model
        # quotes are genuine, never invented; existing PDF validator must
        # independently approve the recovered contiguous source region.
        return [{"cue": 1, "blocks": [1, 2],
                 "quotes": ["Measured momentum equals 12 units",
                            "Final speed becomes 6 units"]}]

    plan = propose_plan(stage, semantic_resolver=model)
    assert recorded == [(1, 1, 3)]
    assert plan["total_cues"] == 1
    cue = plan["slides"][0]["cues"][0]
    assert len(cue["pdf_bboxes"]) == 2
    assert len(cue["semantic_source_quotes"]) == 2
    assert cue["semantic_source_quotes"][0] == "Measured momentum equals 12 units"
    assert not (stage / PLAN_FILE).exists()


def test_normal_planner_persists_private_failed_source_quote_without_second_call(
    tmp_path, monkeypatch,
):
    import fitz
    import socket
    from microgen_timed_cue_planner import prepare_slide_pages, propose_plan, CuePlanningError
    from microgen_timed_cue_tts import PLAN_FILE

    local = tmp_path / "Local"
    stage = local / "MicroGen_AI_Checkpoints" / "FINITE_G2" / "2.5"
    stage.mkdir(parents=True)
    (stage.parent / ".microgen_bounded_provider_authorization.json").write_text("{}")
    with fitz.open() as doc:
        page = doc.new_page(width=460, height=240)
        page.insert_text((30, 45), "Energy remains conserved during collision", fontsize=12)
        page.insert_text((30, 75), "Velocity and acceleration act together", fontsize=12)
        doc.save(stage / "slides.pdf")
    speech = "A different interpretation is needed for this situation."
    (stage / "script_tts.json").write_text(json.dumps({
        "slides": [{"slide": 1, "tts_text": speech, "narration": speech}]
    }), encoding="utf8")
    prepare_slide_pages(stage)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "1")
    monkeypatch.setattr(socket, "gethostname", lambda: "hp")
    calls = []
    fabricated = [{"cue": 1, "block": 1,
                   "quote": "This fabricated quotation was never printed"}]

    def model(*args):
        calls.append(1)
        return fabricated

    with pytest.raises(CuePlanningError, match="Quoted evidence"):
        propose_plan(stage, semantic_resolver=model)
    assert calls == [1]
    evidence = stage / ".microgen_private_semantic_failed_slide_1.json"
    saved = json.loads(evidence.read_text())
    assert saved["original_model_proposal"] == fabricated
    assert saved["status"] == "PRIVATE_FAILED_MODEL_PROPOSAL_NOT_ACCEPTED"
    assert not (stage / PLAN_FILE).exists()
