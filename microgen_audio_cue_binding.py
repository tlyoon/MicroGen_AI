"""Audio-byte and slide-clock binding for staged timed highlights.

A timestamp created for an earlier WAV must never be reused with corrected
speech. This is a structural safety gate, not phonetic or semantic approval.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import pymupdf

from microgen_source_safe_orchestrator import (
    OrchestratorError, verify_workspace, read_json, digest
)

class AudioCueBindingError(OrchestratorError):
    pass


def _duration(path):
    try:
        with wave.open(str(path), "rb") as wav:
            if wav.getnframes() < 1 or not 8000 <= wav.getframerate() <= 48000:
                raise AudioCueBindingError("Unsupported audio duration/sample rate")
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise AudioCueBindingError("Staged cue audio must be mono PCM16")
            return wav.getnframes() / wav.getframerate()
    except (EOFError, wave.Error, OSError) as exc:
        raise AudioCueBindingError("Audio is not an intact WAV") from exc


def _verified_audio_rows(workspace, *, timeline=None):
    root = Path(workspace).resolve(strict=True)
    source = verify_workspace(root)
    if timeline is None:
        timeline = read_json(root / "measured_timeline.json")
    inventory = read_json(root / "audio_inventory.json")
    intervals = timeline.get("slide_intervals")
    count = source["slide_count"]
    entries = inventory.get("entries")
    if (
        not isinstance(intervals, list) or len(intervals) != count
        or not isinstance(entries, list) or len(entries) != count
        or inventory.get("missing") != []
    ):
        raise AudioCueBindingError("Full slide inventory and timeline required")
    result = []
    elapsed = 0.0
    for slide, (interval, entry) in enumerate(zip(intervals, entries), 1):
        audio = root / "audio" / f"slide{slide}.wav"
        if audio.is_symlink() or not audio.is_file():
            raise AudioCueBindingError("Missing or linked cue source WAV")
        sha = digest(audio)
        seconds = _duration(audio)
        if (
            entry.get("slide") != slide or interval.get("slide") != slide
            or sha != entry.get("sha256") or sha != interval.get("wav_sha256")
            or not all(type(interval.get(x)) in (int,float) and
                       math.isfinite(interval[x])
                       for x in ("start_seconds", "end_seconds"))
            or abs(interval["start_seconds"] - elapsed) > 0.04
            or abs(interval["end_seconds"] - elapsed - seconds) > 0.04
        ):
            raise AudioCueBindingError(
                f"Slide {slide} audio SHA or measured clock has changed"
            )
        result.append({"slide": slide, "wav_sha256": sha,
                       "duration_seconds": round(seconds, 6)})
        elapsed += seconds
    if not (type(timeline.get("duration_seconds")) in (int,float)
            and abs(timeline["duration_seconds"] - elapsed) < .05):
        raise AudioCueBindingError("Lecture duration no longer matches WAVs")
    return source, result, intervals


def bind_cues_to_current_audio(workspace, elements, *,
                               derivation="EXTERNAL_TIMES_REQUIRE_REVIEW"):
    """Create v2 receipt only after checking *actual* WAV bytes and clocks."""
    source, rows, intervals = _verified_audio_rows(workspace)
    if not isinstance(elements, list) or len(elements) > 10000:
        raise AudioCueBindingError("Cue list must be bounded")
    if not isinstance(derivation, str) or len(derivation) > 128:
        raise AudioCueBindingError("Invalid cue derivation descriptor")
    result = {
        "version": 2, "source_pdf_sha256": source["source_pdf_sha256"],
        "narration_sha256": source["narration_sha256"],
        "audio_bindings": rows, "elements": elements,
        "derivation": derivation,
        "spoken_word_alignment_verified": False,
        "mathematics_semantics_verified": False,
        "publication_allowed": False
    }
    validate_audio_bound_cues(workspace, result)
    return result


def validate_audio_bound_cues(workspace, manifest):
    """Fail *before rendering* for old v1 manifests and stale replacement WAVs."""
    source, rows, intervals = _verified_audio_rows(workspace)
    if (
        manifest.get("version") != 2
        or manifest.get("audio_bindings") != rows
        or manifest.get("source_pdf_sha256") != source["source_pdf_sha256"]
        or manifest.get("narration_sha256") != source["narration_sha256"]
        or manifest.get("publication_allowed") is not False
        or manifest.get("spoken_word_alignment_verified") is not False
        or manifest.get("mathematics_semantics_verified") is not False
    ):
        raise AudioCueBindingError(
            "Unbound or stale highlight cues; rederive from replacement audio"
        )
    cues = manifest.get("elements")
    if not isinstance(cues, list) or len(cues) > 10000:
        raise AudioCueBindingError("Cue elements missing or unbounded")
    root = Path(workspace).resolve(strict=True)
    original = Path(source["source_root"]) / "slides.pdf"
    with pymupdf.open(original) as pdf:
        if pdf.page_count != source["slide_count"]:
            raise AudioCueBindingError("Original PDF page count changed")
        for cue in cues:
            slide = cue.get("slide")
            if type(slide) is not int or not 1 <= slide <= len(rows):
                raise AudioCueBindingError("Cue slide identity invalid")
            interval = intervals[slide - 1]
            start, end = cue.get("local_start"), cue.get("local_end")
            global_start, global_end = cue.get("start_seconds"), cue.get("end_seconds")
            box = cue.get("box")
            if (
                not all(type(x) in (float,int) and math.isfinite(x)
                        for x in (start,end,global_start,global_end))
                or not 0 <= start < end <= rows[slide - 1]["duration_seconds"] + .02
                or abs(global_start - interval["start_seconds"] - start) > .025
                or abs(global_end - interval["start_seconds"] - end) > .025
                or not isinstance(box, (list,tuple)) or len(box) != 4
                or not all(type(v) in (float,int) and math.isfinite(v) for v in box)
            ):
                raise AudioCueBindingError("Outdated or malformed cue clock")
            width, height = pdf[slide-1].rect.width, pdf[slide-1].rect.height
            x0,y0,x1,y1=box
            if not (0 <= x0 < x1 <= width+.05 and 0 <= y0 < y1 <= height+.05):
                raise AudioCueBindingError("Cue PDF geometry outside source slide")
    return {"checked_audio_slides":len(rows),
            "checked_cues":len(cues),
            "all_wav_sha256_and_times_current":True,
            "spoken_alignment_approved":False,
            "publication_allowed":False}
