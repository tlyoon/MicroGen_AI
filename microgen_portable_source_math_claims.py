"""Typed, source-grounded quantitative check for right-triangle height examples.

Narrow calculation template only. Not general symbolic algebra, scientific truth
or formal academic approval. All source PDF and original figures remain private.
"""
from __future__ import annotations
import math
from pathlib import Path
import re
import pymupdf as fitz


class SourceMathClaimError(ValueError):
    pass


def verified_source_math_claims(pdf: fitz.Document, manifest: dict,
                                vector_equations: dict,
                                source_figure_evidence: dict) -> dict:
    claims=manifest.get("source_math_claims",[])
    if not isinstance(claims,list) or len(claims)>20:
        raise SourceMathClaimError("Invalid source-grounded claim inventory")
    found={}
    for item in claims:
        if not isinstance(item,dict):
            raise SourceMathClaimError("Malformed quantitative claim")
        slide=item.get("slide"); figure_slide=item.get("figure_slide")
        formula=item.get("formula")
        pageno=item.get("source_page")
        distance=item.get("horizontal_distance_m")
        angle=item.get("elevation_degrees")
        claim=item.get("claimed_height_m")
        precision=item.get("precision_decimals")
        labels=item.get("source_figure_text_terms")
        claimed_text=item.get("source_equation_answer_text")
        if (type(slide) is not int or slide in found
            or type(figure_slide) is not int
            or formula!="right_triangle_tangent_height"
            or type(pageno) is not int or not 1<=pageno<=len(pdf)
            or slide not in vector_equations
            or figure_slide not in source_figure_evidence
            or vector_equations[slide]["source_page"]!=pageno
            or source_figure_evidence[figure_slide]["source_page"]!=pageno
            or any(type(x) not in (int,float) or not math.isfinite(x)
                   for x in (distance,angle,claim))
            or not 0<distance<=1e8 or not 0<angle<89.9 or claim<=0
            or type(precision) is not int or not 0<=precision<=6
            or not isinstance(labels,list) or not 2<=len(labels)<=5
            or any(not isinstance(x,str) or not 2<=len(x)<=35 for x in labels)
            or not isinstance(claimed_text,str) or not re.fullmatch(
                r"\d+(?:\.\d+)? m",claimed_text)):
            raise SourceMathClaimError("Unbounded, unsupported or ungrounded mathematics")
        region=fitz.Rect(source_figure_evidence[figure_slide]["source_bbox"])
        figure_text=" ".join(pdf[pageno-1].get_text(clip=region).split())
        if any(s not in figure_text for s in labels):
            raise SourceMathClaimError("Measured values absent from original figure source")
        # The declared numbers must themselves occur as measured source values;
        # a correct answer from different invented numbers is not source-grounded.
        distances=[float(x) for x in re.findall(
            r"(?<![\w.])(\d+(?:\.\d+)?)\s*m\b",figure_text,re.I)]
        angles=[float(x) for x in re.findall(
            r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:°|degrees\b)",
            figure_text,re.I)]
        if (not any(abs(x-distance)<1e-7 for x in distances)
            or not any(abs(x-angle)<1e-7 for x in angles)):
            raise SourceMathClaimError("Declared angle or distance differs from source measurements")
        eq_region=fitz.Rect(vector_equations[slide]["source_bbox"])
        eq_text=" ".join(pdf[pageno-1].get_text(clip=eq_region).split())
        if claimed_text not in eq_text:
            raise SourceMathClaimError("Reported numerical answer absent from source equation")
        source_value=float(claimed_text.removesuffix(" m"))
        if abs(source_value-claim)>1e-7:
            raise SourceMathClaimError("Claimed result does not match literal source equation")
        predicted=distance*math.tan(math.radians(angle))
        # Compare reported precision only: rounding from an exact trig result.
        # Avoid a brittle stricter equality than the source's stated precision.
        if abs(round(predicted,precision)-claim)>10**(-precision)*.001:
            raise SourceMathClaimError("Independent tangent calculation disagrees with result")
        found[slide]={
            "formula":formula,
            "source_page":pageno,
            "figure_slide":figure_slide,
            "horizontal_distance_m":float(distance),
            "elevation_degrees":float(angle),
            "recomputed_height_m":round(predicted,8),
            "source_reported_height_m":float(claim),
            "precision_decimals":precision,
            "source_figure_measurements_literal_verified":True,
            "source_equation_result_literal_verified":True,
            "typed_numerical_claim_consistent":True,
            "complete_mathematical_semantics_certified":False,
            "complete_academic_certification":False,
            "publication_allowed":False
        }
    return found
