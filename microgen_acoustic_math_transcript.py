"""Conservative expected-BLIND canonicalization of mathematical ASR typography.

A recognizer may display the SAME audible variable using a letter-name
("vee ex"), subscript ("v sub x") or symbolic shorthand ("vx").
This module removes known transcriber *formatting* differences only.
It never removes sign, magnitude, equality, negation or narration words.

It is not an acoustic approval: both independent recognizers, source-side
risk checks, the unchanged mismatch limit and sensitive-token screen still
make the decision.
"""
from __future__ import annotations
import re

_COMPONENT = {"a": "ay ex", "v": "vee ex"}
_NUMBER_NAMES = {"zero": "0", "one": "1", "two": "2",
                 "three": "3", "four": "4", "five": "5",
                 "six": "6", "seven": "7", "eight": "8",
                 "nine": "9", "ten": "10"}


def canonical_math_transcript(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("Acoustic transcript must be text")
    value = text
    # Reviewers must remain blind to expected speech. Do not delete malformed
    # assistant deliberation or output markup to hide a failed recognizer.
    value = value.replace("\u2212", "-")
    # A symbol or spelled number represents the same exact decimal only
    # inside a numeric x.point.y construction; not an arbitrary sentence.
    digits = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
    decimal = re.compile(rf"\b({digits})\s+point\s+({digits})\b", re.I)
    def decimal_repl(m):
        lhs = _NUMBER_NAMES.get(m[1].lower(), m[1])
        rhs = _NUMBER_NAMES.get(m[2].lower(), m[2])
        return f"{lhs} point {rhs}"
    value = decimal.sub(decimal_repl, value)
    # Preserve minus as an explicit token. No mathematics operation removed.
    value = re.sub(r"(?<![A-Za-z])-\s*(?=[\d])", " minus ", value)
    value = re.sub(r"(?<=[txyav])\s*-\s*(?=\d)", " minus ",
                   value, flags=re.I)
    value = re.sub(r"(?<=[txyav])\s*-\s*(?=[txyav]\b)", " minus ",
                   value, flags=re.I)
    # A hyphen in "one-second interval" is NOT spoken "minus".
    # Only a numeric-minus-mathematical-variable construction qualifies.
    value = re.sub(r"(?<=\d)\s*-\s*(?=[txyav]\b)",
                   " minus ", value, flags=re.I)
    value = re.sub(r"(?<=\w)\s*=\s*(?=[A-Za-z0-9\-])",
                   " equals ", value)
    value = re.sub(r"(?<=\w)\s*\+\s*(?=[A-Za-z0-9])",
                   " plus ", value)
    value = re.sub(r"\b(?:negative)\s+(?=\d+\b)", "minus ",
                   value, flags=re.I)
    # Explicit SI shorthand is a different orthography, not a different unit.
    value = re.sub(r"\bm\s*/\s*s\s*(?:\^?2|squared)\b",
                   "meters per second squared", value, flags=re.I)
    value = re.sub(r"\bm\s*/\s*s\b",
                   "meters per second", value, flags=re.I)
    # The text 'tee'/'vee' is the phonetic spelling of these two single
    # mathematical letters. In ordinary prose no other word is changed.
    value = re.sub(r"\btee\b", "t", value, flags=re.I)
    # Normalize mathematical squared/cubed exponents without dropping powers.
    # Math polynomial typography retained by a recognizer (bt^3 - ct).
    # Do not rewrite an unrelated word such as chemical abbreviation CT.
    value = re.sub(r"\bb\s*t\s*\^\s*3\b", "b t cubed",
                   value, flags=re.I)
    value = re.sub(r"\bbt3\b", "b t cubed", value, flags=re.I)
    value = re.sub(r"(?<=\bcubed)\s*-\s*(?=ct\b)", " minus ", value, flags=re.I)
    value = re.sub(r"(?<=\bminus )ct\b", "see t", value, flags=re.I)
    value = re.sub(r"\b([tx])\s*\^\s*([23])\b",
                   lambda m: m[1]+" "+("squared" if m[2]=="2" else "cubed"),
                   value, flags=re.I)
    value = re.sub(r"\b([tx])([23])\b",
                   lambda m: m[1]+" "+("squared" if m[2]=="2" else "cubed"),
                   value, flags=re.I)
    value = re.sub(r"(?<![A-Za-z])([0-9]+)\s*([t])\b",
                   r"\1 \2", value, flags=re.I)
    value = re.sub(r"\b([av])\s+(?:sub\s+)?(?:e\s+x|x|ex)\b",
                   lambda m: _COMPONENT[m[1].lower()], value, flags=re.I)
    value = re.sub(r"\b([av])\s+y\s+x\b",
                   lambda m: _COMPONENT[m[1].lower()], value, flags=re.I)
    value = re.sub(r"\b(?:ay|vee)\s+(?:sub\s+)?(?:e\s+x|x|ex)\b",
                   lambda m: ("vee ex" if m[0].lower().startswith("vee")
                              else "ay ex"), value, flags=re.I)
    value = re.sub(r"\b(vx|ax)\b",
                   lambda m: _COMPONENT[m[1][0].lower()],
                   value, flags=re.I)
    value = re.sub(r"\bdvx\b", "d vee ex", value, flags=re.I)
    value = re.sub(r"\bdt\b", "d t", value, flags=re.I)
    value = re.sub(r"\b(?:a\s+v\s+g|average)\b(?=\s*(?:over|acceleration|,|\b))",
                   "avg", value, flags=re.I)
    value = re.sub(r"\b(s\s+i)\b", "si", value, flags=re.I)
    # No absolute frequency-tolerance, signed-number waiver, or script-driven
    # insertion is allowed here. The caller's sensitive comparator still runs.
    return value
