"""Fail-closed reuse of independently obtained Gemini ASR transcripts.

Only for the owner's bounded HP G2 campaign. Reclassifies original BLIND
reviewer words against a corrected, source-blind mathematical formatter, when
every script/voice/WAV byte and independent model identity still matches.
No paid requests, regeneration, invented reviewers, or waived mathematics.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket

PREFIX = ".microgen_private_acoustic_failed_"
OWNER = ".microgen_bounded_provider_authorization.json"
MAX_BYTES = 180_000


class VerifiedAcousticReplayError(RuntimeError):
    pass


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path, limit: int = MAX_BYTES) -> dict | None:
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > limit):
        return None
    try:
        value = json.loads(path.read_text(encoding="utf8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def valid_trace(path: Path, snapshot: dict, slide_count: int,
                models: tuple[str, str]) -> dict | None:
    """Validate source/WAV lineage and unchanged Gemini blind words."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        return None
    raw = path.read_bytes()
    match = re.fullmatch(r"\.microgen_private_acoustic_failed_([0-9a-f]{20})\.json",
                         path.name)
    if not match or hashlib.sha256(raw).hexdigest()[:20] != match[1]:
        return None
    try:
        report = json.loads(raw.decode("utf8"))
    except (UnicodeError, ValueError):
        return None
    if (not isinstance(report, dict) or report.get("schema_version") != 1
            or report.get("status") != "PRIVATE_FAILED_ASR_EVIDENCE_NOT_ACCEPTED"
            or report.get("source_snapshot_sha256") != snapshot
            or report.get("models") != list(models)
            or report.get("accepted_for_video") is not False
            or report.get("publication_allowed") is not False
            or report.get("phonetic_accuracy_certified") is not False
            or not isinstance(report.get("review_required_slides"), list)
            or not report["review_required_slides"]):
        return None
    rows = report.get("slides")
    if not isinstance(rows, list) or len(rows) != slide_count:
        return None
    for n, row in enumerate(rows, 1):
        if (not isinstance(row, dict) or row.get("slide") != n
                or row.get("wav_sha256") != snapshot[f"slide{n}.wav"]
                or not re.fullmatch(r"[0-9a-f]{64}",
                                    str(row.get("expected_spoken_sha256", "")))):
            return None
        transcripts = row.get("original_blind_transcripts")
        if (not isinstance(transcripts, list) or len(transcripts) != 2
                or any(not isinstance(t, str) or not 5 <= len(t.strip()) <= 12000
                       for t in transcripts)):
            return None
    return report


