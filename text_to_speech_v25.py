from __future__ import annotations

import glob
import hashlib
import wave
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
    from microgen_pronunciation_closed_loop import expand_unambiguous_math
    # Reviewed, context-limited notation expansions are applied ONLY to TTS
    # speech input, before legacy symbol/unit conversion. Never edit slides.
    out = expand_unambiguous_math(str(text or ""))
    for source, target in replacements:
        out = out.replace(source, target)
    # Stable symbol names are safe to normalize without guessing their role.
    # Ambiguous expression structure is handled by the offline preflight.
    math_symbols = (
        ("α", " alpha "), ("β", " beta "), ("γ", " gamma "),
        ("θ", " theta "), ("λ", " lambda "), ("μ", " mu "),
        ("ρ", " rho "), ("φ", " phi "), ("ω", " omega "),
        ("∞", " infinity "), ("≤", " less than or equal to "),
        ("≥", " greater than or equal to "), ("≠", " not equal to "),
    )
    for symbol, spoken_name in math_symbols:
        out = out.replace(symbol, spoken_name)
    # Text TTS frequently interprets "y-value" as "yay value" rather than
    # the name of the mathematical letter Y ("why"). Expand letter names
    # only in well-defined coordinate/math compounds, never globally.
    math_letter_compounds = (
        "value", "values", "axis", "axes", "intercept", "intercepts",
        "coordinate", "coordinates", "component", "components",
    )
    out = re.sub(
        r"(?<![A-Za-z])(?P<letter>[xy])\s*[-\u2010-\u2015]\s*"
        r"(?P<noun>" + "|".join(math_letter_compounds) + r")\b",
        lambda match: ("why" if match["letter"].lower() == "y" else "ex")
        + " " + match["noun"],
        out, flags=re.I,
    )
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
    # A mathematical point such as "at c. Next..." must be spoken as the
    # letter C, not expanded by a TTS abbreviation model to "circa".
    # Keep the punctuation and the original narration unchanged: this
    # conversion is for synthesis and its content-addressed cache key only.
    # Require a mathematical cue and a sentence boundary to preserve
    # historical dates ("c. 1900") and initials ("C. Smith").
    out = re.sub(
        r"(?P<prefix>\b(?i:at|point|approaches|of|equals|variable|constant|coefficient)\s+)"
        r"c\.(?=\s+[A-Z]|$)",
        lambda match: match["prefix"] + "see.",
        out,
    )
    return re.sub(r"\s+", " ", out).strip()


