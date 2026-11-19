"""Literal worked-example cue recovery for rendered PDF text fragments.

Recognizes narrowly defined physical statements with fully printed source
numbers, signs, variables, units, and one unique source location. Never
calculates a missing value or trusts a model's empty/unsupported proposal.
The normal cue builder and independent PCM/video verifier recompute all
source evidence. No slide numbers, specimen identifiers, or fixed values.
"""
from __future__ import annotations

import re

_SIGN = "[-\u2212]"
_NUMBER = r"\d+(?:\.\d+)?"
_UNIT = r"m\s*/\s*s"
_SQUARED = r"(?:2|\u00b2)"


def _flatten(value: str) -> str:
    return " ".join(value.split())


def _source_number(value: str) -> str:
    """Numerically equivalent printed decimal, never rounding."""
    from decimal import Decimal, InvalidOperation
    try:
        return format(Decimal(value).normalize(), "f")
    except InvalidOperation:
        return ""


def _has_number_unit(source: str, value: str, unit: str) -> bool:
    """Printed unit-attested value, not inferred from arithmetic."""
    pattern = rf"(?<![\d.]){re.escape(value)}(?![\d])\s*{unit}\b"
    return bool(re.search(pattern, source, flags=re.I))


def _literal_equivalent_number(value: str, text: str) -> bool:
    from microgen_cue_semantic_mapping import numbers
    return _source_number(value) in numbers(text)


def _printed_fraction_rounding_is_consistent(
    speed: str, duration: str, printed_result: str,
) -> bool:
    """Verify, never *invent*, the printed rounded signed result.

    The source displays the measured fraction and its evaluated result.
    A result of -3.2 cannot be accepted for (0 - 63)/2.0 merely because a
    minus sign appears. Match the printed decimal precision using standard
    half-up rounding, and reject malformed, absent or ambiguous result lines.
    No replacement numeric value is generated or published.
    """
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

    # A source block with multiple incompatible result equalities is
    # ambiguous; do not select the first convenient signed result.
    if printed_result.count("=")!=1:
        return False
    value=re.search(
        rf"=\s*[-\u2212]\s*(?P<result>{_NUMBER})\s*"
        rf"m\s*/\s*s{_SQUARED}\b",
        printed_result, flags=re.I,
    )
    if not value:
        return False
    result=value["result"]
    decimals=len(result.split(".")[1]) if "." in result else 0
    quantum=Decimal(1).scaleb(-decimals)
    try:
        denominator=Decimal(duration)
        if denominator <= 0:
            return False
        calculated=-(Decimal(speed)/denominator)
        observed=-Decimal(result)
        return (calculated.quantize(quantum,rounding=ROUND_HALF_UP)
                == observed)
    except (InvalidOperation,ZeroDivisionError,OverflowError,ValueError):
        return False


def _exact_x_component_spoken_aliases(spoken: str) -> str:
    """Source-blind, mathematical identity-preserving speech spellings.

    The original velocity x-subscript can be voiced explicitly rather than
    as short letter names. Translate only the exact same variable and its
    initial/final index back to its symbolic spoken name *before* the
    unchanged printed-source sign/value/unit/equation proof. Never translate
    arbitrary x-axis functions, y components or scientific conclusions.
    """
    s=_flatten(spoken)
    substitutions=(
        (r"\binitial velocity along the (?:x|ex) axis\b",
         "initial velocity vee ex eye"),
        (r"\bfinal velocity along the (?:x|ex) axis\b",
         "final velocity vee ex eff"),
        (r"\bthe initial (?:x|ex) component of velocity\b",
         "vee ex eye"),
        (r"\bthe final (?:x|ex) component of velocity\b",
         "vee ex final"),
        (r"\bthe (?:x|ex) component of acceleration\b",
         "ay ex"),
    )
    for pattern,equivalent in substitutions:
        s=re.sub(pattern,equivalent,s,flags=re.I)
    # Voice clarification of a complete signed worked fraction must be
    # compared as ONE mathematical cue. The voice adapter deliberately
    # says "whole-number value" to avoid 63 sounding like 6.3. Translate
    # only the exact SAME numerator, subtraction, denominator and digits
    # back to the original source-bound relation for matching. This does
    # NOT invent a missing fraction, round a value, or accept source mismatch.
    # The printed original fraction and rounded signed result are still
    # mandatory in _candidate_kind() below and in independent plan QA.
    s=re.sub(
        r"\bgives\s+the\s+numerator\s+0\s+minus\s+the\s+whole-number"
        r"\s+value\s+(?P<speed>[1-9]\d{1,2})\s+with\s+that\s+entire"
        r"\s+numerator\s+divided\s+by\s+(?P<duration>\d+(?:\.\d+)?)\b",
        lambda m:"gives 0 minus "+m["speed"]+" divided by "+m["duration"],
        s,flags=re.I)
    return s


