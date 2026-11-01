"""Synthetic typed trigonometric example tests; no textbook source in GitHub."""
import tempfile
import math
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_portable_source_math_claims import (
    SourceMathClaimError, verified_source_math_claims)


def fixture():
    pdf=fitz.open()
    page=pdf.new_page()
    page.insert_text((70,110),"50.0 m     25.0 degrees",fontsize=16)
    page.insert_text((70,205),"h = (50.0 m) tan 25.0 = 23.3 m",fontsize=15)
    figs={1:{"source_page":1,"source_bbox":[60,90,380,130],
              "source_caption_label_nearby_verified":True,
              "original_pdf_raster_pixels_identical":True}}
    equations={2:{"source_page":1,"source_bbox":[60,180,440,225],
                  "original_pdf_vector_copied":True}}
    row={
        "slide":2,"figure_slide":1,"source_page":1,
        "formula":"right_triangle_tangent_height",
        "horizontal_distance_m":50.0,
        "elevation_degrees":25.0,
        "claimed_height_m":23.3,
        "precision_decimals":1,
        "source_figure_text_terms":["50.0 m","25.0"],
        "source_equation_answer_text":"23.3 m"}
    return pdf,figs,equations,row


def test_independently_recomputed_tree_height_and_both_source_regions():
    pdf,fig,eq,row=fixture()
    try:
        result=verified_source_math_claims(pdf,{"source_math_claims":[row]},eq,fig)
        assert set(result)=={2}
        evidence=result[2]
        assert evidence["recomputed_height_m"]==23.31538291
        assert evidence["source_reported_height_m"]==23.3
        assert evidence["typed_numerical_claim_consistent"]
        assert evidence["source_figure_measurements_literal_verified"]
        assert evidence["source_equation_result_literal_verified"]
        assert not evidence["complete_mathematical_semantics_certified"]
        assert not evidence["publication_allowed"]
    finally:
        pdf.close()


@pytest.mark.parametrize("fault",[
    "distance","angle","answer","units","source_tokens","source_answer",
    "unlinked_equation","unlinked_figure","negative_angle","fractional_precision",
    "wrong_formula","float_slide","consistent_but_forged_measurements",
])
def test_wrong_or_unsupported_claims_are_not_silently_accepted(fault):
    pdf,fig,eq,row=fixture()
    try:
        if fault=="distance":row["horizontal_distance_m"]=55
        elif fault=="angle":row["elevation_degrees"]=30
        elif fault=="answer":row["claimed_height_m"]=25.0
        elif fault=="units":row["source_equation_answer_text"]="23.3 ft"
        elif fault=="source_tokens":row["source_figure_text_terms"]=["55.0 m","25.0"]
        elif fault=="source_answer":row["source_equation_answer_text"]="24.3 m"
        elif fault=="unlinked_equation":eq.clear()
        elif fault=="unlinked_figure":fig.clear()
        elif fault=="negative_angle":row["elevation_degrees"]=-25
        elif fault=="fractional_precision":row["precision_decimals"]=1.5
        elif fault=="wrong_formula":row["formula"]="cotangent_height"
        elif fault=="float_slide":row["slide"]=2.0
        elif fault=="consistent_but_forged_measurements":
            row["horizontal_distance_m"]=100.0
            row["elevation_degrees"]=math.degrees(math.atan(23.3/100.0))
        with pytest.raises(SourceMathClaimError):
            verified_source_math_claims(pdf,{"source_math_claims":[row]},eq,fig)
    finally:
        pdf.close()


def test_optional_math_claims_preserve_old_section_contracts():
    pdf,fig,eq,row=fixture()
    try:
        assert verified_source_math_claims(pdf,{},eq,fig)=={}
        with pytest.raises(SourceMathClaimError):
            verified_source_math_claims(pdf,{"source_math_claims":"untrusted"},eq,fig)
        with pytest.raises(SourceMathClaimError):
            verified_source_math_claims(pdf,{"source_math_claims":[row,row]},eq,fig)
    finally:
        pdf.close()
