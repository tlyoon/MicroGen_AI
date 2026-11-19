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


def _third_component_witness_hold(state: dict) -> Exception:
    """Distinguish absent provider from a genuinely contrary third opinion.

    A known billing/network/model failure can never be misreported as a
    mathematical rejection, and neither outcome grants a second paid send.
    """
    if not isinstance(state,dict):
        return VerifiedAcousticReplayError(
            "COMPONENT_WITNESS_MATHEMATICS_HOLD: independent evidence missing")
    if (state.get("status")=="THIRD_GEMINI_REVIEWER_UNAVAILABLE"
            or (state.get("status")=="MATH_WITNESS_UNRESOLVED"
                and any(isinstance(a,dict)
                        and a.get("status")=="WITNESS_UNAVAILABLE"
                        for a in state.get("attempts",[])))):
        return RuntimeError(
            "G3_COMPONENT_THIRD_GEMINI_UNAVAILABLE: finite independent "
            "witness consumed without a usable reply; hold prior audio "
            "and preserve the paid-call reservation")
    if state.get("status") in {
            "PAID_WITNESS_SCOPE_UNAUTHORIZED",
            "PAID_WITNESS_ALREADY_RESERVED_OR_INVALID"}:
        return VerifiedAcousticReplayError(
            "COMPONENT_WITNESS_SCOPE_HOLD: no authorized fresh single "
            "third-Gemini request; no paid replay allowed")
    return VerifiedAcousticReplayError(
        "COMPONENT_WITNESS_MATHEMATICS_HOLD: independently obtained third "
        "review did not corroborate the original math variable; "
        "original WAVs and paid reservation remain frozen")


