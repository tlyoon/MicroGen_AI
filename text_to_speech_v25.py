from __future__ import annotations

import glob
import json
import os
import re
import sys
import time
import warnings
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_FILE = Path("script.txt")
TTS_SIDECAR = Path("script_tts.json")
VOICE_NAME = os.environ.get("MICROVID_TTS_VOICE", "en-US-Chirp-HD-F")
LANGUAGE_CODE = os.environ.get("MICROVID_TTS_LANGUAGE", "en-US")
SPEAKING_RATE = float(os.environ.get("MICROVID_TTS_SPEAKING_RATE", "0.8"))
LOCATION = os.environ.get("MICROVID_TTS_LOCATION", "global")


def _microvid_config_dir() -> Path:
    configured = os.environ.get("MICROVID_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Microvid"
    return Path.home() / "AppData" / "Local" / "Microvid"


def _google_cloud_credential_path(config_dir: Path) -> Path:
    explicit = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        raise RuntimeError(f"GOOGLE_APPLICATION_CREDENTIALS points to a missing file: {candidate}")
    preferred = config_dir / "google_cloud_credentials.json"
    if preferred.is_file():
        return preferred.resolve()
    candidates = sorted(config_dir.glob("*.json")) if config_dir.is_dir() else []
    # script_tts.json lives in the project, not config_dir, so it is never considered here.
    if len(candidates) == 1:
        return candidates[0].resolve()
    if len(candidates) > 1:
        raise RuntimeError(
            f"{preferred} was not found and multiple JSON files exist in {config_dir}; "
            "rename the intended service-account file or set GOOGLE_APPLICATION_CREDENTIALS explicitly."
        )
    raise RuntimeError(
        f"Google Cloud credentials not found in {config_dir}. Place google_cloud_credentials.json there "
        "or set GOOGLE_APPLICATION_CREDENTIALS."
    )


def _load_runtime_environment() -> None:
    config_dir = _microvid_config_dir()
    env_path = config_dir / ".env"
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path, override=False)
    cred = _google_cloud_credential_path(config_dir)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred)
    print(f"Using shared Microvid Google Cloud credentials from: {cred}")


def normalize_scientific_speech(text: str) -> str:
    replacements = (
        ("±", " plus or minus "), ("×", " times "), ("÷", " divided by "),
        ("π", " pi "), ("Δ", " delta "), ("σ", " sigma "), ("Ω", " ohms "),
        ("°C", " degrees Celsius "), ("%", " percent "),
    )
    out = str(text or "")
    for source, target in replacements:
        out = out.replace(source, target)
    unit_patterns = (
        (r"\bkg\s*/\s*m(?:\^?3|³)\b", " kilograms per cubic metre "),
        (r"\bkg\s+m(?:\^\s*-?3|⁻³)\b", " kilograms per cubic metre "),
        (r"\bg\s*/\s*cm(?:\^?3|³)\b", " grams per cubic centimetre "),
        (r"\bg\s+cm(?:\^\s*-?3|⁻³)\b", " grams per cubic centimetre "),
        (r"\bm\s*/\s*s(?:\^?2|²)\b", " metres per second squared "),
        (r"\bm\s+s(?:\^\s*-?2|⁻²)\b", " metres per second squared "),
        (r"\bm\s*/\s*s\b", " metres per second "),
        (r"\bm\s+s(?:\^\s*-?1|⁻¹)\b", " metres per second "),
        (r"\bcm\s*/\s*s\b", " centimetres per second "),
        (r"\bmm\b", " millimetres "), (r"\bcm\b", " centimetres "),
    )
    for pattern, replacement in unit_patterns:
        out = re.sub(pattern, replacement, out, flags=re.I)
    out = re.sub(r"\\mathrm\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\text\{([^{}]+)\}", r"\1", out)
    out = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"\1 divided by \2", out)
    out = re.sub(r"([A-Za-z0-9)]+)\s*\^\s*2\b", r"\1 squared", out)
    out = re.sub(r"([A-Za-z0-9)]+)\s*\^\s*3\b", r"\1 cubed", out)
    out = out.replace("²", " squared ").replace("³", " cubed ")
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    return re.sub(r"\s+", " ", out).strip()