def maybe_replay_verified_acoustic(stage: Path, texts: list[str]) -> dict | None:
    """Find ONE genuine failed review, re-evaluate both model outputs strictly.

    Only a changed comparison implementation authorizes offline replay. If
    unchanged evidence remains ambiguous, block instead of model-shopping.
    """
    stage = Path(stage).resolve()
    root = Path(os.environ.get("LOCALAPPDATA", "/unavailable")) / "MicroGen_AI_Checkpoints"
    if (os.name != "nt" or socket.gethostname().casefold() != "hp"
            or stage.parent.parent != root or not stage.is_dir()
            or not isinstance(texts, list) or not texts):
        return None
    new_grant = read_json(stage.parent / OWNER)
    from microgen_tts_acoustic_qa import _input_snapshot, audit_with_recognizer
    from microgen_autonomous_acoustic_gate import _verify
    snapshot = _input_snapshot(stage, len(texts))
    source_file = stage / "source.pdf"
    math_file = stage / "microgen_acoustic_math_transcript.py"
    if (not source_file.is_file() or source_file.is_symlink()
            or not math_file.is_file() or math_file.is_symlink()
            or new_grant is None):
        return None
    new_scope = new_grant.get("scope", {})
    source_sha = sha(source_file)
    if (new_grant.get("publication_authorized") is not False
            or not isinstance(new_scope, dict)
            or new_scope.get("host") != "hp"
            or new_scope.get("source_sha256") != source_sha
            or new_scope.get("stop_after") != "acceptance"):
        return None
    matches = []
    for parent in root.iterdir():
        if parent == stage.parent or parent.is_symlink() or not parent.is_dir():
            continue
        old = parent / stage.name
        old_grant = read_json(parent / OWNER)
        if (not old.is_dir() or old.is_symlink() or old_grant is None
                or old_grant.get("publication_authorized") is not False):
            continue
        scope = old_grant.get("scope", {})
        old_cp = read_json(old / ".microgen_checkpoint.json")
        if (not isinstance(scope, dict) or scope.get("host") != "hp"
                or scope.get("source_sha256") != source_sha
                or scope.get("stop_after") != "acceptance"
                or old_cp is None
                or old_cp.get("package_commit") != scope.get("code_revision")
                or not old_cp.get("completed", {}).get("tts")
                or not (old / "source.pdf").is_file()
                or (old / "source.pdf").is_symlink()
                or sha(old / "source.pdf") != source_sha
                or not (old / math_file.name).is_file()
                or (old / math_file.name).is_symlink()
                or sha(old / math_file.name) == sha(math_file)):
            continue
        for diagnostic_path in old.glob(".microgen_acoustic_blocked_*.json"):
            diagnostic = read_json(diagnostic_path, 128_000)
            if (diagnostic is None
                    or diagnostic.get("status") != "INDEPENDENT_ACOUSTIC_SCREEN_BLOCKED"
                    or diagnostic.get("root_cause_family") != "ASR_DISAGREEMENT_HOLD"
                    or diagnostic.get("input_snapshot_sha256") != snapshot
                    or diagnostic.get("private_blind_transcripts_retained") is not True):
                continue
            models = diagnostic.get("recognition_models")
            if (not isinstance(models, list) or len(models) != 2
                    or models[0] == models[1]
                    or any(not isinstance(m, str) or not m.startswith("gemini-")
                           for m in models)):
                continue
            for f in old.glob(PREFIX + "*.json"):
                trace = valid_trace(f, snapshot, len(texts), tuple(models))
                if trace is None:
                    continue
                if trace["review_required_slides"] != diagnostic.get("review_required_slides"):
                    continue
                if any(row["expected_spoken_sha256"] !=
                       hashlib.sha256(text.encode("utf8")).hexdigest()
                       for row, text in zip(trace["slides"], texts)):
                    continue
                matches.append((diagnostic.get("audit_utc", ""), old, f, trace))
    if not matches:
        return None
    # Do not select a convenient older opinion after a newer failure.
    matches.sort(key=lambda x: x[0], reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        raise VerifiedAcousticReplayError("Ambiguous equally recent independent ASR evidence")
    _, old, trace_path, trace = matches[0]
    rows = trace["slides"]
    def recognizer(index):
        def replay(path):
            n = int(path.stem[5:])
            if path != stage / f"slide{n}.wav" or not 1 <= n <= len(rows):
                raise VerifiedAcousticReplayError("Unexpected replay WAV")
            return rows[n-1]["original_blind_transcripts"][index]
        return replay
    report = audit_with_recognizer(
        stage, texts, recognizer(0), lambda x: x,
        independent_recognizer=recognizer(1),
        recognition_models=tuple(trace["models"]))
    if report.get("review_required_slides"):
        raise VerifiedAcousticReplayError(
            "Previously recorded dual-Gemini evidence still has substantive "
            "acoustic disagreements; do not rebill unchanged audio")
    _verify(stage, report, texts)
    return {
        "report": report,
        "evidence": {
            "method": "SHA_BOUND_PREVIOUS_BLIND_GEMINI_TRANSCRIPT_RECLASSIFICATION",
            "original_private_trace_sha256": sha(trace_path),
            "original_campaign": old.parent.name,
            "math_comparator_sha256": sha(math_file),
            "paid_recognition_calls": 0,
            "audio_regeneration": False,
            "publication_allowed": False,
        },
    }


def verify_replay_evidence(stage: Path, receipt: dict) -> None:
    """Reject forged/stale historical-ASR acceptance on every later gate."""
    evidence = receipt.get("verified_historical_asr_reclassification")
    if evidence is None:
        return
    if (not isinstance(evidence, dict)
            or set(evidence) != {
                "method", "original_private_trace_sha256", "original_campaign",
                "math_comparator_sha256", "paid_recognition_calls",
                "audio_regeneration", "publication_allowed"}
            or evidence["method"] !=
               "SHA_BOUND_PREVIOUS_BLIND_GEMINI_TRANSCRIPT_RECLASSIFICATION"
            or evidence["paid_recognition_calls"] != 0
            or evidence["audio_regeneration"] is not False
            or evidence["publication_allowed"] is not False
            or not isinstance(evidence["original_campaign"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}",
                                evidence["original_campaign"])
            or not re.fullmatch(r"[0-9a-f]{64}",
                                str(evidence["original_private_trace_sha256"]))):
        raise VerifiedAcousticReplayError("Invalid historic reviewer proof")
    stage = Path(stage).resolve()
    root = Path(os.environ.get("LOCALAPPDATA", "/unavailable")) / "MicroGen_AI_Checkpoints"
    if (os.name != "nt" or socket.gethostname().casefold() != "hp"
            or stage.parent.parent != root
            or evidence["math_comparator_sha256"] !=
               sha(stage / "microgen_acoustic_math_transcript.py")
            or receipt.get("repaired_audio_slides") != 0):
        raise VerifiedAcousticReplayError("Historic reviewer proof out of scope")
    old = root / evidence["original_campaign"] / stage.name
    if (not old.is_dir() or old.is_symlink()
            or not (old / "source.pdf").is_file()
            or sha(old / "source.pdf") != sha(stage / "source.pdf")):
        raise VerifiedAcousticReplayError("Historic source unavailable or changed")
    report = receipt.get("independent_report")
    if not isinstance(report, dict):
        raise VerifiedAcousticReplayError("Missing independently compared transcript rows")
    candidates = [
        f for f in old.glob(PREFIX + "*.json")
        if f.is_file() and not f.is_symlink()
        and sha(f) == evidence["original_private_trace_sha256"]
    ]
    if len(candidates) != 1:
        raise VerifiedAcousticReplayError("Historic two-model trace not unique")
    trace = valid_trace(candidates[0], report.get("input_snapshot_sha256"),
                        report.get("slide_count"), tuple(report.get("recognition_models", ())))
    rows = report.get("slides")
    if (trace is None or not isinstance(rows, list)
            or len(rows) != len(trace["slides"])
            or any(row.get("transcripts") != original["original_blind_transcripts"]
                   for row, original in zip(rows, trace["slides"]))):
        raise VerifiedAcousticReplayError("Historical reviewer transcript identity drift")
