"""General acoustic comparison variants; no model calls or lecture regeneration."""
from microgen_tts_acoustic_qa import mismatch_details


def same(expected, heard):
    result=mismatch_details(expected,heard)
    assert result["difference_fraction_upper_bound"]==0, result["differences"]
    assert result["sensitive_mismatches"]==0


def test_compound_nonisolated_spelling_is_not_speech_error():
    same("8.1 Analysis Model: Nonisolated System (Energy)",
         "8.1 Analysis model: Non-isolated system, energy.")
    same("The combined system is nonisolated.",
         "The combined system is non isolated.")


def test_subscript_letters_not_conflated_with_actual_different_letters():
    same("Matter transfer T sub M T and sound T sub M W, electrical T sub E T.",
         "Matter transfer T sub MT and sound T sub MW, electrical T sub ET.")
    different=mismatch_details("T sub M T", "T sub E T")
    assert different["difference_fraction_upper_bound"]>0


def test_equation_reference_spellings_and_contractions_are_equivalent():
    same("Equation eight point two explains the process.",
         "Equation 8.2 explains the process.")
    same("The boundary you have drawn.", "The boundary you've drawn.")


def test_math_changes_do_not_disappear_in_normalization():
    for expected, heard in [
        ("Equation eight point two", "Equation eight point three"),
        ("The number is eight point two", "The number is eight two"),
        ("The derivative is positive", "The derivative is negative"),
        ("Energy is not conserved", "Energy is conserved"),
        ("The function is evaluated at c", "The function is evaluated at circa"),
    ]:
        result=mismatch_details(expected,heard)
        assert result["difference_fraction_upper_bound"]>0, (expected,heard)
        assert result["sensitive_mismatches"] or result["circa_red_flags"], (expected,heard)


def test_letter_y_and_circa_explicit_guards_remain():
    assert mismatch_details("The variable y", "The variable yay")["letter_y_yay_red_flags"]
    assert mismatch_details("At c", "At circa")["circa_red_flags"]
