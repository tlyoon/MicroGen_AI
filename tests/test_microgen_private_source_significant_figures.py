"""Only synthetic significant-figures arithmetic and fake source PDFs."""
import tempfile
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_private_source_significant_figures import (
    SignificantFiguresProofError,count_significant_digits,
    independently_round_product,verify_source_significant_figure_claims)
from microgen_pronunciation_closed_loop import sha_file
from microgen_source_passage_discovery import discover_passages


def case(root):
    path=root/"synthetic.pdf"
    pdf=fitz.open()
    pg=pdf.new_page()
    pg.insert_text((45,181),"B.2 Measured Area",fontsize=14)
    pg.insert_textbox(fitz.Rect(45,220,550,350),
        "A measured rectangle has length 12.71 m and width 3.46 m. "
        "A responsible experimenter computes a rounded final area of "
        "44.0 m2 while keeping intermediate results unrounded. "*3,
        fontsize=12)
    pg=pdf.new_page()
    pg.insert_text((45,250),"B.3 Later Topic",fontsize=14)
    pg.insert_textbox(fitz.Rect(45,280,540,430),
        "An unrelated following section includes an incorrect area estimate "
        "that should not be used to support the previous section. "*3,
        fontsize=12)
    pdf.save(path);pdf.close()
    original=discover_passages(path,"B.2 Measured Area","B.3 Later Topic")
    pid=next(x["passage_id"] for x in original["passages"] if x["source_page"]==1)
    m={
        "source_pdf_sha256":sha_file(path),
        "start_marker":"B.2 Measured Area",
        "next_section_marker":"B.3 Later Topic",
        "source_significant_figure_claims":[{
            "slide":1,"source_page":1,"source_passage_ids":[pid],
            "source_anchor":"A measured rectangle has length",
            "operation":"rectangular_area_m2",
            "length_m":"12.71","width_m":"3.46","reported_area_m2":"44.0"
        }]
    }
    n={"slides":[{"source_page":1,"narration":
        "Measured dimensions 12.71 m and 3.46 m give the reported area 44.0 square metres."}]}
    return path,m,n


def test_correct_original_source_provenance_and_area():
    with tempfile.TemporaryDirectory() as td:
        src,m,n=case(Path(td))
        result=verify_source_significant_figure_claims(src,m,n)
        assert result[1]["recomputed_reported_area"]=="44.0"
        assert result[1]["input_significant_digits"]==[4,3]
        assert result[1]["result_significant_digits"]==3
        assert result[1]["source_original_number_and_units_verified"]
        assert result[1]["reported_result_actually_narrated"]
        assert not result[1]["full_scientific_semantics_proven"]
        assert result[1]["publication_allowed"] is False


def test_literal_significant_figure_count_preserves_trailing_decimal_zeros():
    assert count_significant_digits("12.71")==4
    assert count_significant_digits("3.46")==3
    assert count_significant_digits("44.0")==3
    assert count_significant_digits("0.030")==2
    assert count_significant_digits("0.0075")==2
    with pytest.raises(SignificantFiguresProofError):
        count_significant_digits("1500")


@pytest.mark.parametrize("a,b,reported",[
    ("12.71","3.46","44"),
    ("12.71","3.46","44.00"),
    ("12.71","3.46","43.9"),
    ("12.71","3.46","43.98"),
    ("1500","3.46","5190"),
    ("0","3.46","0.0"),
    ("NaN","3.46","44.0"),
    ("12.71","Infinity","44.0"),
    ("12.71","3.46","-44.0"),
])
def test_false_or_ambiguous_numerical_precision_rejected(a,b,reported):
    with pytest.raises(SignificantFiguresProofError):
        independently_round_product(a,b,reported)


@pytest.mark.parametrize("fault",[
    "wrong_pdf_sha","wrong_page","wrong_passage","fake_anchor",
    "wrong_area_literal","fake_dimensions","missing_spoken_answer",
    "wrong_operation","duplicate_source_claim"
])
def test_suspicious_source_math_cannot_pass(fault):
    with tempfile.TemporaryDirectory() as td:
        src,m,n=case(Path(td))
        q=m["source_significant_figure_claims"][0]
        if fault=="wrong_pdf_sha":m["source_pdf_sha256"]="0"*64
        elif fault=="wrong_page":q["source_page"]=2
        elif fault=="wrong_passage":q["source_passage_ids"]=["invented"]
        elif fault=="fake_anchor":q["source_anchor"]="Completely invented original source"
        elif fault=="wrong_area_literal":q["reported_area_m2"]="43.9"
        elif fault=="fake_dimensions":q["length_m"]="12.72"
        elif fault=="missing_spoken_answer":n["slides"][0]["narration"]="Area is unknown."
        elif fault=="wrong_operation":q["operation"]="arbitrary_python_eval"
        elif fault=="duplicate_source_claim":m["source_significant_figure_claims"].append(q.copy())
        with pytest.raises(SignificantFiguresProofError):
            verify_source_significant_figure_claims(src,m,n)


def test_optional_empty_original_claim_inventory_is_backwards_compatible():
    with tempfile.TemporaryDirectory() as td:
        src,m,n=case(Path(td))
        m.pop("source_significant_figure_claims")
        assert verify_source_significant_figure_claims(src,m,n)=={}
