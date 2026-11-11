"""Bounded, source-bound semantic mapping for spoken cues to PDF text elements.

One spoken cue may refer to several *adjacent* visible elements. A multi-block
proposal is only a candidate: the independent PDF, text, numeric, and decoded
highlight verifiers must still pass. A model never certifies meaning, phonemes,
rights, or publication.
"""
from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal

MAX_GROUP_BLOCKS = 5


class SemanticMappingError(RuntimeError):
    pass


def compact(text: str) -> str:
    return "".join(x for x in unicodedata.normalize("NFKC", text).casefold() if x.isalnum())


def numbers(text: str) -> set[str]:
    """Extract exact decimal values, including adjacent formula coefficients.

    PDF extraction often renders 5 t squared as '5t2': the coefficient 5
    is still visible mathematical text, not a missing source number.
    Treat numerically equal 2 and 2.0 alike; NEVER infer a computed value
    absent from the printed expression.
    """
    tokens = re.findall(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])", text)
    return {format(Decimal(token).normalize(), "f") for token in tokens}


def validate_matches(matches: object, missing: list[tuple[int, str]],
                     blocks: list[tuple]) -> dict[int, tuple[tuple[int, ...], tuple[str, ...]]]:
    """Validate ALL cue proposals against original immutable PDF text blocks.

    Supports legacy single-block rows and strict, ordered, contiguous groups
    of at most five blocks. Each selected block needs its own verbatim quote.
    Never substitute a fabricated text region or omit an unresolved cue.
    """
    if not isinstance(matches, list) or len(matches) != len(missing):
        raise SemanticMappingError("Semantic proposal must cover all unresolved cues")
    needed = dict(missing)
    verified = {}
    for row in matches:
        if not isinstance(row, dict):
            raise SemanticMappingError("Invalid semantic proposal row")
        fields = set(row)
        if fields == {"cue", "block", "quote"}:
            chosen, quotes = [row["block"]], [row["quote"]]
        elif fields == {"cue", "blocks", "quotes"}:
            chosen, quotes = row["blocks"], row["quotes"]
            if (not isinstance(chosen, list) or not isinstance(quotes, list)
                    or not 2 <= len(chosen) <= MAX_GROUP_BLOCKS
                    or len(chosen) != len(quotes)):
                raise SemanticMappingError("Unsafe or incomplete multi-element group")
        else:
            raise SemanticMappingError("Unexpected semantic proposal fields")
        cue = row["cue"]
        if type(cue) is not int or cue not in needed or cue in verified:
            raise SemanticMappingError("Invalid or repeated semantic cue")
        if (not chosen or any(type(x) is not int or not 1 <= x <= len(blocks)
                               for x in chosen)
                or chosen != list(range(chosen[0], chosen[0] + len(chosen)))):
            raise SemanticMappingError("Multi-element blocks must be adjacent and ordered")
        if any(not isinstance(q, str) or not 8 <= len(q) <= 200 or
               len(compact(q)) < 8 or
               compact(q) not in compact(blocks[b - 1][1])
               for b, q in zip(chosen, quotes)):
            raise SemanticMappingError("Quoted evidence not present in rendered PDF text")
        labels = " ".join(blocks[b - 1][1] for b in chosen)
        if not numbers(needed[cue]).issubset(numbers(labels)):
            raise SemanticMappingError("Numerical claim not anchored to selected source blocks")
        verified[cue] = (tuple(b - 1 for b in chosen), tuple(quotes))
    if set(verified) != set(needed):
        raise SemanticMappingError("Missing or duplicated semantic cue")
    return verified


def propose_with_gemini(slide: int, missing: list[tuple[int, str]],
                        blocks: list[tuple]) -> list[dict]:
    """At most one authorized model request for one slide; no source mutation."""
    from microgen_flash_tts import _load_gemini_keys_from_microvid
    from gemini_keys import call_with_client_failover, create_gemini_client

    if not missing or len(missing) > 40 or not 1 <= len(blocks) <= 150:
        raise SemanticMappingError("Unsafe semantic proposal size")
    _load_gemini_keys_from_microvid()
    prompt = {
        "task": (
            "For EVERY spoken narration cue choose either a single visible slide PDF "
            "text block or an ordered, consecutive group of 2 to 5 visible text blocks "
            "supporting the cue. A spoken enumeration of several labels needs a group, "
            "not one arbitrary label. Paraphrases may be proposed but are NOT certified. "
            "Return one result per unresolved cue and cite each selected block with "
            "8 or more verbatim characters. If ANY cue cannot be grounded, return "
            "an empty matches list. Never invent labels, blocks, numbers or quotes."
        ),
        "slide": slide,
        "unresolved_cues": [{"cue": n, "spoken": text[:600]} for n, text in missing],
        "source_blocks": [{"block": i, "text": row[1]} for i, row in enumerate(blocks, 1)],
        "output_contract": {
            "single_element": {"cue": 1, "block": 1, "quote": "exact visible text"},
            "multi_element": {
                "cue": 2, "blocks": [2, 3],
                "quotes": ["exact text from block 2", "exact text from block 3"],
            },
        },
    }
    response = call_with_client_failover(
        create_gemini_client,
        lambda client: client.models.generate_content(
            model="gemini-3.8-flash",
            contents=json.dumps(prompt, ensure_ascii=False),
            config={"temperature": 0, "response_mime_type": "application/json"},
        ),
        label=f"MicroGen semantic cue screen slide {slide}",
        max_retries=0,
    )
    payload = str(getattr(response, "text", "") or "")
    if len(payload) > 30000:
        raise SemanticMappingError("Oversized semantic proposal")
    try:
        data = json.loads(payload)
    except (ValueError, TypeError) as exc:
        raise SemanticMappingError("Invalid model JSON") from exc
    if not isinstance(data, dict) or set(data) != {"matches"}:
        raise SemanticMappingError("Unexpected model proposal schema")
    return data["matches"]
