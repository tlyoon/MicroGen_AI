"""Recompute conservative word cues from the exact WAVs in a staged lesson.

Never use the original lecture's ASR clocks after changing its narration.
Offline ASR is evidence of a *model observation*, not proof of speech, maths,
speaker identity or release suitability. No API, source edits or publication.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

import pymupdf as fitz

from microgen_audio_cue_binding import (
    _verified_audio_rows, bind_cues_to_current_audio,
    validate_audio_bound_cues,
)
from microgen_offline_asr_pdf_highlight import _word, _BLOCKED
from microgen_offline_vosk_capture import (
    capture_offline_words, validate_vosk_words,
)
from microgen_source_safe_orchestrator import (
    OrchestratorError, atomic_json, digest, read_json, verify_workspace,
)


class RealtimeCueError(OrchestratorError):
    pass


def _stage(workspace):
    root = Path(workspace).resolve(strict=True)
    source, audios, intervals = _verified_audio_rows(root)
    return root, source, audios, intervals


def _refuse_output(stage, output):
    output = Path(output).resolve(strict=False)
    if output.exists() or output.is_symlink():
        raise RealtimeCueError("Existing candidate cannot be overwritten")
    if output == Path(stage).resolve(strict=True):
        raise RealtimeCueError("A candidate path cannot be the stage directory")
    return output


def capture_current_audio_asr(workspace, model_directory, ffmpeg, output):
    """Observe all staged WAVs once with a supplied, installed offline Vosk.

    The ASR report is bound to the *current* slide bytes and PDF/script.
    This function never installs weights or sends to an online service.
    """
    stage, source, audios, _ = _stage(workspace)
    dest = _refuse_output(stage, output)
    if dest.is_relative_to(Path(source["source_root"]).resolve(strict=True)):
        raise RealtimeCueError("Cannot write ASR evidence into source files")
    model_dir = Path(model_directory).resolve(strict=True)
    if not model_dir.is_dir() or not (model_dir / "am").is_dir():
        raise RealtimeCueError("Explicit installed offline Vosk model required")
    if not Path(ffmpeg).is_file():
        raise RealtimeCueError("Explicit local FFmpeg required")
    try:
        from vosk import Model
    except ImportError as exc:
        raise RealtimeCueError("Optional Vosk dependency not installed") from exc
    model = Model(str(model_dir))
    results = []
    for audio in audios:
        path = stage / "audio" / f"slide{audio['slide']}.wav"
        result = capture_offline_words(path, model, ffmpeg)
        if result.get("source_wav_sha256") != audio["wav_sha256"]:
            raise RealtimeCueError("WAV changed during offline recognition")
        results.append({"slide": audio["slide"], **result})
    # Recheck entire stage after every recognition, not only the last WAV.
    _, second_source, second_audio, _ = _stage(stage)
    if second_source != source or second_audio != audios:
        raise RealtimeCueError("Staged audio or source changed during ASR")
    data = {
        "schema_version": 1,
        "status": "CURRENT_STAGE_OFFLINE_ASR_NOT_GROUND_TRUTH",
        "source_pdf_sha256": source["source_pdf_sha256"],
        "narration_sha256": source["narration_sha256"],
        "stage_audio_bindings": audios,
        "results": results,
        "phonetic_identity_verified": False,
        "semantic_alignment_verified": False,
        "publication_allowed": False,
    }
    atomic_json(dest, data)
    return {"result": str(dest), "slides": len(results),
            "publication_allowed": False}


def regenerate_stage_cues(workspace, recognition_report, *,
                          minimum_confidence=0.90):
    """Derive new v2 cues for the exact audio already staged, fail closed.

    Refuses the legacy ASR report and old WAV clocks, even if the scene
    index and text are otherwise identical. Never mutates a prior cue file.
    """
    stage, source, audios, intervals = _stage(workspace)
    out = _refuse_output(stage, stage / "cues.json")
    if (type(minimum_confidence) not in (float, int) or
            not math.isfinite(minimum_confidence) or
            not 0.75 <= minimum_confidence <= 1.0):
        raise RealtimeCueError("Invalid confidence cutoff")
    report = read_json(recognition_report)
    if (report.get("schema_version") != 1 or
            report.get("status") != "CURRENT_STAGE_OFFLINE_ASR_NOT_GROUND_TRUTH" or
            report.get("publication_allowed") is not False or
            report.get("phonetic_identity_verified") is not False or
            report.get("semantic_alignment_verified") is not False or
            report.get("source_pdf_sha256") != source["source_pdf_sha256"] or
            report.get("narration_sha256") != source["narration_sha256"] or
            report.get("stage_audio_bindings") != audios):
        raise RealtimeCueError("Recognition must match current WAV and source SHA")
    observations = report.get("results")
    if (not isinstance(observations, list) or len(observations) != len(audios) or
            [row.get("slide") for row in observations if isinstance(row, dict)]
            != list(range(1, len(audios) + 1))):
        raise RealtimeCueError("Missing, repeated or misordered slide ASR")
    elements = []
    original = Path(source["source_root"]) / "slides.pdf"
    with fitz.open(original) as pdf:
        if pdf.page_count != len(audios):
            raise RealtimeCueError("PDF and stage slide count differ")
        for i, (obs, audio) in enumerate(zip(observations, audios), 1):
            if (obs.get("source_wav_sha256") != audio["wav_sha256"] or
                    obs.get("phonetic_identity_verified") is not False or
                    obs.get("semantic_word_alignment_certified") is not False):
                raise RealtimeCueError("ASR slide is unbound or falsely approved")
            words = validate_vosk_words(
                obs.get("words"), limit_seconds=audio["duration_seconds"])
            occurrences = collections.Counter(_word(w["word"]) for w in words)
            pdfwords = pdf[i - 1].get_text("words")
            counts = collections.Counter(_word(w[4]) for w in pdfwords)
            positions = {_word(w[4]): list(map(float, w[:4]))
                         for w in pdfwords if _word(w[4])}
            start_of_slide = intervals[i - 1]["start_seconds"]
            for word in words:
                token = _word(word["word"])
                start, stop = word["start"], word["end"]
                if (not token or token in _BLOCKED or
                        word["conf"] < minimum_confidence or
                        occurrences[token] != 1 or counts[token] != 1 or
                        stop - start < 0.09 or
                        start >= audio["duration_seconds"] or
                        stop > audio["duration_seconds"] + .01):
                    continue
                elements.append({
                    "slide": i, "text": token, "box": positions[token],
                    "local_start": start, "local_end": min(stop, audio["duration_seconds"]),
                    "start_seconds": round(start + start_of_slide, 6),
                    "end_seconds": round(min(stop, audio["duration_seconds"]) + start_of_slide, 6),
                })
            if len([x for x in elements if x["slide"] == i]) > 64:
                raise RealtimeCueError("Too many uncertain ASR word cues")
    if digest(original) != source["source_pdf_sha256"]:
        raise RealtimeCueError("Source PDF changed during cue extraction")
    cues = bind_cues_to_current_audio(
        stage, elements, derivation="CURRENT_STAGE_OFFLINE_ASR_NOT_PHONETIC_GROUND_TRUTH")
    validate_audio_bound_cues(stage, cues)
    # Re-read recognition bytes and revalidate audio/source before commit.
    if (read_json(recognition_report) != report or
            _stage(stage)[2] != audios or
            _stage(stage)[1] != source):
        raise RealtimeCueError("Evidence changed during generation")
    atomic_json(out, cues)
    return {"stage": str(stage), "cue_count": len(elements),
            "slides": len(audios), "publication_allowed": False,
            "mathematical_figure_alignment_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline, source-bound ASR and fresh cue staging")
    sub = parser.add_subparsers(dest="operation", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--stage", type=Path, required=True)
    capture.add_argument("--model", type=Path, required=True)
    capture.add_argument("--ffmpeg", type=Path, required=True)
    capture.add_argument("--out", type=Path, required=True)
    align = sub.add_parser("align")
    align.add_argument("--stage", type=Path, required=True)
    align.add_argument("--recognition", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.operation == "capture":
        result = capture_current_audio_asr(
            args.stage, args.model, args.ffmpeg, args.out)
    else:
        result = regenerate_stage_cues(args.stage, args.recognition)
    print(json.dumps(result, sort_keys=True))
    return 2  # unapproved ASR observation cannot be a publishable result


if __name__ == "__main__":
    raise SystemExit(main())
