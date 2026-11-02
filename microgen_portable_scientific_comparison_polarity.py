"""Source-confirmed, strictly bounded speed-limit conclusion consistency.

Only scans definite driver/car/vehicle vs posted-limit conclusions on a slide
with a previously SI-verified strict source conversion. Unknown wording is
UNVERIFIED, not an error. Never uses a language model or remote service.
"""
from __future__ import annotations

import re


class ScientificComparisonContradiction(ValueError):
    pass


_SUBJECT=r"\b(?:driver|vehicle|car)\b"
_LIMIT=r"\b(?:the\s+)?(?:posted\s+)?(?:speed\s+)?limit\b"
_POSITIVE=re.compile(_SUBJECT+r"[^.!?]{0,130}\b(?:exceed(?:s|ed|ing)?|above|over)\b[^.!?]{0,55}"+_LIMIT,re.I)
_NEGATIVE=re.compile(_SUBJECT+r"[^.!?]{0,130}\b(?:below|under|within)\b[^.!?]{0,55}"+_LIMIT,re.I)
_NEGATED=re.compile(_SUBJECT+r"[^.!?]{0,130}\b(?:does?\s+not|is\s+not|was\s+not|never)\s+(?:be\s+)?(?:exceed(?:s|ed|ing)?|above|over)\b[^.!?]{0,55}"+_LIMIT,re.I)
_HEDGE=re.compile(r"\b(?:if|suppose|might|may|could|would|whether|hypothetically|incorrect|false|wrong|untrue|imagine)\b",re.I)


def _asserted_limit_polarities(text:str)->list[int]:
    """Only definite explicit sentences, not hypotheticals/questions/metatalk."""
    if not isinstance(text,str) or len(text)>3500:
        raise ScientificComparisonContradiction("Invalid bounded comparison wording")
    signs=[]
    for sentence in re.split(r"(?<=[.!?])\s+",text):
        if not sentence or _HEDGE.search(sentence) or sentence.endswith("?"):
            continue
        negated=bool(_NEGATED.search(sentence))
        negative=bool(_NEGATIVE.search(sentence))
        positive=bool(_POSITIVE.search(sentence))
        if (negated or negative) and positive and not negated:
            # Both directions in one clause are not unambiguous.
            continue
        if negated or negative:
            signs.append(-1)
        elif positive:
            signs.append(+1)
    return signs


def checked_source_comparison_narration(manifest:dict,narration:dict,source_si_proof:dict)->dict:
    """Compare definite spoken conclusions to independently verified source claims.

    The caller MUST first invoke verified_source_unit_conversions on the same
    contract/PDF/narration. Thus only proven claims can supply source_si_proof.
    """
    rows=manifest.get("source_unit_conversion_claims",[])
    if not isinstance(rows,list) or len(rows)>20:
        raise ScientificComparisonContradiction("Malformed source claims")
    slides=narration.get("slides")
    if not isinstance(slides,list) or not 1<=len(slides)<=60:
        raise ScientificComparisonContradiction("Bounded narration slide inventory required")
    result={}
    for claim in rows:
        relation=claim.get("relation","equal_with_rounding") if isinstance(claim,dict) else None
        if relation not in ("greater_than","less_than"):
            continue
        slide=claim.get("slide")
        if type(slide) is not int or slide not in source_si_proof or not 1<=slide<=len(slides):
            raise ScientificComparisonContradiction("Expected prior independent source SI proof absent")
        proof=source_si_proof[slide]
        if (proof.get("relation")!=relation
            or proof.get("independent_si_conversion_verified") is not True):
            raise ScientificComparisonContradiction(
                "Typed source claim disagrees with independently checked SI proof")
        if proof.get("quantity_dimension")!="speed":
            # Other physical comparisons are outside this narrow semantic gate.
            continue
        # Claims may involve speed comparison without a driver/limit; skip.
        source_anchor=claim.get("source_comparison_anchor","")
        source_signs=_asserted_limit_polarities(source_anchor)
        if not source_signs:
            continue
        expected=+1 if relation=="greater_than" else -1
        if any(s!=expected for s in source_signs):
            raise ScientificComparisonContradiction(
                f"Slide {slide}: original cited comparison conclusion contradicts SI direction")
        authored=slides[slide-1].get("narration")
        signs=_asserted_limit_polarities(authored)
        if not signs:
            continue
        if any(s!=expected for s in signs):
            raise ScientificComparisonContradiction(
                f"Slide {slide}: definite spoken speed-limit conclusion contradicts source-verified SI")
        result[slide]={
            "typed_source_si_comparison_already_verified":True,
            "source_comparison_anchor_verified_by_prior_source_gate":True,
            "definite_narrated_limit_conclusion_matches_source":True,
            "recognized_definite_conclusions_count":len(signs),
            "source_page":proof["source_page"],
            "source_passage_ids":proof["source_passage_ids"],
            "unrecognized_semantic_statements_verified":False,
            "academic_completeness_proven":False,
            "publication_allowed":False,
        }
    return result
