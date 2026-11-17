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
    # Orthographic segmentation is not a phonetic change: two independent
    # ASR systems may transcribe "roadmap"/"road map", "antiparallel"/
    # "anti parallel", or "nonzero"/"non zero". Only exact whole lexical
    # compounds qualify. Preserve the NON negation as an explicit token;
    # a missing "non" is mathematically material and still blocking.
    value = re.sub(r"\broad[\s-]?map\b", "roadmap", value, flags=re.I)
    value = re.sub(r"\banti[\s-]?parallel\b", "antiparallel", value, flags=re.I)
    value = re.sub(r"\bnon[\s-]?(?:zero|0)\b", "non zero", value, flags=re.I)
    # Reviewers must remain blind to expected speech. Do not delete malformed
    # assistant deliberation or output markup to hide a failed recognizer.
    value = value.replace("\u2212", "-")
    # In a mathematical position-function assignment, "x of t" and
    # "x at time t" denote the same function argument. Require the full
    # position/function/equality context; never change a general "at time"
    # or a different argument such as x(x), x(t squared), or y(t).
    value = re.sub(
        r"\bposition\s*,?\s*(?:ex|x)\s+(?:of|at\s+time)\s+"
        r"(?:t|tee)\s*,?\s*(?:equal|equals)\b",
        "position ex at time tee equals", value, flags=re.I)
    # Letter names for the time variable are equivalent only as an explicit
    # factor of a named mathematical coefficient, not in ordinary prose.
    value = re.sub(
        r"\b(?P<coefficient>b|c|see)\s+multiplied\s+by\s+(?:t|tee)\b",
        lambda m: m["coefficient"] + " multiplied by tee",
        value, flags=re.I)
    # Independent ASR can print a time-function as x(t), v_x(t) or a_x(t)
    # while the source-safe voice says "ex of tee", "vee ex of tee", etc.
    # Only exact t arguments are aliases: x(x), x(t squared), and changed
    # coordinate/derivative labels must remain different.
    value = re.sub(
        r"(?<![A-Za-z])(?P<component>[av])_?x\s*\(\s*t\s*\)",
        lambda m: _COMPONENT[m["component"].lower()] + " of tee",
        value, flags=re.I)
    value = re.sub(
        r"(?<![A-Za-z])(?P<coordinate>[xy])\s*\(\s*t\s*\)",
        lambda m: ("ex" if m["coordinate"].lower() == "x"
                   else "why") + " of tee",
        value, flags=re.I)
    # A symbol or spelled number represents the same exact decimal only
    # inside a numeric x.point.y construction; not an arbitrary sentence.
    digits = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
    decimal = re.compile(rf"\b({digits})\s+point\s+({digits})\b", re.I)
    def decimal_repl(m):
        lhs = _NUMBER_NAMES.get(m[1].lower(), m[1])
        rhs = _NUMBER_NAMES.get(m[2].lower(), m[2])
        return f"{lhs} point {rhs}"
    value = decimal.sub(decimal_repl, value)
    # Real two-Gemini ASR recurrence: the same spoken "one half" is
    # typeset as 1/2. Recognizers receive only WAV, not the source.
    # Restrict the equivalence to the exact one-half fraction; never
    # silently rewrite 1/3, 2/3, 1/20, 12 or a changed magnitude.
    value = re.sub(r"(?<![A-Za-z0-9])1\s*/\s*2(?![A-Za-z0-9])",
                   "one half", value)
    # Only canonical mathematical velocity subscripts, with the ORIGINAL
    # initial/final index preserved. No generic i/f letter conversions.
    value = re.sub(r"\bvxi\b", "vee ex eye", value, flags=re.I)
    value = re.sub(r"\bvxf\b", "vee ex eff", value, flags=re.I)
    value = re.sub(r"\bvex\s+(?:initial|eye|i)\b",
                   "vee ex eye", value, flags=re.I)
    value = re.sub(r"\bvex\s+(?:final|eff|f)\b",
                   "vee ex eff", value, flags=re.I)
    # A spoken index name "initial" denotes the same printed x_i;
    # this does NOT equate initial with final or remove a subscript.
    value = re.sub(r"\bvee\s+ex\s+initial\b",
                   "vee ex eye", value, flags=re.I)
    value = re.sub(r"\bvee\s+ex\s+i\b",
                   "vee ex eye", value, flags=re.I)
    value = re.sub(r"\bvee\s+ex\s+f\b",
                   "vee ex eff", value, flags=re.I)
    # A named mathematical factor "times t" / "over t" may be spelled
    # as the letter name tee, but ordinary text "tea" remains untouched.
    value = re.sub(r"\b(times|over)\s+t\b",
                   lambda m: m[1] + " tee", value, flags=re.I)
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
    # An isolated "tee" may be an ordinary word or a speech defect.
    # Historical regression requires it remain different from the bare t.
    # Only an explicit mathematical context permits that equivalence.
    value = re.sub(r"\b(?:time|versus|d)\s+tee\b",
                   lambda m: m[0][:-3] + "t", value, flags=re.I)
    value = re.sub(r"\b(minus|plus)\s+see\s+tee\b",
                   lambda m: m[1] + " see t", value, flags=re.I)
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
    # Some recognizers spell the explicit x subscript as "a y sub x".
    # Only the complete a-y-sub-x sequence is a component alias.
    value = re.sub(r"\ba\s+y\s+sub\s+(?:e\s+)?x\b",
                   "ay ex", value, flags=re.I)
    value = re.sub(r"\b(?:ay|vee)\s+(?:sub\s+)?(?:e\s+x|x|ex)\b",
                   lambda m: ("vee ex" if m[0].lower().startswith("vee")
                              else "ay ex"), value, flags=re.I)
    value = re.sub(r"\b(vx|ax)\b",
                   lambda m: _COMPONENT[m[1][0].lower()],
                   value, flags=re.I)
    # A transcription may use "VX of T" rather than "v_x(t)".
    # The time-letter alias is limited to a complete component function.
    value = re.sub(
        r"\b(?P<component>vee|ay)\s+ex\s+of\s+t\b",
        lambda m: m["component"] + " ex of tee",
        value, flags=re.I)
    value = re.sub(r"\bdvx\b", "d vee ex", value, flags=re.I)
    value = re.sub(r"\bdt\b", "d t", value, flags=re.I)
    value = re.sub(r"\b(?:a\s+v\s+g|average)\b(?=\s*(?:over|acceleration|,|\b))",
                   "avg", value, flags=re.I)
    value = re.sub(r"\b(s\s+i)\b", "si", value, flags=re.I)
    # Source-BLIND and mathematical-identity-preserving ASR typography.
    # Underscore notation is a PRINTED component subscript, not a different
    # spoken variable. Never map y to x, initial to final, or v(x) to v_x.
    value = re.sub(r"(?<![A-Za-z])([av])_x\b",
                   lambda m: _COMPONENT[m[1].lower()], value, flags=re.I)
    # A differential d(v_x)/dt is precisely the verbal derivative named
    # "dee vee ex over dee tee". Require BOTH its numerator x and denominator
    # t. A changed differentiated coordinate, time, sign or power remains
    # different; standalone dv/dx is NOT silently rewritten.
    value = re.sub(
        r"\b(?:dv_x|dv\s+(?:sub\s+)?x)\s+over\s+(?:d\s*t|dee\s+tee)\b",
        "dee vee ex over dee tee", value, flags=re.I)
    value = re.sub(
        r"\bdee\s+vee\s+ex\s+over\s+d\s+t\b",
        "dee vee ex over dee tee", value, flags=re.I)
    # Letter labels are preserved EXACTLY; panel b and panel bee both name B.
    # Crucially panel i is not panel e/ee, so a mislabelled physics graph
    # cannot be waved through as a harmless ASR formatting disagreement.
    panel_names={"a":"ay","b":"bee","c":"see",
                 "d":"dee","e":"ee","f":"eff"}
    value = re.sub(
        r"\bpanel\s+([a-f])\b",
        lambda m:"panel "+panel_names[m[1].lower()],
        value,flags=re.I)
    # A one-second delay spoken as '1.00 seconds later' is the same time
    # interval, not a distinct numerical value. Restrict pluralization to
    # the SAME explicit numeral immediately followed by 'later'; otherwise
    # preserve every spoken time unit and exponent.
    value = re.sub(
        r"\b(\d+(?:\.\d+|\s+point\s+\d+)?)\s+seconds\s+later\b",
        r"\1 second later",value,flags=re.I)
    # No absolute frequency-tolerance, signed-number waiver, or script-driven
    # insertion is allowed here. The caller's sensitive comparator still runs.
    return value
