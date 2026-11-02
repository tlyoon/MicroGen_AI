"""High-confidence automatic SI consistency scan of literal narrated equivalences.

This is a restricted numeric phrase recognizer, NOT an AI model or a general
physics language understanding system. It fails only unambiguous numeric
equivalence errors; unrecognized content is not claimed verified.
"""
from __future__ import annotations

from decimal import Decimal
import re

from microgen_portable_source_unit_conversions import _SI_FACTOR


class NarrationUnitEquivalenceError(ValueError):
    pass


_ALIASES={
    "kilometers per hour":"km/h","metres per second":"m/s",
    "meters per second":"m/s","miles per hour":"mi/h",
    "kilometers":"km","kilometres":"km",
    "kilometer":"km","kilometre":"km",
    "centimeters":"cm","centimetres":"cm",
    "centimeter":"cm","centimetre":"cm",
    "miles":"mile","meters":"m","metres":"m",
    "meter":"m","metre":"m",
    "inches":"in.","inch":"in.","feet":"ft","foot":"ft",
    "mile":"mile","km/h":"km/h","mi/h":"mi/h","m/s":"m/s",
    "in.":"in.","ft":"ft","km":"km","cm":"cm","m":"m",
}
_WORD_NUMBERS={"one":"1","two":"2","three":"3","ten":"10"}
_NUMBER=r"(?:[0-9]+(?:\.[0-9]{1,6})?|one|two|three|ten)"
_UNITS="|".join(re.escape(x) for x in sorted(_ALIASES,key=len,reverse=True))
_COMPARE=r"(?:is\s+(?:equal\s+to|equivalent\s+to)|equals?|corresponds?\s+to|=)"
_PATTERN=re.compile(
    r"(?<![A-Za-z0-9])(?P<a>"+_NUMBER+r")\s+"
    r"(?P<unit_a>"+_UNITS+r")\s+"
    +_COMPARE+
    r"\s+(?:(?:about|roughly|approximately|exactly)\s+)?"
    r"(?P<b>"+_NUMBER+r")\s+(?P<unit_b>"+_UNITS+r")(?![A-Za-z0-9])",
    flags=re.I)


def _value(text):
    return Decimal(_WORD_NUMBERS.get(text.casefold(),text))


def _unit(name):
    return _ALIASES[name.casefold()]


def check_narrated_unit_equivalences(narration:dict) -> dict:
    """Return checks by slide; reject only high-confidence SI contradictions."""
    slides=narration.get("slides")
    if not isinstance(slides,list) or not 1<=len(slides)<=60:
        raise NarrationUnitEquivalenceError("Bounded narration slide inventory required")
    checks={}
    for idx,item in enumerate(slides,1):
        if not isinstance(item,dict) or not isinstance(item.get("narration"),str):
            raise NarrationUnitEquivalenceError("Malformed narrated scientific text")
        text=item["narration"]
        if len(text)>3500:
            raise NarrationUnitEquivalenceError("Narration exceeds bounded equivalence scanner")
        hits=[]
        for match in _PATTERN.finditer(text):
            before,after=_value(match.group("a")),_value(match.group("b"))
            src,dst=_unit(match.group("unit_a")),_unit(match.group("unit_b"))
            if (before<=0 or after<=0 or src==dst
                or _SI_FACTOR[src][0]!=_SI_FACTOR[dst][0]):
                raise NarrationUnitEquivalenceError(
                    f"Slide {idx}: invalid or cross-dimensional narrated numeric equivalence")
            independent=before*_SI_FACTOR[src][1]/_SI_FACTOR[dst][1]
            printed=match.group("b").casefold()
            decimals=len(printed.split(".")[1]) if "." in printed else 0
            half_unit=Decimal("0.5")*(Decimal(10)**(-decimals))
            difference=abs(after-independent)
            if difference>half_unit or difference/independent>Decimal("0.05"):
                raise NarrationUnitEquivalenceError(
                    f"Slide {idx}: narrated unit equivalence contradicts SI")
            hits.append({
                "from_value":str(before),"from_unit":src,
                "to_value":str(after),"to_unit":dst,
                "numerical_equivalence_verified":True,
                "rounding_decimal_places":decimals,
                "source_text_provenance_independently_proven":False,
                "all_physics_semantics_verified":False
            })
        if hits:checks[idx]=hits
    return checks
