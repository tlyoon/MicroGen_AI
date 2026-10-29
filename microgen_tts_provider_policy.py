"""Authoritative owner TTS policy: Cloud is permitted for troubleshooting.

Formal TTS intentionally has NO default provider. Historical provenance
remains valid; this policy governs only NEW syntheses. Do not treat stored
credentials, a provider's free quota, or CLI --authorize-provider-usage as a
formal TTS choice.
"""
from __future__ import annotations
import os
from pathlib import Path

FORMAL_PROVIDER_ENV = "MICROGEN_FORMAL_TTS_PROVIDER"
NO_FORMAL_PROVIDER = "unconfigured"
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
    value = str(configured or NO_FORMAL_PROVIDER).strip().lower()
    if value in ("", NO_FORMAL_PROVIDER, "none", "off", "disabled"):
        return NO_FORMAL_PROVIDER
    if value == EXPLICIT_CLOUD_PROVIDER:
        return value
    raise TTSProviderPolicyError(
        "Unsupported formal TTS provider; no local voice has been certified. "
        "Do not silently switch from the established narration voice."
    )


def require_formal_provider(environ=None) -> str:
    selected = selected_formal_provider(environ)
    if selected == NO_FORMAL_PROVIDER:
        raise TTSProviderPolicyError(
            "Formal lecture TTS has no default provider under the revised "
            "owner contract. Google Cloud may be used for diagnostics only "
            "without choosing it for formal output. To explicitly opt into "
            "Google Cloud for a formal run, separately configure "
            "MICROGEN_FORMAL_TTS_PROVIDER=google_cloud subject to the "
            "applicable owner and cost authorizations."
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
