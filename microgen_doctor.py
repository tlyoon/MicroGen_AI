"""MicroGen installation doctor and bounded read-only lecture tree audit.

Run: python microgen_doctor.py --source-root "G:\\My Drive\\Textbook"
Does not contact Gemini, expose API keys, modify sources, or start generation.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def inspect_environment(
    source_root: Path | None = None, *,
    python_exe: str | None = None,
) -> dict:
    python_exe = python_exe or sys.executable
    deps = ("fitz", "PIL", "imageio_ffmpeg", "PyPDF2",
            "google.genai", "google.cloud.texttospeech", "dotenv")
    modules: dict[str, bool] = {}
    for name in deps:
        try:
            modules[name] = importlib.util.find_spec(name) is not None
        except (ImportError, AttributeError, ModuleNotFoundError):
            modules[name] = False
    # find_spec alone can return True when the installed SDK crashes during
    # import (observed on Yoga6 with damaged Miniforge package metadata).
    try:
        deep_import=subprocess.run(
            [python_exe,"-c","import google.genai, google.cloud.texttospeech, pydantic"],
            stdin=subprocess.DEVNULL,capture_output=True,text=True,
            errors="replace",timeout=30,
        )
        sdk_importable=deep_import.returncode==0
    except (OSError,subprocess.TimeoutExpired):
        sdk_importable=False
    latex = bool(shutil.which("pdflatex"))
    ffmpeg = bool(shutil.which("ffmpeg"))
    if not ffmpeg and modules.get("imageio_ffmpeg"):
        # Presence only, never launch a potentially long FFmpeg process here.
        ffmpeg = True
    cfg = Path(os.environ.get("MICROVID_CONFIG_DIR") or
               (Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Microvid"))
    env_file = cfg / ".env"
    # Secret *presence* only, never the values or file content.
    possible_credentials = (
        bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")),
        (cfg / "google_cloud_credentials.json").is_file(),
    )
    gemini_keys = any(
        bool(os.environ.get(name))
        for name in ("GEMINI_API_KEY", "GEMINI_API_KEY_1", "GEMINI_API_KEY_2")
    )
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            name, value = line.strip().split("=", 1)
            if name.strip() in {"GEMINI_API_KEY", "GEMINI_API_KEY_1", "GEMINI_API_KEY_2"}:
                if value.strip():
                    gemini_keys = True
    source: dict[str, object] = {"specified": bool(source_root)}
    if source_root is not None:
        path = Path(source_root).expanduser()
        source["exists"] = path.is_dir()
        source["path"] = str(path)
        source["can_read"] = path.is_dir() and os.access(path, os.R_OK)
        source["can_write"] = path.is_dir() and os.access(path, os.W_OK)
    checks = {"python_version_3_11_plus": sys.version_info >= (3, 11),
              "gemini_tts_sdks_importable": sdk_importable,
              "pdflatex_available": latex, "ffmpeg_available": ffmpeg,
              "gemini_key_configured": gemini_keys,
              "cloud_tts_credentials_configured": any(possible_credentials),
              **{f"python:{k}": v for k, v in modules.items()}}
    if source_root is not None:
        checks["source_directory_accessible"] = bool(source.get("can_read"))
        checks["source_directory_writable"] = bool(source.get("can_write"))
    remediation = (None if sdk_importable else
                   "Installed Google packages could not be imported. In this "
                   "Python interpreter run: python -c 'import google.genai, "
                   "google.cloud.texttospeech, pydantic'; repair broken package "
                   "metadata or use a fresh isolated Python environment.")
    return {"host": os.environ.get("COMPUTERNAME") or "unknown",
            "python_executable": python_exe, "checks": checks,
            "sdk_import_remediation": remediation,
            "source": source, "ok": all(checks.values()),
            "note": "Configuration preflight only; does not confirm billing, model access, or source integrity."}


def audit_tree(root: Path) -> dict:
    """Bounded two-level discovery; avoids recursive Drive scans that stall."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Source root unavailable: {root}")
    rows = []
    for chapter in root.iterdir():
        if not chapter.is_dir() or not chapter.name.isdigit():
            continue
        for sub in chapter.iterdir():
            if not sub.is_dir() or not sub.name.startswith(chapter.name + "."):
                continue
            if not (sub / "source.pdf").is_file():
                continue
            row = {"subchapter": sub.name}
            for name in ("source.pdf", "slides.pdf", "script.txt", "slides.mp4"):
                file = sub / name
                row[name] = file.is_file() and file.stat().st_size > 0
            try:
                from microgen_quality import published_manifest_valid
                row["verified_receipt"] = published_manifest_valid(sub)
            except (ImportError, OSError):
                row["verified_receipt"] = False
            rows.append(row)
    rows.sort(key=lambda r: tuple(
        int(v) if v.isdigit() else v for v in r["subchapter"].split(".")))
    return {
        "source_count": len(rows),
        "video_file_count": sum(r["slides.mp4"] for r in rows),
        "verified_receipt_count": sum(r["verified_receipt"] for r in rows),
        "incomplete": [r for r in rows if not (
            r["slides.pdf"] and r["script.txt"] and r["slides.mp4"]
        )],
        "warning": "Existing MP4 without a verified manifest is unverified, not failed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight and audit MicroGen without generating content")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--audit", action="store_true", help="Read-only two-level lecture inventory")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    info = inspect_environment(args.source_root)
    if args.audit:
        if args.source_root is None:
            parser.error("--audit requires --source-root")
        info["audit"] = audit_tree(args.source_root)
    print(json.dumps(info, indent=2, ensure_ascii=False))
    return 0 if info["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
