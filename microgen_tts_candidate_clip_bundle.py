"""External, bounded, SHA-traceable excerpts for uncertain math TTS review.

The clips contain *candidate audio*, not verified phonemes. ASR time suggestions
are approximate. Nothing in this module approves speech, changes production WAVs,
selects a formal TTS provider, or invokes a network/paid service.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import tempfile
import wave
from collections import defaultdict
from pathlib import Path

from microgen_pronunciation_closed_loop import sha_file
from microgen_tts_audio_snippets import extract_clips
from microgen_tts_candidate_timing import build_timing_index


class CandidateClipBundleError(ValueError):
    pass


def create_candidate_clip_bundle(
    stage: Path, asr_dir: Path, evidence_file: Path, timing_file: Path,
    new_output: Path, *, padding_seconds: float = 0.35,
    max_candidates: int = 16, max_total_seconds: float = 60.0
) -> dict:
    """Atomically produce output-only PCM clips and an unapproved review index."""
    stage = Path(stage)
    asr_dir = Path(asr_dir)
    evidence_file = Path(evidence_file)
    timing_file = Path(timing_file)
    new_output = Path(new_output)
    if (not isinstance(max_candidates, int) or isinstance(max_candidates, bool)
            or not 1 <= max_candidates <= 16
            or type(padding_seconds) not in (float, int)
            or not math.isfinite(padding_seconds)
            or not 0 <= padding_seconds <= 1.5
            or type(max_total_seconds) not in (float, int)
            or not math.isfinite(max_total_seconds)
            or not 0 < max_total_seconds <= 60):
        raise CandidateClipBundleError("Unsafe clip budget")
    for path in (stage, asr_dir, evidence_file, timing_file):
        if path.is_symlink() or not path.exists():
            raise CandidateClipBundleError("Real source evidence required")
    if (new_output.is_symlink() or new_output.exists()
            or any(part.casefold() == "my drive" for part in new_output.parts)
            or not new_output.parent.is_dir()):
        raise CandidateClipBundleError("New external output directory required")
    source_root = stage.resolve(strict=True)
    asr_root = asr_dir.resolve(strict=True)
    out = new_output.resolve(strict=False)
    evidence = evidence_file.resolve(strict=True)
    timing = timing_file.resolve(strict=True)
    if any(
        out == path or path in out.parents or out in path.parents
        for path in (source_root, asr_root)
    ) or any(
        out == path or path in out.parents
        for path in (evidence, timing)
    ):
        raise CandidateClipBundleError("Output must not contain or be within sources")
    if any(part.casefold() == "my drive" for part in out.parts):
        raise CandidateClipBundleError("Protected Drive destination")
    pinned = sha_file(timing)
    expected = build_timing_index(source_root, asr_root, evidence)
    actual = json.loads(timing.read_text(encoding="utf-8"))
    if actual != expected or actual.get("phonetic_identity_verified") is not False:
        raise CandidateClipBundleError("Stale or untrusted timing receipt")
    selected = actual["candidates"]
    if len(selected) > max_candidates:
        raise CandidateClipBundleError("Candidate count exceeds bounded budget")
    grouped: dict[int, list[tuple[dict, dict]]] = defaultdict(list)
    skipped = []
    total_duration = 0.0
    for row in selected:
        number = row["slide"]
        window = row["asr_matched_span"]
        if row["status"] != "UNIQUE_ASR_SPAN_UNVERIFIED" or window is None:
            skipped.append({"slide": number, "expected": row["expected"],
                            "recognized": row["recognized"],
                            "reason": "NONUNIQUE_OR_MISSING_ASR_TIMING"})
            continue
        wav = source_root / f"slide{number}.wav"
        if wav.is_symlink():
            raise CandidateClipBundleError("Source WAV symlink not accepted")
        if sha_file(wav) != row["original_wav_sha256"]:
            raise CandidateClipBundleError("Original WAV SHA mismatch")
        with wave.open(str(wav), "rb") as stream:
            if (stream.getcomptype() != "NONE" or stream.getnchannels() != 1
                    or stream.getsampwidth() != 2 or stream.getframerate() <= 0):
                raise CandidateClipBundleError("Mono PCM16 source required")
            duration = stream.getnframes() / stream.getframerate()
        start = max(0.0, window["start_seconds"] - padding_seconds)
        end = min(duration, window["end_seconds"] + padding_seconds)
        if not 0 <= start < end <= duration or end - start > 5.0:
            raise CandidateClipBundleError("Unsafe candidate clip interval")
        grouped[number].append((row, {"start_seconds": start, "end_seconds": end}))
        total_duration += end - start
    if total_duration > max_total_seconds:
        raise CandidateClipBundleError("Total clip duration budget exceeded")
    for number, rows in grouped.items():
        rows.sort(key=lambda pair: (pair[1]["start_seconds"],
                                    pair[1]["end_seconds"], pair[0]["expected"]))
        for a, b in zip(rows, rows[1:]):
            if a[1]["end_seconds"] > b[1]["start_seconds"]:
                raise CandidateClipBundleError(
                    f"Overlapping candidate windows on slide {number}; no guessed clip")

    # Build entirely outside the source tree, then rename a fully validated
    # scratch directory into the fresh destination. On failure only scratch
    # owned by this invocation is cleaned.
    temp = Path(tempfile.mkdtemp(prefix=".microgen-pronunciation-pending-",
                                 dir=out.parent))
    try:
        entries = []
        for number in sorted(grouped):
            wav = source_root / f"slide{number}.wav"
            rows = grouped[number]
            folder_name = f"slide_{number:02d}"
            receipt = extract_clips(
                wav, rows[0][0]["original_wav_sha256"],
                [interval for _, interval in rows], temp / folder_name,
                max_clips=max_candidates)
            if len(receipt["snippets"]) != len(rows):
                raise CandidateClipBundleError("Clip accounting mismatch")
            for (candidate, _), clip in zip(rows, receipt["snippets"]):
                entries.append({
                    "slide": number, "expected": candidate["expected"],
                    "recognized": candidate["recognized"],
                    "source_wav_sha256": candidate["original_wav_sha256"],
                    "offline_asr_report_sha256": candidate["offline_asr_report_sha256"],
                    "relative_clip_path": f"{folder_name}/{clip['file']}",
                    "clip_sha256": clip["sha256"],
                    "start_seconds": clip["start_seconds"],
                    "end_seconds": clip["end_seconds"],
                    "asr_confidence_min": candidate["asr_matched_span"]["asr_confidence_min"],
                    "timing_source": "UNVERIFIED_OFFLINE_ASR_ESTIMATE",
                    "review_status": "UNREVIEWED",
                    "pronunciation_confirmed": False,
                    "automatic_repair_allowed": False
                })
        record = {
            "schema_version": 1, "status": "EXTERNAL_LISTENING_CANDIDATES_NOT_ACOUSTIC_QA",
            "timing_receipt_sha256": pinned,
            "evidence_receipt_sha256": sha_file(evidence),
            "clip_count": len(entries), "skipped_count": len(skipped),
            "clips": entries, "skipped": skipped, "provider_calls": 0,
            "formal_tts_provider_changed": False,
            "production_wavs_modified": False, "phonetic_identity_verified": False,
            "publication_allowed": False
        }
        with (temp / "review_index.json").open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
        # Check the entire original observation inventory once more, as well
        # as every excerpt, immediately prior to atomic publication.
        if build_timing_index(source_root, asr_root, evidence) != actual:
            raise CandidateClipBundleError("Source/ASR identity changed while clipping")
        if sha_file(timing) != pinned:
            raise CandidateClipBundleError("Timing evidence changed during clipping")
        for entry in entries:
            if sha_file(temp / entry["relative_clip_path"]) != entry["clip_sha256"]:
                raise CandidateClipBundleError("Clip content changed")
        if out.exists() or out.is_symlink():
            raise CandidateClipBundleError("Output appeared before publish")
        os.rename(temp, out)
        return record
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--asr-dir", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--new-output", type=Path, required=True)
    opts = parser.parse_args(argv)
    report = create_candidate_clip_bundle(
        opts.stage, opts.asr_dir, opts.evidence, opts.timing, opts.new_output)
    print(json.dumps({"clip_count": report["clip_count"],
                      "skipped": report["skipped_count"],
                      "directory": str(opts.new_output),
                      "publication_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
