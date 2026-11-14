"""Source-independent G3 math voice recovery for vector increments/panels.

Do not alter visible lecture/source PDFs; only pronounce explicit
mathematical increment variables and true numbered figure-panel labels.
Retain isolated-unknown-letter and source-change fail-closed behavior.
"""
import pytest
from microgen_reviewed_math_voice import (
    reviewed_math_voice,voice_input_risk_status,
)
from text_to_speech_v25 import normalize_scientific_speech
from microgen_tts_risk_register import find_pronunciation_risks


@pytest.mark.parametrize("source,expected",[
    ("an equal displacement delta x in interval delta t",
     "an equal displacement delta ex in interval delta tee"),
    ("delta y equals two times delta x",
     "delta why equals two times delta ex"),
    ("Figure 2 point 10 c shows the acceleration",
     "Figure 2 point 10 panel see shows the acceleration"),
    ("Figure 2.10c, Figure 4.12b, Fig. 3.9a",
     "Figure 2.10 panel see, Figure 4.12 panel bee, Fig. 3.9 panel ay"),
    ("Figure 10 point 7 d and Figure 10 point 7 f",
     "Figure 10 point 7 panel dee and Figure 10 point 7 panel eff"),
])
def test_contextual_math_voice_expansion(source,expected):
    assert reviewed_math_voice(source)==expected
    assert reviewed_math_voice(expected)==expected


def test_all_representative_g3_source_risks_clear_before_paid_tts():
    source=[
        "equal displacement delta x occurs in equal time interval delta t",
        "the Figure 2 point 10 c observation shows images",
        "Figure 2 point 10 b and Figure 2 point 10 c each have arrows",
    ]
    for raw in source:
        status=voice_input_risk_status(raw,normalize_scientific_speech)
        assert status["unresolved_source_risk_count"]==0
        assert not status["unresolved_source_risk_codes"]
        spoken=normalize_scientific_speech(reviewed_math_voice(raw))
        assert not find_pronunciation_risks(spoken,spoken)


@pytest.mark.parametrize("text",[
    "Let c be the unknown coefficient in the equation.",
    "The x coordinate is unknown at this stage.",
    "We measure function f(x) without a reviewed argument expansion.",
])
def test_unrelated_math_expression_is_unchanged_by_targeted_voice_adapter(text):
    updated=reviewed_math_voice(text)
    assert "panel" not in updated
    # This specific voice adapter must not globally rewrite an unrelated
    # letter/formula. The separately reviewed generic scientific normalizer
    # may of course handle some safe expressions such as "x coordinate".
    assert updated == text


def test_no_title_number_or_formula_changed():
    source="Figure 2.10c has a delta x of 5 m, but c equals 6."
    changed=reviewed_math_voice(source)
    assert "Figure 2.10 panel see" in changed
    assert "delta ex of 5 m" in changed
    assert "c equals 6" in changed
    assert "Figure 2.11" not in changed
