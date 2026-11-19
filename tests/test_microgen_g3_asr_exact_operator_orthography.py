"""Source-blind exact math printing aliases from a real independent G3 failure.

These are only ASR typography repairs, never pronunciation or science waivers.
No source PDFs, WAVs, private transcripts or provider calls are used.
"""
import pytest
from microgen_tts_acoustic_qa import mismatch_details

@pytest.mark.parametrize("spoken,printed", [
    ("The car's ex component of velocity times tee equals 45.",
     "The car's ex component of velocity * t equals 45."),
    ("The billboard position ex bee equals 45 meters.",
     "The billboard position xB equals 45 meters."),
    ("The billboard position ex bee equals 45 meters.",
     "The billboard position x B equals 45 meters."),
    ("Solve the fraction 63 divided by 2.0.",
     "Solve the fraction 63 / 2.0."),
    ("The result is minus 32 meters per second squared.",
     "The result is -32 m/s²."),
    ("We require t greater than 0.",
     "We require t > 0."),
    ("The position includes tee minus ex bee.",
     "The position includes t - xB."),
    ("The quadratic contains acceleration times tee squared.",
     "The quadratic contains acceleration * t^2."),
])
def test_exact_symbolic_math_is_not_false_asr_disagreement(spoken, printed):
    result=mismatch_details(spoken, printed)
    assert result["difference_fraction_upper_bound"]==0, result
    assert result["sensitive_mismatches"]==0

@pytest.mark.parametrize("spoken,wrong", [
    ("The result is minus 32 meters per second squared.",
     "The result is -3.2 m/s²."),
    ("The result is minus 32 meters per second squared.",
     "The result is -32 m/s."),
    ("The result is minus 32 meters per second squared.",
     "The result is +32 m/s²."),
    ("The billboard position ex bee equals 45 meters.",
     "The billboard position yB equals 45 meters."),
    ("We require t greater than 0.", "We require t < 0."),
    ("The position includes tee minus ex bee.",
     "The position includes t + xB."),
    ("The position ex final minus ex initial is positive.",
     "The position ex final plus ex initial is positive."),
    ("We require tee equals 0.", "We require tee equals 0.0."),
])
def test_wrong_math_or_changed_precision_still_blocks(spoken,wrong):
    result=mismatch_details(spoken,wrong)
    assert result["difference_fraction_upper_bound"]>0, result

def test_no_math_operator_erasure_in_plain_prose():
    assert mismatch_details("I met B at an exhibit.", "I met xB at an exhibit.")[
        "difference_fraction_upper_bound"]>0

@pytest.mark.parametrize("spoken,printed", [
    ("The graph shows the x component of velocity versus t line.",
     "The graph shows the v x versus t line."),
    ("The position x initial equals zero at touchdown.",
     "The position x initial equals 0.0 at touchdown."),
    ("The quadratic has acceleration times tee squared minus the car's x component of velocity times tee.",
     "The quadratic has acceleration * t^2 - the car's x component of velocity * t."),
    ("The equation has velocity times tee minus ex bee.",
     "The equation has velocity * t - xB."),
])
def test_recurrent_source_blind_exact_math_equality(spoken,printed):
    result=mismatch_details(spoken,printed)
    assert result["difference_fraction_upper_bound"]==0, result
    assert result["sensitive_mismatches"]==0

@pytest.mark.parametrize("spoken,wrong", [
    ("The graph shows the x component of velocity versus t line.",
     "The graph shows the y component of velocity versus t line."),
    ("The graph shows the x component of velocity versus t line.",
     "The graph shows the x component of acceleration versus t line."),
    ("The position x initial equals zero at touchdown.",
     "The position x initial equals 0.1 at touchdown."),
    ("The position x final equals zero at touchdown.",
     "The position x final equals 0.0 at touchdown."),
    ("The quadratic has acceleration times tee squared minus the car's x component of velocity times tee.",
     "The quadratic has acceleration * t^2 + the car's x component of velocity * t."),
])
def test_math_aliases_never_change_variable_exponent_sign_or_origin(wrong,spoken):
    assert mismatch_details(spoken,wrong)["difference_fraction_upper_bound"]>0

def test_only_exact_additive_zero_allows_zero_point_zero_transcription():
    assert mismatch_details("The calculation gives 0 plus a term.",
                            "The calculation gives 0.0 plus a term.")[
        "difference_fraction_upper_bound"]==0
    assert mismatch_details("The calculation gives 0 plus a term.",
                            "The calculation gives 0.1 plus a term.")[
        "difference_fraction_upper_bound"]>0
    assert mismatch_details("The measured distance is 0.0 meters.",
                            "The measured distance is 0 meters.")[
        "difference_fraction_upper_bound"]>0