def maybe_replay_verified_acoustic(stage: Path, texts: list[str],
                                   *, third_provider_factory=None) -> dict | None:
    """Find ONE genuine failed review, re-evaluate both model outputs strictly.

    Only a changed comparison or acoustic-gate implementation authorizes
    offline replay. A single original math-symbol split may use one source-
    blind third Gemini model under fresh owner authorization; no other old
    disagreements are waived or ever auto-rebilled.
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
    new_cp = read_json(stage / ".microgen_checkpoint.json")
    if (new_grant.get("publication_authorized") is not False
            or not isinstance(new_scope, dict)
            or new_scope.get("work_root") != str(stage.parent)
            or new_cp is None
            or new_cp.get("package_commit") != new_scope.get("code_revision")
            or not new_cp.get("completed",{}).get("tts")
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
                or not (old / "microgen_autonomous_acoustic_gate.py").is_file()
                or (old / "microgen_autonomous_acoustic_gate.py").is_symlink()
                or (sha(old / math_file.name) == sha(math_file)
                    and sha(old / "microgen_autonomous_acoustic_gate.py") ==
                    sha(stage / "microgen_autonomous_acoustic_gate.py"))):
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
    witness_used = False
    if report.get("review_required_slides"):
        # On an exact source/PCM matched old 2-Gemini disagreement, never
        # issue another 42 ASR calls merely to reconstruct the same words.
        # Only an eligible isolated symbol split can ask ONE third, distinct
        # source-blind Gemini model under the new finite owner grant.
        from microgen_tts_acoustic_qa import (
            verified_isolated_component_letter_witness,
        )
        from microgen_autonomous_acoustic_gate import _bounded_independent_math_tiebreak
        flagged=report["review_required_slides"]
        if (len(flagged)!=1 or flagged!=trace["review_required_slides"]
                or not valid_trace(trace_path,snapshot,len(texts),
                                   tuple(trace["models"]))):
            raise VerifiedAcousticReplayError(
                "Historical dual-Gemini disagreement not an isolated source-bound symbol")
        n=flagged[0]
        original=report["slides"][n-1]
        if (original.get("assessment")!="REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE"
                or original.get("source_pronunciation_risks")
                or not verified_isolated_component_letter_witness(
                    texts[n-1],*original["transcripts"],texts[n-1])):
            raise VerifiedAcousticReplayError(
                "Historical mathematics disagreement still material; no paid replay")
        arguments=({"provider_factory":third_provider_factory}
                   if third_provider_factory is not None else {})
        report=_bounded_independent_math_tiebreak(
            stage,texts,report,tuple(trace["models"]),**arguments)
        if report.get("review_required_slides"):
            raise _third_component_witness_hold(
                report.get("independent_math_tiebreak",{}))
        witness_used = True
    _verify(stage, report, texts)
    return {
        "report": report,
        "evidence": {
            "method": ("SHA_BOUND_PREVIOUS_BLIND_GEMINI_PLUS_THIRD_COMPONENT_WITNESS"
                       if witness_used else
                       "SHA_BOUND_PREVIOUS_BLIND_GEMINI_TRANSCRIPT_RECLASSIFICATION"),
            "original_private_trace_sha256": sha(trace_path),
            "original_campaign": old.parent.name,
            "math_comparator_sha256": sha(math_file),
            "paid_recognition_calls": 1 if witness_used else 0,
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
            or evidence["method"] not in {
               "SHA_BOUND_PREVIOUS_BLIND_GEMINI_TRANSCRIPT_RECLASSIFICATION",
               "SHA_BOUND_PREVIOUS_BLIND_GEMINI_PLUS_THIRD_COMPONENT_WITNESS"}
            or evidence["paid_recognition_calls"] != (
                1 if evidence["method"] ==
                "SHA_BOUND_PREVIOUS_BLIND_GEMINI_PLUS_THIRD_COMPONENT_WITNESS"
                else 0)
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
    if evidence["method"] == (
            "SHA_BOUND_PREVIOUS_BLIND_GEMINI_PLUS_THIRD_COMPONENT_WITNESS"):
        from text_to_speech_v25 import normalize_scientific_speech
        from microgen_tts_acoustic_qa import (
            verified_isolated_component_letter_witness, _input_snapshot,
        )
        from microgen_autonomous_acoustic_gate import MATH_TIEBREAK_MODELS
        flagged=trace["review_required_slides"]
        if (len(flagged)!=1 or report.get("review_required_slides")
                or report.get("input_snapshot_sha256") !=
                   _input_snapshot(stage,len(rows))):
            raise VerifiedAcousticReplayError("Unverifiable component witness scope")
        n=flagged[0]
        row=rows[n-1]
        original=trace["slides"][n-1]
        witness=row.get("third_independent_review")
        timeline=report.get("independent_math_tiebreak")
        if (not isinstance(witness,dict) or
                witness.get("status")!="SOURCE_BOUND_COMPONENT_LETTER_WITNESS"
                or witness.get("model") not in MATH_TIEBREAK_MODELS
                or witness.get("model") in trace["models"]
                or not isinstance(timeline,dict)
                or timeline.get("status")!="VERIFIED_BOUNDED_WITNESS"
                or timeline.get("attempted_slides")!=[n]
                or timeline.get("resolved_slides")!=[n]
                or timeline.get("witness_model")!=witness.get("model")
                or not verified_isolated_component_letter_witness(
                    normalize_scientific_speech(
                        json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
                        ["slides"][n-1]["tts_text"]),
                    *original["original_blind_transcripts"],
                    witness.get("transcript",""))):
            raise VerifiedAcousticReplayError("Third independent math witness invalid")
        reservation=read_json(stage/".microgen_independent_math_witness_attempt.json")
        expected_reservation_hash=hashlib.sha256(
            json.dumps(report["input_snapshot_sha256"],
                       sort_keys=True).encode("utf8")).hexdigest()
        if (reservation is None or reservation.get("schema_version")!=1
                or reservation.get("status")!=
                   "RESERVED_PAID_THIRD_REVIEWER_NO_IMPLICIT_RETRY"
                or reservation.get("candidate_slides")!=[n]
                or reservation.get("chosen_model")!=witness["model"]
                or reservation.get("source_snapshot_sha256")!=
                   expected_reservation_hash
                or reservation.get("max_paid_third_asr_calls")!=1
                or reservation.get("publication_allowed") is not False):
            raise VerifiedAcousticReplayError("Third reviewer paid-call reservation invalid")
