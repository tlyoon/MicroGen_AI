"""Original source-verified Decimal rounding EXAMPLES, optional/private QA.

Verifies only explicitly reported numerical rounding claims. Decimal numeric
quantize is not general physics semantic inference or a language model.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
import re

from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_section_contract import clean
from microgen_source_passage_discovery import discover_passages
from microgen_private_source_significant_figures import _decimal_literal, SignificantFiguresProofError


class SourceRoundingProofError(ValueError):
    pass


def check_decimal_rounding(input_literal:str,reported_literal:str,places:int)->dict:
    if type(places) is not int or not 0<=places<=6:
        raise SourceRoundingProofError("Bounded decimal precision required")
    try:
        original=_decimal_literal(input_literal)
        reported=_decimal_literal(reported_literal)
    except SignificantFiguresProofError as exc:
        raise SourceRoundingProofError("Unbounded or invalid decimal rounding input") from exc
    quantum=Decimal(1).scaleb(-places)
    expected=original.quantize(quantum,rounding=ROUND_HALF_EVEN)
    if (reported!=expected or reported.as_tuple().exponent!=-places):
        raise SourceRoundingProofError("Reported decimal rounding contradicts arithmetic or precision")
    return {"original":input_literal,"reported":reported_literal,
            "rounding_decimal_places":places,"rounding_rule":"ROUND_HALF_EVEN",
            "independent_decimal_rounding_verified":True,
            "all_scientific_semantics_proven":False}


def _has_lit(text:str,literal:str)->bool:
    return bool(re.search(r"(?<![0-9.])"+re.escape(literal)+r"(?![0-9])",text))


def verified_original_source_rounding(source:Path,manifest:dict,narration:dict)->dict:
    rows=manifest.get("original_source_decimal_rounding_claims",[])
    if not isinstance(rows,list) or len(rows)>20:
        raise SourceRoundingProofError("Invalid bounded rounding claim inventory")
    if not rows:return {}
    src=Path(source)
    old_sha=sha_file(src)
    if manifest.get("source_pdf_sha256")!=old_sha:
        raise SourceRoundingProofError("Original source SHA mismatch")
    packet=discover_passages(src,manifest["start_marker"],
        manifest.get("next_section_marker"),
        end_of_pdf=manifest.get("end_of_pdf") is True)
    by_id={p["passage_id"]:p for p in packet["passages"]}
    slides=narration.get("slides")
    if not isinstance(slides,list) or not 1<=len(slides)<=60:
        raise SourceRoundingProofError("Authored slide inventory missing")
    result={}
    seen=set()
    for item in rows:
        if not isinstance(item,dict):
            raise SourceRoundingProofError("Malformed original source rounding claim")
        slide=item.get("slide")
        page=item.get("source_page")
        ids=item.get("source_passage_ids")
        anchor=item.get("source_anchor")
        before=item.get("original_value_literal")
        after=item.get("reported_value_literal")
        places=item.get("decimal_places")
        pair=(slide,before,after)
        if (type(slide) is not int or not 1<=slide<=len(slides)
            or pair in seen
            or type(page) is not int or page!=slides[slide-1].get("source_page")
            or not isinstance(ids,list) or not 1<=len(ids)<=5
            or len(set(ids))!=len(ids)
            or any(type(x) is not str or x not in by_id
                   or by_id[x]["source_page"]!=page for x in ids)
            or type(anchor) is not str or not 12<=len(anchor)<=160):
            raise SourceRoundingProofError("Rounding claim must cite unambiguous original page/passage")
        seen.add(pair)
        body=" ".join(by_id[x]["text"] for x in ids)
        if clean(anchor) not in clean(body):
            raise SourceRoundingProofError("Source anchor absent from actual original section")
        # Both original value and asserted rounded number must literally
        # appear in the independently recovered source AND spoken explanation.
        if (not isinstance(before,str) or not isinstance(after,str)
            or not _has_lit(body,before) or not _has_lit(body,after)):
            raise SourceRoundingProofError("Original source does not support both numeric literals")
        speech=slides[slide-1].get("narration")
        if (not isinstance(speech,str)
            or not _has_lit(speech,before) or not _has_lit(speech,after)):
            raise SourceRoundingProofError("Numerical example not explained in original narration")
        evidence=check_decimal_rounding(before,after,places)
        result.setdefault(slide,[]).append({
            "source_page":page,"source_passage_ids":ids,
            "source_pdf_sha256":old_sha,
            **evidence,
            "source_literals_verified":True,
            "narration_literals_verified":True,
            "academic_certification_complete":False,
            "publication_allowed":False
        })
    if sha_file(src)!=old_sha:
        raise SourceRoundingProofError("Original source modified during check")
    return result
