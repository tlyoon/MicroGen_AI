"""Conservative, deterministic source-PDF math-cue recovery.

No model calls, inferred results, altered narration, or guessed geometric
locations. Every candidate must be a short, contiguous group of literal
text elements in the already rendered PDF. Ambiguity always abstains.
"""
from __future__ import annotations

import re
from itertools import groupby

MAX_BLOCKS = 5
MATH_VARIABLES = (
    "vxavg", "vxcar", "vxi", "vxf", "vx", "ax",
    "xtrooper", "xcar", "xb", "xf", "xi",
)
_NAME_RE = re.compile(
    r"(?<![a-z])(?:" + "|".join(sorted(MATH_VARIABLES, key=len, reverse=True))
    + r")(?![a-z])"
)


def math_signature(text: str, *, spoken: bool) -> set[str]:
    """Translate only explicit kinematics variables to source notation."""
    if not isinstance(text, str):
        return set()
    s = text.lower()
    if spoken:
        # Longest-form variables first, otherwise 'vee ex' consumes an index.
        for prefix, symbol in (("vee", "v"), ("v", "v"),
                               ("ay", "a"), ("a", "a")):
            s = re.sub(
                rf"\b{prefix}\s+(?:sub\s+)?ex\s+"
                r"(initial|final|average|avg|car)\b",
                lambda m, sym=symbol:
                    sym + "x" + {"initial": "i", "final": "f",
                                 "average": "avg", "avg": "avg",
                                 "car": "car"}[m.group(1)], s)
        s = re.sub(
            r"\bex\s+(initial|final|bee|car|trooper)\b",
            lambda m: "x" + {"initial":"i", "final":"f", "bee":"b",
                             "car":"car", "trooper":"trooper"}[m.group(1)],
            s)
        s = re.sub(r"\b(?:vee|v)\s+(?:sub\s+)?ex\b", "vx", s)
        s = re.sub(r"\b(?:ay|a)\s+(?:sub\s+)?ex\b", "ax", s)
    # PDF extractors can render x_f, v_xf, v_{x,avg}, etc.
    s = re.sub(r"(?<![a-z])v[_\s]*x\s*[,]\s*avg\b", "vxavg", s)
    s = re.sub(r"(?<![a-z])v[_\s]*x\s*[,]\s*car\b", "vxcar", s)
    s = re.sub(r"(?<![a-z])([av])[_\s]*x[_\s]*(i|f)\b",
               lambda m: m[1] + "x" + m[2], s)
    s = re.sub(r"(?<![a-z])x[_\s]*(initial|final|car|trooper)\b",
               lambda m: "x" + {"initial":"i","final":"f",
                                "car":"car","trooper":"trooper"}[m[1]], s)
    s = re.sub(r"\bx[_\s]*b\b", "xb", s)
    s = re.sub(r"(?<![a-z])([av])_x\b", lambda m: m[1] + "x", s)
    return set(_NAME_RE.findall(s))


def _canon_math_text(text: str) -> str:
    s = text.lower()
    # Keep real token boundaries: concatenating 'and xf' into 'andxf'
    # would hide a printed x_f left-hand side and compromise verification.
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"vx,avg\b", "vxavg", s)
    s = re.sub(r"vx,car\b", "vxcar", s)
    return (s.replace("−", "-").replace("–", "-")
             .replace("ₓ", "x").replace("×", "*"))


def _directional_equations(spoken: str, source: str) -> bool:
    """Check all explicitly spoken equation LHS/RHS and plus/minus signs.

    Matching the variable *set* alone is not enough: x_f=x_i+... must not
    be accepted for a source x_i=x_f-... or a reversed sign.
    """
    raw = spoken.lower()
    src = _canon_math_text(source)
    variants = (
        (r"(?:vee|v)\s+(?:sub\s+)?ex\s+(?:initial|eye)", "vxi"),
        (r"(?:vee|v)\s+(?:sub\s+)?ex\s+(?:final|eff)", "vxf"),
        (r"(?:vee|v)\s+(?:sub\s+)?ex\s+(?:average|avg)", "vxavg"),
        (r"(?:vee|v)\s+(?:sub\s+)?ex", "vx"),
        (r"(?<!v\s)(?<!vee\s)(?<!sub\s)ex\s+(?:initial|eye)", "xi"),
        (r"(?<!v\s)(?<!vee\s)(?<!sub\s)ex\s+(?:final|eff)", "xf"),
    )
    relations = 0
    for expression, lhs in variants:
        for match in re.finditer(r"\b" + expression + r"\s+equals\s+", raw):
            tail = raw[match.end():]
            rhs_found = None
            for rhs_expr, rhs in variants:
                test = re.match(rhs_expr + r"\b", tail)
                if test:
                    rhs_found = (rhs, tail[test.end():])
                    break
            if rhs_found is None:
                # Unrecognized equation RHS requires independent model QA.
                return False
            rhs, remainder = rhs_found
            signs = {"plus": "+", "minus": "-"}
            sign_match = re.match(r"\s*(plus|minus)\b", remainder)
            op = signs[sign_match[1]] if sign_match else None
            required = (r"(?<![a-z])" + lhs + r"\s*=\s*" + rhs
                        + (r"\s*" + re.escape(op) if op else ""))
            if not re.search(required, src):
                return False
            relations += 1
    return relations >= 1


