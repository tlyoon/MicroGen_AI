"""Authoritative provider policy for API-based MicroGen_AI (NOT MicroGen_AI_Web).

Owner-requested PR270 default is Gemini 3.8 Flash-Lite TTS, voice Kore,
matching the separate Selenium project's TTS engine. Google Cloud is an
explicit formal selector or opt-in LAST fallback, never the default. Historical
Chirp-HD-F provenance and limited Cloud diagnostic permissions remain valid.
"""
from __future__ import annotations
import os
from pathlib import Path

FORMAL_PROVIDER_ENV = "MICROGEN_FORMAL_TTS_PROVIDER"
NO_FORMAL_PROVIDER = "unconfigured"
DEFAULT_GEMINI_PROVIDER = "gemini"
EXPLICIT_CLOUD_PROVIDER = "google_cloud"


class TTSProviderPolicyError(RuntimeError):
    pass


def selected_formal_provider(environ=None) -> str:
    env = os.environ if environ is None else environ
    configured = env.get(FORMAL_PROVIDER_ENV)
    if configured is None:
        # Read ONLY the provider selector from the established .env, without
        # loading service-account credentials or mutating process environment.
        from dotenv import dotenv_values
        base = env.get("MICROVID_CONFIG_DIR")
        if base:
            path = Path(base).expanduser() / ".env"
        elif env.get("LOCALAPPDATA"):
            path = Path(env["LOCALAPPDATA"]) / "Microvid" / ".env"
        else:
            path = Path.home() / "AppData" / "Local" / "Microvid" / ".env"
        configured = dotenv_values(path).get(FORMAL_PROVIDER_ENV) if path.is_file() else None
    value = str(DEFAULT_GEMINI_PROVIDER if configured is None else configured).strip().lower()
    if value in ("", NO_FORMAL_PROVIDER, "none", "off", "disabled"):
        return NO_FORMAL_PROVIDER
    if value in (DEFAULT_GEMINI_PROVIDER, EXPLICIT_CLOUD_PROVIDER):
        return value
    raise TTSProviderPolicyError(
        "Unsupported formal TTS provider; no local voice has been certified. "
        "Do not silently switch from the established narration voice."
    )


def require_formal_provider(environ=None) -> str:
    selected = selected_formal_provider(environ)
    if selected == NO_FORMAL_PROVIDER:
        raise TTSProviderPolicyError(
            "Formal lecture TTS was explicitly disabled in the configuration. "
            "The ordinary default is gemini-3.8-flash-lite-tts with Kore; "
            "an explicit unconfigured/off selector still blocks production. "
            "Google Cloud is never the implicit primary provider."
        )
    return selected


def diagnostic_request_allowed(*, character_count: int, confirmation: bool,
                               output_is_new: bool, maximum=500) -> bool:
    if not confirmation:
        raise TTSProviderPolicyError(
            "Cloud diagnostic request needs explicit chargeable-test confirmation"
        )
    if not output_is_new:
        raise TTSProviderPolicyError(
            "Diagnostic output must be a new isolated directory"
        )
    if not 1 <= character_count <= maximum:
        raise TTSProviderPolicyError(
            f"Cloud diagnostic speech must be 1-{maximum} characters per call"
        )
    return True
