"""Bounded, authenticated LOCAL preservation of failed independent ASR evidence.

Historical G2 failures retained only summary counts, so repeat development
had to pay again to discover the original transcriber disagreement. This
retains the existing model-blind responses privately when QA fails; it does
NOT approve pronunciation, create new calls or weaken the normal gate.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket

SCHEMA_VERSION = 1
MAX_RECORD_BYTES = 180_000
MAX_TRACE_FILES = 4
PREFIX = ".microgen_private_acoustic_failed_"


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def retain_private_failed_acoustic_review(
    stage: Path, texts: list[str], report: dict, models: tuple[str, str],
) -> bool:
    """Retain the original blinded reviewer words only on owner's private HP.

    SHA-bind all currently observed WAVs, TTS narration sidecar and provider
    voice manifest before recording. Local data is not exported by
    publish_bundle and not entered into Git, stdout or shared sources.
    """
    try:
        stage = Path(stage).resolve()
        private_root = Path(os.environ["LOCALAPPDATA"]).resolve() / "MicroGen_AI_Checkpoints"
        receipt = stage.parent / ".microgen_bounded_provider_authorization.json"
        if (os.name != "nt" or socket.gethostname().casefold() != "hp"
                or stage.parent.parent != private_root
                or not receipt.is_file() or receipt.is_symlink()
                or not isinstance(texts, list) or not texts
                or not isinstance(report, dict)
                or not isinstance(report.get("review_required_slides"), list)
                or not report["review_required_slides"]
                or len(models) != 2 or not all(isinstance(m, str) and m for m in models)
                or models[0] == models[1]):
            return False
        from microgen_tts_acoustic_qa import _input_snapshot

        snapshot = _input_snapshot(stage, len(texts))
        if snapshot != report.get("input_snapshot_sha256"):
            return False
        rows = report.get("slides")
        if not isinstance(rows, list) or len(rows) != len(texts):
            return False
        saved_rows = []
        for index, (row, expected) in enumerate(zip(rows, texts), 1):
            if (not isinstance(row, dict) or row.get("slide") != index
                    or row.get("audio_sha256") != snapshot[f"slide{index}.wav"]
                    or row.get("expected_spoken_sha256") != _hash(expected.encode("utf8"))):
                return False
            transcripts = row.get("transcripts")
            if (not isinstance(transcripts, list) or len(transcripts) != 2
                    or any(not isinstance(t, str) or len(t) > 12000 for t in transcripts)):
                return False
            saved_rows.append({
                "slide": index,
                "wav_sha256": row["audio_sha256"],
                "expected_spoken_sha256": row["expected_spoken_sha256"],
                "original_blind_transcripts": transcripts,
                "assessment": row.get("assessment"),
                "source_risk_codes": sorted({
                    risk.get("code") for risk in row.get("source_pronunciation_risks", [])
                    if isinstance(risk, dict) and isinstance(risk.get("code"), str)
                }),
            })
        evidence = {
            "schema_version": SCHEMA_VERSION,
            "status": "PRIVATE_FAILED_ASR_EVIDENCE_NOT_ACCEPTED",
            "models": list(models),
            "source_snapshot_sha256": snapshot,
            "review_required_slides": report["review_required_slides"],
            "slides": saved_rows,
            "accepted_for_video": False,
            "phonetic_accuracy_certified": False,
            "publication_allowed": False,
        }
        raw = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
        encoded = raw.encode("utf8")
        if len(encoded) > MAX_RECORD_BYTES:
            return False
        existing = list(stage.glob(PREFIX + "*.json"))
        digest = _hash(encoded)[:20]
        destination = stage / f"{PREFIX}{digest}.json"
        if destination.is_file() and not destination.is_symlink():
            return destination.read_bytes() == encoded
        if len(existing) >= MAX_TRACE_FILES or destination.exists() or destination.is_symlink():
            return False
        with destination.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return destination.read_bytes() == encoded
    except (KeyError, OSError, RuntimeError, ValueError, TypeError):
        return False
