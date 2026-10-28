"""Source-verified isolated full-slide WAV stage for Section 2.5 trial speech.

Build a NEW, nonpublishing timeline from original legacy-recovered clips and
exactly three selected historical correction trials. Never touch the source
folder, replace production clips, assume speaker/phonetic validity, or reuse
original ASR clocks. No APIs, Whisper or publication.
"""
from __future__ import annotations

import shutil
import wave
from pathlib import Path

from microgen_source_safe_orchestrator import (
    OrchestratorError, atomic_json, create_workspace, digest,
    read_json, source_bound_timeline, verify_workspace,
)


class CorrectedStageError(OrchestratorError):
    pass


_RISKS = {5: "CDOT", 6: "CDOT", 10: "Y_VALUE"}


def _duration(wav):
    try:
        with wave.open(str(wav), "rb") as audio:
            if (audio.getnchannels() != 1 or audio.getsampwidth() != 2 or
                    not 8000 <= audio.getframerate() <= 48000 or
                    audio.getnframes() < 1):
                raise CorrectedStageError("Expected regular mono PCM16 WAV")
            seconds = audio.getnframes() / audio.getframerate()
    except (OSError, EOFError, wave.Error) as exc:
        raise CorrectedStageError("Invalid recorded WAV") from exc
    if not .05 <= seconds < 600:
        raise CorrectedStageError("Unsafe slide audio duration")
    return seconds