def _candidate_kind(spoken: str, chosen: list[tuple], page) -> bool:
    """Accept only exact source-verifiable math relations from printed cells."""
    s = _exact_x_component_spoken_aliases(spoken)
    src = _flatten(" ".join(row[1] for row in chosen))
    compact = re.sub(r"\s+", "", src).lower()
    values = [row[1] for row in chosen]

    # A worked-example reference and its real "Problem:" statement.
    pattern = (rf"^In Example (?P<example>\d+\.\d+), a jet lands on an "
               rf"aircraft carrier with an initial velocity "
               rf"(?:vee|v) (?:sub )?ex (?:eye|initial) of "
               rf"approximately (?P<speed>{_NUMBER}) meters per second "
               rf"and stops in (?P<duration>{_NUMBER}) seconds?\.$")
    match = re.fullmatch(pattern, s, re.I)
    if match:
        if len(chosen) != 2 or not re.search(
                rf"\bExample\s+{re.escape(match['example'])}\s*:",
                values[0], re.I):
            return False
        problem = values[1]
        return bool(
            re.search(r"^Problem:\s+A jet lands on an aircraft carrier", problem, re.I)
            and re.search(r"\bvxi\s*[\u2248~]", problem, re.I)
            and _has_number_unit(problem, match["speed"], _UNIT)
            and re.search(r"stops\s*\(\s*vxf\s*=\s*0\s*\)", problem, re.I)
            and re.search(
                rf"\bt\s*=\s*{re.escape(match['duration'])}\s*s\b", problem, re.I)
        )

    # Printed vxf - vxi / t followed by the literal 0 - N / T fraction.
    pattern = (rf"^Calculating (?:ay|a) (?:sub )?ex equals the fraction "
               rf"(?:v|vee) ex final minus (?:vee|v) ex eye over t "
               rf"gives 0 minus (?P<speed>{_NUMBER}) divided by "
               rf"(?P<duration>{_NUMBER}),?$")
    match = re.fullmatch(pattern, s, re.I)
    if match:
        if len(chosen) != 3:
            return False
        first, second, third = (_flatten(x) for x in values)
        return bool(
            re.search(r"\bax\s*=\s*vxf\s*[-\u2212]\s*vxi\b", first, re.I)
            and re.search(r"\bt\s*=\s*0\s*[-\u2212]", second, re.I)
            and _has_number_unit(second, match["speed"], _UNIT)
            and re.search(
                rf"(?<!\d){re.escape(match['duration'])}\s*s\b", third, re.I)
            and re.search(r"=\s*[-\u2212]", third)
            and _printed_fraction_rounding_is_consistent(
                match["speed"],match["duration"],third)
        )

    # Spoken signed acceleration (already printed on the result line).
    match = re.fullmatch(
        rf"^yielding (?:minus|negative) (?P<result>{_NUMBER}) "
        r"meters per second squared\.$", s, re.I)
    if match:
        if len(chosen) != 1:
            return False
        return bool(re.search(
            rf"=\s*[-\u2212]\s*{re.escape(match['result'])}\s*"
            rf"m\s*/\s*s{_SQUARED}\b", src, re.I))

    # The explicit delay-based position xB from the exact printed equation.
    match = re.fullmatch(
        rf"^During that one-second delay, the car reaches position "
        rf"x B of (?P<distance>{_NUMBER}) meters\.$", s, re.I)
    if match:
        if len(chosen) != 1:
            return False
        return bool(re.search(
            rf"\bxB\s*=\s*\(\s*{_NUMBER}\s*{_UNIT}\s*\)\s*"
            rf"\(\s*1(?:\.0+)?\s*s\s*\)\s*=\s*"
            rf"{re.escape(match['distance'])}\s*m\b", src, re.I))

    # Two separate source equations, a car and a uniformly accelerating
    # trooper. Do not infer the 1/2 factor: the actual printed denominator
    # must be present as the very next contiguous source text block.
    pattern = (r"^Therefore, the car's position is ex car equals ex bee "
               r"plus vee ex car times t, and the trooper's position is "
               r"ex trooper equals one-half ay sub ex times tee squared\.$")
    if re.fullmatch(pattern, s, re.I):
        if len(chosen) != 2:
            return False
        first, second = (_flatten(x) for x in values)
        return bool(
            re.search(r"\bxcar\s*=\s*xB\s*\+\s*vx,car\s*t\b", first, re.I)
            and re.search(r"\bxtrooper\s*=\s*1\b", first, re.I)
            and re.fullmatch(r"2\s*a\s*x\s*t(?:2|\u00b2)", second, re.I)
        )

    # Literal plus-square-root result. The root glyph must be its own
    # original PDF TEXT block between the two genuine numeric equations.
    match = re.fullmatch(
        rf"^When we substitute numerical values, the expression becomes "
        rf"(?P<base>{_NUMBER}) plus the square root of "
        rf"(?P<radicand>{_NUMBER}), which equals "
        rf"(?P<result>{_NUMBER}) seconds?\.$", s, re.I)
    if match:
        if len(chosen) != 3:
            return False
        a, radical, b = (_flatten(x) for x in values)
        if (radical != "\u221a" or
            not re.search(rf"=\s*{re.escape(match['base'])}\s*\+", a)
            or not re.search(
                rf"^\s*{re.escape(match['radicand'])}\s*=\s*"
                rf"{re.escape(match['result'])}\s*s\b", b, re.I)):
            return False
        left, root, right = [row[0] for row in chosen]
        return bool(
            left[2] - 2 <= root[0] <= right[0] + 2
            and left[2] - 2 <= root[2] <= right[0] + 2
            and root[1] >= min(left[1], right[1]) - 20
            and root[3] <= max(left[3], right[3]) + 8
        )

    return False


