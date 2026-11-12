"""Source-grounded recovery for an explicit printed Question N + its next body.

No Gemini requests, OCR, publication or invented equations. The same shared
normal cue planner must validate these pairs against both original PDF blocks.
"""
import pytest

from microgen_cue_semantic_mapping import (
    SemanticMappingError, numbers, repair_question_heading_body_pair,
    validate_matches,
)


def actual_shape_fixture():
    # Source-free reconstruction of the real G2 slide-14 failure SHAPE,
    # not a claim to reproduce Gemini's unrecorded response body.
    blocks = [
        ([30, 30, 220, 50], "Concept Check", set()),
        ([30, 56, 320, 76], "Question 1: Direction of Force (Quick Quiz 2.5)", set()),
        ([30, 80, 450, 112],
         "A car travels eastward along a straight road and is slowing down. "
         "What is the direction of the net force on the car?", set()),
        ([30, 122, 110, 140], "(a) Eastward", set()),
        ([30, 144, 110, 162], "(b) Westward", set()),
        ([30, 166, 260, 184], "(c) Neither eastward nor westward", set()),
        ([30, 192, 330, 214], "Question 2: Sign of Acceleration", set()),
        ([30, 216, 450, 251],
         "A particle moves along the x axis with vx = -15 m/s "
         "and ax = -3.0 m/s2. Is the particle speeding up or slowing down?",
         set()),
    ]
    missing = [
        (1, "Let us test these principles with a concept check."),
        (2, "In Question 1, a car travels eastward along a straight road "
            "and is slowing down."),
        (4, "In Question 2, a particle moves along the x axis with "
            "velocity minus 15 meters per second and acceleration "
            "minus 3.0 meters per second squared."),
    ]
    return blocks, missing


def test_numbered_question_body_recovers_exactly_two_pdf_blocks():
    blocks, missing = actual_shape_fixture()
    model = [
        {"cue": 1, "block": 1, "quote": "Concept Check"},
        {"cue": 2, "block": 3,
         "quote": "A car travels eastward along a straight road"},
        {"cue": 4, "block": 7,
         "quote": "Question 2: Sign of Acceleration"},
    ]
    with pytest.raises(SemanticMappingError, match="Numerical claim"):
        validate_matches(model, missing, blocks)
    repaired = repair_question_heading_body_pair(model, missing, blocks)
    assert repaired[0] == model[0]
    assert repaired[1]["blocks"] == [2, 3]
    assert repaired[2]["blocks"] == [7, 8]
    for row in repaired[1:]:
        assert len(row["quotes"]) == 2
    checked = validate_matches(repaired, missing, blocks)
    assert checked[2][0] == (1, 2)
    assert checked[4][0] == (6, 7)
    assert numbers(missing[2][1]).issubset(
        numbers(blocks[6][1] + " " + blocks[7][1])
    )


@pytest.mark.parametrize("bad", [
    {"cue": 2, "block": 4, "quote": "(a) Eastward"},
    {"cue": 2, "block": 3, "quote": "Fabricated source quote"},
    {"cue": 2, "block": 3, "quote": "A car"},
])
def test_wrong_or_unverified_model_evidence_never_overridden(bad):
    blocks, missing = actual_shape_fixture()
    original = [
        {"cue": 1, "block": 1, "quote": "Concept Check"},
        bad,
        {"cue": 4, "block": 7, "quote": "Question 2: Sign of Acceleration"},
    ]
    repaired = repair_question_heading_body_pair(original, missing, blocks)
    assert repaired[1] == bad
    with pytest.raises(SemanticMappingError):
        validate_matches(repaired, missing, blocks)


def test_unprinted_result_or_wrong_numeric_number_stays_blocked():
    blocks, missing = actual_shape_fixture()
    missing = [(2, "In Question 1, the car finishes with 999 meters per second.")]
    proposal = [{"cue": 2, "block": 3,
                 "quote": "A car travels eastward along a straight road"}]
    assert repair_question_heading_body_pair(proposal, missing, blocks) == proposal
    with pytest.raises(SemanticMappingError, match="Numerical"):
        validate_matches(proposal, missing, blocks)


def test_duplicate_numbered_question_header_stays_ambiguous():
    blocks, missing = actual_shape_fixture()
    blocks.insert(2, (blocks[1][0], blocks[1][1], set()))
    proposal = [{"cue": 2, "block": 4,
                 "quote": "A car travels eastward along a straight road"}]
    altered = repair_question_heading_body_pair(
        proposal, [missing[1]], blocks
    )
    assert altered == proposal


def test_question_pair_not_connected_to_paraphrase_cannot_be_joined():
    blocks, missing = actual_shape_fixture()
    blocks[2] = (
        blocks[2][0],
        "The mass of the moon is recorded for another experiment.", set()
    )
    proposal = [{"cue": 2, "block": 2,
                 "quote": "Question 1: Direction of Force"}]
    assert repair_question_heading_body_pair(
        proposal, [missing[1]], blocks
    ) == proposal


