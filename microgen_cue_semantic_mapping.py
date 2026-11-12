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

# The Gemini JSON MIME setting alone does not require a particular shape.
# Constrain output *at generation time*, then independently validate every
# returned cue, verbatim PDF quote, number, and visible block coordinate.
# Empty matches remain legal: a model must be allowed to abstain rather
# than being forced to invent a source mapping.
SEMANTIC_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "matches": {
            "type": "array",
            "description": (
                "One exact PDF-grounded mapping for every unresolved cue, "
                "or an empty array if any cue cannot be grounded"
            ),
            "items": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "cue": {"type": "integer", "minimum": 1},
                            "block": {"type": "integer", "minimum": 1},
                            "quote": {
                                "type": "string",
                                "description": (
                                    "Eight or more verbatim characters "
                                    "from the selected source PDF block"
                                ),
                            },
                        },
                        "required": ["cue", "block", "quote"],
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "cue": {"type": "integer", "minimum": 1},
                            "blocks": {
                                "type": "array",
                                "minItems": 2,
                                "maxItems": MAX_GROUP_BLOCKS,
                                "items": {"type": "integer", "minimum": 1},
                            },
                            "quotes": {
                                "type": "array",
                                "minItems": 2,
                                "maxItems": MAX_GROUP_BLOCKS,
                                "items": {
                                    "type": "string",
                                    "description": (
                                        "Verbatim quote from corresponding "
                                        "source PDF block"
                                    ),
                                },
                            },
                        },
                        "required": ["cue", "blocks", "quotes"],
                    },
                ]
            },
        },
    },
    "required": ["matches"],
}


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


def repair_numbered_heading_body_pair(
    matches: object, missing: list[tuple[int, str]], blocks: list[tuple],
) -> object:
    """Recover an explicit *Question N / Answer N + adjacent source body*.

    A model may quote only a printed numbered question/answer heading or
    only its following body, although the narrated cue combines the number
    and physical content. The only repair is a UNIQUE, same-kind two-block
    source-PDF pair with a matching "Question N:" or "Answer N:" heading and
    its immediately adjacent, lexically corroborated body. Original model
    quotes must already belong to these exact regions. Never invent a
    number, infer an equation, join different problems, change the source
    speech, or treat this as academic certification. Independent PDF, cue,
    audio and highlight validators remain mandatory.
    """
    if not isinstance(matches, list) or len(matches) != len(missing):
        return matches
    required = dict(missing)
    repaired = []
    for row in matches:
        if (not isinstance(row, dict)
                or type(row.get("cue")) is not int
                or row["cue"] not in required):
            return matches
        spoken = required[row["cue"]]
        ordinal = re.search(
            r"\b(question|answer)\s+([1-9]\d{0,2})\b", spoken, re.I)
        if not ordinal:
            repaired.append(row)
            continue
        kind, num = ordinal.group(1), ordinal.group(2)
        pair_headers = [
            i for i, block in enumerate(blocks[:-1])
            if re.match(
                r"^\s*" + re.escape(kind) + r"\s+" +
                re.escape(num) + r"\s*:",
                str(block[1]), re.I
            )
        ]
        if len(pair_headers) != 1:
            repaired.append(row)
            continue
        header = pair_headers[0]
        body = header + 1
        header_text = str(blocks[header][1])
        body_text = str(blocks[body][1])
        if (len(body_text) < 20
                or not numbers(spoken).issubset(
                    numbers(header_text + " " + body_text))):
            repaired.append(row)
            continue
        # A mathematical / verbal match is necessary; proximity and a
        # question number alone cannot justify selecting a random block.
        words = lambda text: set(re.findall(r"[a-z]{4,}", text.casefold()))
        shared_body = words(spoken) & words(body_text)
        if len(shared_body) < 3:
            repaired.append(row)
            continue
        fields = set(row)
        if fields == {"cue", "block", "quote"}:
            selected, given_quotes = [row["block"]], [row["quote"]]
        elif fields == {"cue", "blocks", "quotes"}:
            selected, given_quotes = row["blocks"], row["quotes"]
        else:
            repaired.append(row)
            continue
        if (not isinstance(selected, list)
                or not isinstance(given_quotes, list)
                or len(selected) != len(given_quotes)
                or not selected
                or any(type(s) is not int or s not in (header + 1, body + 1)
                       for s in selected)
                or any(not isinstance(q, str)
                       or not 8 <= len(q) <= 200
                       or len(compact(q)) < 8
                       or compact(q) not in compact(blocks[s-1][1])
                       for s, q in zip(selected, given_quotes))):
            repaired.append(row)
            continue
        # Generate only authentic contiguous PDF-source substrings. The
        # subsequent general validator independently checks both citations.
        a, b = header_text[:160].strip(), body_text[:160].strip()
        if (not 8 <= len(a) <= 200 or not 8 <= len(b) <= 200
                or len(compact(a)) < 8 or len(compact(b)) < 8):
            repaired.append(row)
            continue
        if selected != [header + 1, body + 1]:
            print("[semantic source] unique numbered heading/body "
                  f"pair recovered for cue {row['cue']}; original-PDF "
                  "numeric/quote checks still required", flush=True)
        repaired.append({
            "cue": row["cue"],
            "blocks": [header + 1, body + 1],
            "quotes": [a, b],
        })
    return repaired