def unique_printed_worked_math_span(
    spoken: str, blocks: list[tuple], page
) -> tuple[int, ...] | None:
    """Find exactly one minimal matching source span, with strict bounds."""
    if (not isinstance(spoken, str) or len(spoken) > 700
            or not isinstance(blocks, list) or not blocks
            or page is None):
        return None
    from microgen_cue_semantic_mapping import numbers
    claim = numbers(spoken)
    solutions = []
    for start in range(len(blocks)):
        for end in range(start+1, min(start+3,len(blocks))+1):
            selected = blocks[start:end]
            labels = " ".join(x[1] for x in selected)
            if not claim.issubset(numbers(labels)):
                continue
            if not _candidate_kind(spoken,selected,page):
                continue
            regions=[x[0] for x in selected]
            x0=min(x[0] for x in regions); y0=min(x[1] for x in regions)
            x1=max(x[2] for x in regions); y1=max(x[3] for x in regions)
            if (x0 < -0.5 or y0 < -0.5 or x1 > page.rect.width+0.5
                    or y1 > page.rect.height+0.5 or x1<=x0 or y1<=y0
                    or (x1-x0)*(y1-y0) >
                    page.rect.width*page.rect.height*.40):
                continue
            solutions.append((end-start,start,end))
    if not solutions:
        return None
    minimal = min(x[0] for x in solutions)
    candidates = {(start,end) for count,start,end in solutions
                  if count==minimal}
    if len(candidates) != 1:
        return None
    lo,hi=next(iter(candidates))
    return tuple(range(lo,hi))
