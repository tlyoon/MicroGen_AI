"""Independent waveform-only assessment of source-anchored pronunciation candidates.

No recognition or pronunciation classification is attempted: RMS, PCM clipping
and zero-signal checks are strictly physical measurements, not lexical verdicts.
"""
from __future__ import annotations
import argparse
import json
import math
import wave
from pathlib import Path

from microgen_tts_pcm_features import file_sha256, pcm_envelope


class CandidateSignalError(ValueError):
    pass


def assess_candidate_signals(clips_dir: Path, source_stage: Path,
                             *, clipping_fraction_threshold: float = .01) -> dict:
    directory = Path(clips_dir)
    stage = Path(source_stage)
    if (directory.is_symlink() or stage.is_symlink()
            or not directory.is_dir() or not stage.is_dir()
            or type(clipping_fraction_threshold) not in (float, int)
            or not math.isfinite(clipping_fraction_threshold)
            or not 0 < clipping_fraction_threshold <= .1):
        raise CandidateSignalError("Invalid trusted signal inputs or thresholds")
    index_path = directory / "review_index.json"
    if index_path.is_symlink() or not index_path.is_file():
        raise CandidateSignalError("Untrusted candidate index")
    original = file_sha256(index_path)
    index = json.loads(index_path.read_text(encoding="utf8"))
    rows = index.get("clips")
    if (index.get("publication_allowed") is not False or
            index.get("phonetic_identity_verified") is not False or
            index.get("provider_calls") != 0 or
            not isinstance(rows, list) or not rows or len(rows) > 16 or
            index.get("clip_count") != len(rows)):
        raise CandidateSignalError("Only bounded unapproved clip evidence is valid")
    observed = []
    source_hashes = {}
    seen = set()
    for entry in rows:
        if (not isinstance(entry, dict) or
                entry.get("review_status") != "UNREVIEWED" or
                entry.get("pronunciation_confirmed") is not False or
                entry.get("automatic_repair_allowed") is not False):
            raise CandidateSignalError("Audio review status cannot imply phonetic approval")
        number = entry.get("slide")
        rel = entry.get("relative_clip_path")
        if (type(number) is not int or not 1 <= number <= 300 or
                not isinstance(rel, str) or not rel or
                Path(rel).is_absolute() or ".." in Path(rel).parts or
                Path(rel).as_posix() in seen):
            raise CandidateSignalError("Unsafe or duplicate source clip reference")
        seen.add(Path(rel).as_posix())
        clip = directory / rel
        if clip.is_symlink() or not clip.is_file() or directory.resolve() not in clip.resolve().parents:
            raise CandidateSignalError("Missing, escaping or symlinked excerpt")
        source = stage / f"slide{number}.wav"
        if source.is_symlink() or not source.is_file():
            raise CandidateSignalError("Original source audio missing")
        src_hash = file_sha256(source)
        if src_hash != entry.get("source_wav_sha256"):
            raise CandidateSignalError("Original WAV/source provenance mismatch")
        if file_sha256(clip) != entry.get("clip_sha256"):
            raise CandidateSignalError("Excerpt SHA-256 mismatch")
        if number in source_hashes and source_hashes[number] != src_hash:
            raise CandidateSignalError("Source WAV identity drift")
        source_hashes[number] = src_hash
        try:
            signal = pcm_envelope(clip, max_seconds=5)
        except (OSError, ValueError, wave.Error) as exc:
            raise CandidateSignalError("Unreadable source-bound PCM16 excerpt") from exc
        threshold = max(signal["frame_clipping_fraction"], default=0)
        fully_silent = signal["whole_rms"] == 0
        clipped = threshold >= clipping_fraction_threshold
        physical_issue = ("DIGITAL_SILENCE" if fully_silent else
                          "SUSTAINED_PCM_CLIPPING" if clipped else None)
        observed.append({
            "slide": number, "expected": entry["expected"],
            "asr_recognized": entry["recognized"],
            "clip_path": rel, "original_wav_sha256": src_hash,
            "clip_sha256": entry["clip_sha256"],
            "duration_seconds": signal["duration_seconds"],
            "whole_rms": signal["whole_rms"],
            "maximum_frame_clipping_fraction": threshold,
            "physical_signal_issue": physical_issue,
            "acoustic_signal_preserved": physical_issue is None,
            "phonetic_identity_verified": False,
            "technical_term_pronunciation_assessed": False,
            "automatic_tts_regeneration_authorized": False
        })
    if file_sha256(index_path) != original or any(
            file_sha256(stage / f"slide{i}.wav") != h for i,h in source_hashes.items()):
        raise CandidateSignalError("Source evidence changed during measurement")
    if any(file_sha256(directory / row["clip_path"]) != row["clip_sha256"]
           for row in observed):
        raise CandidateSignalError("Excerpt changed during measurement")
    return {
        "schema_version": 1, "status": "INDEPENDENT_SIGNAL_ONLY_NOT_PHONEME_QA",
        "clip_index_sha256": original, "source_slide_count": len(source_hashes),
        "clip_count": len(observed),
        "physical_audio_issue_count": sum(bool(r["physical_signal_issue"]) for r in observed),
        "clips": observed, "provider_calls": 0,
        "automatic_pronunciation_repairs": 0,
        "phonetic_identity_verified": False, "publication_allowed": False
    }


def main(argv=None) -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--clips-dir",type=Path,required=True)
    p.add_argument("--source-stage",type=Path,required=True)
    p.add_argument("--new-report",type=Path,required=True)
    args=p.parse_args(argv)
    target=args.new_report
    cliproot=args.clips_dir.resolve(strict=True)
    source=args.source_stage.resolve(strict=True)
    output=target.resolve(strict=False)
    if (target.exists() or target.is_symlink() or not output.parent.is_dir()
            or any(part.casefold()=="my drive" for part in output.parts)
            or cliproot in output.parents or source in output.parents):
        raise CandidateSignalError("New external output-only report required")
    result=assess_candidate_signals(args.clips_dir,args.source_stage)
    with output.open("x",encoding="utf8") as f:
        json.dump(result,f,indent=2,ensure_ascii=False)
    print(json.dumps({"report":str(target),"clips":result["clip_count"],
                      "physical_audio_issues":result["physical_audio_issue_count"],
                      "phonetic_identity_verified":False}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
