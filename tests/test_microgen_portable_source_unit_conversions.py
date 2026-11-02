"""Source-grounded independent unit conversion facts; synthetic fixtures only."""
import copy
import tempfile
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_portable_source_unit_conversions import (
    UnitConversionProofError,verified_source_unit_conversions,
)
from microgen_source_passage_discovery import discover_passages
from microgen_pronunciation_closed_loop import sha_file


def build_case(root):
    source=root/"source.pdf"
    pdf=fitz.open();page=pdf.new_page()
    page.insert_text((45,88),"7.2 Unit Conversion",fontsize=14)
    page.insert_textbox(fitz.Rect(45,140,515,220),
        "The length of 1 mile is approximately 1.609 km. "
        "Using unit ratios helps compare road distances.",fontsize=12)
    page.insert_textbox(fitz.Rect(45,245,515,320),
        "One 1 in. distance equals 2.54 cm in the length table. "
        "This relationship has an exactly defined conversion factor.",fontsize=12)
    page.insert_textbox(fitz.Rect(45,340,515,445),
        "A car moving at 38.0 m/s is compared with a posted speed limit "
        "of 75.0 mi/h. The driver is exceeding the posted speed limit.",fontsize=12)
    page.insert_text((45,530),"7.3 Next Section",fontsize=14)
    page.insert_textbox(fitz.Rect(45,550,515,650),
        "A different concept must not count for this unit section.",fontsize=12)
    pdf.save(source);pdf.close()
    evidence=discover_passages(source,"Unit Conversion","Next Section")
    p1=next(x for x in evidence["passages"] if "1 mile" in x["text"])
    p2=next(x for x in evidence["passages"] if "2.54 cm" in x["text"])
    p3=next(x for x in evidence["passages"] if "38.0 m/s" in x["text"])
    manifest={"source_pdf_sha256":sha_file(source),
       "start_marker":"Unit Conversion","next_section_marker":"Next Section",
       "source_unit_conversion_claims":[{
         "slide":1,"source_page":1,
         "source_passage_ids":[p1["passage_id"]],
         "source_anchor":"The length of 1 mile",
         "source_value_literal":"1","source_unit":"mile",
         "target_value_literal":"1.609","target_unit":"km"
       },{
         "slide":2,"source_page":1,
         "source_passage_ids":[p2["passage_id"]],
         "source_anchor":"One 1 in. distance equals",
         "source_value_literal":"1","source_unit":"in.",
         "target_value_literal":"2.54","target_unit":"cm"
       }]}
    narration={"slides":[{"source_page":1},{"source_page":1},
                          {"source_page":1}]}
    return source,manifest,narration,p3


def test_two_source_verified_length_factors_and_old_manifest_compatibility():
    with tempfile.TemporaryDirectory() as td:
        source,manifest,narr,_=build_case(Path(td))
        before=sha_file(source)
        proof=verified_source_unit_conversions(source,manifest,narr)
        assert len(proof)==2
        assert proof[1]["quantity_dimension"]=="length"
        assert proof[1]["target_rounding_places"]==3
        assert proof[2]["target_rounding_places"]==2
        assert proof[1]["source_literal_pairs_verified"]
        assert all(not p["physical_model_complete_semantics_proven"] for p in proof.values())
        assert sha_file(source)==before
        assert verified_source_unit_conversions(source,{},narr)=={}


def test_false_speed_limit_equality_rejected_despite_real_source_numbers():
    with tempfile.TemporaryDirectory() as td:
        source,manifest,narr,p3=build_case(Path(td))
        claim={"slide":3,"source_page":1,"source_passage_ids":[p3["passage_id"]],
           "source_anchor":"A car moving at 38.0",
           "source_value_literal":"38.0","source_unit":"m/s",
           "target_value_literal":"75.0","target_unit":"mi/h"}
        manifest["source_unit_conversion_claims"].append(claim)
        with pytest.raises(UnitConversionProofError,match="numerically inconsistent"):
            verified_source_unit_conversions(source,manifest,narr)


