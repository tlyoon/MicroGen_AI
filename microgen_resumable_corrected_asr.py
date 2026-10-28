"""Resumable, local-only Vosk capture for current corrected lecture audio.

The existing monolithic capture loses useful all-slide progress if a model,
PC or decoder fails on a later slide. This isolated checkpoint stores one
validated, byte-bound model observation at a time, never overwrites files,
and never certifies phonetics, voice, equations or publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from microgen_audio_cue_binding import _verified_audio_rows
from microgen_offline_vosk_capture import capture_offline_words, validate_vosk_words
from microgen_source_safe_orchestrator import atomic_json, read_json, digest, verify_workspace


class CurrentASRCheckpointError(ValueError):
    pass


def _model_evidence(model_dir):
    model = Path(model_dir).absolute()
    if model.is_symlink() or not model.is_dir() or not (model / "am").is_dir():
        raise CurrentASRCheckpointError("Explicit local offline Vosk model missing")
    files = sorted(model.rglob("*"))
    if not files or len(files) > 500:
        raise CurrentASRCheckpointError("Unbounded Vosk model inventory")
    h = hashlib.sha256()
    names = []
    for f in files:
        if f.is_symlink():
            raise CurrentASRCheckpointError("Linked model files are disallowed")
        if f.is_dir():
            continue
        relative = f.relative_to(model).as_posix()
        if not f.is_file() or f.stat().st_size > 500_000_000:
            raise CurrentASRCheckpointError("Untrusted model contents")
        value = digest(f)
        h.update(relative.encode("utf8") + b"\0" + value.encode("ascii") + b"\n")
        names.append({"name": relative, "sha256": value, "bytes": f.stat().st_size})
    if not names:
        raise CurrentASRCheckpointError("Empty acoustic model")
    return {"model_dir": str(model), "model_tree_sha256": h.hexdigest(),
            "file_count": len(names), "total_bytes": sum(x["bytes"] for x in names)}


def _source(stage):
    base = Path(stage).resolve(strict=True)
    src, audios, _ = _verified_audio_rows(base)
    if src["slide_count"] != 17 or len(audios) != 17:
        raise CurrentASRCheckpointError("Full 17-slide source-bound audio required")
    return base, src, audios


def _path_is_safe(stage, target, model):
    t = Path(target).absolute()
    protected = [Path(stage).resolve(strict=True),
                 Path(model).resolve(strict=True)]
    origin = Path(verify_workspace(stage)["source_root"]).resolve(strict=True)
    protected.append(origin)
    if (t.is_symlink() or
            any(t == p or t.is_relative_to(p) or p.is_relative_to(t)
                for p in protected)):
        raise CurrentASRCheckpointError("ASR progress cannot alter source, model or stage")
    return t


def _validate_one(result, audio, *, slide, model_hash, src):
    if (not isinstance(result, dict)
            or result.get("slide") != slide
            or result.get("model_tree_sha256") != model_hash
            or result.get("source_pdf_sha256") != src["source_pdf_sha256"]
            or result.get("narration_sha256") != src["narration_sha256"]
            or result.get("source_wav_sha256") != audio["wav_sha256"]
            or result.get("publication_allowed") is not False
            or result.get("phonetic_identity_verified") is not False
            or result.get("semantic_word_alignment_certified") is not False):
        raise CurrentASRCheckpointError("Slide checkpoint not bound to this WAV/model")
    validated = validate_vosk_words(result.get("words"),
                                    limit_seconds=audio["duration_seconds"])
    if not validated:
        raise CurrentASRCheckpointError("Empty ASR observation cannot certify a processed slide")
    return validated


def resume_current_audio_asr(stage, model_dir, ffmpeg, progress_dir, *,
                              max_new_slides=17):
    """Run at most max_new_slides; preserve already verified per-slide receipts.

    The only completion is a candidate ASR report in an isolated progress
    directory; its release and phonetic flags remain False.
    """
    if type(max_new_slides) is not int or not 1 <= max_new_slides <= 17:
        raise CurrentASRCheckpointError("Invalid bounded ASR batch size")
    base, src, audios = _source(stage)
    ff = Path(ffmpeg).resolve(strict=True)
    if ff.is_symlink() or not ff.is_file():
        raise CurrentASRCheckpointError("Explicit local FFmpeg binary required")
    model = _model_evidence(model_dir)
    target = _path_is_safe(base, progress_dir, model_dir)
    if target.exists() and not target.is_dir():
        raise CurrentASRCheckpointError("ASR checkpoint path is not a directory")
    if target.exists() and target.is_symlink():
        raise CurrentASRCheckpointError("Linked ASR checkpoint cannot be used")
    preexisting = target.exists()
    if preexisting:
        meta = read_json(target / "session.json")
        if (meta.get("status") != "CORRECTED_OFFLINE_ASR_IN_PROGRESS"
                or meta.get("model") != model
                or meta.get("source") != src
                or meta.get("audio_bindings") != audios
                or meta.get("publication_allowed") is not False):
            raise CurrentASRCheckpointError("Checkpoint session provenance changed")
    else:
        target.mkdir(parents=True, exist_ok=False)
        meta = {"schema_version": 1, "status": "CORRECTED_OFFLINE_ASR_IN_PROGRESS",
                "model": model, "source": src, "audio_bindings": audios,
                "publication_allowed": False}
        atomic_json(target / "session.json", meta)
    # Existing files can only be the declared JSON records and completed report.
    expected = {"session.json", "asr_current_audio.json"} | {
        f"slide{i:02d}.json" for i in range(1, 18)}
    if any(x.is_symlink() or x.name not in expected
           for x in target.iterdir()):
        raise CurrentASRCheckpointError("Unexpected files in checkpoint directory")
    done = []
    for slide, audio in enumerate(audios, 1):
        path = target / f"slide{slide:02d}.json"
        if path.exists():
            done.append({"slide": slide, "content": read_json(path)})
            _validate_one(done[-1]["content"], audio, slide=slide,
                          model_hash=model["model_tree_sha256"], src=src)
    complete_file = target / "asr_current_audio.json"
    if complete_file.exists():
        raise CurrentASRCheckpointError("ASR report already finalized; no overwrite")
    missing = [i for i in range(1, 18)
               if not (target / f"slide{i:02d}.json").exists()]
    if missing:
        try:
            from vosk import Model
        except ImportError as exc:
            raise CurrentASRCheckpointError(
                "Offline Vosk Python module unavailable; existing progress preserved") from exc
        recognizer_model = Model(str(model_dir))
        for slide in missing[:max_new_slides]:
            audio = audios[slide - 1]
            obs = capture_offline_words(
                base / "audio" / f"slide{slide}.wav", recognizer_model, ff)
            row = {"slide": slide, **obs,
                   "model_tree_sha256": model["model_tree_sha256"],
                   "source_pdf_sha256": src["source_pdf_sha256"],
                   "narration_sha256": src["narration_sha256"],
                   "publication_allowed": False}
            _validate_one(row, audio, slide=slide,
                          model_hash=model["model_tree_sha256"], src=src)
            # Recheck *all* audio, source and model after each completed slide.
            _, latest_source, latest_audio = _source(base)
            if (latest_source != src or latest_audio != audios
                    or _model_evidence(model_dir) != model):
                raise CurrentASRCheckpointError(
                    "Source/model changed during inference; reject current observation")
            atomic_json(target / f"slide{slide:02d}.json", row)
    _, latest_source, latest_audio = _source(base)
    if (latest_source != src or latest_audio != audios
            or _model_evidence(model_dir) != model):
        raise CurrentASRCheckpointError("WAV/source/model changed after ASR")
    saved = []
    for slide, audio in enumerate(audios, 1):
        p = target / f"slide{slide:02d}.json"
        if p.exists():
            row = read_json(p)
            _validate_one(row, audio, slide=slide,
                          model_hash=model["model_tree_sha256"], src=src)
            saved.append(row)
    completed = len(saved) == 17
    if completed:
        output = {
            "schema_version": 1,
            "status": "CURRENT_STAGE_OFFLINE_ASR_NOT_GROUND_TRUTH",
            "source_pdf_sha256": src["source_pdf_sha256"],
            "narration_sha256": src["narration_sha256"],
            "stage_audio_bindings": audios,
            "results": [{k: v for k, v in row.items() if k in
                         ("slide", "file", "source_wav_sha256", "words",
                          "phonetic_identity_verified",
                          "semantic_word_alignment_certified")} for row in saved],
            "model_tree_sha256": model["model_tree_sha256"],
            "phonetic_identity_verified": False,
            "semantic_alignment_verified": False,
            "publication_allowed": False}
        atomic_json(complete_file, output)
    return {"status": "OFFLINE_ASR_CANDIDATE_COMPLETE" if completed
                    else "OFFLINE_ASR_RESUMABLE_PROGRESS",
            "verified_slides": len(saved), "total_slides": 17,
            "report": str(complete_file) if completed else None,
            "publication_allowed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Safe resumable corrected offline ASR")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--progress", required=True)
    parser.add_argument("--max-new-slides", type=int, default=17)
    args = parser.parse_args(argv)
    result = resume_current_audio_asr(args.stage, args.model, args.ffmpeg,
                                      args.progress,
                                      max_new_slides=args.max_new_slides)
    print(json.dumps(result, sort_keys=True))
    return 2  # Model hypothesis is not publication acceptance


if __name__ == "__main__":
    raise SystemExit(main())