def exact_source_math_span(spoken: str, blocks: list[tuple], page) -> tuple[int, ...] | None:
    """One uniquely minimal, adjacent, printed equation group, else abstain.

    The independent plan/PCM verifier will recompute this source-bound
    selection, inspect every PDF bbox and recheck all claimed numbers.
    """
    if not isinstance(spoken, str) or not isinstance(blocks, list) or page is None:
        return None
    from microgen_cue_semantic_mapping import numbers
    signatures = math_signature(spoken, spoken=True)
    if len(signatures) < 3 or not re.search(
            r"\b(?:equals?|equation|fraction|divided|plus|minus)\b",
            spoken, re.I):
        return None
    claim_nums = numbers(spoken)
    results = []
    for start in range(len(blocks)):
        for stop in range(start + 1, min(start + MAX_BLOCKS, len(blocks)) + 1):
            chosen = blocks[start:stop]
            if any(not isinstance(row, tuple) or len(row) < 3
                   or len(row[1]) < 8 for row in chosen):
                continue
            src = " ".join(row[1] for row in chosen)
            if ("=" not in src and "≈" not in src):
                continue
            if not claim_nums.issubset(numbers(src)):
                continue
            if not signatures.issubset(math_signature(src, spoken=False)):
                continue
            if not _directional_equations(spoken, src):
                continue
            # Signed computed values may NEVER become positive numbers by
            # merely checking their unsigned numeric membership.
            for number in sorted(claim_nums):
                if re.search(r"\b(?:minus|negative)\s+" + re.escape(number)
                             + r"\b", spoken, re.I):
                    if not re.search(r"(?<![\d.])[-−]\s*" + re.escape(number)
                                     + r"(?!\d)", src):
                        break
            else:
                boxes = [row[0] for row in chosen]
                x0=min(b[0] for b in boxes); y0=min(b[1] for b in boxes)
                x1=max(b[2] for b in boxes); y1=max(b[3] for b in boxes)
                if (x0 < -0.5 or y0 < -0.5 or x1 > page.rect.width + 0.5
                        or y1 > page.rect.height + 0.5 or x1 <= x0 or y1 <= y0
                        or (x1-x0)*(y1-y0) >
                           page.rect.width*page.rect.height*0.40):
                    continue
                # Preserve exact source order. A small vertical/2D equation
                # may span rows, but a course-wide highlight is forbidden.
                if y1-y0 > page.rect.height*0.38:
                    continue
                results.append((stop-start, start, stop))
    if not results:
        return None
    minimal = min(r[0] for r in results)
    winners = {(start, stop) for count,start,stop in results if count == minimal}
    return tuple(range(*next(iter(winners)))) if len(winners)==1 else None


def build_exact_source_math_cue(
    slide_no: int, cue_no: int, spoken: str, blocks: list[tuple], page
) -> dict | None:
    """Private cue evidence; exact PDF strings, boxes and a stable rule tag."""
    indices = exact_source_math_span(spoken, blocks, page)
    if indices is None:
        return None
    from microgen_cue_semantic_mapping import numbers
    import fitz
    selected = [blocks[i] for i in indices]
    labels = [row[1] for row in selected]
    if any(not source_math_quote_valid(label) for label in labels):
        return None
    boxes = [row[0] for row in selected]
    union = fitz.Rect(boxes[0])
    for box in boxes[1:]:
        union |= fitz.Rect(box)
    text = page.get_textbox(union).strip()
    from microgen_timed_cue_planner import normalized
    if (not 8 <= len(text) <= 400
            or any(normalized(label) not in normalized(text)
                   for label in labels)
            or not numbers(spoken).issubset(numbers(" ".join(labels)))):
        return None
    cue = {
        "element_id": f"s{slide_no}_e{cue_no}",
        "spoken_text": spoken,
        "pdf_text": text,
        "pdf_bbox": list(map(float, union)),
        "source_math_evidence": "EXACT_SOURCE_MATH_V1",
    }
    if len(indices) == 1:
        cue["semantic_source_quote"] = labels[0][:200]
    else:
        cue["pdf_bboxes"] = [list(map(float, b)) for b in boxes]
        cue["pdf_texts"] = labels
        cue["semantic_source_quotes"] = [label[:200] for label in labels]
    return cue


def source_math_quote_valid(label: str) -> bool:
    """Exception only for genuine, two-variable, printed compact equations.

    Such as xf=xi+1: normalized length 5 but physically distinct from a
    meaningless fragment. Only legal alongside re-derived math provenance.
    """
    from microgen_cue_semantic_mapping import compact
    return (isinstance(label, str) and 8 <= len(label) <= 350
            and ((len(compact(label[:200])) >= 8)
                 or (5 <= len(compact(label[:200])) < 8
                     and "=" in label
                     and len(math_signature(label, spoken=False)) >= 2)))


def verified_source_math_row(
    cue: dict, slide_no: int, cue_no: int, blocks: list[tuple], page
) -> bool:
    """Independently rederive every persisted source+geometry claim."""
    if (not isinstance(cue, dict)
            or cue.get("source_math_evidence") != "EXACT_SOURCE_MATH_V1"):
        return False
    expected = build_exact_source_math_cue(
        slide_no, cue_no, cue.get("spoken_text"), blocks, page)
    if not expected:
        return False
    return all(cue.get(key) == value for key, value in expected.items())
