"""Source/PCM-bound timed acoustic repair for existing measured cue lectures.

An acoustic replacement for a complete slide cannot inherit old cue clocks.
Revoice the *same documented cue fragments* in the same provider/voice,
concatenate their actual PCM, independently review the resulting whole slide,
and prevalidate an updated complete cue manifest in a private scratch stage.
This module does not weaken QA or directly install accepted media.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import wave
from pathlib import Path
from typing import Callable


class TimedAcousticRepairError(RuntimeError):
    pass


MAX_TIMED_REPAIR_CUES = 12


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_timed_repair(
    stage: Path,
    slides: list[int],
    texts: list[str],
    records: list[dict],
    scratch: Path,
    synthesize: Callable,
    verify_candidate: Callable,
    *,
    selected_cues: dict[int,list[int]] | None=None,
) -> dict:
    """Prepare and validate corrected cue-WAV inventory; return scratch paths.

    The original stage must pass all timed PCM/PDF checks BEFORE provider use.
    A synthetic or paid candidate is never installed if any check fails.
    """
    from microgen_flash_tts import _merge_wavs
    from microgen_timed_highlight_contract import (
        MANIFEST, inspect_timed_highlights,
    )
    from microgen_tts_provenance import wav_characteristics
    from microgen_tts_wave_integrity import analyze_pcm
    from text_to_speech_v25 import normalize_scientific_speech
    from microgen_timed_highlight_contract import _equivalent_text

    stage, scratch = Path(stage), Path(scratch)
    verified = inspect_timed_highlights(stage)
    manifest = json.loads((stage / MANIFEST).read_text(encoding="utf8"))
    rows = manifest["slides"]
    if (not isinstance(slides, list) or not slides
            or sorted(set(slides)) != slides
            or len(slides) > 2 or any(type(n) is not int
                                       or n < 1 or n > len(rows) for n in slides)
            or len(texts) != len(rows) or len(records) != len(rows)
            or verified["slide_count"] != len(rows)):
        raise TimedAcousticRepairError("Untrusted bounded acoustic slide selection")
    if selected_cues is not None:
        if (not isinstance(selected_cues,dict) or
                set(selected_cues)!=set(slides) or
                any(not isinstance(v,list) or not v or
                    sorted(set(v))!=v or any(type(j) is not int or
                    j<1 or j>len(rows[n-1]["cues"]) for j in v)
                    for n,v in selected_cues.items())):
            raise TimedAcousticRepairError("Untrusted precise timed cue selection")
    count=sum(len(selected_cues[n]) if selected_cues is not None
              else len(rows[n-1]["cues"]) for n in slides)
    if not 1 <= count <= MAX_TIMED_REPAIR_CUES:
        raise TimedAcousticRepairError("Finite timed acoustic cue budget exceeded")
    # Match the original production Flash cue synthesizer's exact
    # normalization; fail before ANY paid call if the source changed.
    cue_texts = {}
    for n in slides:
        fragments = [
            normalize_scientific_speech(cue["spoken_text"])
            for cue in rows[n - 1]["cues"]
        ]
        if (not all(fragments) or _equivalent_text(" ".join(fragments))
                != _equivalent_text(texts[n - 1])):
            raise TimedAcousticRepairError(
                "Source-bound timed cue text does not reconstruct narration")
        cue_texts[n] = fragments

    # Real source PDF, narration, PCM, and all old cue hashes are verified.
    # Even the *unmodified* slides must remain part of a full-deck check.
    prepared = scratch / "timed_prepared"
    if prepared.exists() or prepared.is_symlink():
        raise TimedAcousticRepairError("Prepared correction already exists")
    prepared.mkdir()
    for name in ("source.pdf", "slides.pdf", "script_tts.json"):
        shutil.copy2(stage / name, prepared / name)
    for n in range(1, len(rows) + 1):
        shutil.copy2(stage / f"slide{n}.pdf", prepared / f"slide{n}.pdf")
        shutil.copy2(stage / f"slide{n}.wav", prepared / f"slide{n}.wav")
    chunk_dir = prepared / "highlight_chunks"
    chunk_dir.mkdir()
    for row in rows:
        for cue in row["cues"]:
            rel = cue["audio_chunk"]
            shutil.copy2(stage / rel, prepared / rel)

    new_manifest = copy.deepcopy(manifest)
    modifications: dict[str, Path] = {}
    for n in slides:
        outputs = []
        old_record = records[n - 1]
        row = new_manifest["slides"][n - 1]
        for j, cue in enumerate(row["cues"], 1):
            # Only source-identified sensitive cues are revoiced. Everything
            # else keeps the exact original PCM/hash/timing evidence.
            if selected_cues is not None and j not in selected_cues[n]:
                outputs.append((stage/cue["audio_chunk"]).read_bytes())
                continue
            # Avoid duplicate provider effect or an unsupported extra source cue.
            target = scratch / f"timed_slide{n}_cue{j}.wav"
            if target.exists() or target.is_symlink():
                raise TimedAcousticRepairError("Duplicate cue repair candidate")
            synthesize(cue_texts[n][j - 1], target, old_record)
            if not target.is_file() or target.is_symlink():
                raise TimedAcousticRepairError("Timed cue TTS candidate missing")
            defects = analyze_pcm(target)["blocking_defects"]
            if defects:
                raise TimedAcousticRepairError("Timed cue acoustic PCM defects")
            if (wav_characteristics(target)["sample_rate_hz"]
                    != old_record["sample_rate_hz"]):
                raise TimedAcousticRepairError("Timed cue sample rate changed")
            with wave.open(str(target), "rb") as w:
                if w.getnframes() / w.getframerate() < 0.08:
                    raise TimedAcousticRepairError("Timed cue is too short")
            rel = cue["audio_chunk"]
            shutil.copy2(target, prepared / rel)
            cue["audio_chunk_sha256"] = _sha(prepared / rel)
            modifications[rel] = prepared / rel
            outputs.append(target.read_bytes())
        combined = _merge_wavs(outputs)
        candidate = scratch / f"slide{n}.wav"
        candidate.write_bytes(combined)
        if not verify_candidate(candidate, texts[n - 1]):
            raise TimedAcousticRepairError(
                "Two independent reviewers rejected timed revoiced slide")
        shutil.copy2(candidate, prepared / f"slide{n}.wav")
        row["slide_wav_sha256"] = _sha(candidate)

    manifest_candidate = prepared / MANIFEST
    manifest_candidate.write_text(
        json.dumps(new_manifest, ensure_ascii=False, indent=2), encoding="utf8")
    # This validates exact current cue PCM concatenation, physical time
    # boundaries, every source PDF region, and full 21-slide speech coverage.
    evidence = inspect_timed_highlights(prepared)
    if (evidence["slide_count"] != len(rows)
            or evidence["status"] != "SOURCE_AND_PCM_TIMING_STRUCTURALLY_VERIFIED"):
        raise TimedAcousticRepairError("Prepared measured cue proof invalid")
    return {
        "manifest": manifest_candidate,
        "chunks": modifications,
        "prepared": prepared,
        "cue_count": count,
        "changed_slides": list(slides),
        "selected_cues":({str(n):selected_cues[n] for n in slides}
                         if selected_cues is not None else None),
        "publication_allowed": False,
    }
