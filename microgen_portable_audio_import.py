"""Private, model-free import of previously generated voice WAVs.

Only validates an explicit handoff and SHA-pinned capture manifest. No audio
generation, provider access, local model, voice approval, or publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import wave

from microgen_portable_voice_input_handoff import _read_json
from microgen_pronunciation_closed_loop import sha_file
from microgen_tts_wave_integrity import require_structurally_usable_audio


class PortableAudioImportError(ValueError):
    pass


def _verified_handoff(file: Path) -> dict:
    if file.is_symlink() or not file.is_file():
        raise PortableAudioImportError("Private handoff file missing")
    data = _read_json(file)
    rows = data.get("requests")
    count = data.get("slide_count")
    if (data.get("status") != "PORTABLE_VOICE_INPUT_READY_FORMAL_PRODUCTION_BLOCKED"
            or type(count) is not int or not 2 <= count <= 20
            or not isinstance(rows, list) or len(rows) != count
            or data.get("publication_allowed") is not False
            or data.get("formal_voice_synthesis_authorized") is not False
            or data.get("formal_voice_provider") is not None
            or data.get("formal_voice_name") is not None):
        raise PortableAudioImportError("No valid nonformal source-bound voice handoff")
    for idx, row in enumerate(rows, 1):
        if (row.get("slide") != idx or
                not isinstance(row.get("topic_id"), str) or
                not isinstance(row.get("source_page"), int) or
                not isinstance(row.get("text_sha256"), str) or
                not re.fullmatch(r"[a-f0-9]{64}", row["text_sha256"]) or
                hashlib.sha256(str(row.get("input_text", "")).encode("utf8")).hexdigest() !=
                    row["text_sha256"] or
                row.get("formal_synthesis_authorized") is not False or
                row.get("audio_filename") is not None or
                row.get("audio_sha256") is not None):
            raise PortableAudioImportError("Incomplete or falsely completed audio request")
    return data


def make_audio_capture_template(handoff_path: Path) -> dict:
    """Create a no-audio manifest for later owner-authorized voice production."""
    handoff = _verified_handoff(Path(handoff_path))
    return {
        "schema_version": 1,
        "voice_input_handoff_sha256": sha_file(handoff_path),
        "declared_provider": None,
        "declared_voice": None,
        "publication_allowed": False,
        "formal_production_authorized": False,
        "captured_wavs": [
            {"slide": row["slide"],
             "filename": f"slide{row['slide']:02d}.wav",
             "source_text_sha256": row["text_sha256"],
             "wav_sha256": None}
            for row in handoff["requests"]],
    }


def audit_portable_audio_import(handoff_path: Path, audio_dir: Path,
                                capture_manifest: Path) -> dict:
    """Return private technical identity/PCM evidence; not provider authenticity."""
    handoff_path, audio_dir, capture_manifest = map(
        Path, (handoff_path, audio_dir, capture_manifest))
    handoff = _verified_handoff(handoff_path)
    if (audio_dir.is_symlink() or not audio_dir.is_dir()
            or capture_manifest.is_symlink() or not capture_manifest.is_file()):
        raise PortableAudioImportError("Real private audio directory and manifest required")
    meta = _read_json(capture_manifest)
    expected = make_audio_capture_template(handoff_path)
    if (meta.get("schema_version") != 1 or
            meta.get("voice_input_handoff_sha256") != expected["voice_input_handoff_sha256"]
            or meta.get("publication_allowed") is not False
            or meta.get("formal_production_authorized") is not False
            or not isinstance(meta.get("captured_wavs"), list)
            or len(meta["captured_wavs"]) != handoff["slide_count"]):
        raise PortableAudioImportError("Capture manifest differs from private speech handoff")
    declared_provider = meta.get("declared_provider")
    declared_voice = meta.get("declared_voice")
    if (not isinstance(declared_provider, str) or not 2 <= len(declared_provider) <= 80
            or not declared_provider.isascii() or
            not isinstance(declared_voice, str) or not 2 <= len(declared_voice) <= 80
            or not declared_voice.isascii()):
        raise PortableAudioImportError("A named but unverified provider/voice is required")
    expected_files = {entry["filename"] for entry in expected["captured_wavs"]}
    if ({p.name for p in audio_dir.glob("*.wav")} != expected_files):
        raise PortableAudioImportError("Missing, additional or misnamed WAV files")
    prior = {"handoff": sha_file(handoff_path),
             "capture": sha_file(capture_manifest)}
    captured = []
    for idx, (item, template) in enumerate(zip(
            meta["captured_wavs"], expected["captured_wavs"]), 1):
        if (not isinstance(item, dict) or set(item) != set(template)
                or item["slide"] != idx
                or item["filename"] != template["filename"]
                or item["source_text_sha256"] != template["source_text_sha256"]
                or not isinstance(item["wav_sha256"], str)
                or not re.fullmatch("[a-f0-9]{64}", item["wav_sha256"])):
            raise PortableAudioImportError("Capture row not linked to requested speech")
        wav = audio_dir / item["filename"]
        if wav.is_symlink() or not wav.is_file() or wav.stat().st_size > 30_000_000:
            raise PortableAudioImportError("Source WAV unavailable or unbounded")
        digest = sha_file(wav)
        if digest != item["wav_sha256"]:
            raise PortableAudioImportError("Captured WAV file modified or swapped")
        try:
            technical = require_structurally_usable_audio(wav)
            with wave.open(str(wav), "rb") as stream:
                seconds = stream.getnframes() / stream.getframerate()
            if not 0.2 <= seconds <= 180:
                raise PortableAudioImportError("Implausible per-slide recording duration")
        except (OSError, wave.Error, EOFError, ValueError) as exc:
            raise PortableAudioImportError("Invalid recorded PCM voice data") from exc
        captured.append({
            "slide": idx, "wav_filename": item["filename"],
            "wav_sha256": digest,
            "source_text_sha256": item["source_text_sha256"],
            "seconds": round(seconds, 3),
            "structural_pcm_quality_checks_passed": True,
            "acoustic_word_accuracy_proven": False,
        })
    if (sha_file(handoff_path) != prior["handoff"]
            or sha_file(capture_manifest) != prior["capture"]
            or any(sha_file(audio_dir / x["wav_filename"]) != x["wav_sha256"]
                   for x in captured)):
        raise PortableAudioImportError("Protected source audio changed during verification")
    return {
        "schema_version": 1,
        "status": "EXTERNAL_VOICE_WAVS_SHA_AND_PCM_VERIFIED_NOT_PRODUCTION_APPROVED",
        "section_id": handoff["section_id"],
        "source_pdf_sha256": handoff["source_pdf_sha256"],
        "rendered_pdf_sha256": handoff["rendered_pdf_sha256"],
        "private_handoff_sha256": prior["handoff"],
        "capture_manifest_sha256": prior["capture"],
        "slide_count": len(captured),
        "declared_provider": declared_provider,
        "declared_voice": declared_voice,
        "provider_identity_independently_verified": False,
        "narration_words_actually_spoken_verified": False,
        "voice_rights_proven": False,
        "local_model_invocations": 0,
        "provider_calls": 0,
        "formal_voice_synthesis_authorized": False,
        "publication_allowed": False,
        "captured_wavs": captured,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-handoff", required=True, type=Path)
    parser.add_argument("--new-private-template", type=Path)
    parser.add_argument("--audio-dir", type=Path)
    parser.add_argument("--capture-manifest", type=Path)
    parser.add_argument("--new-private-receipt", type=Path)
    opts = parser.parse_args(argv)
    if opts.new_private_template:
        report = make_audio_capture_template(opts.private_handoff)
        output = opts.new_private_template
    elif opts.audio_dir and opts.capture_manifest and opts.new_private_receipt:
        report = audit_portable_audio_import(
            opts.private_handoff, opts.audio_dir, opts.capture_manifest)
        output = opts.new_private_receipt
    else:
        parser.error("Specify only template or a complete recorded WAV audit")
    output = Path(output).resolve(strict=False)
    if (output.exists() or output.is_symlink() or not output.parent.is_dir()
            or any(p.casefold() == "my drive" for p in output.parts)
            or output == opts.private_handoff.resolve(strict=True)):
        raise PortableAudioImportError("Fresh private output required")
    with output.open("x", encoding="utf8") as out:
        json.dump(report, out, indent=2)
    print(json.dumps({
        "section": report.get("section_id", "template"),
        "recordings_or_requests": len(report.get("captured_wavs", [])),
        "publication_allowed": False, "model_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
