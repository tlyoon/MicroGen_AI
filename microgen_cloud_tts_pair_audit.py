"""Read-only hash-bound paired Cloud TTS c-dot diagnostic audit.

Compares *actual* recorded Cloud diagnostic WAVs and optional local Vosk word
screen. Does not issue provider calls, synthesize, modify media, infer a
certified phonetic truth, or approve production/publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from microgen_tts_provenance import wav_characteristics
from text_to_speech_v25 import normalize_scientific_speech

class CloudTTSPairAuditError(ValueError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _receipt(folder: Path) -> tuple[dict, Path]:
    if folder.is_symlink() or not folder.is_dir():
        raise CloudTTSPairAuditError("Diagnostic directory missing or a symlink")
    manifest = folder / "diagnostic_receipt.json"
    wav = folder / "diagnostic_cloud_tts_NOT_FORMAL.wav"
    if (not manifest.is_file() or manifest.is_symlink()
            or not wav.is_file() or wav.is_symlink()):
        raise CloudTTSPairAuditError("Actual isolated diagnostic WAV and receipt required")
    receipt = json.loads(manifest.read_text(encoding="utf-8"))
    if (receipt.get("purpose") != "CLOUD_TTS_TROUBLESHOOTING_ONLY_NOT_FORMAL"
        or receipt.get("publication_allowed") is not False
        or receipt.get("formal_tts_manifest_created") is not False
        or receipt.get("formal_tts_default_changed_to_cloud") is not False
        or receipt.get("attempted_api_calls_maximum") != 1
        or receipt.get("chargeable_request_explicitly_confirmed") is not True
        or receipt.get("wav_sha256") != sha(wav)):
        raise CloudTTSPairAuditError("Diagnostic receipt is untrusted or mismatched")
    measured = wav_characteristics(wav)
    if measured != receipt.get("audio"):
        raise CloudTTSPairAuditError("Diagnostic WAV format/frames mismatch")
    return receipt, wav


def _words(row: dict, sha256: str) -> list[str]:
    recog = row.get("recognition", {})
    if (recog.get("source_wav_sha256") != sha256
        or recog.get("phonetic_identity_verified") is not False
        or recog.get("semantic_word_alignment_certified") is not False):
        raise CloudTTSPairAuditError("ASR not bound to genuine diagnostic WAV or overclaimed")
    if not isinstance(recog.get("words"), list):
        raise CloudTTSPairAuditError("ASR word list invalid")
    output = []
    for word in recog["words"]:
        if not isinstance(word, dict) or not isinstance(word.get("word"), str):
            raise CloudTTSPairAuditError("ASR word format invalid")
        if not word["word"].strip():
            raise CloudTTSPairAuditError("ASR empty word")
        output.append(word["word"].strip().casefold())
    return output


def audit_pair(raw_dir: Path, normalized_dir: Path, text: str,
               *, asr_report: Path | None = None) -> dict:
    raw, raw_audio = _receipt(Path(raw_dir))
    norm, norm_audio = _receipt(Path(normalized_dir))
    if Path(raw_dir).resolve() == Path(normalized_dir).resolve():
        raise CloudTTSPairAuditError("Need independent raw and normalized recordings")
    normalized = normalize_scientific_speech(text)
    if normalized == text or "see." not in normalized.casefold():
        raise CloudTTSPairAuditError("Not a meaningful mathematical c-dot comparison")
    for receipt, spoken in ((raw, text.strip()), (norm, normalized)):
        if (receipt.get("requested_utterance_sha256") !=
            hashlib.sha256(spoken.encode("utf-8")).hexdigest()
            or receipt.get("requested_characters") != len(spoken)):
            raise CloudTTSPairAuditError("Recorded request does not match original comparison text")
    if raw.get("synthesis_mode") != "RAW_C_DOT_CONTROL_ONLY":
        raise CloudTTSPairAuditError("Raw WAV missing explicit control label")
    if raw.get("normalization_applied") is not False:
        raise CloudTTSPairAuditError("Literal sample unexpectedly normalized")
    if norm.get("synthesis_mode", "NORMALIZED_SCIENTIFIC_SPEECH") != "NORMALIZED_SCIENTIFIC_SPEECH":
        raise CloudTTSPairAuditError("Expected normalized sample")
    if norm.get("normalization_applied", True) is not True:
        raise CloudTTSPairAuditError("Normalized sample flagged literal")
    if (not raw.get("voice_name") or
        raw["voice_name"] != norm.get("voice_name") or
        raw.get("provider") != norm.get("provider") or
        raw.get("language") != norm.get("language")):
        raise CloudTTSPairAuditError("Comparison must use same configured provider/voice/language")
    result = {
        "schema_version": 1,
        "status": "RECORDED_C_DOT_CLOUD_TTS_PAIR_AUDITED_NOT_PHONETIC_CERTIFICATION",
        "voice_name": raw["voice_name"],
        "provider": raw["provider"],
        "literal_wav_sha256": raw["wav_sha256"],
        "normalized_wav_sha256": norm["wav_sha256"],
        "literal_duration_seconds": raw["audio"]["duration_seconds"],
        "normalized_duration_seconds": norm["audio"]["duration_seconds"],
        "literal_receipt_sha256": sha(Path(raw_dir) / "diagnostic_receipt.json"),
        "normalized_receipt_sha256": sha(Path(normalized_dir) / "diagnostic_receipt.json"),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "asr_screening_available": False,
        "asr_raw_circa": False,
        "asr_normalized_see_like": False,
        "phonetic_identity_verified": False,
        "same_speaker_acoustically_verified": False,
        "formal_tts_default_changed": False,
        "production_lecture_generated": False,
        "publication_allowed": False,
    }
    if asr_report:
        file = Path(asr_report)
        if file.is_symlink() or not file.is_file():
            raise CloudTTSPairAuditError("Missing ASR receipt")
        asr = json.loads(file.read_text(encoding="utf-8"))
        rows = asr.get("items", [])
        if (len(rows) != 2 or
                {row.get("label") for row in rows} != {"normalized", "literal"} or
                asr.get("publication_allowed") is not False):
            raise CloudTTSPairAuditError("Unexpected offline recognizer report")
        match = {row["label"]: row for row in rows}
        if (match["literal"].get("receipt_wav_sha256") != raw["wav_sha256"] or
            match["normalized"].get("receipt_wav_sha256") != norm["wav_sha256"]):
            raise CloudTTSPairAuditError("ASR observation audio identities drifted")
        rw = _words(match["literal"], raw["wav_sha256"])
        nw = _words(match["normalized"], norm["wav_sha256"])
        result.update({
            "asr_screening_available": True,
            "asr_report_sha256": sha(file),
            "asr_raw_words": rw,
            "asr_normalized_words": nw,
            "asr_raw_circa": "circa" in rw,
            "asr_normalized_see_like": any(s in nw for s in ("see", "sea", "cee")),
            "asr_screening_supports_normalization": (
                "circa" in rw and "circa" not in nw and
                any(s in nw for s in ("see", "sea", "cee"))
            ),
        })
    # Rehash at end, preventing TOCTOU drift during offline ASR parsing.
    if (sha(raw_audio) != raw["wav_sha256"] or sha(norm_audio) != norm["wav_sha256"]):
        raise CloudTTSPairAuditError("WAV changed during independent audit")
    return result


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--raw-diagnostic-dir", type=Path, required=True)
    p.add_argument("--normalized-diagnostic-dir", type=Path, required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--offline-asr-report", type=Path)
    p.add_argument("--new-report", type=Path, required=True)
    args = p.parse_args()
    if args.new_report.exists() or args.new_report.is_symlink():
        raise CloudTTSPairAuditError("Refusing to overwrite existing evidence")
    result = audit_pair(args.raw_diagnostic_dir,args.normalized_diagnostic_dir,
                        args.text,asr_report=args.offline_asr_report)
    args.new_report.parent.mkdir(parents=True,exist_ok=True)
    with args.new_report.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps({k:result[k] for k in ("status","voice_name","asr_raw_circa",
        "asr_normalized_see_like","phonetic_identity_verified","publication_allowed")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
