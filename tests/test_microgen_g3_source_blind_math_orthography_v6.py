"""General source-blind mathematical ASR formatting with strict negatives.

There are no Gemini requests and no source data copied from any textbook.
Any operator, coordinate, panel identity, sign, number or exponent drift
must remain a real scientific/acoustic QA concern.
"""
import pytest
from microgen_acoustic_math_transcript import canonical_math_transcript
from microgen_tts_acoustic_qa import mismatch_details


@pytest.mark.parametrize("expected,blind_asr", [
    (
        "The acceleration ay ex equals dee vee ex over dee tee.",
        "The acceleration a_x equals dv_x over d t.",
    ),
    (
        "The acceleration ay ex equals dee vee ex over dee tee.",
        "The acceleration a_x equals dv sub x over d t.",
    ),
    (
        "The velocity vee ex is constant and acceleration ay ex is zero.",
        "The velocity v_x is constant and acceleration a_x is zero.",
    ),
    (
        "Graph panel ay matches panel ee, while graph panel bee matches panel eff.",
        "Graph panel a matches panel e, while graph panel b matches panel f.",
    ),
    (
        "The trooper starts 1 point 00 second later.",
        "The trooper starts 1 point 00 seconds later.",
    ),
])
def test_exact_identity_preserving_transcript_notations(expected,blind_asr):
    result=mismatch_details(expected,blind_asr)
    assert result["difference_fraction_upper_bound"]==0,result
    assert result["sensitive_mismatches"]==0
    for source in (expected,blind_asr):
        once=canonical_math_transcript(source)
        assert canonical_math_transcript(once)==once


@pytest.mark.parametrize("expected,scientifically_different", [
    ("The acceleration ay ex equals zero.", "The acceleration a_y equals zero."),
    ("The acceleration ay ex equals zero.", "The acceleration ay sub y equals zero."),
    ("The derivative dee vee ex over dee tee is positive.",
     "The derivative dv_y over d t is positive."),
    ("The derivative dee vee ex over dee tee is positive.",
     "The derivative dv_x over d x is positive."),
    ("The velocity vee ex is constant.", "The velocity v(x) is constant."),
    ("The graph panel ee has zero slope.", "The graph panel i has zero slope."),
    ("The graph panel ay has zero slope.", "The graph panel b has zero slope."),
    ("The velocity is minus 32 meters per second squared.",
     "The velocity is minus 3 point 2 meters per second squared."),
    ("The derivative a_x is negative.", "The derivative a_x is positive."),
    ("The interval is 1 point 00 second later.",
     "The interval is 2 point 00 seconds later."),
    ("The derivative d v x squared is zero.",
     "The derivative d v x cubed is zero."),
])
def test_material_math_change_cannot_be_canonicalized_away(
        expected,scientifically_different):
    result=mismatch_details(expected,scientifically_different)
    assert result["difference_fraction_upper_bound"]>0,result


def test_time_plural_is_only_a_numeric_later_context():
    assert mismatch_details(
        "It starts 1.00 second later.",
        "It starts 1.00 seconds later."
    )["difference_fraction_upper_bound"]==0
    assert mismatch_details(
        "I measured a second derivative.",
        "I measured a seconds derivative."
    )["difference_fraction_upper_bound"]>0
