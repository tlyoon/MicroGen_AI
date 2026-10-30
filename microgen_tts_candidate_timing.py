"""Read-only, SHA-bound Vosk timing for unverified technical-word TTS candidates.

Word times are ASR hypotheses, NOT proven word boundaries or pronunciation
verdicts. This module never runs ASR/TTS, modifies audio, or authorizes release.
"""
from __future__ import annotations

import argparse
import json
import math
import wave
from pathlib import Path

from microgen_pronunciation_closed_loop import _word, sha_file
from microgen_pronunciation_evidence_pipeline import build_post_tts_evidence
from text_to_speech_v25 import normalize_scientific_speech

TECHNICAL = "POTENTIAL_TECHNICAL_TERM_DIFFERENCE_UNVERIFIED"


class CandidateTimingError(ValueError):
    pass


def _duration(wav: Path) -> float:
    with wave.open(str(wav), "rb") as stream:
        if (stream.getcomptype() != "NONE" or stream.getframerate() <= 0
                or stream.getnframes() <= 0):
            raise CandidateTimingError("Invalid PCM WAV timing source")
        return stream.getnframes() / stream.getframerate()


def _verified_words(rows: list, duration: float) -> list[dict]:
    if not isinstance(rows, list) or len(rows) > 1000:
        raise CandidateTimingError("Invalid ASR word count")
    checked = []
    for word in rows:
        if not isinstance(word, dict) or not isinstance(word.get("word"), str):
            raise CandidateTimingError("Invalid timed ASR word")
        start, end, conf = (word.get(x) for x in ("start", "end", "conf"))
        if (any(type(x) not in (int, float) or not math.isfinite(x)
                for x in (start, end, conf))
                or not 0 <= conf <= 1 or not 0 <= start < end
                or end > duration + 0.05):
            raise CandidateTimingError("Invalid ASR timestamp or confidence")
        checked.append({
            "token": _word(word["word"]), "start": float(start),
            "end": float(min(end, duration)), "conf": float(conf)
        })
    return checked


def build_timing_index(stage: Path, asr_dir: Path, evidence_file: Path) -> dict:
    stage = Path(stage).resolve(strict=True)
    asr_dir = Path(asr_dir).resolve(strict=True)
    evidence_file = Path(evidence_file)
    if (evidence_file.is_symlink() or not evidence_file.is_file()
            or stage == asr_dir or not stage.is_dir() or not asr_dir.is_dir()):
        raise CandidateTimingError("Independent evidence inputs required")
    original = json.loads(evidence_file.read_text(encoding="utf-8"))
    sidecar = stage / "script_tts.json"
    if sidecar.is_symlink() or not sidecar.is_file():
        raise CandidateTimingError("Source narration sidecar required")
    slides = json.loads(sidecar.read_text(encoding="utf-8"))["slides"]
    observations, words_by_slide, report_hashes = [], {}, []
    for i in range(1, len(slides) + 1):
        wav = stage / f"slide{i}.wav"
        report = asr_dir / f"slide{i:02d}.json"
        if wav.is_symlink() or report.is_symlink() or not report.is_file():
            raise CandidateTimingError("ASR/audio source identity unavailable")
        audio_hash = sha_file(wav)
        item = json.loads(report.read_text(encoding="utf-8"))
        if (item.get("slide") != i or item.get("wav_sha256") != audio_hash
                or item.get("recognition", {}).get("source_wav_sha256") != audio_hash):
            raise CandidateTimingError("Offline ASR/WAV SHA mismatch")
        duration = _duration(wav)
        observation = item["recognition"]
        words_by_slide[i] = _verified_words(observation.get("words"), duration)
        observations.append(observation)
        report_hashes.append(sha_file(report))
    rebuilt = build_post_tts_evidence(
        stage, slides, normalize_scientific_speech, observations=observations)
    if rebuilt != original or original.get("phonetic_identity_verified") is not False:
        raise CandidateTimingError("Evidence receipt differs from actual source/WAV/ASR")
    entries = []
    for candidate in original["unverified_word_pair_candidates"]:
        if candidate["priority"] != TECHNICAL:
            continue
        if (candidate.get("mispronunciation_confirmed") is not False
                or candidate.get("automatic_rule_authorized") is not False):
            raise CandidateTimingError("Unauthorized acoustic verdict in candidate")
        sequence = candidate["recognized"].split()
        for number in candidate["slides"]:
            words = words_by_slide[number]
            positions = [j for j in range(len(words) - len(sequence) + 1)
                         if sequence and [r["token"] for r in words[j:j + len(sequence)]]
                         == sequence]
            status = ("UNIQUE_ASR_SPAN_UNVERIFIED" if len(positions) == 1
                      else "AMBIGUOUS_ASR_SPAN" if positions
                      else "ASR_SPAN_NOT_FOUND")
            interval = None
            if len(positions) == 1:
                chunk = words[positions[0]:positions[0] + len(sequence)]
                interval = {
                    "start_seconds": chunk[0]["start"],
                    "end_seconds": chunk[-1]["end"],
                    "asr_confidence_min": min(r["conf"] for r in chunk),
                    "timing_is_approximate": True
                }
            entries.append({
                "slide": number, "expected": candidate["expected"],
                "recognized": candidate["recognized"], "status": status,
                "asr_matched_span": interval,
                "original_wav_sha256": original["slide_wav_sha256"][number - 1],
                "offline_asr_report_sha256": report_hashes[number - 1],
                "pronunciation_confirmed": False, "automatic_repair_allowed": False
            })
    if any(sha_file(stage / f"slide{i}.wav") != h for i, h in enumerate(
            original["slide_wav_sha256"], start=1)):
        raise CandidateTimingError("WAV changed during timestamp audit")
    return {
        "schema_version": 1, "status": "ASR_TIME_SUGGESTIONS_NOT_PHONETIC_QA",
        "source_evidence_sha256": sha_file(evidence_file),
        "narration_sha256": original["original_script_tts_sha256"],
        "slide_count": len(slides), "candidates": entries,
        "candidate_count": len(entries),
        "unambiguous_asr_spans": sum(x["status"] == "UNIQUE_ASR_SPAN_UNVERIFIED"
                                      for x in entries),
        "voice_verified": False, "phonetic_identity_verified": False,
        "publication_allowed": False, "provider_calls": 0,
        "production_wav_modified": False
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--asr-dir", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--new-output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.new_output.resolve(strict=False)
    stage = args.stage.resolve(strict=True)
    if (output.exists() or output.is_symlink() or not output.parent.is_dir()
            or stage == output.parent or stage in output.parents
            or any(x.casefold() == "my drive" for x in output.parts)):
        raise CandidateTimingError("Fresh external non-source output required")
    data = build_timing_index(args.stage, args.asr_dir, args.evidence)
    with output.open("x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(json.dumps({"output": str(output),
                      "candidate_count": data["candidate_count"],
                      "unambiguous_asr_spans": data["unambiguous_asr_spans"],
                      "publication_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
