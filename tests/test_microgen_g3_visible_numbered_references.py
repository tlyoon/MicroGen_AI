"""Exact textbook-reference identity in source-grounded visual cue matching.

A reference such as Section 2.7 or Figure 2.10c is not a physical
floating-point quantity. The printed PDF and correct spoken rendering
must agree without admitting a different figure, panel, section, quiz,
equation or measured value.
"""
import pytest
from microgen_cue_semantic_mapping import numbers


@pytest.mark.parametrize("printed,spoken,identifier",[
    ("Figure 2.10", "Figure 2 point 10", "figure:2.10"),
    ("Fig. 4.12b", "Figure 4 point 12 panel bee", "figure:4.12:b"),
    ("Figure 2.10c", "Figure 2 point 10 c", "figure:2.10:c"),
    ("Section 2.7.", "Section 2 point 7", "section:2.7"),
    ("Sec. 12.4", "Section 12 point 4", "section:12.4"),
    ("Quick Quiz 2.6", "Quick Quiz 2 point 6", "quiz:2.6"),
    ("Example 3.5.", "Example 3 point 5", "example:3.5"),
    ("Eq. 2.8", "Equation 2 point 8", "equation:2.8"),
])
def test_identical_source_reference_in_pdf_and_spoken_cue(
        printed,spoken,identifier):
    assert numbers(printed)=={identifier}
    assert numbers(spoken)=={identifier}


@pytest.mark.parametrize("printed,wrong",[
    ("Figure 2.10", "Figure 2 point 11"),
    ("Figure 2.10b", "Figure 2 point 10 panel see"),
    ("Section 2.7", "Section 2 point 8"),
    ("Section 2.7", "Quick Quiz 2 point 7"),
    ("Quick Quiz 2.6", "Quick Quiz 2 point 7"),
    ("Example 3.5", "Equation 3 point 5"),
])
def test_wrong_source_identity_is_never_an_accepted_match(printed,wrong):
    assert not numbers(wrong).issubset(numbers(printed))


@pytest.mark.parametrize("literal,expected",[
    ("value 2.10 m per second", {"2.1"}),
    ("value 2.10.", {"2.1"}),
    ("40 is the constant.", {"40"}),
    ("the value is 2.7.1", set()),
    ("v equals 40 minus 5t squared", {"40","5"}),
])
def test_real_math_values_remain_numeric_not_reference_identifiers(literal,expected):
    assert numbers(literal)==expected


def test_real_g3_structure_requires_correct_visible_source_number():
    figure="Vector conventions (Figure 2.10):"
    spoken="Under our vector conventions from Figure 2 point 10"
    section="Bridge forward: equations developed in Section 2.7."
    section_spoken="equations developed in Section 2 point 7"
    quiz="Concept Check: Quick Quiz 2.6"
    quiz_spoken="Now consider Quick Quiz 2 point 6."
    for source,narration in (
        (figure,spoken),(section,section_spoken),(quiz,quiz_spoken)):
        assert numbers(narration).issubset(numbers(source))
    assert not numbers("Section 2 point 8").issubset(numbers(section))
    assert not numbers("Quick Quiz 2 point 7").issubset(numbers(quiz))
