"""Automatic narration numerical equivalence QA; wholly original test text."""
import pytest

from microgen_portable_narration_unit_equivalence import (
    check_narrated_unit_equivalences,NarrationUnitEquivalenceError,
)


def inventory(*sentences):
    return {"slides":[{"narration":x} for x in sentences]}


def test_scanner_recognizes_original_chatgpt_mile_factor():
    res=check_narrated_unit_equivalences(inventory(
        "The source gives the useful relationship that one mile corresponds to 1.609 km."))
    assert 1 in res and len(res[1])==1
    assert res[1][0]["numerical_equivalence_verified"]
    assert not res[1][0]["source_text_provenance_independently_proven"]


def test_exact_inch_and_speed_equivalence():
    res=check_narrated_unit_equivalences(inventory(
        "A distance of 1 inch equals exactly 2.54 cm.",
        "One foot is equal to 0.3048 m.",
        "38.0 meters per second equals 85.0 miles per hour."))
    assert set(res)=={1,2,3}
    assert res[3][0]["from_unit"]=="m/s"
    assert res[3][0]["to_unit"]=="mi/h"


@pytest.mark.parametrize("wrong",[
    "One mile corresponds to 2 km.",
    "38.0 m/s equals 75.0 mi/h.",
    "1 inch equals 3 cm.",
    "One mile equals one centimeter.",
    "One mile is equal to 1.609 miles per hour.",
    "1 mile equals 1600 km.",
])
def test_explicit_false_scientific_equivalences_rejected(wrong):
    with pytest.raises(NarrationUnitEquivalenceError):
        check_narrated_unit_equivalences(inventory(wrong))


@pytest.mark.parametrize("not_claim",[
    "The driver sees 38.0 m/s and a sign marked 75.0 mi/h.",
    "A journey of one mile can be described using kilometers.",
    "Do not assume one mile is equal to an arbitrary length.",
    "The speedometer shows both miles per hour and kilometers per hour.",
    "Two instruments have similar dimensions but different calibrations.",
])
def test_unrecognized_or_non_equivalence_sentences_do_not_false_block(not_claim):
    assert check_narrated_unit_equivalences(inventory(not_claim))=={}


def test_comprehensive_certification_is_never_implied():
    with pytest.raises(NarrationUnitEquivalenceError):
        check_narrated_unit_equivalences({"slides":[]})
    with pytest.raises(NarrationUnitEquivalenceError):
        check_narrated_unit_equivalences({"slides":[{"narration":"x"*4000}]})
    with pytest.raises(NarrationUnitEquivalenceError):
        check_narrated_unit_equivalences({"slides":[{"title":"missing narration"}]})
