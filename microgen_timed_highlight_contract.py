"""Measured, source-bound element timing for future animated MicroGen lectures.

The original API pipeline currently produces one WAV per whole slide and
looped static PDF images. Do not infer sentence-level timestamps by dividing
that WAV proportionally: doing so cannot prove synchronization.

This module accepts an explicit per-element TTS PCM-chunk manifest. It checks
that the ordered chunk audio is sample-for-sample identical to the whole-slide
WAV, that every highlighted region contains its declared PDF text, and that
all source inputs are hash-bound. It makes no ASR, academic or publication
claim. The renderer and a visual/timing acceptance gate are separate tasks.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import wave
from pathlib import Path

MANIFEST = ".microgen_timed_highlights.json"
SCHEMA_VERSION = 1
MAX_SLIDES = 200
MAX_CUES_PER_SLIDE = 40
MIN_CUE_SECONDS = 0.15
_CHUNK_NAME = re.compile(r"highlight_chunks/slide([1-9]\d*)_cue([1-9]\d*)\.wav\Z")


class HighlightContractError(RuntimeError):
    """Unverifiable source-element or precise PCM timing claim."""


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(stage: Path, name: str) -> Path:
    target = stage / name
    if target.is_symlink() or not target.is_file():
        raise HighlightContractError(f"Missing or unsafe highlight asset: {name}")
    return target


def _equivalent_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())


def _frames_digest(handle: wave.Wave_read) -> str:
    digest = hashlib.sha256()
    remaining = handle.getnframes()
    while remaining:
        block = handle.readframes(min(16384, remaining))
        if not block:
            raise HighlightContractError("Truncated PCM frame stream")
        width = handle.getnchannels() * handle.getsampwidth()
        if len(block) % width:
            raise HighlightContractError("Incomplete PCM frame")
        remaining -= len(block) // width
        digest.update(block)
    return digest.hexdigest()


def _pcm_params(handle: wave.Wave_read) -> tuple[int, int, int]:
    if handle.getcomptype() != "NONE" or handle.getsampwidth() not in (2, 3, 4):
        raise HighlightContractError("Cue requires uncompressed PCM WAV")
    return handle.getnchannels(), handle.getsampwidth(), handle.getframerate()


def _manifest_data(stage: Path) -> dict:
    path = _require(stage, MANIFEST)
    if path.stat().st_size > 500000:
        raise HighlightContractError("Oversized highlight manifest")
    try:
        data = json.loads(path.read_text(encoding="utf8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HighlightContractError("Invalid timed highlight JSON") from exc
    if (not isinstance(data, dict)
            or data.get("schema_version") != SCHEMA_VERSION
            or data.get("timing_method") != "measured_ordered_pcm_chunks"
            or data.get("publication_allowed") is not False):
        raise HighlightContractError("Invalid timing or publication contract")
    return data


def inspect_timed_highlights(stage: Path) -> dict:
    """Read-only validation. Does NOT certify that words were spoken on cue."""
    stage = Path(stage)
    if stage.is_symlink() or not stage.is_dir():
        raise HighlightContractError("Highlight stage must be a real directory")
    data = _manifest_data(stage)
    deck = _require(stage, "slides.pdf")
    script = _require(stage, "script_tts.json")
    if (data.get("slides_pdf_sha256") != _hash(deck)
            or data.get("script_tts_sha256") != _hash(script)):
        raise HighlightContractError("Highlight deck or narration source changed")

    try:
        import fitz
        with fitz.open(str(deck)) as pdf:
            count = pdf.page_count
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        raise HighlightContractError("Unreadable source slide PDF") from exc
    if not 1 <= count <= MAX_SLIDES:
        raise HighlightContractError("Invalid slide count")

    try:
        sidecar = json.loads(script.read_text(encoding="utf8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HighlightContractError("Unreadable narration sidecar") from exc
    narration = sidecar.get("slides", [])
    slide_rows = data.get("slides", [])
    if (not isinstance(narration, list)
            or [x.get("slide") for x in narration] != list(range(1, count + 1))
            or not isinstance(slide_rows, list)
            or [x.get("slide") for x in slide_rows] != list(range(1, count + 1))):
        raise HighlightContractError("Missing or reordered narrated slide cues")

    result = []
    for slide_no, row in enumerate(slide_rows, 1):
        pdf_file = _require(stage, f"slide{slide_no}.pdf")
        wav_file = _require(stage, f"slide{slide_no}.wav")
        if (row.get("slide_pdf_sha256") != _hash(pdf_file)
                or row.get("slide_wav_sha256") != _hash(wav_file)):
            raise HighlightContractError(f"Slide {slide_no} PDF/WAV hash changed")
        try:
            with fitz.open(str(pdf_file)) as doc:
                if doc.page_count != 1:
                    raise HighlightContractError("Highlight source must be a single PDF page")
                page = doc[0]
                page_w, page_h = float(page.rect.width), float(page.rect.height)
                box = page.rect
                # Bind the individual PDF page to the exact corresponding deck.
                with fitz.open(str(deck)) as full:
                    if _equivalent_text(page.get_text()) != _equivalent_text(
                            full[slide_no - 1].get_text()):
                        raise HighlightContractError("Slide PDF page differs from lecture deck")
                cues = row.get("cues")
                if not isinstance(cues, list) or not 1 <= len(cues) <= MAX_CUES_PER_SLIDE:
                    raise HighlightContractError("Missing or excessive element cues")
                seen_ids = set()
                position = 0
                samples_hash = hashlib.sha256()
                try:
                    with wave.open(str(wav_file), "rb") as whole:
                        params = _pcm_params(whole)
                        total_frames = whole.getnframes()
                        whole_digest = _frames_digest(whole)
                except (OSError, ValueError, wave.Error) as exc:
                    raise HighlightContractError("Invalid complete WAV") from exc
                elements = []
                for cue_index, cue in enumerate(cues, 1):
                    if not isinstance(cue, dict):
                        raise HighlightContractError("Invalid highlight cue object")
                    element = cue.get("element_id")
                    label = cue.get("pdf_text")
                    rect = cue.get("pdf_bbox")
                    if (not isinstance(element, str)
                            or not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", element)
                            or element in seen_ids or not isinstance(label, str)
                            or not 2 <= len(label) <= 400
                            or not isinstance(rect, list) or len(rect) != 4
                            or any(type(v) not in (int, float) or not math.isfinite(v)
                                   for v in rect)):
                        raise HighlightContractError("Invalid or duplicate PDF element")
                    seen_ids.add(element)
                    x0, y0, x1, y1 = map(float, rect)
                    if (x0 < box.x0 or y0 < box.y0 or x1 > box.x1 or y1 > box.y1
                            or x1 <= x0 or y1 <= y0):
                        raise HighlightContractError("Out-of-page or empty highlighted region")
                    actual = _equivalent_text(page.get_textbox(fitz.Rect(rect)))
                    if not actual or _equivalent_text(label) not in actual:
                        raise HighlightContractError(
                            f"Slide {slide_no} cue {cue_index} is not PDF-text grounded")
                    filename = cue.get("audio_chunk")
                    match = _CHUNK_NAME.fullmatch(filename) if isinstance(filename, str) else None
                    if not match or (int(match.group(1)), int(match.group(2))) != (
                            slide_no, cue_index):
                        raise HighlightContractError("Unsafe or out-of-order PCM chunk path")
                    chunk_file = _require(stage, filename)
                    if cue.get("audio_chunk_sha256") != _hash(chunk_file):
                        raise HighlightContractError("PCM timing chunk changed")
                    try:
                        with wave.open(str(chunk_file), "rb") as piece:
                            if _pcm_params(piece) != params:
                                raise HighlightContractError("Incompatible PCM cue format")
                            frames = piece.getnframes()
                            if frames < MIN_CUE_SECONDS * params[2]:
                                raise HighlightContractError("Cue too brief for stable highlighting")
                            remaining = frames
                            while remaining:
                                block = piece.readframes(min(16384, remaining))
                                if not block:
                                    raise HighlightContractError("Truncated PCM cue")
                                size = params[0] * params[1]
                                if len(block) % size:
                                    raise HighlightContractError("Broken PCM cue frame")
                                samples_hash.update(block)
                                remaining -= len(block) // size
                    except (OSError, ValueError, wave.Error) as exc:
                        raise HighlightContractError("Unreadable PCM timing chunk") from exc
                    elements.append({
                        "element_id": element,
                        "pdf_bbox": [x0, y0, x1, y1],
                        "start_seconds": position / params[2],
                        "end_seconds": (position + frames) / params[2],
                    })
                    position += frames
                if position != total_frames or samples_hash.hexdigest() != whole_digest:
                    raise HighlightContractError(
                        f"Slide {slide_no} cue chunks do not reconstruct WAV exactly")
                result.append({
                    "slide": slide_no, "page_width": page_w,
                    "page_height": page_h, "duration_seconds": total_frames / params[2],
                    "elements": elements,
                })
        except (OSError, ValueError, RuntimeError) as exc:
            if isinstance(exc, HighlightContractError):
                raise
            raise HighlightContractError(f"Cannot inspect slide {slide_no}") from exc
    return {
        "status": "SOURCE_AND_PCM_TIMING_STRUCTURALLY_VERIFIED",
        "slide_count": count,
        "slides": result,
        "manifest_sha256": _hash(stage / MANIFEST),
        "visual_highlight_rendering_verified": False,
        "spoken_word_to_element_alignment_verified": False,
        "publication_allowed": False,
    }
