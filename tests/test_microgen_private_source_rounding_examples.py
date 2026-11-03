"""Synthetic original PDF source-backed decimal rounding, not copyrighted text."""
import tempfile
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_private_source_rounding_examples import (
    SourceRoundingProofError,check_decimal_rounding,
    verified_original_source_rounding)
from microgen_source_passage_discovery import discover_passages
from microgen_pronunciation_closed_loop import sha_file


def fixture(root):
    source=root/"source.pdf"
    doc=fitz.open()
    page=doc.new_page()
    page.insert_text((45,191),"B.2 Numerical Precision",fontsize=14)
    page.insert_textbox(fitz.Rect(45,215,525,410),
       "A synthetic rounding rule is illustrated when 1.346 becomes 1.35 "
       "and a second synthetic value 1.343 becomes 1.34 after rounding "
       "to two decimal places. These two different values are both "
       "useful for explaining a measured numerical result. "*2,fontsize=12)
    page=doc.new_page()
    page.insert_text((45,310),"B.3 Following Physics",fontsize=13)
    page.insert_textbox(fitz.Rect(45,330,525,470),
       "This next source section is unrelated and must never be cited "
       "to support a previously discussed numerical precision rule. "*3,fontsize=11)
    doc.save(source);doc.close()
    packet=discover_passages(source,"B.2 Numerical Precision","B.3 Following Physics")
    pid=next(x["passage_id"] for x in packet["passages"] if x["source_page"]==1)
    claims=[{
      "slide":1,"source_page":1,"source_passage_ids":[pid],
      "source_anchor":"A synthetic rounding rule is illustrated",
      "original_value_literal":value,"reported_value_literal":answer,
      "decimal_places":2
      } for value,answer in [("1.346","1.35"),("1.343","1.34")]]
    manifest={
      "source_pdf_sha256":sha_file(source),
      "start_marker":"B.2 Numerical Precision",
      "next_section_marker":"B.3 Following Physics",
      "original_source_decimal_rounding_claims":claims,
    }
    narrative={"slides":[{"source_page":1,
       "narration":"The first example 1.346 gives 1.35 and the second example "
                   "1.343 gives 1.34 after the specified rounding."}]}
    return source,manifest,narrative


@pytest.mark.parametrize("src,out",[
    ("1.346","1.35"),("1.343","1.34"),
    ("1.345","1.34"),("1.355","1.36")
])
def test_independent_decimal_rounding_including_half_to_even_ties(src,out):
    v=check_decimal_rounding(src,out,2)
    assert v["independent_decimal_rounding_verified"]
    assert v["rounding_rule"]=="ROUND_HALF_EVEN"


@pytest.mark.parametrize("src,out,places",[
    ("1.346","1.34",2),("1.343","1.35",2),
    ("1.345","1.35",2),("1.355","1.35",2),
    ("1.346","1.350",2),("NaN","1.35",2),
    ("1.346","Infinity",2),("1.346","1.35",-1),
    ("1.346","1.35",9)
])
def test_incorrect_rounding_or_precision_is_not_accepted(src,out,places):
    with pytest.raises(SourceRoundingProofError):
        check_decimal_rounding(src,out,places)


def test_both_original_source_examples_and_spoken_explanations_verified():
    with tempfile.TemporaryDirectory() as td:
        source,m,n=fixture(Path(td))
        old=sha_file(source)
        v=verified_original_source_rounding(source,m,n)
        assert len(v)==1 and len(v[1])==2
        assert all(x["source_literals_verified"] for x in v[1])
        assert all(x["narration_literals_verified"] for x in v[1])
        assert not any(x["academic_certification_complete"] for x in v[1])
        assert all(x["publication_allowed"] is False for x in v[1])
        assert sha_file(source)==old


@pytest.mark.parametrize("fault",[
 "wrong_pdf_sha","wrong_page","wrong_passage",
 "fake_source_anchor","wrong_source_value","invented_output",
 "wrong_rounding","narration_missing_output","duplicate_claim"
])
def test_adversarial_source_or_spoken_value_rejected(fault):
    with tempfile.TemporaryDirectory() as td:
        source,m,n=fixture(Path(td))
        c=m["original_source_decimal_rounding_claims"][0]
        if fault=="wrong_pdf_sha":m["source_pdf_sha256"]="f"*64
        elif fault=="wrong_page":c["source_page"]=2
        elif fault=="wrong_passage":c["source_passage_ids"]=["invented"]
        elif fault=="fake_source_anchor":c["source_anchor"]="Not an original physical source"
        elif fault=="wrong_source_value":c["original_value_literal"]="1.347"
        elif fault=="invented_output":c["reported_value_literal"]="1.36"
        elif fault=="wrong_rounding":c["decimal_places"]=3
        elif fault=="narration_missing_output":
            n["slides"][0]["narration"]="The first example is removed."
        elif fault=="duplicate_claim":
            m["original_source_decimal_rounding_claims"].append(c.copy())
        with pytest.raises((SourceRoundingProofError,ValueError)):
            verified_original_source_rounding(source,m,n)


def test_legacy_section_without_declared_rounding_remains_valid():
    with tempfile.TemporaryDirectory() as td:
        source,m,n=fixture(Path(td))
        del m["original_source_decimal_rounding_claims"]
        assert verified_original_source_rounding(source,m,n)=={}
