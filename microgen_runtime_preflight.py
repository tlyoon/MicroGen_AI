"""Bounded, offline runtime capability checks for the original API MicroGen.

These checks never contact Gemini, install software, expose credentials, or
write to the source tree.  Only the current Python process environment may
be changed when a usable local FFmpeg/FFprobe pair is discovered.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SDK_PROBE_CODE = """\
import importlib.metadata as metadata
from google.genai import types
import google.cloud.texttospeech, pydantic
required=('HttpOptions','HttpRetryOptions','ThinkingConfig','GenerateContentConfig','Part')
missing=[name for name in required if not hasattr(types,name)]
if missing:
    raise SystemExit('Incompatible google-genai SDK: missing '+','.join(missing)+
        '. Upgrade only the selected Python environment: python -m pip install "google-genai>=2.33,<3"')
try:
    types.HttpOptions(timeout=120000, retry_options=types.HttpRetryOptions(attempts=1))
except Exception as exc:
    raise SystemExit('Incompatible google-genai SDK HTTP retry API: '+type(exc).__name__+
        '. Upgrade only the selected Python environment to google-genai>=2.33,<3')
print('google-genai='+metadata.version('google-genai'))
print('ThinkingConfig='+','.join(getattr(types.ThinkingConfig,'model_fields',{}).keys()))
"""


def _config_root() -> Path:
    configured = os.environ.get("MICROVID_CONFIG_DIR")
    return Path(configured).expanduser() if configured else (
        Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Microvid")


def _media_folders() -> list[Path]:
    root = _config_root()
    candidates = []
    override = os.environ.get("MICROGEN_MEDIA_BIN", "").strip()
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(root / "media_tools" / "bin")
    candidates.append(root / "media_tools")
    # Read existing isolated release installs without relying on a dated name.
    # Bounded to the last ten local candidates; never scan the source drive.
    try:
        historical = sorted(root.glob("microgen_release_media_tools_*/bin"),
                            reverse=True)[:10]
    except OSError:
        historical = []
    candidates += historical
    seen = set()
    unique = []
    for folder in candidates:
        key = str(folder).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(folder)
    return unique


def find_ffprobe() -> str | None:
    configured = os.environ.get("MICROGEN_FFPROBE", "").strip()
    if configured and Path(configured).is_file():
        return configured
    path = shutil.which("ffprobe")
    if path:
        return path
    for directory in _media_folders():
        for name in ("ffprobe.exe", "ffprobe"):
            candidate = directory / name
            if candidate.is_file():
                return str(candidate)
    configured_ffmpeg = os.environ.get("MICROVID_FFMPEG", "").strip()
    if configured_ffmpeg:
        folder = Path(configured_ffmpeg).parent
        for name in ("ffprobe.exe", "ffprobe"):
            candidate = folder / name
            if candidate.is_file():
                return str(candidate)
    return None


def _ffmpeg_candidates(probe: str | None) -> list[str]:
    result = []
    configured = os.environ.get("MICROVID_FFMPEG", "").strip()
    if configured:
        result.append(configured)
    if probe:
        for name in ("ffmpeg.exe", "ffmpeg"):
            path = Path(probe).parent / name
            if path.is_file():
                result.append(str(path))
    try:
        import imageio_ffmpeg
        result.append(imageio_ffmpeg.get_ffmpeg_exe())
    except (ImportError, RuntimeError, OSError):
        pass
    system = shutil.which("ffmpeg")
    if system:
        result.append(system)
    return list(dict.fromkeys(result))


def _validated(args: list[str], needle: str, timeout: float = 8.0) -> bool:
    try:
        outcome = subprocess.run(args, capture_output=True, text=True,
                                 errors="replace", stdin=subprocess.DEVNULL,
                                 timeout=timeout)
        return outcome.returncode == 0 and needle in (
            (outcome.stdout or "") + (outcome.stderr or ""))
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_h264_ffmpeg(probe: str | None = None) -> str | None:
    for candidate in _ffmpeg_candidates(probe):
        if _validated([candidate, "-hide_banner", "-encoders"], "libx264"):
            return candidate
    return None


def inspect_media_tools() -> dict[str, object]:
    """Observe media binaries without mutating PATH or generating content."""
    probe = find_ffprobe()
    probe_ok = bool(probe) and _validated([probe, "-version"], "ffprobe")
    ffmpeg = find_h264_ffmpeg(probe if probe_ok else None)
    return {
        "ffprobe_available": bool(probe_ok),
        "ffmpeg_h264_available": bool(ffmpeg),
        "ffprobe": probe if probe_ok else None,
        "ffmpeg": ffmpeg,
    }


def prepare_media_tools() -> dict[str, object]:
    """Self-recover usable installed binaries in this process only, or fail early.

    No network install or global PATH mutation. All stage subprocesses inherit
    these temporary environment values.
    """
    result = inspect_media_tools()
    if not (result["ffprobe_available"] and result["ffmpeg_h264_available"]):
        raise RuntimeError(
            "Media preflight failed before paid generation: require ffprobe "
            "and an FFmpeg with libx264. Install both in "
            "%LOCALAPPDATA%\\Microvid\\media_tools\\bin or set "
            "MICROGEN_MEDIA_BIN / MICROGEN_FFPROBE and MICROVID_FFMPEG "
            "to verified local executables. No global install was attempted.")
    probe_path = Path(str(result["ffprobe"]))
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if str(probe_path.parent).casefold() not in {x.casefold() for x in path_parts}:
        os.environ["PATH"] = str(probe_path.parent) + os.pathsep + os.environ.get("PATH", "")
    os.environ["MICROVID_FFMPEG"] = str(result["ffmpeg"])
    return result
