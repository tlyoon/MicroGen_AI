"""Optional original-source-cited significant-figure numeric QA.

Only explicit rectangular-area multiplication, matching metres to square metres;
uses bounded Decimal arithmetic, not Python eval or an authoring language model.
No claim of full scientific correctness or publication permission.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
import re

from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_section_contract import clean
from microgen_source_passage_discovery import discover_passages


class SignificantFiguresProofError(ValueError):
    pass


_NUMBER=re.compile(r"(?:0|[1-9]\d{0,6})(?:\.\d{1,6})?\Z")


def _decimal_literal(value:str)->Decimal:
    if type(value) is not str or not _NUMBER.fullmatch(value):
        raise SignificantFiguresProofError("Bounded positive decimal literal required")
    try:
        number=Decimal(value)
    except InvalidOperation as exc:
        raise SignificantFiguresProofError("Unparseable decimal literal") from exc
    if not number.is_finite() or number<=0:
        raise SignificantFiguresProofError("Only positive finite measured values supported")
    return number


def count_significant_digits(value:str)->int:
    """Count significant figures, preserving printed trailing decimal zeros.

    For integer literals ending in zero without decimal notation, the number
    of significant figures is ambiguous; reject instead of guessing.
    """
    _decimal_literal(value)
    if "." not in value and value.endswith("0"):
        raise SignificantFiguresProofError("Ambiguous trailing zero in integer measurement")
    sig=value.replace(".","").lstrip("0")
    if not sig:
        raise SignificantFiguresProofError("No nonzero significant digits")
    return len(sig)


def independently_round_product(a:str,b:str,reported:str)->dict:
    """Check measured lengths multiplication to printed result precision."""
    left,right,out=map(_decimal_literal,(a,b,reported))
    significant=min(count_significant_digits(a),count_significant_digits(b))
    if count_significant_digits(reported)!=significant:
        raise SignificantFiguresProofError("Reported area has wrong count of significant digits")
    raw=left*right
    quantum=Decimal(1).scaleb(raw.adjusted()-significant+1)
    expected=raw.quantize(quantum,rounding=ROUND_HALF_EVEN)
    if out!=expected or out.as_tuple().exponent!=expected.as_tuple().exponent:
        # Compare both value and the precision actually written.
        raise SignificantFiguresProofError("Reported rounded product differs from independent calculation")
    return {
        "input_significant_digits":[count_significant_digits(a),count_significant_digits(b)],
        "result_significant_digits":significant,
        "unrounded_product":str(raw),
        "recomputed_reported_area":str(expected),
        "decimal_rounding_rule":"ROUND_HALF_EVEN",
        "numeric_result_independently_verified":True,
        "complete_academic_semantics_proven":False,
    }


def _source_pair(text:str,number:str,unit:str)->bool:
    return bool(re.search(
        r"(?<![a-zA-Z0-9.])"+re.escape(number)+r"\s*"+re.escape(unit)+r"(?![a-zA-Z0-9])",
        text,flags=re.I))


def verify_source_significant_figure_claims(source:Path,manifest:dict,narration:dict)->dict:
    claims=manifest.get("source_significant_figure_claims",[])
    if not isinstance(claims,list) or len(claims)>20:
        raise SignificantFiguresProofError("Invalid bounded typed scientific-figure inventory")
    if not claims:
        return {}
    original=Path(source)
    before=sha_file(original)
    if manifest.get("source_pdf_sha256")!=before:
        raise SignificantFiguresProofError("Original source PDF SHA does not match manifest")
    try:
        packet=discover_passages(original,manifest["start_marker"],
            manifest.get("next_section_marker"),
            end_of_pdf=manifest.get("end_of_pdf") is True)
    except (KeyError,ValueError,TypeError) as exc:
        raise SignificantFiguresProofError("Original bounded source not independently recoverable") from exc
    passages={x["passage_id"]:x for x in packet["passages"]}
    slides=narration.get("slides")
    if not isinstance(slides,list) or not 1<=len(slides)<=60:
        raise SignificantFiguresProofError("Original narrated slides unavailable")
    out={}
    for claim in claims:
        if not isinstance(claim,dict) or claim.get("operation")!="rectangular_area_m2":
            raise SignificantFiguresProofError("Unsupported non-rectangular physical operation")
        idx=claim.get("slide")
        page=claim.get("source_page")
        ids=claim.get("source_passage_ids")
        anchor=claim.get("source_anchor")
        if (type(idx) is not int or idx in out or not 1<=idx<=len(slides)
            or type(page) is not int or slides[idx-1].get("source_page")!=page
            or not isinstance(ids,list) or not 1<=len(ids)<=5
            or len(set(ids))!=len(ids)
            or any(type(i) is not str or i not in passages or
                   passages[i]["source_page"]!=page for i in ids)
            or type(anchor) is not str or not 12<=len(anchor)<=160):
            raise SignificantFiguresProofError("Typed claim not bound to one valid source slide")
        text=" ".join(passages[i]["text"] for i in ids)
        if clean(anchor) not in clean(text):
            raise SignificantFiguresProofError("Original bounded source anchor absent")
        a,b,target=(claim.get(k) for k in
            ("length_m","width_m","reported_area_m2"))
        _decimal_literal(a);_decimal_literal(b);_decimal_literal(target)
        if not (_source_pair(text,a,"m") and _source_pair(text,b,"m")
                and _source_pair(text,target,"m2")):
            raise SignificantFiguresProofError("Source PDF does not contain claimed measured values")
        speech=slides[idx-1].get("narration","")
        if not isinstance(speech,str) or not re.search(
            r"(?<![0-9.])"+re.escape(target)+r"(?!\d)",speech):
            raise SignificantFiguresProofError("Claimed result not actually narrated on cited slide")
        proof=independently_round_product(a,b,target)
        out[idx]={
            "source_page":page,"source_passage_ids":ids,
            "source_pdf_sha256":before,
            "operation":"rectangular_area_m2",
            "length_m":a,"width_m":b,"reported_area_m2":target,
            **proof,
            "source_original_number_and_units_verified":True,
            "reported_result_actually_narrated":True,
            "full_scientific_semantics_proven":False,
            "publication_allowed":False,
        }
    if sha_file(original)!=before:
        raise SignificantFiguresProofError("Original source PDF changed during typed check")
    return out
