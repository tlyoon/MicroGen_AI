"""General time-function ASR orthography recovery on the normal QA path.

Never treat a different function argument, component or exponent as an alias.
"""
import pytest
from microgen_acoustic_math_transcript import canonical_math_transcript
from microgen_tts_acoustic_qa import mismatch_details


@pytest.mark.parametrize("script,recognized", [
    ("The coordinate ex of tee changes.", "The coordinate x(t) changes."),
    ("The velocity vee ex of t varies.", "The velocity vx(t) varies."),
    ("The velocity vee ex of t varies.", "The velocity VX of T varies."),
    ("The acceleration ay ex of t varies.", "The acceleration a_x(t) varies."),
    ("The acceleration ay ex of t varies.", "The acceleration ax(t) varies."),
    ("Velocity vee ex of tee is positive.", "Velocity v_x(t) is positive."),
])
def test_time_function_format_does_not_create_acoustic_mismatch(script, recognized):
    result = mismatch_details(script, recognized)
    assert result["difference_fraction_upper_bound"] == 0, result
    assert result["sensitive_mismatches"] == 0


@pytest.mark.parametrize("script,incorrect", [
    ("ex of tee", "x(x)"),
    ("ex of tee", "x(t squared)"),
    ("vee ex of tee", "v_x(y)"),
    ("ay ex of tee", "v_x(t)"),
    ("vee ex of tee minus 5", "vx(t) plus 5"),
    ("vee ex of tee is 40", "vx(t) is 4t"),
])
def test_changed_math_remains_a_real_disagreement(script, incorrect):
    assert mismatch_details(script, incorrect)["difference_fraction_upper_bound"] > 0


def test_time_function_rewrite_is_idempotent_and_nonmath_prose_unchanged():
    for original in ("x(t)", "v_x(t)", "ax(t)", "The next appointment is on Tuesday."):
        once = canonical_math_transcript(original)
        assert canonical_math_transcript(once) == once
    assert canonical_math_transcript("The next appointment is on Tuesday.") == (
        "The next appointment is on Tuesday."
    )
