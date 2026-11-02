"""Synthetic bounded physical-dimension checks (no copyrighted source)."""
import copy
import tempfile
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_portable_source_dimensional_relations import (
    check_source_dimensional_relations,DimensionProofError,
    parse_dimension,_variable_definitions)
from microgen_source_passage_discovery import discover_passages
from microgen_pronunciation_closed_loop import sha_file


def synthetic_fixture(root):
    src=root/"source.pdf"
    pdf=fitz.open()
    p=pdf.new_page()
    p.insert_text((40,100),"7.2 Dimensional Analysis",fontsize=14)
    p.insert_textbox(fitz.Rect(40,140,520,270),
        "The speed v is related to acceleration a and elapsed time t. "
        "These measurable quantities may form a physically meaningful equation. "*3,
        fontsize=12)
    p=pdf.new_page()
    p.insert_textbox(fitz.Rect(40,100,520,265),
        "A description of circular motion relates acceleration a to speed v and radius r. "*4,
        fontsize=12)
    p.insert_text((40,350),"7.3 Next Chapter",fontsize=14)
    p.insert_textbox(fitz.Rect(40,380,520,500),
        "Unrelated next chapter should not enter this source. "*4,
        fontsize=12)
    pdf.save(src);pdf.close()
    passages=discover_passages(src,"Dimensional Analysis","Next Chapter")
    p1=next(p for p in passages["passages"] if p["source_page"]==1)
    p2=next(p for p in passages["passages"] if p["source_page"]==2)
    manifest={
        "source_pdf_sha256":sha_file(src),
        "start_marker":"Dimensional Analysis",
        "next_section_marker":"Next Chapter",
        "source_dimension_claims":[{
            "slide":1,"source_page":1,"source_passage_ids":[p1["passage_id"]],
            "source_anchor":"The speed v is related to acceleration",
            "required_source_terms":["speed","acceleration","time"],
            "variables":{"v":"L/T","a":"L/T**2","t":"T"},
            "lhs":"v","rhs":"a*t"
        },{
            "slide":2,"source_page":2,"source_passage_ids":[p2["passage_id"]],
            "source_anchor":"A description of circular motion relates acceleration",
            "required_source_terms":["circular","acceleration","radius"],
            "variables":{"v":"L/T","a":"L/T**2","r":"L"},
            "lhs":"a","rhs":"v**2/r"
        }]
    }
    narration={"slides":[{"source_page":1},{"source_page":2}]}
    return src,manifest,narration


def test_pure_dimension_algebra_covers_motion_and_circular_scaling():
    vars=_variable_definitions({"x":"L","t":"T","a":"L/T**2",
                                "v":"L/T","r":"L"})
    assert parse_dimension("x",vars)==parse_dimension("0.5*a*t**2",vars)
    assert parse_dimension("v",vars)==parse_dimension("a*t",vars)
    assert parse_dimension("a",vars)==parse_dimension("v**2/r",vars)
    assert parse_dimension("x + 2*x",vars)==(1,0,0)


def test_verified_source_evidence_and_dimension_consistency():
    with tempfile.TemporaryDirectory() as td:
        src,m,n=synthetic_fixture(Path(td))
        original_sha=sha_file(src)
        result=check_source_dimensional_relations(src,m,n)
        assert set(result)=={1,2}
        assert result[1]["dimensions_L_M_T"]==[1,0,-1]
        assert result[2]["dimensions_L_M_T"]==[1,0,-2]
        assert all(x["dimensionally_consistent"] for x in result.values())
        assert all(not x["physical_relationship_semantically_proven"]
                   for x in result.values())
        assert sha_file(src)==original_sha
        assert check_source_dimensional_relations(src,{
            "source_dimension_claims":[]},n)=={}


@pytest.mark.parametrize("bad_rhs",[
    "a*t*t","a+t","a*t**100","a*t**0.5","a*cos(t)",
    "a*__import__('os')","a*(t.__class__)","a*(unknown)"
])
def test_bad_formula_dimensions_or_unsafe_python_ast_are_rejected(bad_rhs):
    with tempfile.TemporaryDirectory() as td:
        src,m,n=synthetic_fixture(Path(td))
        m["source_dimension_claims"][0]["rhs"]=bad_rhs
        with pytest.raises(DimensionProofError):
            check_source_dimensional_relations(src,m,n)


@pytest.mark.parametrize("fault",[
    "source_hash","source_page","source_anchor","wrong_passage",
    "source_terms","bad_variable","duplicate_slide","bad_claims",
    "wrong_narration_page","unbounded_variables"
])
def test_wrong_claim_provenance_fails_closed(fault):
    with tempfile.TemporaryDirectory() as td:
        src,m,n=synthetic_fixture(Path(td))
        claim=m["source_dimension_claims"][0]
        if fault=="source_hash":m["source_pdf_sha256"]="0"*64
        elif fault=="source_page":claim["source_page"]=2
        elif fault=="source_anchor":claim["source_anchor"]="The answer is unrelated"
        elif fault=="wrong_passage":claim["source_passage_ids"]=["not-source"]
        elif fault=="source_terms":claim["required_source_terms"]=["speed","phantom"]
        elif fault=="bad_variable":claim["variables"]["v"]="L/F"
        elif fault=="duplicate_slide":m["source_dimension_claims"][1]["slide"]=1
        elif fault=="bad_claims":m["source_dimension_claims"]="untrusted"
        elif fault=="wrong_narration_page":n["slides"][0]["source_page"]=2
        elif fault=="unbounded_variables":claim["variables"]={f"v{i}":"L" for i in range(18)}
        with pytest.raises(DimensionProofError):
            check_source_dimensional_relations(src,m,n)


@pytest.mark.parametrize("expr",[
    "1/0","x**-99","x**(2+3)","x + t","[x]","x.__class__",
    "x if True else t", "x % t", "x @ t"
])
def test_unsafe_arithmetic_or_incompatible_addition_rejected(expr):
    variables=_variable_definitions({"x":"L","t":"T"})
    with pytest.raises(DimensionProofError):
        parse_dimension(expr,variables)
