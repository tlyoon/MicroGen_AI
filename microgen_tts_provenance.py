"""Secret-free, checksum-bound TTS WAV provenance and release verification.

This is a technical integrity check, not listening/academic QA. The SAPI
fallback is allowed by synthesis policy but has no pinned voice in MicroGen:
it cannot acquire a verified *single-voice* completion manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import wave
from pathlib import Path

SCHEMA_VERSION = 1
MANIFEST_FILE = ".microgen_tts_provenance.json"


class TTSProvenanceError(RuntimeError):
    pass


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wav_characteristics(path: Path) -> dict:
    try:
        with wave.open(str(path), "rb") as audio:
            if audio.getnframes() <= 0 or audio.getframerate() <= 0:
                raise TTSProvenanceError("Empty or invalid WAV")
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
                raise TTSProvenanceError("Expected mono 16-bit PCM")
            return {
                "sample_rate_hz": audio.getframerate(),
                "channels": audio.getnchannels(),
                "sample_width_bytes": audio.getsampwidth(),
                "frames": audio.getnframes(),
                "duration_seconds": round(audio.getnframes()/audio.getframerate(), 6),
            }
    except (OSError, ValueError, EOFError, wave.Error) as exc:
        raise TTSProvenanceError(f"Invalid WAV: {path}") from exc


def make_record(
    *, slide: int, path: Path, text: str, provider: str, key: str,
    voice_name: str, language_code: str, speaking_rate: float, location: str,
) -> dict:
    if slide < 1 or not provider:
        raise TTSProvenanceError("Slide number or provider invalid")
    # A successful Cloud request binds the configured voice to the provider.
    # SAPI.SpVoice currently uses a machine default, not a selectable/pinned
    # identity, so it must NOT pass the voice-provenance verification gate.
    pinned_voice = provider == "google_cloud_chirp3" and bool(voice_name)
    return {
        "schema_version": SCHEMA_VERSION,
        "slide": slide,
        "key": key,
        "sha256": digest_file(path),
        "provider": provider,
        "voice_name": voice_name if pinned_voice else None,
        "voice_identity_verified": pinned_voice,
        "language_code": language_code,
        "speaking_rate": speaking_rate,
        "location": location,
        "normalized_input_sha256": digest_text(text),
        **wav_characteristics(path),
    }


def verify_record(
    record: dict, path: Path, *, slide: int, text: str, key: str,
    voice_name: str, language_code: str, speaking_rate: float, location: str,
) -> None:
    if record.get("schema_version") != SCHEMA_VERSION:
        raise TTSProvenanceError(f"Unverified old TTS cache metadata: slide {slide}")
    required = {
        "slide": slide, "key": key,
        "normalized_input_sha256": digest_text(text),
        "voice_name": voice_name, "language_code": language_code,
        "speaking_rate": speaking_rate, "location": location,
        "voice_identity_verified": True,
    }
    for field, value in required.items():
        if record.get(field) != value:
            raise TTSProvenanceError(f"TTS {field} mismatch for slide {slide}")
    if record.get("provider") != "google_cloud_chirp3":
        raise TTSProvenanceError(f"Unverified TTS provider for slide {slide}")
    if digest_file(path) != record.get("sha256"):
        raise TTSProvenanceError(f"WAV SHA-256 drift for slide {slide}")
    characteristics = wav_characteristics(path)
    for name, value in characteristics.items():
        if record.get(name) != value:
            raise TTSProvenanceError(f"WAV {name} drift for slide {slide}")


def verify_records(folder: Path, records: list[dict], inputs: list[str]) -> dict:
    if not records or len(records) != len(inputs):
        raise TTSProvenanceError("Missing or extra WAV provenance entries")
    voices = {(r.get("provider"),r.get("voice_name"),r.get("speaking_rate"),
               r.get("language_code"),r.get("location"),r.get("sample_rate_hz"))
              for r in records}
    if len(voices) != 1:
        raise TTSProvenanceError("Mixed TTS provider, voice, rate or audio format")
    for number, (record, input_text) in enumerate(zip(records, inputs), 1):
        verify_record(record, Path(folder)/f"slide{number}.wav",
                      slide=number, text=input_text, key=record["key"],
                      voice_name=record["voice_name"],
                      language_code=record["language_code"],
                      speaking_rate=record["speaking_rate"],
                      location=record["location"])
    return {
        "schema_version": SCHEMA_VERSION,
        "slides": records,
        "slide_count": len(records),
        "provider": records[0]["provider"],
        "voice_name": records[0]["voice_name"],
        "total_seconds": round(sum(x["duration_seconds"] for x in records),6),
        "normalized_input_list_sha256": digest_text(json.dumps(inputs,ensure_ascii=False)),
        "technical_provenance_verified": True,
        "listening_qa_verified": False,
        "academic_qa_verified": False,
        "element_highlight_qa_verified": False,
    }


def write_manifest(folder: Path, records: list[dict], inputs: list[str]) -> Path:
    folder = Path(folder)
    manifest = verify_records(folder, records, inputs)
    path = folder / MANIFEST_FILE
    tmp = folder / f"{MANIFEST_FILE}.tmp"
    try:
        tmp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def verify_manifest(folder: Path, inputs: list[str]) -> dict:
    folder = Path(folder)
    try:
        document = json.loads((folder/MANIFEST_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TTSProvenanceError("Missing or unreadable TTS completion manifest") from exc
    verified = verify_records(folder, document.get("slides", []), inputs)
    if document != verified:
        raise TTSProvenanceError("TTS completion manifest is inconsistent")
    return verified