def test_unrelated_numeric_problem_not_falsely_repaired():
    blocks = [
        ([10, 10, 220, 30], "Momentum = 10 kg m/s", set()),
        ([10, 35, 220, 55], "Energy = 20 Joules", set()),
    ]
    proposal = [{"cue": 1, "block": 1, "quote": "Momentum = 10"}]
    assert repair_question_heading_body_pair(
        proposal, [(1, "The result equals 999 joules")], blocks
    ) == proposal
    with pytest.raises(SemanticMappingError):
        validate_matches(
            proposal, [(1, "The result equals 999 joules")], blocks)



def test_numbered_answers_also_recover_exact_adjacent_pdf_source():
    from microgen_cue_semantic_mapping import repair_numbered_heading_body_pair
    blocks = [
        ([30,30,240,50], "Concept Check: Reasoning", set()),
        ([30,55,270,78], "Answer 1: Westward", set()),
        ([30,82,310,102], "The car's velocity points eastward.", set()),
        ([30,106,410,127], "Because the car is slowing down, its acceleration opposes velocity.", set()),
        ([30,131,405,150], "The net force must act westward.", set()),
        ([30,157,280,180], "Answer 2: Speeding Up", set()),
        ([30,184,425,207],
         "Both velocity and acceleration are negative; thus they point "
         "in the same direction.", set()),
        ([30,211,430,234],
         "When velocity and acceleration have the same sign, speed increases.", set()),
    ]
    missing = [
        (1, "Reviewing the reasoning, for Answer 1, the car's velocity "
            "points eastward."),
        (4, "For Answer 2, both velocity and acceleration are negative, "
            "pointing in the same direction."),
    ]
    hints = [
        {"cue": 1, "block": 3,
         "quote": "The car's velocity points eastward"},
        {"cue": 4, "block": 6,
         "quote": "Answer 2: Speeding Up"},
    ]
    with pytest.raises(SemanticMappingError, match="Numerical"):
        validate_matches(hints, missing, blocks)
    recovered = repair_numbered_heading_body_pair(hints, missing, blocks)
    assert recovered[0]["blocks"] == [2,3]
    assert recovered[1]["blocks"] == [6,7]
    assert validate_matches(recovered, missing, blocks)[1][0] == (1,2)
    assert validate_matches(recovered, missing, blocks)[4][0] == (5,6)


def test_mismatched_answer_number_is_not_joined_to_other_answer():
    from microgen_cue_semantic_mapping import repair_numbered_heading_body_pair
    blocks=[
        ([30,10,250,30],"Answer 1: Westward",set()),
        ([30,35,440,65],"The car travels eastward and slows down.",set()),
        ([30,72,250,95],"Answer 2: Speeding Up",set()),
        ([30,98,440,120],"The particle travels westward and speeds up.",set()),
    ]
    missing=[(1,"For Answer 2, the car travels eastward and slows down.")]
    hint=[{"cue":1,"block":2,
           "quote":"The car travels eastward and slows down"}]
    assert repair_numbered_heading_body_pair(hint,missing,blocks)==hint
    with pytest.raises(SemanticMappingError):
        validate_matches(hint,missing,blocks)



def test_normal_full_cue_planner_recovers_question_and_answer_pdf_evidence(
    tmp_path, monkeypatch,
):
    import json
    import fitz
    from microgen_timed_cue_planner import (
        prepare_slide_pages, propose_plan,
    )
    from microgen_timed_cue_tts import PLAN_FILE

    stage = tmp_path / "private"
    stage.mkdir()
    with fitz.open() as pdf:
        first = pdf.new_page(width=420, height=260)
        first.insert_text((40, 40), "Question 1: Direction of Force",
                          fontsize=11)
        first.insert_text((40, 80),
                          "A car travels eastward along a straight road\n"
                          "and is slowing down.", fontsize=10)
        second = pdf.new_page(width=420, height=260)
        second.insert_text((40, 40), "Answer 1: Westward", fontsize=11)
        second.insert_text((40, 80),
                           "The car's velocity points eastward.", fontsize=10)
        pdf.save(stage / "slides.pdf")
    narration = [
        "In Question 1, a car travels eastward along a straight road "
        "and is slowing down.",
        "For Answer 1, the car's velocity points eastward.",
    ]
    (stage / "script_tts.json").write_text(json.dumps({
        "slides": [{"slide": i, "tts_text": txt, "narration": txt}
                   for i, txt in enumerate(narration, 1)]
    }), encoding="utf8")
    prepare_slide_pages(stage)
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "2")
    called = []

    def fake_model(slide, missing, blocks):
        called.append((slide, [c for c, _ in missing]))
        assert len(blocks) == 2
        assert len(missing) == 1
        # This is a valid real-PDF quote, but intentionally omits the
        # adjacent numbered question/answer heading in each row.
        return [{"cue": 1, "block": 2,
                 "quote": blocks[1][1][:100].strip()}]

    plan = propose_plan(stage, semantic_resolver=fake_model)
    assert called == [(1,[1]), (2,[1])]
    assert plan["total_cues"] == 2
    assert plan["planning_method"] == "source_pdf_grounded_semantic_screen"
    for row in plan["slides"]:
        cue = row["cues"][0]
        assert len(cue["pdf_bboxes"]) == 2
        assert len(cue["semantic_source_quotes"]) == 2
    assert not (stage / PLAN_FILE).exists()