# Compatibility alias for source-grounded question-pair tests; the shared
# normal planner invokes the generalized question/answer implementation.
repair_question_heading_body_pair = repair_numbered_heading_body_pair


def repair_unique_verbatim_quote_location(
    matches: object, missing: list[tuple[int, str]], blocks: list[tuple],
) -> object:
    """Re-anchor a real model quote misindexed within the SAME source PDF page.

    Reuses PR #258's source-line recovery principle: only a unique existing
    source fragment can repair a citation. Never invent/replace the quote,
    infer meaning from an index, remap duplicated text or override an
    unsupported scientific number. Original full validator runs afterward.
    """
    if not isinstance(matches, list) or len(matches) != len(missing):
        return matches
    needed = dict(missing)
    result = []
    for row in matches:
        if not isinstance(row, dict) or type(row.get("cue")) is not int:
            return matches
        spoken = needed.get(row["cue"])
        if spoken is None:
            return matches
        if set(row) == {"cue", "block", "quote"}:
            chosen, quotes = [row["block"]], [row["quote"]]
        elif set(row) == {"cue", "blocks", "quotes"}:
            chosen, quotes = row["blocks"], row["quotes"]
        else:
            result.append(row)
            continue
        if (not isinstance(chosen, list) or not isinstance(quotes, list)
                or not chosen or len(chosen) != len(quotes)
                or len(chosen) > MAX_GROUP_BLOCKS
                or any(type(x) is not int or not 1 <= x <= len(blocks)
                       for x in chosen)
                or any(not isinstance(q, str) or not 8 <= len(q) <= 200
                       or len(compact(q)) < 8 for q in quotes)):
            result.append(row)
            continue
        valid_at_current = all(
            compact(q) in compact(str(blocks[b-1][1]))
            for b, q in zip(chosen, quotes))
        if valid_at_current:
            result.append(row)
            continue
        # Every supplied quote must exist in EXACTLY ONE actual rendered PDF
        # text block, including after whitespace/superscript normalization.
        anchors = []
        for quote in quotes:
            positions = [i for i, block in enumerate(blocks, 1)
                         if compact(quote) in compact(str(block[1]))]
            if len(positions) != 1:
                break
            anchors.append(positions[0])
        if (len(anchors) != len(quotes) or len(set(anchors)) != len(anchors)
                or anchors != list(range(anchors[0], anchors[0] + len(anchors)))
                or (len(anchors) == 1 and len(chosen) != 1)):
            result.append(row)
            continue
        labels = " ".join(str(blocks[x-1][1]) for x in anchors)
        if not numbers(spoken).issubset(numbers(labels)):
            result.append(row)
            continue
        # A shifted citation needs INDEPENDENT cue/source corroboration;
        # verbatim presence alone could still cite an unrelated source line.
        tokens = lambda s: set(re.findall(r"[a-z]{4,}", s.casefold()))
        if len(tokens(spoken) & tokens(labels)) < 2:
            result.append(row)
            continue
        recovered = {"cue": row["cue"]}
        if len(anchors) == 1:
            recovered.update(block=anchors[0], quote=quotes[0])
        else:
            recovered.update(blocks=anchors, quotes=list(quotes))
        print("[semantic source] re-anchored unique original-PDF quotation "
              f"for cue {row['cue']}; source/numeric validation mandatory",
              flush=True)
        result.append(recovered)
    return result


