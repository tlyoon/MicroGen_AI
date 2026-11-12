"""Source-grounded narration element cues with optional bounded semantic screen.

The default remains strictly offline and lexical. Only explicit Gemini opt-in
can propose anchors for paraphrases. The existing PDF bbox/text, source hash,
numerical claim, cue order and downstream TTS validation remain authoritative.
Semantic entailment is NOT certified; no publication or phoneme claim.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

PLAN_FILE = ".microgen_timed_cue_plan.json"
STOP = frozenset("""a an and are as at be been by can do does for from had has have
he her here in into is it its may of on or our per than that the their
there these they this those to via was were when where which while who will
with within would we you your one two three four five six seven eight nine
first second third into through about all each energy example consider
concept system model physical therefore represents represents""".split())
WORD = re.compile(r"[^\W\d_][\w-]*", re.UNICODE)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


class CuePlanningError(RuntimeError):
    """No sufficiently grounded, complete, bounded cue plan could be made."""


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized(text: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold()
                   if c.isalnum())


def salient(text: str) -> set[str]:
    return {word.casefold().strip("-") for word in WORD.findall(text)
            if len(word) >= 4 and word.casefold() not in STOP}


def speech_units(text: str) -> list[str]:
    from microgen_flash_tts import _split_tts_text
    stripped = re.sub(r"\s+", " ", text).strip()
    if not stripped:
        raise CuePlanningError("Empty source narration")
    fragments = []
    for sentence in SENTENCE.split(stripped):
        fragments.extend(_split_tts_text(sentence, max_chars=390))
    fragments = [x.strip() for x in fragments if x.strip()]
    if not fragments or normalized(" ".join(fragments)) != normalized(stripped):
        raise CuePlanningError("Narration splitting lost source content")
    # Very brief fragments are not independently synthesizeable.
    result = []
    for fragment in fragments:
        if len(fragment) < 18 and result:
            result[-1] += " " + fragment
        else:
            result.append(fragment)
    if len(result) >= 2 and len(result[0]) < 18:
        result[1] = result[0] + " " + result[1]
        del result[0]
    return result


def source_grounded_speech_units(text: str, blocks: list[tuple]) -> list[str]:
    """Split only a numerical cue spanning independently printed PDF regions.

    A model must not invent a giant source highlight joining a title and a
    distant equation. Prefer intact narration; when a comma separates two
    individually source-attested numerical claims, split there with all
    original words and punctuation intact. The same logic is used by
    preflight and production plan/TTS, never by paid transcription.
    """
    from microgen_cue_semantic_mapping import numbers

    units = speech_units(text)
    source_values = [numbers(label) for _, label, _ in blocks]
    def split_one(fragment: str) -> list[str]:
        claims = numbers(fragment)
        if not claims or any(claims.issubset(value) for value in source_values):
            return [fragment]
        choices = []
        for match in re.finditer(r",\s+", fragment):
            left, right = fragment[:match.start()+1].strip(), fragment[match.end():].strip()
            if len(left) < 18 or len(right) < 18:
                continue
            left_nums, right_nums = numbers(left), numbers(right)
            if not left_nums or not right_nums:
                continue
            if (any(left_nums.issubset(vals) for vals in source_values)
                    and any(right_nums.issubset(vals) for vals in source_values)):
                choices.append((abs(len(left)-len(right)), left, right))
        if not choices:
            return [fragment]
        _, left, right = min(choices, key=lambda item: item[0])
        return split_one(left) + split_one(right)

    result = [piece for fragment in units for piece in split_one(fragment)]
    if (len(result) > 40 or normalized(" ".join(result)) != normalized(text)
            or any(not piece or len(piece) < 10 for piece in result)):
        raise CuePlanningError("Source-preserving narration cue splitting failed")
    return result


def prepare_slide_pages(stage: Path) -> list[Path]:
    """One source-preserving, byte-stable page extraction before opt-in TTS.

    This closes the existing pipeline dependency: ordinary slide slicing runs
    after TTS, but measured element cues require verified page PDFs earlier.
    Existing valid pages are never overwritten; a mismatched page fails closed.
    """
    import fitz
    import io
    import os
    from PyPDF2 import PdfReader, PdfWriter

    stage=Path(stage)
    slide_deck=stage/"slides.pdf"
    if slide_deck.is_symlink() or not slide_deck.is_file():
        raise CuePlanningError("No verified slide deck to slice")
    inserted=[]
    try:
        with fitz.open(str(slide_deck)) as full:
            if not 1<=full.page_count<=200:
                raise CuePlanningError("Invalid PDF page count")
            reader=PdfReader(str(slide_deck))
            if len(reader.pages)!=full.page_count:
                raise CuePlanningError("PDF page count discrepancy")
            targets=[]
            for page_index in range(full.page_count):
                target=stage/f"slide{page_index+1}.pdf"
                if target.is_symlink():
                    raise CuePlanningError("Unsafe existing slide PDF symlink")
                if target.exists():
                    if not target.is_file():
                        raise CuePlanningError("Unsafe existing slide PDF")
                    with fitz.open(str(target)) as old:
                        if (old.page_count!=1 or
                            normalized(old[0].get_text())!=
                            normalized(full[page_index].get_text())):
                            raise CuePlanningError(
                                "Existing sliced slide differs from source deck")
                    targets.append(target)
                    continue
                # Original established PyPDF2 slicing format, not a separate
                # downstream page renderer.
                writer=PdfWriter()
                writer.add_page(reader.pages[page_index])
                stream=io.BytesIO()
                writer.write(stream)
                payload=stream.getvalue()
                with fitz.open(stream=payload,filetype="pdf") as check:
                    if (check.page_count!=1 or
                        normalized(check[0].get_text())!=
                        normalized(full[page_index].get_text())):
                        raise CuePlanningError("Source PDF page extraction altered text")
                # Exclusive create avoids overwrite after a concurrent run.
                with target.open("xb") as handle:
                    handle.write(payload)
                inserted.append(target)
                targets.append(target)
        return targets
    except Exception:
        # Remove only pages created by this call; leave all previous data.
        for target in reversed(inserted):
            target.unlink(missing_ok=True)
        raise



def _pdf_text_blocks(page) -> list[tuple]:
    """Preserve visible equation elements as well as prose in both normal paths.

    Previous extraction silently threw away mathematics containing only short
    variables and numbers (e.g., `vxf = 40 - 5(2)2 = 20 m/s`), so a genuine
    printed result looked absent to the downstream source-evidence gate.
    The same source-PDF coordinate/text constraints still apply.
    """
    blocks = []
    for block in page.get_text("blocks"):
        # PyMuPDF returns image blocks too. Only accept extractable PDF text.
        if len(block) < 7 or block[6] != 0:
            continue
        label = str(block[4]).strip()
        terms = salient(label)
        math_text = (
            len(normalized(label)) >= 8
            and bool(re.search(r"[=+−×÷∆Δ∂∫√≤≥<>]", label))
            and bool(re.search(r"\d|[A-Za-zα-ωΑ-Ω]", label))
        )
        if (len(label) < 3 or (not terms and not math_text)
                or re.fullmatch(r"\s*\d+\s*/\s*\d+\s*", label)):
            continue
        box = list(map(float, block[:4]))
        if (box[0] < -0.5 or box[1] < -0.5
                or box[2] > page.rect.width + 0.5
                or box[3] > page.rect.height + 0.5):
            continue
        blocks.append((box, label[:350], terms))
    return blocks


def _lexical_match(slide_no: int, texts: list[str], blocks: list[tuple],
                   *, allow_unanchored: bool) -> tuple[list, list[tuple]]:
    """Identical matching logic for private full-lecture admission and cue planning."""
    used = set()
    cues = [None] * len(texts)
    unresolved = []
    for cue_number, spoken in enumerate(texts, 1):
        terms = salient(spoken)
        if not terms and not allow_unanchored:
            raise CuePlanningError(f"Slide {slide_no}: narration has no anchored terms")
        from microgen_cue_semantic_mapping import numbers
        claim_values = numbers(spoken)
        scored = []
        for block_number, (box, label, tokens) in enumerate(blocks):
            # A lexical hit does NOT override a contradictory or absent
            # numeric value in the chosen source element. Combined claims
            # across blocks must take the verified semantic-group path.
            if not claim_values.issubset(numbers(label)):
                continue
            shared = terms & tokens
            evidence = len(shared) / max(1, min(6, len(terms)))
            evidence += 0.02 * len(shared)
            # Reuse is a presentation preference, NOT a reason to discard
            # independently sufficient source-text evidence. A later spoken
            # cue may genuinely refer to the same visible element again.
            preference = evidence - (0.25 if block_number in used else 0.0)
            scored.append((preference, evidence, len(shared), block_number))
        if scored:
            _, evidence, overlap, winner = max(scored)
        else:
            # No one PDF element contains all spoken numeric claims.
            # A verified multi-element semantic group may still support it.
            evidence, overlap, winner = 0.0, 0, 0
        if scored and (not terms or overlap < 2 or evidence < 0.32):
            # The presentation preference can otherwise select an unsupported
            # unused element over the actual, previously highlighted element.
            # Fall back only to the same conservative lexical threshold; do
            # not infer semantics or relax the two-term evidence requirement.
            _, evidence, overlap, winner = max(
                scored, key=lambda candidate: (candidate[1], candidate[2],
                                               candidate[0]))
        if not terms or overlap < 2 or evidence < 0.32:
            # A single-block title/card may be spoken verbatim even when it
            # contains only one salient word (e.g. a numbered section title).
            # Its complete visible phrase and all spoken numbers must match.
            # Never generalize this exception to a sparse paraphrase or an
            # ambiguous multi-block slide.
            verbatim_single = False
            if len(blocks) == 1 and len(terms) == 1:
                from microgen_cue_semantic_mapping import numbers
                label = blocks[0][1]
                exact = normalized(label)
                verbatim_single = (
                    len(exact) >= 10 and exact in normalized(spoken)
                    and terms.issubset(blocks[0][2])
                    and numbers(spoken).issubset(numbers(label))
                )
                if verbatim_single:
                    winner = 0
            # Before any paid semantic proposal, reuse unique verbatim
            # mathematical evidence already printed in the fixed PDF. This
            # is not numerical inference: the exact signed expression or
            # initial/final values must share one unambiguous source block.
            from microgen_cue_semantic_mapping import exact_math_source_block
            mathematical = exact_math_source_block(spoken, blocks)
            if mathematical is not None:
                winner = mathematical
            if not verbatim_single and mathematical is None and (
                    not terms or overlap < 2 or evidence < 0.32):
                unresolved.append((cue_number, spoken))
                continue
        used.add(winner)
        box, label, _ = blocks[winner]
        cues[cue_number - 1] = {
            "element_id": f"s{slide_no}_e{cue_number}",
            "pdf_text": label, "spoken_text": spoken,
            "pdf_bbox": box,
        }
    return cues, unresolved


def _require_visible_numeric_evidence(
    slide_no: int, texts: list[str], blocks: list[tuple],
) -> None:
    """Fail early when no PDF text block supports a spoken numeric literal.

    The semantic proposal protocol permits only exact source-PDF text
    regions; it cannot invent a region containing a calculated result.
    A mathematically correct derived number that is NOT printed on the
    slide needs an independent derivation certificate (not implemented)
    or source-anchored narration revised under a new permitted campaign.
    This guard makes such a case deterministic *before* spending on a
    doomed Gemini semantic mapping. It never asserts the calculation wrong.
    """
    from microgen_cue_semantic_mapping import numbers

    visible = set().union(*(numbers(label) for _, label, _ in blocks))
    for cue_no, spoken in enumerate(texts, 1):
        unavailable = numbers(spoken) - visible
        if unavailable:
            raise CuePlanningError(
                f"Slide {slide_no} cue {cue_no}: "
                "UNATTESTED_VISIBLE_NUMERIC_CUE: spoken numeric value has "
                "no matching literal in extractable PDF text elements; "
                "source-grounded narration or an independently verified "
                "mathematical derivation is "
                "required before semantic mapping; no semantic calls made"
            )


def _require_budget_preflight(stage: Path, *, semantic_limit: int,
                              max_cues: int) -> None:
    """Before *any* semantic API request inspect the entire frozen lecture.

    An unaffordable known number of slides is not recoverable by key rotation.
    Reusing the same lexical matcher avoids stale divergent admission rules.
    No model calls, files written, narration edits, or budget increases occur.
    """
    import fitz
    pdf = stage / "slides.pdf"
    script = stage / "script_tts.json"
    if any(p.is_symlink() or not p.is_file() for p in (pdf, script)):
        raise CuePlanningError("Slide PDF and narration sidecar required")
    try:
        source = json.loads(script.read_text(encoding="utf8"))["slides"]
        with fitz.open(pdf) as doc:
            if not isinstance(source, list) or len(source) != doc.page_count:
                raise CuePlanningError("Narration/PDF page counts differ")
            assisted_slides = []
            cues_seen = 0
            for slide_no, (row, page) in enumerate(zip(source, doc), 1):
                if not isinstance(row, dict) or row.get("slide") != slide_no:
                    raise CuePlanningError("Narration slide order changed")
                one = stage / f"slide{slide_no}.pdf"
                if one.is_symlink() or not one.is_file():
                    raise CuePlanningError("Source PDF page has not been sliced")
                with fitz.open(one) as single:
                    if single.page_count != 1 or (
                            normalized(single[0].get_text()) !=
                            normalized(page.get_text())):
                        raise CuePlanningError("Numbered PDF differs from source deck")
                blocks = _pdf_text_blocks(page)
                if not blocks:
                    raise CuePlanningError(f"Slide {slide_no}: no grounded text blocks")
                texts = source_grounded_speech_units(
                    str(row.get("tts_text") or row.get("narration") or ""), blocks)
                cues_seen += len(texts)
                if cues_seen > max_cues:
                    raise CuePlanningError("Cue inventory exceeds one global voice batch")
                _require_visible_numeric_evidence(slide_no, texts, blocks)
                _, unresolved = _lexical_match(
                    slide_no, texts, blocks, allow_unanchored=True)
                if unresolved:
                    assisted_slides.append(slide_no)
            if len(assisted_slides) > semantic_limit:
                raise CuePlanningError(
                    "Bounded semantic slide budget exceeded in offline preflight: "
                    f"required={len(assisted_slides)} allowed={semantic_limit} "
                    f"slides={assisted_slides}; no semantic requests made")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError,
            KeyError, IndexError, ValueError, RuntimeError) as exc:
        if isinstance(exc, CuePlanningError):
            raise
        raise CuePlanningError("Semantic admission preflight cannot verify source") from exc


def propose_plan(stage: Path, *, max_cues: int = 120, semantic_resolver=None) -> dict:
    """Do not write any source file; caller may save verified proposal itself."""
    import fitz
    stage = Path(stage)
    # Explicit opt-in prevents hidden billed requests during legacy/offline runs.
    # Tests may inject a non-billing resolver for deterministic validation.
    if semantic_resolver is None and os.environ.get("MICROGEN_TIMED_SEMANTIC_ASSIST") == "1":
        from microgen_cue_semantic_mapping import propose_with_gemini
        semantic_resolver = propose_with_gemini
    semantic_limit = int(os.environ.get("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "4"))
    if not 1 <= semantic_limit <= 40:
        raise CuePlanningError("Invalid bounded semantic slide budget")
    # An entire lecture may need >budget slides even when the first assisted
    # slide is easy. Refuse before incurring a doomed sequence of model calls.
    if semantic_resolver is not None:
        _require_budget_preflight(
            stage, semantic_limit=semantic_limit, max_cues=max_cues)
    semantic_slides = 0
    pdf = stage / "slides.pdf"
    narration_path = stage / "script_tts.json"
    if any(p.is_symlink() or not p.is_file() for p in (pdf, narration_path)):
        raise CuePlanningError("Slide PDF and narration sidecar required")
    try:
        source = json.loads(narration_path.read_text(encoding="utf8"))["slides"]
        if not isinstance(source, list):
            raise ValueError("Not a list")
        with fitz.open(pdf) as doc:
            if len(source) != doc.page_count or not 1 <= len(source) <= 200:
                raise CuePlanningError("Narration/PDF page counts differ")
            inventory = []
            total_cues = 0
            for slide_no, (row, page) in enumerate(zip(source, doc), 1):
                if not isinstance(row, dict) or row.get("slide") != slide_no:
                    raise CuePlanningError("Narration slide order changed")
                one = stage / f"slide{slide_no}.pdf"
                if one.is_symlink() or not one.is_file():
                    raise CuePlanningError("Source PDF page has not been sliced")
                with fitz.open(one) as single:
                    if (single.page_count != 1 or
                            normalized(single[0].get_text()) != normalized(page.get_text())):
                        raise CuePlanningError("Numbered PDF differs from source deck")
                speech = str(row.get("tts_text") or row.get("narration") or "")
                blocks = _pdf_text_blocks(page)
                if not blocks:
                    raise CuePlanningError(f"Slide {slide_no}: no grounded text blocks")
                texts = source_grounded_speech_units(speech, blocks)
                if total_cues + len(texts) > max_cues:
                    raise CuePlanningError("Cue inventory exceeds one global voice batch")
                _require_visible_numeric_evidence(slide_no, texts, blocks)
                cues, unresolved = _lexical_match(
                    slide_no, texts, blocks,
                    allow_unanchored=semantic_resolver is not None)
                if unresolved:
                    if semantic_resolver is None:
                        raise CuePlanningError(
                            f"Slide {slide_no} cue {unresolved[0][0]}: insufficient "
                            "narration-to-PDF text overlap; cannot invent mapping")
                    semantic_slides += 1
                    if semantic_slides > semantic_limit:
                        raise CuePlanningError("Bounded semantic slide budget exceeded")
                    from microgen_cue_semantic_mapping import (
                        validate_matches, SemanticMappingError,
                        repair_numbered_heading_body_pair,
                    )
                    try:
                        choices = semantic_resolver(slide_no, unresolved, blocks)
                        # Gemini may cite a question/answer's genuine body
                        # but omit its immediately preceding "Question N:"
                        # or "Answer N:" heading, or vice versa. Recover
                        # only an independently UNIQUE, lexically supported
                        # adjacent two-block pair in the actual source PDF.
                        # The unchanged numeric and quote gates run afterward.
                        choices = repair_numbered_heading_body_pair(
                            choices, unresolved, blocks)
                        verified = validate_matches(choices, unresolved, blocks)
                    except (SemanticMappingError, ValueError, KeyError) as exc:
                        raise CuePlanningError(
                            f"Slide {slide_no}: untrusted semantic proposal: {exc}") from exc
                    except Exception as exc:
                        # Distinguish a failed external model/key request from
                        # bad source PDF content. Never retry an unchanged PDF
                        # as a 'LaTeX fix' for a Gemini service outage.
                        raise CuePlanningError(
                            f"Slide {slide_no}: semantic service unavailable "
                            f"({type(exc).__name__}); no plan published") from exc
                    for number, spoken in unresolved:
                        indices, quotes = verified[number]
                        if len(indices) == 1:
                            box, label, _ = blocks[indices[0]]
                            cues[number-1] = {
                                "element_id": f"s{slide_no}_e{number}",
                                "pdf_text": label, "spoken_text": spoken,
                                "pdf_bbox": box, "semantic_source_quote": quotes[0],
                            }
                            continue
                        # A spoken list may refer to several *adjacent* real
                        # PDF elements. Keep every actual region and quote,
                        # not a fabricated single-source element.
                        regions = [blocks[index][0] for index in indices]
                        x0 = min(box[0] for box in regions)
                        y0 = min(box[1] for box in regions)
                        x1 = max(box[2] for box in regions)
                        y1 = max(box[3] for box in regions)
                        union = [x0, y0, x1, y1]
                        if (x1 <= x0 or y1 <= y0 or
                                (x1 - x0) * (y1 - y0) >
                                page.rect.width * page.rect.height * 0.40):
                            raise CuePlanningError(
                                f"Slide {slide_no}: unsafe multi-element region")
                        group_text = page.get_textbox(fitz.Rect(union)).strip()
                        if (not 8 <= len(group_text) <= 400 or
                                any(normalized(blocks[index][1]) not in
                                    normalized(group_text) for index in indices)):
                            raise CuePlanningError(
                                f"Slide {slide_no}: multi-element text not fully visible")
                        cues[number-1] = {
                            "element_id": f"s{slide_no}_e{number}",
                            "spoken_text": spoken,
                            "pdf_text": group_text, "pdf_bbox": union,
                            "pdf_bboxes": regions,
                            "pdf_texts": [blocks[index][1] for index in indices],
                            "semantic_source_quotes": list(quotes),
                        }
                if any(cue is None for cue in cues):
                    raise CuePlanningError("Incomplete cue proposal")
                total_cues += len(cues)
                if total_cues > max_cues:
                    raise CuePlanningError("Cue inventory exceeds one global voice batch")
                inventory.append({
                    "slide": slide_no, "slide_pdf_sha256": sha(one),
                    "cues": cues,
                })
    except (OSError, UnicodeDecodeError, json.JSONDecodeError,
            KeyError, IndexError, ValueError, RuntimeError) as exc:
        if isinstance(exc, CuePlanningError):
            raise
        raise CuePlanningError("Unreadable PDF or source narration") from exc
    return {
        "schema_version": 1, "planning_method": (
            "source_pdf_grounded_semantic_screen" if semantic_slides
            else "source_pdf_overlap_conservative"
        ),
        "slides_pdf_sha256": sha(pdf),
        "script_tts_sha256": sha(narration_path),
        "slides": inventory, "total_cues": total_cues,
        "publication_allowed": False,
        "semantic_mapping_certified": False,
        "semantic_assist_applied": bool(semantic_slides),
        "speech_phonemes_aligned": False,
    }

def write_verified_plan(stage: Path, *, semantic_resolver=None) -> Path:
    """Store a new, fully checked proposal; never replace an existing plan."""
    stage=Path(stage)
    target=stage/PLAN_FILE
    if target.exists() or target.is_symlink():
        raise CuePlanningError("Existing source-cue plan must be preserved")
    plan=propose_plan(stage, semantic_resolver=semantic_resolver)
    # Verify all mapping claims before publishing the plan to the TTS stage.
    from microgen_timed_cue_tts import _verified_plan
    with target.open("x",encoding="utf8") as handle:
        json.dump(plan,handle,ensure_ascii=False,indent=2)
    try:
        _verified_plan(stage)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target
