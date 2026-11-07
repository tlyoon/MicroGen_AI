"""Bounded Gemini screen for narration paraphrases against actual slide text.

A model can only select an enumerated, immutable PDF text block and cite
verbatim text within it. This never certifies semantic entailment, equations,
phonemes, or publication. No call is made without explicit opt-in by the caller.
"""
from __future__ import annotations

import json
import re
import unicodedata


class SemanticMappingError(RuntimeError):
    pass


def compact(text: str) -> str:
    return "".join(x for x in unicodedata.normalize("NFKC", text).casefold() if x.isalnum())


def numbers(text: str) -> set[str]:
    return set(re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])", text))


def validate_matches(matches: object, missing: list[tuple[int, str]],
                     blocks: list[tuple]) -> dict[int, tuple[int, str]]:
    """Treat model output as untrusted; only source-present quotes are legal."""
    if not isinstance(matches, list) or len(matches) != len(missing):
        raise SemanticMappingError("Semantic proposal must cover all unresolved cues")
    needed = dict(missing)
    verified = {}
    for row in matches:
        if not isinstance(row, dict) or set(row) != {"cue", "block", "quote"}:
            raise SemanticMappingError("Unexpected semantic proposal fields")
        cue, block, quote = row["cue"], row["block"], row["quote"]
        if (type(cue) is not int or cue not in needed or cue in verified
                or type(block) is not int or not 1 <= block <= len(blocks)
                or not isinstance(quote, str) or not 8 <= len(quote) <= 200):
            raise SemanticMappingError("Invalid semantic cue/block/quote")
        label = blocks[block - 1][1]
        if len(compact(quote)) < 8 or compact(quote) not in compact(label):
            raise SemanticMappingError("Quoted evidence not present in rendered PDF text")
        spoken_numbers = numbers(needed[cue])
        if not spoken_numbers.issubset(numbers(label)):
            raise SemanticMappingError("Numerical claim not anchored to selected source block")
        verified[cue] = (block - 1, quote)
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
        "task": ("For each spoken narration cue choose exactly one visible slide "
                 "PDF text block that supports its meaning. Paraphrases are allowed. "
                 "If any cue cannot be grounded, return an empty matches list. "
                 "Never infer or invent a PDF block or numerical claim. "
                 "Quote at least eight characters verbatim from the selected block."),
        "slide": slide,
        "unresolved_cues": [{"cue": n, "spoken": text[:600]} for n, text in missing],
        "source_blocks": [{"block": i, "text": row[1]} for i, row in enumerate(blocks, 1)],
        "output_contract": {"matches": [{"cue": 1, "block": 1, "quote": "exact visible text"}]},
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
