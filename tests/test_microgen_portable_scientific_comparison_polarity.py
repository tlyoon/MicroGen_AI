"""Source-verified spoken speed-limit polarity; synthetic factual cases."""
import copy
import pytest
from microgen_portable_scientific_comparison_polarity import (
    checked_source_comparison_narration,ScientificComparisonContradiction,
)


def case(speech="After converting, the driver is found to exceed the limit.",
         source="The driver is indeed exceeding the speed limit and should slow down.",
         relation="greater_than"):
    m={"source_unit_conversion_claims":[{
        "slide":1,"relation":relation,"source_comparison_anchor":source}]}
    n={"slides":[{"narration":speech}]}
    q={1:{"relation":relation,"quantity_dimension":"speed",
        "independent_si_conversion_verified":True,
        "source_page":1,"source_passage_ids":["p01_012_source"]}}
    return m,n,q


def test_source_confirmed_realistic_exceeding_speed_limit():
    evidence=checked_source_comparison_narration(*case())
    assert len(evidence)==1
    assert evidence[1]["definite_narrated_limit_conclusion_matches_source"]
    assert evidence[1]["source_passage_ids"]==["p01_012_source"]
    assert not evidence[1]["academic_completeness_proven"]


@pytest.mark.parametrize("wrong",[
    "The driver is below the speed limit.",
    "The car is under the limit.",
    "The driver is not exceeding the speed limit.",
    "The driver does not exceed the limit.",
    "The vehicle is within the posted speed limit.",
])
def test_direct_false_narration_contradicts_verified_source(wrong):
    with pytest.raises(ScientificComparisonContradiction,match="spoken"):
        checked_source_comparison_narration(*case(speech=wrong))


def test_false_source_direction_rejected_even_if_si_proof_exists():
    with pytest.raises(ScientificComparisonContradiction,match="original cited"):
        checked_source_comparison_narration(*case(
           source="The driver is not exceeding the speed limit."))


@pytest.mark.parametrize("narration",[
    "Imagine a driver who is below a speed limit.",
    "If the driver is below the limit, check the unit conversion.",
    "Could the driver be below the posted speed limit?",
    "It would be wrong to say the driver is below the speed limit.",
    "The driver might be below the posted speed limit.",
    "The driver is traveling at 38.0 meters per second.",
    "The vehicle speed and posted limit must have common units.",
])
def test_speculative_and_unrecognized_text_does_not_overblock(narration):
    assert checked_source_comparison_narration(*case(speech=narration))=={}


def test_reverse_direction_matches_correct_source_and_rejects_wrong():
    manifest,narration,proof=case(
        speech="The driver is below the posted limit.",
        source="The driver is below the speed limit.",
        relation="less_than")
    assert len(checked_source_comparison_narration(manifest,narration,proof))==1
    narration["slides"][0]["narration"]="The driver is exceeding the speed limit."
    with pytest.raises(ScientificComparisonContradiction):
        checked_source_comparison_narration(manifest,narration,proof)


@pytest.mark.parametrize("mode",[
    "no_claims","equality","not_speed","missing_si","wrong_source_relation",
    "unsafe_narration","unsupported_source_text",
])
def test_optional_and_unsafe_cases_are_bounded(mode):
    m,n,q=case()
    if mode=="no_claims":m["source_unit_conversion_claims"]=[]
    if mode=="equality":m["source_unit_conversion_claims"][0]["relation"]="equal_with_rounding"
    if mode=="not_speed":q[1]["quantity_dimension"]="length"
    if mode=="missing_si":q={}
    if mode=="wrong_source_relation":q[1]["relation"]="less_than"
    if mode=="unsafe_narration":n["slides"][0]["narration"]="a"*3501
    if mode=="unsupported_source_text":
        m["source_unit_conversion_claims"][0]["source_comparison_anchor"]="Speed was computed."
    if mode in ("missing_si","wrong_source_relation","unsafe_narration"):
        with pytest.raises(ScientificComparisonContradiction):
            checked_source_comparison_narration(m,n,q)
    else:
        assert checked_source_comparison_narration(m,n,q)=={}