@pytest.mark.parametrize("fault",[
    "hash","wrong_page","missing_id","anchor","wrong_src_number",
    "wrong_target_number","unit_dimension","unknown_unit","duplicate_slide",
    "extra_claims","source_num_shape","zero","wrong_narration_page"
])
def test_forged_source_or_wrong_conversion_claim_fails_closed(fault):
    with tempfile.TemporaryDirectory() as td:
        source,manifest,narr,_=build_case(Path(td))
        claim=manifest["source_unit_conversion_claims"][0]
        if fault=="hash":manifest["source_pdf_sha256"]="0"*64
        elif fault=="wrong_page":claim["source_page"]=2
        elif fault=="missing_id":claim["source_passage_ids"]=["fake"]
        elif fault=="anchor":claim["source_anchor"]="A made up formula"
        elif fault=="wrong_src_number":claim["source_value_literal"]="2"
        elif fault=="wrong_target_number":claim["target_value_literal"]="1.60934"
        elif fault=="unit_dimension":claim["target_unit"]="m/s"
        elif fault=="unknown_unit":claim["source_unit"]="smoot"
        elif fault=="duplicate_slide":
            manifest["source_unit_conversion_claims"][1]["slide"]=1
        elif fault=="extra_claims":manifest["source_unit_conversion_claims"]=[claim]*22
        elif fault=="source_num_shape":claim["source_value_literal"]="1e0"
        elif fault=="zero":claim["source_value_literal"]="0"
        elif fault=="wrong_narration_page":narr["slides"][0]["source_page"]=2
        with pytest.raises(UnitConversionProofError):
            verified_source_unit_conversions(source,manifest,narr)


def test_supported_strict_speed_comparison_matches_si_with_rounding_limits():
    with tempfile.TemporaryDirectory() as td:
        source,manifest,narr,p3=build_case(Path(td))
        manifest["source_unit_conversion_claims"].append({
            "slide":3,"source_page":1,
            "source_passage_ids":[p3["passage_id"]],
            "source_anchor":"A car moving at 38.0",
            "source_comparison_anchor":"The driver is exceeding the posted speed limit",
            "source_value_literal":"38.0","source_unit":"m/s",
            "target_value_literal":"75.0","target_unit":"mi/h",
            "relation":"greater_than",
        })
        result=verified_source_unit_conversions(source,manifest,narr)
        assert len(result)==3 and result[3]["relation"]=="greater_than"
        assert result[3]["quantity_dimension"]=="speed"
        assert not result[3]["physical_model_complete_semantics_proven"]


@pytest.mark.parametrize("error",[
    "wrong_direction","missing_comparison_source","fake_source_conclusion",
    "unknown_comparison","different_units"
])
def test_invalid_comparison_source_or_direction_rejected(error):
    with tempfile.TemporaryDirectory() as td:
        source,manifest,narr,p3=build_case(Path(td))
        claim={
            "slide":3,"source_page":1,"source_passage_ids":[p3["passage_id"]],
            "source_anchor":"A car moving at 38.0",
            "source_comparison_anchor":"The driver is exceeding the posted speed limit",
            "source_value_literal":"38.0","source_unit":"m/s",
            "target_value_literal":"75.0","target_unit":"mi/h",
            "relation":"greater_than",
        }
        if error=="wrong_direction":claim["relation"]="less_than"
        elif error=="missing_comparison_source":claim.pop("source_comparison_anchor")
        elif error=="fake_source_conclusion":
            claim["source_comparison_anchor"]="The driver is below the posted limit"
        elif error=="unknown_comparison":claim["relation"]="approximately"
        elif error=="different_units":claim["target_unit"]="km"
        manifest["source_unit_conversion_claims"].append(claim)
        with pytest.raises(UnitConversionProofError):
            verified_source_unit_conversions(source,manifest,narr)