def _is_transient_tts_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if callable(code):
        code = code()
    code_text = str(code).upper()
    return code in {408, 429, 500, 502, 503, 504} or any(
        marker in code_text for marker in ("DEADLINE_EXCEEDED", "INTERNAL", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
    ) or type(exc).__name__ in {"DeadlineExceeded", "InternalServerError", "RetryError", "ServiceUnavailable", "TooManyRequests"}


def _google_synthesize(text: str, output: Path) -> str:
    from google.cloud import texttospeech

    location = LOCATION.strip().lower()
    options = None if location in {"", "global"} else {"api_endpoint": f"{location}-texttospeech.googleapis.com"}
    response = None
    for attempt in range(4):
        try:
            client = texttospeech.TextToSpeechClient(client_options=options) if options else texttospeech.TextToSpeechClient()
            response = client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=text),
                voice=texttospeech.VoiceSelectionParams(
                    language_code=LANGUAGE_CODE,
                    name=VOICE_NAME,
                    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
                ),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    speaking_rate=SPEAKING_RATE,
                ),
            )
            break
        except Exception as exc:
            if attempt == 3 or not _is_transient_tts_error(exc):
                raise
            time.sleep(2**attempt)
    if response is None:
        raise RuntimeError("Google Cloud TTS returned no response.")
    output.write_bytes(response.audio_content)
    return "google_cloud_chirp3"


def _sapi_synthesize(text: str, output: Path) -> str:
    if os.name != "nt":
        raise RuntimeError("SAPI fallback requires Windows.")
    import win32com.client

    voice = win32com.client.Dispatch("SAPI.SpVoice")
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    stream.Open(str(output.resolve()), 3, False)
    try:
        voice.AudioOutputStream = stream
        voice.Speak(text)
    finally:
        stream.Close()
    return "sapi"


def synthesize(text: str, output: Path) -> str:
    spoken = normalize_scientific_speech(text)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _google_synthesize(spoken, output)
    except Exception as primary_exc:
        if os.environ.get("MICROVID_TTS_FALLBACK", "sapi").lower() != "sapi":
            raise
        warnings.warn(f"Primary TTS failed ({primary_exc}); using SAPI fallback.", RuntimeWarning, stacklevel=2)
        try:
            return _sapi_synthesize(spoken, output)
        except Exception as fallback_exc:
            raise RuntimeError(f"Primary TTS failed: {primary_exc}; fallback TTS also failed: {fallback_exc}") from fallback_exc


def _legacy_script_slides(path: Path) -> list[str]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    blocks = [block.strip() for block in re.split(r"(?=\*\*Slide\s+\d+)", text) if block.strip()]
    results = []
    for block in blocks:
        lines = block.splitlines()
        if lines and lines[0].lstrip().startswith("**Slide"):
            lines = lines[1:]
        narration = "\n".join(lines).strip().rstrip("*").strip()
        results.append(narration)
    return results


def _speech_items() -> list[dict[str, str]]:
    if TTS_SIDECAR.is_file():
        payload = json.loads(TTS_SIDECAR.read_text(encoding="utf-8"))
        items = payload.get("slides", [])
        if items:
            return [
                {
                    "narration": str(item.get("narration", "")).strip(),
                    "tts_text": str(item.get("tts_text") or item.get("narration") or "").strip(),
                }
                for item in items
            ]
    if not SCRIPT_FILE.is_file():
        raise FileNotFoundError("script.txt is missing. Run gen_script first.")
    return [{"narration": text, "tts_text": text} for text in _legacy_script_slides(SCRIPT_FILE)]


def main() -> None:
    _load_runtime_environment()
    items = _speech_items()
    if not items:
        raise RuntimeError("No slide narration found.")

    for old in glob.glob("slide*.wav"):
        try:
            Path(old).unlink()
        except OSError:
            pass

    providers = []
    for idx, item in enumerate(items, start=1):
        text = item["tts_text"] or item["narration"]
        if not text:
            raise RuntimeError(f"Slide {idx} has no narration/tts_text.")
        output = Path(f"slide{idx}.wav")
        provider = synthesize(text, output)
        providers.append(provider)
        print(f'Audio content written to file "{output}" using {provider}')

    produced = sorted(Path.cwd().glob("slide*.wav"), key=lambda p: int(re.search(r"\d+", p.stem).group()))
    if len(produced) != len(items):
        raise RuntimeError(f"Expected {len(items)} WAV files, but found {len(produced)}.")
    print(f"Success: Produced {len(produced)} audio files, matching the number of slides.")
    print(f"TTS providers used: {sorted(set(providers))}")


if __name__ == "__main__":
    main()
