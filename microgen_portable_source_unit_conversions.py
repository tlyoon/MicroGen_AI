"""Typed, source-linked and independently computed SI unit conversions.

Only narrowly supported length and speed units; original PDF source numeric
statements MUST contain the value/unit pair. This cannot certify all physics.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_section_contract import clean
from microgen_source_passage_discovery import discover_passages


class UnitConversionProofError(ValueError):
    pass


# Exact SI definitions. In particular the international mile is exactly
# 1609.344 metres, whereas the *printed* textbook factor may be rounded.
_SI_FACTOR={
    "m":("length",Decimal("1")),
    "cm":("length",Decimal("0.01")),
    "km":("length",Decimal("1000")),
    "ft":("length",Decimal("0.3048")),
    "in.":("length",Decimal("0.0254")),
    "mile":("length",Decimal("1609.344")),
    "mi":("length",Decimal("1609.344")),
    "m/s":("speed",Decimal("1")),
    "km/h":("speed",Decimal("1000")/Decimal("3600")),
    "mi/h":("speed",Decimal("1609.344")/Decimal("3600"))
}


def _declared_number(value):
    if (type(value) is not str or
        not re.fullmatch(r"(?:0|[1-9]\d{0,8})(?:\.\d{1,6})?",value)):
        raise UnitConversionProofError("Finite nonnegative literal with bounded decimal places required")
    try:
        result=Decimal(value)
    except InvalidOperation as exc:
        raise UnitConversionProofError("Invalid numeric conversion claim") from exc
    if result<=0:
        raise UnitConversionProofError("Only positive, nonzero measurement magnitudes supported")
    return result


def _pair_occurs(text,number,unit):
    pattern=(r"(?<![A-Za-z0-9.])"+re.escape(number)+r"\s*"+
             re.escape(unit)+r"(?![A-Za-z0-9])")
    return bool(re.search(pattern,text))


def verified_source_unit_conversions(source:Path,manifest:dict,narration:dict):
    rows=manifest.get("source_unit_conversion_claims",[])
    if not isinstance(rows,list) or len(rows)>20:
        raise UnitConversionProofError("Malformed/beyond-bounded source unit claims")
    if not rows:
        return {}
    source=Path(source)
    before=sha_file(source)
    if manifest.get("source_pdf_sha256")!=before:
        raise UnitConversionProofError("Original source PDF changed")
    try:
        packet=discover_passages(source,manifest["start_marker"],
            manifest.get("next_section_marker"),
            end_of_pdf=manifest.get("end_of_pdf") is True)
    except (KeyError,ValueError,TypeError) as exc:
        raise UnitConversionProofError("Source section boundaries not independently found") from exc
    by_id={p["passage_id"]:p for p in packet["passages"]}
    slides=narration.get("slides")
    if not isinstance(slides,list):
        raise UnitConversionProofError("Narration slide inventory unavailable")
    result={}
    for claim in rows:
        if not isinstance(claim,dict):
            raise UnitConversionProofError("Malformed individual source conversion claim")
        slide=claim.get("slide")
        page=claim.get("source_page")
        ids=claim.get("source_passage_ids")
        anchor=claim.get("source_anchor")
        if (type(slide) is not int or not 1<=slide<=len(slides) or slide in result
            or type(page) is not int or page!=slides[slide-1].get("source_page")
            or not isinstance(ids,list) or not 1<=len(ids)<=5
            or len(ids)!=len(set(ids))
            or any(type(i) is not str or i not in by_id
                   or by_id[i]["source_page"]!=page for i in ids)
            or not isinstance(anchor,str) or not 8<=len(anchor)<=160):
            raise UnitConversionProofError("Conversion lacks unique slide, page and source passage IDs")
        text=" ".join(by_id[i]["text"] for i in ids)
        if clean(anchor) not in clean(text):
            raise UnitConversionProofError("Conversion source anchor absent from original PDF")
        unit_a=claim.get("source_unit")
        unit_b=claim.get("target_unit")
        if (not isinstance(unit_a,str) or not isinstance(unit_b,str)
            or unit_a not in _SI_FACTOR or unit_b not in _SI_FACTOR
            or _SI_FACTOR[unit_a][0]!=_SI_FACTOR[unit_b][0]
            or unit_a==unit_b):
            raise UnitConversionProofError("Units undefined, different dimensions or identical")
        literal_a=claim.get("source_value_literal")
        literal_b=claim.get("target_value_literal")
        value_a=_declared_number(literal_a)
        value_b=_declared_number(literal_b)
        if not (_pair_occurs(text,literal_a,unit_a)
                and _pair_occurs(text,literal_b,unit_b)):
            raise UnitConversionProofError("Declared measurement unit/value absent from cited source")
        relation=claim.get("relation","equal_with_rounding")
        if relation not in ("equal_with_rounding","greater_than","less_than"):
            raise UnitConversionProofError("Unsupported dimensioned relation")
        independent=value_a*_SI_FACTOR[unit_a][1]/_SI_FACTOR[unit_b][1]
        places=len(literal_b.split(".")[1]) if "." in literal_b else 0
        half_ulp=Decimal("0.5")*(Decimal(10)**(-places))
        if relation=="equal_with_rounding":
            relative_difference=abs(value_b-independent)/independent
            if abs(value_b-independent)>half_ulp or relative_difference>Decimal("0.05"):
                raise UnitConversionProofError("Source-cited conversion numerically inconsistent with SI")
        else:
            support=claim.get("source_comparison_anchor")
            if (not isinstance(support,str) or not 12<=len(support)<=180
                or clean(support) not in clean(text)
                or not re.search(
                  (r"exceed|higher|greater|faster|above|larger|more" if relation=="greater_than"
                   else r"below|less|lower|slower|smaller"),
                  support,flags=re.I)):
                raise UnitConversionProofError("Comparison requires an explicit matching source conclusion")
            unc_a=Decimal("0.5")*(Decimal(10)**(
                -(len(literal_a.split(".")[1]) if "." in literal_a else 0)))
            unc_b=half_ulp
            # Require the strict inequality even at the stated measurement
            # rounding limits; near-boundary comparisons fail conservatively.
            lower_a=(value_a-unc_a)*_SI_FACTOR[unit_a][1]
            upper_a=(value_a+unc_a)*_SI_FACTOR[unit_a][1]
            lower_b=(value_b-unc_b)*_SI_FACTOR[unit_b][1]
            upper_b=(value_b+unc_b)*_SI_FACTOR[unit_b][1]
            if ((relation=="greater_than" and not lower_a>upper_b)
                or (relation=="less_than" and not upper_a<lower_b)):
                raise UnitConversionProofError("Source-cited strict unit comparison contradicts SI")
        result[slide]={
            "source_page":page,
            "source_passage_ids":ids,
            "source_pdf_sha256":before,
            "source_value_literal":literal_a,"source_unit":unit_a,
            "target_value_literal":literal_b,"target_unit":unit_b,
            "quantity_dimension":_SI_FACTOR[unit_a][0],
            "relation":relation,
            "independent_si_conversion_verified":True,
            "target_rounding_places":places,
            "source_literal_pairs_verified":True,
            "physical_model_complete_semantics_proven":False,
            "publication_allowed":False
        }
    if sha_file(source)!=before:
        raise UnitConversionProofError("Source PDF changed during independent unit checks")
    return result