def source_quote_constrained_schema(blocks: list[tuple]) -> dict:
    """Constrain one existing Gemini request to actual source-PDF quote strings.

    This is a generation-time prevention of invented verbatim citations,
    analogous to the established provider-native *shape* schema. The
    original quote/block/numeric postcondition remains required.
    """
    import copy
    schema = copy.deepcopy(SEMANTIC_RESPONSE_JSON_SCHEMA)
    candidates = []
    for block in blocks:
        label = block[1]
        if not isinstance(label, str):
            continue
        # Use source-exact substrings; never generate an alternative
        # rendering or silently make a model quotation source-valid.
        for excerpt in ((label[:160].strip(), label[-160:].strip())
                        if len(label) > 170 else (label.strip(),)):
            if 8 <= len(excerpt) <= 200 and len(compact(excerpt)) >= 8:
                if excerpt not in candidates:
                    candidates.append(excerpt)
    if not candidates or len(candidates) > 80 or sum(map(len, candidates)) > 10000:
        return schema  # Existing strict validator still protects all calls.
    single, grouped = schema["properties"]["matches"]["items"]["anyOf"]
    single["properties"]["quote"]["enum"] = candidates
    grouped["properties"]["quotes"]["items"]["enum"] = candidates
    return schema


def persist_private_semantic_failure(
    stage: object, slide: int, original_proposal: object,
    missing: list[tuple[int, str]], blocks: list[tuple], error: Exception,
) -> bool:
    """Preserve one failed model proposal ONLY in the authorized private HP root.

    Past terminal G2 runs lost the actual model quotation, forcing speculative
    diagnosis and repeat billing. The record is never copied to source/output,
    Git, stdout, or a public artifact. Its content has a strict byte ceiling.
    """
    import hashlib
    import os
    from pathlib import Path
    import socket
    root = Path(os.environ.get("LOCALAPPDATA", "")).resolve()
    stage = Path(stage).resolve()
    private_root = root / "MicroGen_AI_Checkpoints"
    if (socket.gethostname().casefold() != "hp"
            or stage.parent.parent != private_root
            or not (stage.parent / ".microgen_bounded_provider_authorization.json").is_file()
            or not isinstance(slide, int) or not 1 <= slide <= 200):
        return False
    slide_file, script_file = stage / "slides.pdf", stage / "script_tts.json"
    if not slide_file.is_file() or not script_file.is_file():
        return False
    reason = ("UNTRUSTED_SEMANTIC_QUOTE"
              if isinstance(error, SemanticMappingError)
              and "Quoted evidence not present" in str(error)
              else "UNTRUSTED_SEMANTIC_SOURCE_EVIDENCE")
    try:
        saved = {
            "schema_version": 1,
            "status": "PRIVATE_FAILED_MODEL_PROPOSAL_NOT_ACCEPTED",
            "reason_code": reason,
            "slide": slide,
            "slides_pdf_sha256": hashlib.sha256(slide_file.read_bytes()).hexdigest(),
            "script_tts_sha256": hashlib.sha256(script_file.read_bytes()).hexdigest(),
            "source_blocks_sha256": hashlib.sha256(json.dumps(
                [str(row[1]) for row in blocks], ensure_ascii=False
            ).encode("utf8")).hexdigest(),
            "unresolved_cue_ids": [n for n, _ in missing],
            "original_model_proposal": original_proposal,
            "publication_allowed": False,
            "accepted_semantic_mapping": False,
        }
        raw = json.dumps(saved, ensure_ascii=False, sort_keys=True, indent=2)
        if len(raw.encode("utf8")) > 16000:
            saved["original_model_proposal"] = None
            saved["proposal_oversize_not_retained"] = True
            raw = json.dumps(saved, ensure_ascii=False, sort_keys=True, indent=2)
        target = stage / f".microgen_private_semantic_failed_slide_{slide}.json"
        if target.exists() or target.is_symlink():
            return False
        with target.open("x", encoding="utf8") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return True
    except (OSError, ValueError, TypeError):
        return False


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
            "Cite every selected source block using at least eight verbatim "
            "characters. If ANY cue cannot be grounded, return an empty matches "
            "array. Never invent labels, blocks, numbers or source quotes."
        ),
        "slide": slide,
        "unresolved_cues": [{"cue": n, "spoken": text[:600]} for n, text in missing],
        "source_blocks": [{"block": i, "text": row[1]} for i, row in enumerate(blocks, 1)],
    }
    response = call_with_client_failover(
        create_gemini_client,
        lambda client: client.models.generate_content(
            model="gemini-3.8-flash",
            contents=json.dumps(prompt, ensure_ascii=False),
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
                # Use provider-native constrained decoding to prevent
                # predictable response-shape errors before the existing
                # deterministic normalizer / original-PDF validator run.
                "response_json_schema": source_quote_constrained_schema(blocks),
            },
        ),
        label=f"MicroGen semantic cue screen slide {slide}",
        max_retries=0,
    )
    # A narrow, deterministic representation adapter handles harmless JSON
    # wrappers, exact cue-index aliases and parsed SDK objects from THIS
    # request. It never retries Gemini, rewrites source, or certifies meaning.
    # The actual original-PDF verifier remains the mandatory postcondition.
    return _parse_semantic_model_response(response, missing)
