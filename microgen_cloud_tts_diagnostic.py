"""Explicit single-call Google Cloud TTS troubleshooting (not formal speech).

Requires a *new* standalone diagnostic directory and a chargeable-test flag.
One <=500 character normalized utterance, exactly one API attempt, no retries.
Never produces slideN.wav, scripts, lecture manifests or release evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from microgen_tts_provider_policy import (
    diagnostic_request_allowed, TTSProviderPolicyError,
)


def run_diagnostic(text: str, directory: Path, *,
                   confirm_chargeable: bool = False,
                   literal_c_dot_comparison: bool = False) -> dict:
    from text_to_speech_v25 import (
        VOICE_NAME, LANGUAGE_CODE, normalize_scientific_speech,
        _load_runtime_environment, _google_synthesize,
    )
    from microgen_pronunciation import require_safe_speech
    from microgen_tts_provenance import wav_characteristics

    dest = Path(directory).expanduser().resolve(strict=False)
    if (dest.exists() or dest.is_symlink()
            or "diagnostic" not in dest.name.casefold()
            or any(x.casefold() == "my drive" for x in dest.parts)
            or any(x.casefold() in (".git", "projects") for x in dest.parts)):
        raise TTSProviderPolicyError(
            "Use a NEW local directory named *diagnostic*, outside project/source Drive"
        )
    normalized = normalize_scientific_speech(text)
    require_safe_speech(text, normalized)
    if literal_c_dot_comparison:
        # A deliberately uncorrected control sample is permitted ONLY for
        # the known mathematical c. -> "circa" bug, in this diagnostic path.
        # Never relax the formal speech preflight or enable raw LaTeX.
        if not re.search(r"(?i)\b(?:at|point|variable|equals|constant)\s+c\.(?=\s+[A-Z]|$)", text):
            raise TTSProviderPolicyError("Literal comparison requires an actual mathematical c. case")
        spoken = text.strip()
    else:
        spoken = normalized
    diagnostic_request_allowed(
        character_count=len(spoken), confirmation=confirm_chargeable,
        output_is_new=not dest.exists(),
    )
    dest.mkdir(parents=True, exist_ok=False)
    audio = dest / "diagnostic_cloud_tts_NOT_FORMAL.wav"
    try:
        _load_runtime_environment()
        provider = _google_synthesize(spoken, audio, max_attempts=1)
        evidence = wav_characteristics(audio)
        report = {
            "schema_version": 1,
            "purpose": "CLOUD_TTS_TROUBLESHOOTING_ONLY_NOT_FORMAL",
            "provider": provider,
            "voice_name": VOICE_NAME,
            "language": LANGUAGE_CODE,
            "requested_characters": len(spoken),
            "synthesis_mode": (
                "RAW_C_DOT_CONTROL_ONLY" if literal_c_dot_comparison
                else "NORMALIZED_SCIENTIFIC_SPEECH"
            ),
            "normalization_applied": not literal_c_dot_comparison,
            "mathematical_c_dot_control_high_risk": literal_c_dot_comparison,
            "requested_utterance_sha256": hashlib.sha256(
                spoken.encode("utf-8")).hexdigest(),
            "wav_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
            "audio": evidence,
            "chargeable_request_explicitly_confirmed": True,
            "attempted_api_calls_maximum": 1,
            "production_narration_verified": False,
            "formal_tts_default_changed_to_cloud": False,
            "formal_tts_manifest_created": False,
            "publication_allowed": False,
        }
        (dest / "diagnostic_receipt.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        return report
    except Exception:
        # Only remove the unique new directory created by this invocation.
        shutil.rmtree(dest)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True,
                        help="One short trouble-shooting utterance (max 500 normalized characters)")
    parser.add_argument("--new-diagnostic-directory", type=Path, required=True)
    parser.add_argument("--literal-c-dot-comparison", action="store_true",
                        help="One bounded deliberately unnormalized mathematical c. diagnostic control; never production")
    parser.add_argument("--confirm-chargeable-diagnostic", action="store_true",
                        help="Explicitly confirm that this one Google Cloud request could be charged")
    args = parser.parse_args()
    result = run_diagnostic(
        args.text, args.new_diagnostic_directory,
        confirm_chargeable=args.confirm_chargeable_diagnostic,
        literal_c_dot_comparison=args.literal_c_dot_comparison,
    )
    print(json.dumps({
        "purpose": result["purpose"],
        "voice": result["voice_name"],
        "duration_seconds": result["audio"]["duration_seconds"],
        "publication_allowed": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
