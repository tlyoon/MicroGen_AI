"""Gemini Flash-Lite production TTS adapted from MicroGen_AI_Web/selenium_pipeline/tts.py.

Only this API-based MicroGen_AI repository is changed. The Web repository is
reference-only. Gemini 3.8 Flash-Lite (Kore) is the default, Gemini 3.8 Flash
is first fallback, and Google Cloud Chirp 3 HD is the owner's bounded
last-resort private-development fallback only when both Gemini models fail.
Regenerate a WHOLE BATCH on fallback: never mix narrator engines.
Never infers permission to publish from a voice name, WAV hash or API response.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave

DEFAULT_PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-3.8-flash-lite-tts"
FALLBACK_MODEL = "gemini-3.8-flash-tts"
DEFAULT_VOICE = "Kore"
STYLE = ("Natural and clear university-level physics teaching narration, "
         "calm pacing, precise mathematical and scientific terminology. "
         "Read the transcript faithfully, with appropriate short pauses.")
CLOUD_FALLBACK_ENV = "MICROGEN_TTS_ENABLE_CLOUD_FALLBACK"
CLOUD_MAX_CHARS_ENV = "MICROGEN_TTS_CLOUD_FALLBACK_MAX_CHARACTERS"
BATCH_RECEIPT = "private_flash_tts_batch_receipt.json"


class FlashTTSError(RuntimeError):
    """Fail-closed source/voice/audio or authorization validation."""


def provider_specs(voice: str = DEFAULT_VOICE, *, enable_cloud: bool = False) -> list[dict]:
    """Exact MicroGen_AI_Web provider/model/voice order; no silent Cloud billing."""
    if not isinstance(voice, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,63}", voice):
        raise FlashTTSError("A valid, explicitly named TTS voice is required")
    specs = [
        {"provider": "gemini_flash_lite_tts", "model": DEFAULT_MODEL, "voice": voice},
        {"provider": "gemini_flash_tts", "model": FALLBACK_MODEL, "voice": voice},
    ]
    if enable_cloud:
        specs.append({"provider": "google_cloud_chirp3", "model": "chirp3-hd",
                      "voice": f"en-US-Chirp3-HD-{voice}"})
    return specs


def _load_gemini_keys_from_microvid() -> None:
    """Read existing HP-private Microvid .env, without requiring Cloud credentials."""
    from dotenv import load_dotenv
    base = os.environ.get("MICROVID_CONFIG_DIR")
    path = (Path(base).expanduser() if base else
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
            / "Microvid") / ".env"
    if path.is_file():
        load_dotenv(dotenv_path=path, override=False)


def _response_wav(response) -> bytes:
    for candidate in getattr(response, "candidates", None) or ():
        for part in getattr(getattr(candidate, "content", None), "parts", None) or ():
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                raw = inline.data
                payload = base64.b64decode(raw) if isinstance(raw, str) else bytes(raw)
                if payload.startswith((b"RIFF", b"RF64")):
                    return payload
    raise FlashTTSError("Gemini TTS returned no complete WAV; no audio was published")


def _gemini_api(text: str, model: str, voice: str) -> bytes:
    _load_gemini_keys_from_microvid()
    from gemini_keys import call_with_client_failover, create_gemini_client
    response = call_with_client_failover(
        create_gemini_client,
        lambda client: client.models.generate_content(
            model=model,
            contents=[{"role": "user", "parts": [
                {"text": text, "speech_metadata": {"style": STYLE}}
            ]}],
            config={"response_modalities": ["AUDIO"],
                    "speech_config": {"voice_config": {"voice": voice}}},
        ),
        label="MicroGen Gemini 3.8 TTS",
        max_retries=0,
    )
    return _response_wav(response)


def _set_chirp3_credentials() -> None:
    configured = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if configured:
        if not Path(configured).is_file():
            raise FlashTTSError("Configured Cloud credentials path does not exist")
        return
    config = os.environ.get("MICROVID_CONFIG_DIR")
    base = (Path(config).expanduser() if config else
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
            / "Microvid")
    cred = base / "google_cloud_credentials.json"
    if not cred.is_file():
        raise FlashTTSError("Cloud fallback credential file is missing")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred)


def _chirp3_api(text: str, voice: str) -> bytes:
    _set_chirp3_credentials()
    from google.cloud import texttospeech
    client = texttospeech.TextToSpeechClient()
    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(
            language_code="en-US", name=voice),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=0.9),
        retry=None,
        timeout=60,
    )
    payload = response.audio_content
    if not payload.startswith((b"RIFF", b"RF64")):
        raise FlashTTSError("Chirp3 fallback returned no PCM WAV")
    return payload


def _timeout_seconds(text: str) -> float:
    override = os.environ.get("MICROGEN_TTS_HARD_TIMEOUT_SECONDS")
    if override:
        return max(10.0, float(override))
    base = max(30.0, float(os.environ.get("MICROGEN_TTS_TIMEOUT_BASE_SECONDS", "90")))
    per100 = max(0.0, float(os.environ.get("MICROGEN_TTS_TIMEOUT_PER_100_CHARS_SECONDS", "15")))
    cap = max(base, float(os.environ.get("MICROGEN_TTS_TIMEOUT_MAX_SECONDS", "300")))
    return min(cap, base + per100 * math.ceil(max(1, len(text)) / 100))


def _split_tts_text(text: str, max_chars: int = 450) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    chunks, current = [], ""
    for sentence in sentences:
        while len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            cut = sentence.rfind(" ", 0, max_chars + 1)
            if cut < max_chars // 2:
                cut = max_chars
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            candidate = (current + " " + sentence).strip()
            if len(candidate) > max_chars:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def _merge_wavs(payloads: list[bytes]) -> bytes:
    if not payloads:
        raise FlashTTSError("No WAV segments")
    output = io.BytesIO()
    signature = None
    pcm = []
    for payload in payloads:
        with wave.open(io.BytesIO(payload), "rb") as audio:
            props = (audio.getnchannels(), audio.getsampwidth(),
                     audio.getframerate(), audio.getcomptype())
            if signature is None:
                signature = props
            if signature != props:
                raise FlashTTSError("Chunk WAV formats differ; refusing broken concatenation")
            pcm.append(audio.readframes(audio.getnframes()))
    with wave.open(output, "wb") as audio:
        audio.setnchannels(signature[0])
        audio.setsampwidth(signature[1])
        audio.setframerate(signature[2])
        audio.setcomptype(signature[3], "not compressed")
        audio.writeframes(b"".join(pcm))
    return output.getvalue()


def _worker_request(text: str, spec: dict) -> bytes:
    """Bound each potentially hanging API request in a killable child process."""
    with tempfile.TemporaryDirectory(prefix=".microgen-tts-worker-") as tmp:
        output = Path(tmp) / "candidate.wav"
        args = [sys.executable, str(Path(__file__).resolve()),
                "--worker-output", str(output),
                "--worker-provider", spec["provider"],
                "--worker-model", spec["model"], "--worker-voice", spec["voice"]]
        done = subprocess.run(args, input=text, text=True, capture_output=True,
                              timeout=_timeout_seconds(text))
        if done.returncode or not output.is_file():
            raise FlashTTSError("TTS worker failed: " + (done.stderr or done.stdout)[-500:])
        return output.read_bytes()


def _speak(text: str, spec: dict) -> bytes:
    """Attempt the whole text first; sentence-aware chunking only after timeout."""
    try:
        return _worker_request(text, spec)
    except subprocess.TimeoutExpired:
        if spec["provider"] == "google_cloud_chirp3" or len(text) <= 450:
            raise
        chunks = _split_tts_text(text)
        if len(chunks) < 2:
            raise
        return _merge_wavs([_worker_request(chunk, spec) for chunk in chunks])


def _valid_wav(payload: bytes) -> dict:
    if not 44 < len(payload) <= 30_000_000:
        raise FlashTTSError("TTS WAV is empty or above safe file size")
    try:
        with wave.open(io.BytesIO(payload), "rb") as wav:
            if (wav.getnchannels() != 1 or wav.getsampwidth() != 2
                or wav.getframerate() < 8000 or wav.getnframes() <= 0
                or wav.getcomptype() != "NONE"):
                raise FlashTTSError("Expected nonempty mono PCM16 WAV")
            seconds = wav.getnframes() / wav.getframerate()
            if seconds < 0.08 or seconds > 180:
                raise FlashTTSError("WAV duration outside safe slide range")
            return {"seconds": round(seconds, 4), "sample_rate_hz": wav.getframerate()}
    except (EOFError, wave.Error, ZeroDivisionError, OSError) as exc:
        raise FlashTTSError("Invalid WAV data") from exc


def render_batch(texts: list[str], new_private_output: Path, *,
                 voice: str = DEFAULT_VOICE, allow_cloud: bool = False,
                 speak=None) -> dict:
    """All-or-nothing batch; alternate engine remakes ALL slides for consistent voice.

    No output directory is created until every WAV in one engine passes.
    Private G2 development uses the owner's standing finite TTS grant;
    other callers must supply existing bounded Cloud settings. No provider
    receipt grants external publication rights.
    """
    output = Path(new_private_output).resolve(strict=False)
    if (output.exists() or output.is_symlink() or not output.parent.is_dir()
            or any(p.casefold() == "my drive" for p in output.parts)):
        raise FlashTTSError("A fresh local private output is mandatory")
    if (not isinstance(texts, list) or not 1 <= len(texts) <= 120
            or any(not isinstance(t, str) or not 1 <= len(t) <= 10_000
                   for t in texts)):
        raise FlashTTSError("Invalid bounded narration inventory")
    count = sum(len(t) for t in texts)
    if allow_cloud:
        ceiling = os.environ.get(CLOUD_MAX_CHARS_ENV, "").strip()
        if (os.environ.get(CLOUD_FALLBACK_ENV) != "1"
                or not ceiling.isdigit() or int(ceiling) < count):
            raise FlashTTSError("Cloud fallback is not budget/owner authorized")
    call = _speak if speak is None else speak
    specs = provider_specs(voice, enable_cloud=allow_cloud)
    cloud_char_ceiling = int(os.environ[CLOUD_MAX_CHARS_ENV]) if allow_cloud else 0
    cloud_char_attempts = 0
    failures = []
    for spec in specs:
        temp = Path(tempfile.mkdtemp(prefix=".microgen-flash-batch-", dir=output.parent))
        rows = []
        try:
            for index, text in enumerate(texts, 1):
                last_error = None
                for attempt in range(1, max(1, int(os.environ.get("MICROGEN_TTS_QUEUE_ROUNDS", "3"))) + 1):
                    try:
                        if spec["provider"] == "google_cloud_chirp3":
                            # Count every attempt, even when it fails: it may be billable.
                            if cloud_char_attempts + len(text) > cloud_char_ceiling:
                                raise FlashTTSError("Cloud fallback cumulative attempt budget exhausted")
                            cloud_char_attempts += len(text)
                        wav = call(text, spec)
                        details = _valid_wav(wav)
                        break
                    except Exception as exc:
                        last_error = exc
                        if attempt == max(1,int(os.environ.get("MICROGEN_TTS_QUEUE_ROUNDS", "3"))):
                            raise
                        time.sleep(min(3, attempt))
                name = f"slide{index:02}.wav"
                file = temp / name
                file.write_bytes(wav)
                rows.append({"slide": index, "wav_filename": name,
                             "text_sha256": hashlib.sha256(text.encode("utf8")).hexdigest(),
                             "wav_sha256": hashlib.sha256(wav).hexdigest(),
                             **details})
            if len(rows) != len(texts):
                raise FlashTTSError("Incomplete TTS batch")
            receipt = {
                "schema_version": 1,
                "status": "PRIVATE_GEMINI_FLASH_TTS_SOURCE_BOUND_AUDIO_NOT_FOR_PUBLICATION",
                "engine": spec["provider"], "model": spec["model"],
                "voice": spec["voice"], "fallback_used": spec != specs[0],
                "fallback_mode": "whole_batch_single_voice",
                "slide_count": len(rows), "text_characters": count,
                "provider_identity_independently_verified": False,
                "spoken_phonemes_independently_verified": False,
                "formal_publication_authorized": False,
                "publication_allowed": False,
                "cloud_fallback_attempted_characters": cloud_char_attempts,
                "slides": rows,
            }
            (temp / BATCH_RECEIPT).write_text(json.dumps(receipt, indent=2), encoding="utf8")
            if output.exists() or output.is_symlink():
                raise FlashTTSError("Destination created concurrently")
            os.rename(temp, output)
            return receipt
        except Exception as exc:
            if output.exists() or output.is_symlink():
                raise FlashTTSError("Private output path appeared; stop all paid fallbacks") from exc
            failures.append(f"{spec['model']}:{type(exc).__name__}")
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    raise FlashTTSError("TTS batch failed all authorized engine choices: " + ", ".join(failures))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--worker-output", type=Path)
    ap.add_argument("--worker-provider", choices=("gemini_flash_lite_tts", "gemini_flash_tts", "google_cloud_chirp3"))
    ap.add_argument("--worker-model", default=DEFAULT_MODEL)
    ap.add_argument("--worker-voice", default=DEFAULT_VOICE)
    a = ap.parse_args(argv)
    if not a.worker_output or not a.worker_provider:
        ap.error("Worker mode required; production callers use render_batch()")
    content = sys.stdin.read()
    if not content.strip():
        ap.error("Empty speech transcript")
    if a.worker_provider == "google_cloud_chirp3":
        value = _chirp3_api(content, a.worker_voice)
    else:
        value = _gemini_api(content, a.worker_model, a.worker_voice)
    _valid_wav(value)
    a.worker_output.write_bytes(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
