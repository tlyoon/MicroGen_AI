"""Reuse existing local Docling installations without reinstalling a package.

Resolution order:
  --docling-py explicit path
  MICROGEN_DOCLING_PY machine-specific environment setting
  known already-installed Conda Docling environments
  current interpreter (preflight will verify availability)

Discovery is bounded and read-only; it does not run conda or pip or search
Google Drive recursively.  A specified interpreter is never silently swapped.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def docling_candidates(home: Path | None = None) -> list[Path]:
    home=Path(home or Path.home())
    names=("docling_3","docling","docling_win")
    bases=(home/"miniconda3"/"envs",home/"miniforge3"/"envs",
           home/"anaconda3"/"envs",home/"AppData"/"Local"/"miniconda3"/"envs",
           home/"AppData"/"Local"/"miniforge3"/"envs")
    result=[]
    for base in bases:
        for name in names:
            candidate=base/name/("python.exe" if os.name=="nt" else "bin/python")
            if candidate.is_file():
                result.append(candidate)
    return result


def supports_docling(executable: str | Path, *, timeout_seconds: float = 90) -> bool:
    executable=str(executable)
    if not Path(executable).is_file():
        return False
    try:
        result=subprocess.run(
            [executable,"-c","from docling.document_converter import DocumentConverter; import pdf2image,PIL"],
            capture_output=True, text=True, errors="replace",
            stdin=subprocess.DEVNULL, timeout=timeout_seconds,
        )
        return result.returncode==0
    except (OSError, subprocess.TimeoutExpired):
        return False


def persisted_windows_docling_python() -> str | None:
    """Read only the Windows user's existing Docling setting.

    Long-lived Remote Desktop/automation agents may inherit an old process
    environment even after the user updated HKCU\\Environment.
    """
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "MICROGEN_DOCLING_PY")
    except (ImportError, OSError):
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return os.path.expandvars(value.strip())


def resolve_docling_python(explicit: str | None = None, *,
                           main_python: str | None = None,
                           env: dict | None = None,
                           home: Path | None = None) -> str:
    main_python=main_python or sys.executable
    # If an explicit env mapping was passed (e.g., in tests), never consult
    # the ambient registry: caller-supplied configuration must be deterministic.
    caller_supplied_env=env is not None
    env=env if caller_supplied_env else os.environ
    configured=(explicit or env.get("MICROGEN_DOCLING_PY")
                or (None if caller_supplied_env else persisted_windows_docling_python()))
    if configured:
        # No fallback when explicitly set: misconfiguration should be reported,
        # not hidden behind an unexpected interpreter choice.
        return str(Path(configured).expanduser())
    if supports_docling(main_python):
        return main_python
    for path in docling_candidates(home):
        if supports_docling(path):
            return str(path)
    return main_python