def prepare_section25_corrected_wavs(recovery, selection, output):
    """Stage 14 verified recovered clips + slides 5, 6, 10 corrected trials.

    The recovered MP4's extra AAC tail is NOT represented as a slide WAV.
    Its separate source-equality/preservation checks remain a subsequent
    mastering step; this staging operation alone does not make a final MP4.
    """
    recovered = Path(recovery).resolve(strict=True)
    chosen = Path(selection).resolve(strict=True)
    source_receipt = verify_workspace(recovered)
    source_root = Path(source_receipt["source_root"]).resolve(strict=True)
    target = Path(output).resolve(strict=False)
    protected = (recovered, chosen, source_root)
    if (target.exists() or target.is_symlink() or
            any(target == p or target.is_relative_to(p) or
                p.is_relative_to(target) for p in protected)):
        raise CorrectedStageError("Output must be new, separate and unprotected")
    if source_receipt["slide_count"] != 17:
        raise CorrectedStageError("Section 2.5 requires all 17 source slides")

    prior_file = recovered / "legacy_mp4_audio_receipt.json"
    selection_file = chosen / "selection_receipt.json"
    prior = read_json(prior_file)
    select = read_json(selection_file)
    prior_sha = digest(prior_file)
    selection_sha = digest(selection_file)
    source_mp4 = source_root / "slides.mp4"
    if (not source_mp4.is_file() or source_mp4.is_symlink() or
            prior.get("status") != "PROVISIONAL_NOT_PUBLISHABLE" or
            prior.get("scene_evidence", {}).get("mp4_sha256") != digest(source_mp4) or
            select.get("status") != "SHADOW_ONLY_TRIAL_SELECTION" or
            select.get("schema_version") != 1 or
            select.get("publication_allowed") is not False or
            select.get("source_pdf_sha256") != source_receipt["source_pdf_sha256"] or
            select.get("source_narration_sha256") != source_receipt["narration_sha256"] or
            select.get("source_mp4_sha256") != digest(source_mp4)):
        raise CorrectedStageError("Source MP4, PDF, script or selection drift")
    trials = select.get("trials")
    clips = prior.get("clips")
    if (not isinstance(trials, list) or len(trials) != 3 or
            not isinstance(clips, list) or len(clips) != 17 or
            any(not isinstance(row, dict) or row.get("slide") != i
                for i, row in enumerate(clips, 1))):
        raise CorrectedStageError("Missing, duplicated or untrusted source clips")
    by_slide = {}
    for row in trials:
        if not isinstance(row, dict):
            raise CorrectedStageError("Malformed correction trial")
        i = row.get("slide")
        if (type(i) is not int or i not in _RISKS or i in by_slide or
                row.get("risk") != _RISKS[i] or
                row.get("phonetic_approved") is not False or
                row.get("voice_independently_verified") is not False):
            raise CorrectedStageError("Correction selection is not source-safe")
        by_slide[i] = row
    if set(by_slide) != set(_RISKS):
        raise CorrectedStageError("Missing source-bound corrected slides")

    # Preflight all 17 inputs and their measured durations BEFORE any writes.
    inputs = []
    duration_total = 0.0
    for slide in range(1, 18):
        if slide in by_slide:
            row = by_slide[slide]
            trial = Path(row.get("trial_path", ""))
            if (trial.is_symlink() or not trial.is_file() or
                    trial.resolve(strict=True).parent != chosen or
                    trial.name != f"slide{slide:02d}_{_RISKS[slide]}_UNAPPROVED.wav"):
                raise CorrectedStageError("Trial path is not an owned selected clip")
            clip = trial
            sha = row["wav_sha256"]
            kind = "UNAPPROVED_SOURCE_BOUND_TRIAL"
        else:
            clip = recovered / "audio" / f"slide{slide}.wav"
            sha = clips[slide - 1].get("sha256")
            kind = "LEGACY_ORIGINAL_RECOVERED_AUDIO"
        if clip.is_symlink() or not clip.is_file() or digest(clip) != sha:
            raise CorrectedStageError("Original or trial WAV changed before stage")
        duration_total += _duration(clip)
        inputs.append((slide, clip, sha, kind))
    if not 0 < duration_total < 600:
        raise CorrectedStageError("Corrected lecture exceeds strict 600 seconds")
    if digest(source_mp4) != select["source_mp4_sha256"]:
        raise CorrectedStageError("Source video drift during audio preflight")

    # Only own newly created directory may be cleaned after failed staging.
    create_workspace(source_root, target)
    try:
        (target / "audio").mkdir()
        entries = []
        for slide, clip, sha, kind in inputs:
            if digest(clip) != sha:
                raise CorrectedStageError("Original WAV changed during stage")
            copied = target / "audio" / f"slide{slide}.wav"
            shutil.copyfile(clip, copied)
            if digest(copied) != sha:
                raise CorrectedStageError("Staged WAV differs from receipt")
            entries.append({
                "slide": slide, "sha256": sha, "source": kind,
                "speaker_authenticated": False,
            })
        atomic_json(target / "audio_inventory.json", {
            "entries": entries, "missing": [],
            "speech_correctness_verified": False,
            "corrected_trial_audio_unapproved": True,
        })
        timeline = source_bound_timeline(target)
        if not 0 < timeline["duration_seconds"] < 600:
            raise CorrectedStageError("Measured staged duration exceeds 600")
        if (digest(source_mp4) != select["source_mp4_sha256"] or
                digest(prior_file) != prior_sha or
                digest(selection_file) != selection_sha or
                verify_workspace(recovered) != source_receipt or
                any(digest(p) != sha for _, p, sha, _ in inputs)):
            raise CorrectedStageError("Source changed during stage creation")
        atomic_json(target / "corrected_stage_receipt.json", {
            "status": "SOURCE_BOUND_CORRECTED_AUDIO_NEEDS_NEW_ASR",
            "source_pdf_sha256": source_receipt["source_pdf_sha256"],
            "narration_sha256": source_receipt["narration_sha256"],
            "source_mp4_sha256": select["source_mp4_sha256"],
            "selection_receipt_sha256": selection_sha,
            "recovery_receipt_sha256": prior_sha,
            "actual_audio_bindings": entries,
            "audio_seconds": timeline["duration_seconds"],
            "corrected_slides": [5, 6, 10],
            "old_asr_cues_discarded": True,
            "fresh_offline_recognition_required": True,
            "source_audio_tail_mastering_pending": True,
            "phonetic_correctness_verified": False,
            "single_speaker_verified": False,
            "mathematical_figure_sync_verified": False,
            "publication_allowed": False,
        })
        if (target / "cues.json").exists():
            raise CorrectedStageError("Stale ASR cue manifest must not be copied")
    except Exception:
        shutil.rmtree(target)
        raise
    return {
        "workspace": str(target), "slides": 17,
        "corrected_slides": [5, 6, 10],
        "duration_seconds": timeline["duration_seconds"],
        "old_cues_copied": False,
        "fresh_asr_required": True,
        "publication_allowed": False,
    }