def _is_transient_tts_error(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if callable(code):
        code = code()
    code_text = str(code).upper()
    return code in {408, 429, 500, 502, 503, 504} or any(
        marker in code_text for marker in ("DEADLINE_EXCEEDED", "INTERNAL", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
    ) or type(exc).__name__ in {"DeadlineExceeded", "InternalServerError", "RetryError", "ServiceUnavailable", "TooManyRequests"}


def _google_synthesize(text: str, output: Path, *, max_attempts: int = 4) -> str:
    from google.cloud import texttospeech

    location = LOCATION.strip().lower()
    options = None if location in {"", "global"} else {"api_endpoint": f"{location}-texttospeech.googleapis.com"}
    response = None
    if max_attempts not in (1, 4):
        raise ValueError("Only bounded one-attempt diagnostics or existing four-attempt formal synthesis")
    for attempt in range(max_attempts):
        try:
            client = texttospeech.TextToSpeechClient(client_options=options) if options else texttospeech.TextToSpeechClient()
            # A diagnostic must bound BOTH our loop and the client SDK retry
            # policy: otherwise one Python attempt could send several RPCs.
            # Preserve the historical formal provider behavior unchanged.
            rpc_options = {"retry": None, "timeout": 30.0} if max_attempts == 1 else {}
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
                **rpc_options,
            )
            break
        except Exception as exc:
            if attempt == max_attempts - 1 or not _is_transient_tts_error(exc):
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
    from microgen_pronunciation import require_safe_speech
    spoken = normalize_scientific_speech(text)
    require_safe_speech(text, spoken)
    from microgen_tts_provider_policy import require_formal_provider
    provider = require_formal_provider()
    if provider == "gemini":
        # The ordinary user-facing API-TTS default now matches MicroGen_AI_Web:
        # Gemini 3.8 Flash-Lite, Kore; Flash first backup, Cloud ONLY when opted in.
        # Direct single-slide calls remain non-batch; use main()/render_batch()
        # for strict whole-lecture narrator continuity.
        from microgen_flash_tts import (
            DEFAULT_VOICE, CLOUD_FALLBACK_ENV, CLOUD_MAX_CHARS_ENV,
            provider_specs, _speak, _valid_wav,
        )
        allow_cloud = (
            os.environ.get(CLOUD_FALLBACK_ENV) == "1"
            and os.environ.get(CLOUD_MAX_CHARS_ENV, "").isdigit()
            and int(os.environ[CLOUD_MAX_CHARS_ENV]) >= len(spoken)
        )
        specs = provider_specs(
            os.environ.get("MICROGEN_TTS_VOICE", DEFAULT_VOICE),
            enable_cloud=allow_cloud,
        )
        errors = []
        for spec in specs:
            try:
                payload = _speak(spoken, spec)
                _valid_wav(payload)
                output.parent.mkdir(parents=True, exist_ok=True)
                candidate = output.with_name(output.name + ".partial")
                if candidate.exists():
                    raise RuntimeError("Refuse existing partially written WAV")
                try:
                    candidate.write_bytes(payload)
                    os.replace(candidate, output)
                finally:
                    candidate.unlink(missing_ok=True)
                return spec["provider"]
            except Exception as exc:
                errors.append(f"{spec['model']}:{type(exc).__name__}")
        raise RuntimeError("All authorized Gemini/Chirp fallbacks failed: " + ", ".join(errors))
    if provider != "google_cloud":
        raise RuntimeError("Unsupported TTS provider selection")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _google_synthesize(spoken, output)
    except Exception as primary_exc:
        if os.environ.get("MICROVID_TTS_FALLBACK", "disabled").lower() != "sapi":
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


def _run_flash_batch(items: list[dict[str, str]]) -> None:
    """Gemini-first lecture batch; whole-engine failover with atomic WAV rollback."""
    import shutil
    import tempfile
    from microgen_flash_tts import (
        render_batch, DEFAULT_VOICE, CLOUD_FALLBACK_ENV, CLOUD_MAX_CHARS_ENV,
    )
    from microgen_quality import check_wavs
    from microgen_tts_provenance import (
        make_record, verify_records, verify_manifest, write_manifest,
    )
    texts = [normalize_scientific_speech(x["tts_text"] or x["narration"]) for x in items]
    voice = os.environ.get("MICROGEN_TTS_VOICE", DEFAULT_VOICE)
    if Path(".microgen_tts_provenance.json").is_file():
        try:
            previous = verify_manifest(Path.cwd(), texts)
            if (previous["provider"] in ("gemini_flash_lite_tts", "gemini_flash_tts")
                    and previous["voice_name"] == voice
                    and previous["slide_count"] == len(texts)):
                print("[TTS] Reusing verified same-voice Gemini Flash batch.")
                return
        except Exception:
            pass
    allow_cloud = os.environ.get(CLOUD_FALLBACK_ENV) == "1"
    if allow_cloud:
        raw = os.environ.get(CLOUD_MAX_CHARS_ENV, "")
        if not raw.isdigit() or int(raw) < sum(map(len, texts)):
            raise RuntimeError("Cloud Chirp3 fallback requires explicit per-batch character ceiling")
    with tempfile.TemporaryDirectory(prefix=".microgen-flash-stage-", dir=str(Path.cwd())) as temp:
        root = Path(temp)
        report = render_batch(
            texts, root / "ready", voice=voice, allow_cloud=allow_cloud,
        )
        stage = root / "prepared"
        stage.mkdir()
        model, engine, actual_voice = report["model"], report["engine"], report["voice"]
        rate = 0.9 if engine == "google_cloud_chirp3" else 1.0
        records = []
        for index, spoken in enumerate(texts, 1):
            candidate = stage / f"slide{index}.wav"
            shutil.copy2(root / "ready" / f"slide{index:02}.wav", candidate)
            key = hashlib.sha256(json.dumps(
                [spoken, engine, model, actual_voice, "en-US", rate, "global",
                 "microgen-flash-tts-v1-provenance"],
                ensure_ascii=False, sort_keys=True,
            ).encode("utf8")).hexdigest()
            record = make_record(
                slide=index, path=candidate, text=spoken, provider=engine,
                key=key, voice_name=actual_voice, language_code="en-US",
                speaking_rate=rate, location="global",
            )
            records.append(record)
        verify_records(stage, records, texts)
        write_manifest(stage, records, texts)
        check_wavs(stage, len(texts))
        cache = Path(".microgen_tts_cache")
        # Create cache only after complete source/voice/PCM validation.
        cache_preexisted = cache.exists()
        if not cache_preexisted:
            cache.mkdir()
        files = [(stage / f"slide{i}.wav", Path(f"slide{i}.wav"))
                 for i in range(1, len(texts) + 1)]
        for i, record in enumerate(records, 1):
            meta = stage / f"slide{i}.json"
            meta.write_text(json.dumps(record, indent=2), encoding="utf8")
            files.append((meta, cache / f"slide{i}.json"))
        files.append((stage / ".microgen_tts_provenance.json",
                      Path(".microgen_tts_provenance.json")))
        backups = root / "old_files"
        backups.mkdir()
        touched = []
        try:
            for position, (source, dest) in enumerate(files):
                backup = backups / f"{position}.original"
                existed = dest.exists()
                if existed:
                    if dest.is_symlink() or not dest.is_file():
                        raise RuntimeError("Unsafe existing narration target")
                    shutil.copy2(dest, backup)
                replacement = dest.with_name(dest.name + ".flash_new")
                if replacement.exists():
                    raise RuntimeError("Existing uncommitted Gemini candidate")
                try:
                    shutil.copy2(source, replacement)
                    os.replace(replacement, dest)
                    touched.append((dest, backup if existed else None))
                finally:
                    replacement.unlink(missing_ok=True)
            verify_manifest(Path.cwd(), texts)
        except Exception:
            for dest, backup in reversed(touched):
                if backup is None:
                    dest.unlink(missing_ok=True)
                else:
                    shutil.copy2(backup, dest)
            if not cache_preexisted:
                try:
                    cache.rmdir()
                except OSError:
                    pass
            raise
    from microgen_tts_risk_register import build_risk_register, save_immutable_risk_report
    from microgen_pronunciation_evidence_pipeline import (
        build_post_tts_evidence, save_stage_evidence,
    )
    wav_evidence = check_wavs(Path.cwd(), len(texts))
    risk = build_risk_register(
        [{"slide": i, "tts_text": str(x["tts_text"] or x["narration"])}
         for i, x in enumerate(items, 1)],
        normalize_scientific_speech, wav_evidence["seconds"],
        wav_sha256=wav_evidence["sha256"],
    )
    risk_path = save_immutable_risk_report(Path(".microgen_tts_cache"), risk)
    evidence = build_post_tts_evidence(
        Path.cwd(),
        [{"slide": i, "tts_text": str(x["tts_text"] or x["narration"])}
         for i, x in enumerate(items, 1)],
        normalize_scientific_speech,
    )
    evidence_path = save_stage_evidence(Path.cwd(), evidence)
    print(f"[TTS] Gemini Flash batch verified: {engine}, {actual_voice}.")
    print(f"[QA] Evidence: {evidence_path}; risks: {risk_path}.")
    print("[QA] Independent listening/academic/copyright release checks remain required.")


def main() -> None:
    from microgen_tts_provider_policy import require_formal_provider
    selected_provider = require_formal_provider()
    if selected_provider == "google_cloud":
        _load_runtime_environment()  # historical explicitly selected Cloud only
    else:
        from microgen_flash_tts import _load_gemini_keys_from_microvid
        _load_gemini_keys_from_microvid()
    items = _speech_items()
    if not items:
        raise RuntimeError("No slide narration found.")
    from microgen_pronunciation import audit_slide_items, PronunciationPreflightError
    issues = audit_slide_items(items, normalize_scientific_speech)
    if issues:
        raise PronunciationPreflightError(
            f"Refusing to synthesize: {len(issues)} unreviewed mathematical "
            f"pronunciation issue(s): {issues[:5]}"
        )

    from microgen_tts_lexicon import check_lexicon_slides
    rule_drift = check_lexicon_slides(
        [{"slide": n, "tts_text": str(item["tts_text"] or item["narration"])}
         for n, item in enumerate(items, 1)], normalize_scientific_speech,
    )
    if rule_drift:
        raise PronunciationPreflightError(
            f"Reviewed pronunciation lexicon mismatch: {rule_drift[:5]}"
        )
    if selected_provider == "gemini":
        _run_flash_batch(items)
        return
    from microgen_quality import sha256, check_wavs
    from microgen_tts_provenance import (
        TTSProvenanceError, make_record, verify_record,
        write_manifest, verify_manifest,
    )
    cache = Path(".microgen_tts_cache")
    cache.mkdir(exist_ok=True)
    providers = []
    records = []
    normalized_inputs = []
    for idx, item in enumerate(items, start=1):
        text = item["tts_text"] or item["narration"]
        if not text:
            raise RuntimeError(f"Slide {idx} has no narration/tts_text.")
        spoken = normalize_scientific_speech(text)
        normalized_inputs.append(spoken)
        output = Path(f"slide{idx}.wav")
        meta = cache / f"slide{idx}.json"
        key = hashlib.sha256(json.dumps(
            [spoken, VOICE_NAME, LANGUAGE_CODE,
             SPEAKING_RATE, LOCATION, "microgen-tts-v3-provenance"],
            ensure_ascii=False, sort_keys=True,
        ).encode("utf-8")).hexdigest()
        provider = None
        record = None
        if output.is_file() and meta.is_file():
            try:
                saved = json.loads(meta.read_text(encoding="utf-8"))
                verify_record(
                    saved, output, slide=idx, text=spoken, key=key,
                    voice_name=VOICE_NAME, language_code=LANGUAGE_CODE,
                    speaking_rate=SPEAKING_RATE, location=LOCATION,
                )
                record = saved
                provider = saved["provider"]
            except (OSError, ValueError, KeyError, TTSProvenanceError):
                provider = None
        if provider:
            print(f"[TTS] provenance-verified WAV reused: slide {idx}", flush=True)
        else:
            candidate = cache / f"slide{idx}.candidate.wav"
            candidate.unlink(missing_ok=True)
            provider = synthesize(text, candidate)
            # The provider must match the first slide BEFORE touching
            # any previously recorded production WAV for this slide.
            if providers and provider != providers[0]:
                candidate.unlink(missing_ok=True)
                raise TTSProvenanceError(
                    f"Mixed TTS providers on slide {idx}; existing WAV preserved"
                )
            record = make_record(
                slide=idx, path=candidate, text=spoken, provider=provider, key=key,
                voice_name=VOICE_NAME, language_code=LANGUAGE_CODE,
                speaking_rate=SPEAKING_RATE, location=LOCATION,
            )
            if output.is_file():
                backup = cache / (f"slide{idx}.before-{sha256(output)[:12]}.wav")
                if not backup.exists():
                    import shutil
                    shutil.copy2(output, backup)
            candidate.replace(output)
            tmp = meta.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            tmp.replace(meta)
        providers.append(provider)
        records.append(record)
        if len(set(providers)) != 1:
            raise TTSProvenanceError(
                "Mixed TTS providers found; completion manifest withheld."
            )
        print(f'Audio content checked: "{output}" using {provider}')
    wav_evidence = check_wavs(Path.cwd(), len(items))
    manifest = write_manifest(Path.cwd(), records, normalized_inputs)
    verify_manifest(Path.cwd(), normalized_inputs)
    from microgen_tts_risk_register import build_risk_register, save_immutable_risk_report
    risk = build_risk_register(
        [{"slide": i, "tts_text": str(item["tts_text"] or item["narration"])}
         for i, item in enumerate(items, 1)],
        normalize_scientific_speech, wav_evidence["seconds"],
        wav_sha256=wav_evidence["sha256"],
    )
    report_path = save_immutable_risk_report(cache, risk)
    print(f"[TTS] Source-derived pronunciation risk report: {report_path} "
          f"({risk['risk_count']} risks, {len(risk['risk_review_slides'])} slides).")
    # Automatic offline pronunciation evidence is produced after the normal
    # TTS voice and WAV manifests are verified. This is an advisory QA
    # checkpoint, not an acoustic approval or new Cloud provider invocation.
    from microgen_pronunciation_evidence_pipeline import (
        build_post_tts_evidence, save_stage_evidence,
    )
    pronunciation_evidence = build_post_tts_evidence(
        Path.cwd(),
        [{"slide": i, "tts_text": str(item["tts_text"] or item["narration"])}
         for i, item in enumerate(items, 1)],
        normalize_scientific_speech,
    )
    evidence_path = save_stage_evidence(Path.cwd(), pronunciation_evidence)
    print(f"[TTS] Offline source/WAV pronunciation evidence: {evidence_path} "
          f"(acoustic approval NOT implied).")
    print(f"Success: technically verified {len(items)} audio files with voice-bound {manifest}.")
    print("[QA] Acoustic transcript screening and independent listening remain REQUIRED before publication.")


if __name__ == "__main__":
    main()
