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


def exact_math_source_block(spoken: str, blocks: list[tuple]) -> int | None:
    """Return one uniquely source-attested mathematical block, or no match.

    No generative semantics: admit only a literal variable/limit identity
    that can be read back from the PDF OR a unique initial/final measured
    velocity calculation with >=3 matching numeric literals and matching
    units. This does not prove a new equation or allow derived numbers that
    the slide does not print.
    """
    if not isinstance(spoken, str) or not isinstance(blocks, list):
        return None
    canonical_spoken = spoken.casefold()
    math_cues = []
    for found in re.finditer(
            r"\b(?:negative|minus)\s+(\d+(?:\.\d+)?)\s+"
            r"(?:times\s+)?([a-z])\b", canonical_spoken):
        math_cues.append("-" + format(Decimal(found.group(1)).normalize(), "f")
                         + found.group(2))
    for found in re.finditer(
            r"\bdelta\s+([a-z])\s+(?:approaches|tends\s+to|"
            r"goes\s+to)\s+(?:zero|0)\b", canonical_spoken):
        math_cues.append("∆" + found.group(1) + "→0")

    complete_values = numbers(spoken)
    matches = []
    for i, row in enumerate(blocks):
        if (not isinstance(row, tuple) or len(row) < 2
                or not isinstance(row[1], str)):
            continue
        label = row[1]
        compact_equation = re.sub(r"\s+", "", label.casefold())
        compact_equation = compact_equation.replace("−", "-").replace("–", "-")
        # casefold() converts the Greek capital delta to lowercase δ; PDF
        # generators may also emit the mathematical increment sign ∆.
        compact_equation = compact_equation.replace("Δ", "∆").replace("δ", "∆")
        if "=" not in compact_equation or not complete_values.issubset(numbers(label)):
            continue
        # Use two different printed symbolic anchors together, never infer a
        # limit or sign from one isolated number.
        literal_symbolic = (len(set(math_cues)) >= 2 and
                            all(part in compact_equation for part in math_cues))
        # In spoken "equals negative N variable", N*variable must be
        # printed as an equation result, not merely appear in a preceding
        # subexpression with a different RHS or sign.
        if literal_symbolic and "equals" in canonical_spoken:
            signed = [part for part in math_cues
                      if re.fullmatch(r"-\d+(?:\.\d+)?[a-z]", part)]
            if signed:
                literal_symbolic = any(
                    re.search(r"=" + re.escape(part) + r"(?![\w])",
                              compact_equation)
                    for part in signed
                )
        # Initial and final velocities are grounded only when BOTH values,
        # their distinct time, and the associated i/f state variables appear
        # in the SAME text region with the correct printed units.
        unit_match = (
            len(complete_values) >= 3
            and "initial" in canonical_spoken and "final" in canonical_spoken
            and bool(re.search(r"\bmet(?:ers|res)\s+per\s+second\b",
                               canonical_spoken))
            and "m/s" in compact_equation
            and bool(re.search(r"\b[a-z]{1,5}_?i\s*=", label.casefold()))
            and bool(re.search(r"\b[a-z]{1,5}_?f\s*=", label.casefold()))
        )
        if literal_symbolic or unit_match:
            matches.append(i)
    return matches[0] if len(matches) == 1 else None


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


def _safe_schema_shape(value: object) -> str:
    """Only JSON type/key metadata, never a model quote or private PDF text."""
    if isinstance(value, dict):
        safe_keys = []
        for key in sorted(value, key=str)[:8]:
            label = str(key)
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", label):
                safe_keys.append(label)
            else:
                safe_keys.append("nonstandard_key")
        return "object_keys=" + ",".join(safe_keys)
    if isinstance(value, list):
        return "array_length=" + str(min(len(value), 999))
    return "type=" + type(value).__name__


def _integer_index(value: object) -> int:
    """Permit unambiguous decimal string IDs; never convert booleans/floats."""
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,2}", value):
        return int(value)
    raise SemanticMappingError("Invalid model semantic cue/block index")


def normalize_model_proposal(data: object, missing: list[tuple[int, str]]
                             ) -> list[dict]:
    """Normalize bounded *structural* Gemini JSON variations only.

    This is NOT semantic repair or permission to bypass source checks.
    Every row is still independently checked by validate_matches() against
    the original slide PDF; guessed/absent quotes, bad signs and numeric
    claims cannot be made valid by reshaping the JSON.
    """
    # A legitimate JSON array and these well-known wrappers carry exactly
    # the same information. Refuse unexpected extra fields or error states.
    for _ in range(2):
        if isinstance(data, dict) and set(data) in (
                {"matches"}, {"mappings"}, {"result"}, {"data"}, {"output"}):
            data = next(iter(data.values()))
            continue
        break
    # A strict indexed map is equivalent to an explicit cue row list.
    if (isinstance(data, dict) and data
            and all(isinstance(k, str) and re.fullmatch(r"[1-9][0-9]{0,2}", k)
                    for k in data)):
        rows = []
        for key, entry in data.items():
            if not isinstance(entry, dict) or "cue" in entry:
                raise SemanticMappingError("Ambiguous semantic keyed-row schema")
            rows.append({"cue": int(key), **entry})
        data = rows
    if isinstance(data, dict):
        # Some models supply a descriptive top-level status or notes;
        # explicitly refuse failures and never turn a refusal into matches.
        safe_meta = {"status", "reason", "notes", "reasoning"}
        if "matches" in data and set(data).issubset(safe_meta | {"matches"}):
            status = data.get("status")
            if status is not None and status not in ("ok", "success", "complete"):
                raise SemanticMappingError("Model refused semantic mapping")
            if any(not isinstance(data.get(k), str) or
                   len(data[k]) > 2000 for k in safe_meta - {"status"}
                   if k in data):
                raise SemanticMappingError("Invalid semantic response metadata")
            data = data["matches"]
        else:
            raise SemanticMappingError(
                "Unexpected model proposal schema (" + _safe_schema_shape(data) + ")"
            )
    if not isinstance(data, list) or len(data) != len(missing):
        raise SemanticMappingError(
            "Semantic model returned incomplete proposal (" +
            _safe_schema_shape(data) + ")"
        )
    normalized = []
    allowed_aliases = {
        "cue_id": "cue", "cue_number": "cue",
        "block_id": "block", "block_index": "block",
        "source_quote": "quote",
        "block_ids": "blocks", "block_indices": "blocks",
        "source_quotes": "quotes",
    }
    for row in data:
        if not isinstance(row, dict):
            raise SemanticMappingError("Invalid semantic response row type")
        translated = {}
        for key, value in row.items():
            name = allowed_aliases.get(key, key)
            if name in translated:
                raise SemanticMappingError("Ambiguous duplicated semantic field")
            translated[name] = value
        if set(translated) not in ({"cue", "block", "quote"},
                                  {"cue", "blocks", "quotes"}):
            raise SemanticMappingError("Unsupported semantic response row fields")
        translated["cue"] = _integer_index(translated["cue"])
        if "block" in translated:
            translated["block"] = _integer_index(translated["block"])
            if not isinstance(translated["quote"], str):
                raise SemanticMappingError("Invalid source quote")
        else:
            if (not isinstance(translated["blocks"], list)
                    or not isinstance(translated["quotes"], list)):
                raise SemanticMappingError("Invalid grouped source evidence")
            translated["blocks"] = [_integer_index(x)
                                     for x in translated["blocks"]]
            if any(not isinstance(q, str) for q in translated["quotes"]):
                raise SemanticMappingError("Invalid source quotes")
        normalized.append(translated)
    if {row["cue"] for row in normalized} != {cue for cue, _ in missing}:
        raise SemanticMappingError("Missing or duplicated semantic model cues")
    return normalized


def _parse_semantic_model_response(response: object,
                                   missing: list[tuple[int, str]]) -> list[dict]:
    """Strict JSON body/SDK-parsed response; zero additional provider calls."""
    raw = getattr(response, "text", None)
    if raw is None or raw == "":
        parsed = getattr(response, "parsed", None)
        if not isinstance(parsed, (dict, list)):
            raise SemanticMappingError("Empty model semantic response")
        return normalize_model_proposal(parsed, missing)
    if not isinstance(raw, str) or len(raw) > 30000:
        raise SemanticMappingError("Oversized or invalid semantic JSON response")
    body = raw.strip()
    # Accept only a full fenced JSON document, not prose mixed with JSON.
    match = re.fullmatch(r"\x60\x60\x60(?:json)?\s*\n(.*?)\n\x60\x60\x60",
                         body, flags=re.DOTALL | re.IGNORECASE)
    if match:
        body = match.group(1).strip()
    try:
        data = json.loads(body)
        if isinstance(data, str) and len(data) <= 30000 and data.lstrip().startswith(
                ("{", "[")):
            data = json.loads(data)
    except (ValueError, TypeError) as exc:
        raise SemanticMappingError("Invalid model JSON") from exc
    normalized = normalize_model_proposal(data, missing)
    canonical = (
        isinstance(data, dict) and set(data) == {"matches"}
        and isinstance(data["matches"], list)
        and all(isinstance(row, dict)
                and set(row) in ({"cue", "block", "quote"},
                                 {"cue", "blocks", "quotes"})
                for row in data["matches"])
    )
    if not canonical:
        print("[semantic model] accepted equivalent JSON structure "
              f"{_safe_schema_shape(data)}; original-PDF evidence checks "
              "still mandatory", flush=True)
    return normalized


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
            "8 or more verbatim characters. The ENTIRE response MUST be one JSON "
            "object with exactly the key matches holding an array of rows. "
            "A single-block row has exactly cue, block, quote; a group has exactly "
            "cue, blocks, quotes. If ANY cue cannot be grounded, return "
            "{\"matches\": []}. Never include extra keys, markdown, explanations, "
            "fabricated labels, blocks, numbers or quotes."
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
    # A narrow, deterministic representation adapter handles harmless JSON
    # wrappers, exact cue-index aliases and parsed SDK objects from THIS
    # request. It never retries Gemini, rewrites source, or certifies meaning.
    # The actual original-PDF verifier remains the mandatory postcondition.
    return _parse_semantic_model_response(response, missing)
