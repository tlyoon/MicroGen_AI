#!/usr/bin/env python3
"""Resumable multi-subchapter production runner for MicroGen_AI.

Each subchapter has a persistent checkpoint. A failed narration/TTS/video stage
therefore resumes at that stage instead of repeating Docling, figure mapping,
and slide generation. Gemini billing circuit events pause Gemini stages rather
than burning retry attempts across every worker.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from gemini_lane import circuit_is_open
import microgen_quality as quality
from microgen_drive_assignments import DriveAssignedOwner, configured_gemini_lane
from microgen_docling_environment import resolve_docling_python

STAGES = [
    "figure_extraction",
    "figure_mapping",
    "figure_merge",
    "slides",
    "narration",
    "tts",
    "slide_slicing",
    "video",
    "published",
]
GEMINI_STAGES = {"figure_mapping", "slides", "narration"}


def inspect_local_checkout(repo: Path, *, expected_commit: str | None = None) -> str:
    """Fail closed before multi-PC paid generation if Git code is unsafe.

    The coordinator must pin the same full commit on all PCs. Synced cloud
    folders can expose mixed Git objects and incomplete tracked worktrees.
    """
    repo = Path(repo).resolve()
    synced = {"my drive", "google drive", "onedrive", "dropbox"}
    if {part.casefold() for part in repo.parts} & synced:
        raise RuntimeError(
            "Multi-PC code must execute from a private local disk Git clone, "
            "not a synchronized Drive directory"
        )

    def git(*arguments: str) -> str:
        try:
            process = subprocess.run(
                ["git", "-C", str(repo), *arguments],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                errors="replace", timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Cannot verify local Git checkout: {exc}") from exc
        if process.returncode:
            raise RuntimeError(
                f"Local Git checkout verification failed ({' '.join(arguments)}): "
                + (process.stderr or process.stdout).strip()[:350]
            )
        return process.stdout.strip()

    root = Path(git("rev-parse", "--show-toplevel")).resolve()
    if root != repo:
        raise RuntimeError(f"Expected repository root {repo}, found {root}")
    head = git("rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", head):
        raise RuntimeError("Git HEAD is not a complete 40-character commit SHA")
    if expected_commit not in (None, "", "unknown"):
        if not re.fullmatch(r"[0-9a-fA-F]{40}", expected_commit):
            raise RuntimeError("--commit must be the full 40-character Git SHA")
        if expected_commit.lower() != head.lower():
            raise RuntimeError("The checked-out commit does not match --commit")
    if git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise RuntimeError(
            "Multi-PC source checkout is dirty or incompletely synchronized; "
            "preserve local edits and use a fresh local Git clone"
        )
    return head


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def split_targets(value: str) -> list[str]:
    items = []
    for raw in value.split(","):
        item = raw.strip()
        if item and item not in items:
            items.append(item)
    return items


def source_for(root: Path, subchapter: str) -> Path:
    chapter = subchapter.split(".", 1)[0]
    return root / chapter / subchapter / "source.pdf"


def destination_for(root: Path, subchapter: str) -> Path:
    chapter = subchapter.split(".", 1)[0]
    return root / chapter / subchapter


def wait_for_path(path: Path, timeout: float, *, label: str) -> None:
    deadline = time.time() + timeout
    last = 0.0
    while not path.exists():
        if time.time() >= deadline:
            raise FileNotFoundError(f"{label} unavailable after {timeout:.0f}s: {path}")
        if time.time() - last >= 30:
            print(f"[batch] waiting for {label}: {path}", flush=True)
            last = time.time()
        time.sleep(5)


def source_signature(path: Path) -> dict[str, int]:
    st = path.stat()
    return {"size": int(st.st_size), "mtime_ns": int(st.st_mtime_ns)}


def load_checkpoint(path: Path) -> dict:
    if not path.is_file():
        return {"completed": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"completed": {}}
        data.setdefault("completed", {})
        return data
    except (OSError, json.JSONDecodeError):
        return {"completed": {}}


def save_checkpoint(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def copy_repo_into_stage(repo: Path, stage: Path) -> None:
    """Refresh code/assets without deleting generated outputs."""
    blocked_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", "tests"}
    for item in repo.iterdir():
        if item.name in blocked_dirs:
            continue
        dest = stage / item.name
        if item.is_file():
            shutil.copy2(item, dest)
        elif item.is_dir():
            if dest.exists():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copytree(item, dest)


def prepare_stage(
    repo: Path,
    source_root: Path,
    work_root: Path,
    subchapter: str,
    source_wait: float,
    commit: str,
) -> tuple[Path, dict, Path]:
    src = source_for(source_root, subchapter)
    wait_for_path(src, source_wait, label="source.pdf")
    sig = source_signature(src)
    stage = work_root / subchapter
    checkpoint_path = stage / ".microgen_checkpoint.json"

    if stage.exists():
        cp = load_checkpoint(checkpoint_path)
        old_sig = cp.get("source_signature")
        if old_sig and old_sig != sig:
            stale = stage.with_name(f"{stage.name}.stale.{int(time.time())}")
            stage.rename(stale)
            print(f"[{subchapter}] source changed; previous stage moved to {stale}", flush=True)
    stage.mkdir(parents=True, exist_ok=True)
    copy_repo_into_stage(repo, stage)
    shutil.copy2(src, stage / "source.pdf")
    # An explicitly reviewed topic boundary manifest may travel with source.pdf.
    # The model is never allowed to silently approve its own scene proposals.
    reviewed = src.parent / "lesson_scenes.json"
    if reviewed.is_file():
        shutil.copy2(reviewed, stage / "lesson_scenes.json")

    cp = load_checkpoint(checkpoint_path)
    cp.update(
        {
            "subchapter": subchapter,
            "source_signature": sig,
            "package_commit": commit,
            "updated_utc": utc_now(),
        }
    )
    cp.setdefault("completed", {})
    save_checkpoint(checkpoint_path, cp)
    return stage, cp, checkpoint_path


def numbered_files(stage: Path, suffix: str) -> list[Path]:
    rx = re.compile(rf"^slide(\d+)\.{re.escape(suffix)}$", re.I)
    files = [p for p in stage.iterdir() if p.is_file() and rx.match(p.name)]
    return sorted(files, key=lambda p: int(rx.match(p.name).group(1)))


def slide_count(stage: Path) -> int | None:
    pdf = stage / "slides.pdf"
    if not pdf.is_file() or pdf.stat().st_size <= 0:
        return None
    try:
        from PyPDF2 import PdfReader
        return len(PdfReader(str(pdf)).pages)
    except Exception:
        try:
            import fitz
            doc = fitz.open(str(pdf))
            count = doc.page_count
            doc.close()
            return count
        except Exception:
            return None


def nonempty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def source_page_extraction_valid(stage: Path) -> bool:
    """Verify all source pages, not merely a partially created pages/ folder."""
    source = stage / "source.pdf"
    pages = stage / "pages"
    if (source.is_symlink() or not source.is_file() or
            pages.is_symlink() or not pages.is_dir()):
        return False
    try:
        import hashlib
        import pymupdf
        marker = stage / "figure_extraction_receipt.json"
        if marker.is_symlink() or not marker.is_file():
            return False
        evidence = json.loads(marker.read_text(encoding="utf8"))
        with pymupdf.open(source) as pdf:
            count = len(pdf)
        if (not 1 <= count <= 1000 or
                evidence.get("status") != "OFFLINE_SOURCE_FIGURE_EXTRACTION_COMPLETE" or
                evidence.get("page_count") != count or
                evidence.get("publication_allowed") is not False or
                evidence.get("gemini_invoked") is not False or
                evidence.get("tts_invoked") is not False or
                len(evidence.get("pages", [])) != count):
            return False

        def sha(file):
            return hashlib.sha256(file.read_bytes()).hexdigest()

        if sha(source) != evidence.get("source_sha256"):
            return False
        for index, record in enumerate(evidence["pages"], 1):
            folder = pages / f"page_{index}"
            image = folder / f"page_{index}.png"
            single = folder / f"page_{index}.pdf"
            if (record.get("page") != index or folder.is_symlink() or
                    not folder.is_dir() or
                    any(f.is_symlink() or not f.is_file() or f.stat().st_size == 0
                        for f in (image, single)) or
                    record.get("pdf_sha256") != sha(single) or
                    record.get("png_sha256") != sha(image)):
                return False
            with pymupdf.open(single) as one_page:
                if len(one_page) != 1:
                    return False
            found = sorted(folder.glob("fig_*.png"))
            listed = record.get("figures")
            if not isinstance(listed, list) or len(found) != len(listed):
                return False
            if any(f.is_symlink() or not f.is_file() or
                   row.get("name") != f.name or row.get("sha256") != sha(f)
                   for f, row in zip(found, listed)):
                return False
        return True
    except (OSError, ValueError, RuntimeError, ImportError, TypeError, KeyError,
            json.JSONDecodeError):
        return False


def stage_valid(stage: Path, name: str, dest: Path) -> bool:
    if name == "figure_extraction":
        return source_page_extraction_valid(stage)
    if name in {"figure_mapping", "figure_merge"}:
        # Even zero-figure pages receive a final structured provenance receipt.
        try:
            from microgen_figure_composition import validate_figure_receipt
            validate_figure_receipt(stage)
            return True
        except (OSError, ValueError, RuntimeError):
            return False
    if name == "published":
        return quality.published_manifest_valid(dest)
    if name in {"slides", "narration", "tts", "slide_slicing", "video"}:
        try:
            if name == "slides":
                quality.check_slide_pdf(stage / "slides.pdf", require_footer=True)
                quality.check_graphics(stage / "slides.tex")
                return True
            count = quality.check_slide_pdf(stage / "slides.pdf", require_footer=True)["pages"]
            if name == "narration":
                quality.check_narration(stage / "script.txt", stage / "script_tts.json", count)
            elif name == "tts":
                quality.check_wavs(stage, count)
            elif name == "slide_slicing":
                quality.numbered_files(stage, "pdf", count)
            elif name == "video":
                wav = quality.check_wavs(stage, count)
                quality.check_video(stage / "slides.mp4", expected_seconds=wav["total_seconds"])
                if os.environ.get("MICROGEN_MULTIPART", "0") == "1":
                    quality.check_multipart_receipt(stage)
            return True
        except (quality.QualityError, OSError, ValueError):
            return False
    return False


def invalidate_from(cp: dict, stage_name: str) -> None:
    completed = cp.setdefault("completed", {})
    idx = STAGES.index(stage_name)
    for name in STAGES[idx:]:
        completed.pop(name, None)
        cp.setdefault("dependency_fingerprints", {}).pop(name, None)


def mark_complete(cp: dict, checkpoint_path: Path, stage_name: str, stage: Path) -> None:
    cp.setdefault("completed", {})[stage_name] = utc_now()
    cp.setdefault("dependency_fingerprints", {})[stage_name] = quality.dependency_fingerprint(stage, stage_name)
    cp["last_error"] = None
    cp["updated_utc"] = utc_now()
    save_checkpoint(checkpoint_path, cp)


def wait_for_gemini_circuit(lease=None) -> None:
    """Pause while the shared billing/capacity circuit is open.

    A failed/lost distributed lease must interrupt even a long capacity wait.
    """
    last = 0.0
    while True:
        if lease is not None:
            lease.assert_held()
        opened, data = circuit_is_open()
        if not opened:
            return
        retry_after = float((data or {}).get("retry_after_epoch", 0) or 0)
        wait = max(1.0, retry_after - time.time())
        if time.time() - last >= 60:
            print(
                f"[batch] Gemini circuit open ({(data or {}).get('type','unknown')}); "
                f"pausing this stage, next probe in about {wait:.0f}s",
                flush=True,
            )
            last = time.time()
        time.sleep(min(5.0 if lease is not None else 60.0, wait))


def _assign_windows_kill_job(proc: subprocess.Popen):
    """Attach a Windows kill-on-close Job Object to the stage process.

    Unlike taskkill /T, this is tied to the actual live process handle and
    reliably terminates all child processes that remain in the job.
    Fail closed if assigning the job is forbidden by host policy.
    """
    import ctypes
    from ctypes import wintypes as w

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", w.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", w.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", w.DWORD),
            ("SchedulingClass", w.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimits),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.CreateJobObjectW.argtypes = (ctypes.c_void_p, w.LPCWSTR)
    dll.CreateJobObjectW.restype = w.HANDLE
    dll.SetInformationJobObject.argtypes = (w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD)
    dll.SetInformationJobObject.restype = w.BOOL
    dll.AssignProcessToJobObject.argtypes = (w.HANDLE, w.HANDLE)
    dll.AssignProcessToJobObject.restype = w.BOOL
    dll.CloseHandle.argtypes = (w.HANDLE,)
    dll.CloseHandle.restype = w.BOOL
    handle = dll.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not dll.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not dll.AssignProcessToJobObject(handle, proc._handle):
            raise ctypes.WinError(ctypes.get_last_error())
        return handle
    except BaseException:
        dll.CloseHandle(handle)
        raise


def _resume_windows_process(proc: subprocess.Popen) -> None:
    """Resume a suspended stage only after assigning its Windows Job Object.

    Without CREATE_SUSPENDED, the Python driver can spawn children *before*
    job assignment, letting those early descendants escape job termination.
    """
    import ctypes
    from ctypes import wintypes as w

    class ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", w.DWORD),
            ("cntUsage", w.DWORD),
            ("th32ThreadID", w.DWORD),
            ("th32OwnerProcessID", w.DWORD),
            ("tpBasePri", w.LONG),
            ("tpDeltaPri", w.LONG),
            ("dwFlags", w.DWORD),
        ]

    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.CreateToolhelp32Snapshot.argtypes = (w.DWORD, w.DWORD)
    dll.CreateToolhelp32Snapshot.restype = w.HANDLE
    dll.Thread32First.argtypes = (w.HANDLE, ctypes.POINTER(ThreadEntry))
    dll.Thread32First.restype = w.BOOL
    dll.Thread32Next.argtypes = (w.HANDLE, ctypes.POINTER(ThreadEntry))
    dll.Thread32Next.restype = w.BOOL
    dll.OpenThread.argtypes = (w.DWORD, w.BOOL, w.DWORD)
    dll.OpenThread.restype = w.HANDLE
    dll.ResumeThread.argtypes = (w.HANDLE,)
    dll.ResumeThread.restype = w.DWORD
    dll.CloseHandle.argtypes = (w.HANDLE,)
    dll.CloseHandle.restype = w.BOOL

    snap = dll.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD
    if int(snap) == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    resumed = 0
    try:
        entry = ThreadEntry()
        entry.dwSize = ctypes.sizeof(entry)
        ok = dll.Thread32First(snap, ctypes.byref(entry))
        while ok:
            if entry.th32OwnerProcessID == proc.pid:
                thread = dll.OpenThread(0x0002, False, entry.th32ThreadID)  # THREAD_SUSPEND_RESUME
                if not thread:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    previous = dll.ResumeThread(thread)
                    if previous == 0xFFFFFFFF:
                        raise ctypes.WinError(ctypes.get_last_error())
                    resumed += 1
                finally:
                    dll.CloseHandle(thread)
            ok = dll.Thread32Next(snap, ctypes.byref(entry))
    finally:
        dll.CloseHandle(snap)
    if resumed < 1:
        raise RuntimeError("Cannot resume suspended leased worker; no threads found")


def _close_windows_kill_job(handle) -> None:
    import ctypes
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.CloseHandle.argtypes = (ctypes.c_void_p,)
    dll.CloseHandle.restype = ctypes.c_int
    if not dll.CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _terminate_stage_tree(proc: subprocess.Popen) -> None:
    """Stop child tools as well as the stage driver after loss of ownership.

    Merely killing the Python driver can leave FFmpeg, LaTeX, and other
    descendants writing into scratch. This is only used for a leased worker.
    """
    if proc.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _run_leased_stage(command: list[str], *, cwd: Path, log, lease,
                      timeout_seconds: float) -> int:
    """Fence live work while the distributed lease is active.

    Check the strong remote ownership token periodically and stop the whole
    subprocess tree when it is lost, rather than waiting until stage exit.
    """
    lease.assert_held()
    proc = None
    windows_job = None
    try:
        if os.name == "nt":
            proc = subprocess.Popen(
                command, cwd=str(cwd), stdout=log, stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004,
            )
            # Start suspended, attach the process tree to a kill-on-close job,
            # then resume. No child can escape before the job exists.
            windows_job = _assign_windows_kill_job(proc)
            _resume_windows_process(proc)
        else:
            proc = subprocess.Popen(
                command, cwd=str(cwd), stdout=log, stderr=subprocess.STDOUT,
                text=True, start_new_session=True,
            )
        deadline = time.monotonic() + timeout_seconds
        while True:
            lease.assert_held()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout_seconds)
            try:
                result = proc.wait(timeout=min(5.0, remaining))
                lease.assert_held()
                return result
            except subprocess.TimeoutExpired:
                continue
    except BaseException:
        if windows_job is not None:
            _close_windows_kill_job(windows_job)
            windows_job = None
        if proc is not None:
            _terminate_stage_tree(proc)
        raise
    finally:
        # Even successful drivers must not leave detached FFmpeg/LaTeX
        # descendants behind after their main process has exited.
        if windows_job is not None:
            _close_windows_kill_job(windows_job)


def run_subprocess(
    python_exe: str,
    script: str,
    stage: Path,
    log_path: Path,
    label: str,
    *,
    gemini_stage: bool,
    retries: int,
    lease=None,
) -> None:
    attempt = 0
    while True:
        if lease is not None:
            lease.assert_held()
        if gemini_stage:
            wait_for_gemini_circuit(lease)
        with log_path.open("a", encoding="utf-8", errors="replace") as log:
            log.write(f"\n===== {label} :: {script} :: attempt {attempt + 1} =====\n")
            log.flush()
            stage_timeout = float(os.environ.get("MICROGEN_STAGE_TIMEOUT_SECONDS", "7200"))
            if lease is None:
                proc = subprocess.run(
                    [python_exe, script],
                    cwd=str(stage), stdout=log, stderr=subprocess.STDOUT,
                    text=True, timeout=stage_timeout,
                )
                returncode = proc.returncode
            else:
                returncode = _run_leased_stage(
                    [python_exe, script], cwd=stage, log=log, lease=lease,
                    timeout_seconds=stage_timeout,
                )
            log.write(f"\n[{label}] exit={returncode}\n")
        if returncode == 0:
            return

        # If the request tripped the shared circuit, this is an external pause,
        # not a stage failure and must not consume the retry count.
        if gemini_stage:
            opened, _ = circuit_is_open()
            if opened:
                print(f"[{stage.name}] {label}: Gemini circuit opened; pausing", flush=True)
                wait_for_gemini_circuit(lease)
                continue

        if attempt >= retries:
            raise RuntimeError(f"{label} failed after {attempt + 1} attempt(s)")
        attempt += 1
        delay = min(60.0, 5.0 * (2 ** (attempt - 1)))
        print(
            f"[{stage.name}] {label} failed; retrying same stage in {delay:.0f}s "
            f"({attempt}/{retries})",
            flush=True,
        )
        if lease is not None:
            lease.assert_held()
        time.sleep(delay)
        if lease is not None:
            lease.assert_held()


def atomic_publish_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".microgen.tmp")
    shutil.copy2(src, tmp)
    tmp.replace(dest)


def publish(stage: Path, dest: Path, *, lease=None) -> None:
    """Publish only a verified bundle, keeping backups of earlier assets."""
    info = quality.manifest_for(stage, require_footer=True)
    quality.publish_bundle(stage, dest, manifest=info,
                           still_owner=(lease.assert_held if lease is not None else None))
    if not quality.published_manifest_valid(dest):
        raise RuntimeError("Publication receipt/checksum validation failed")


def cleanup_intermediates(stage: Path) -> None:
    """Retain checked slide PDFs and WAVs for accurate resume and audit."""
    for dirname in ("pages", "crops"):
        shutil.rmtree(stage / dirname, ignore_errors=True)


def preflight(main_py: str, docling_py: str, *, figure_extraction_only: bool = False) -> None:
    print(f"[batch] main Python: {main_py}", flush=True)
    print(f"[batch] Docling Python: {docling_py}", flush=True)
    if figure_extraction_only:
        probe = subprocess.run([main_py, "-c",
                                "import pymupdf; print('Offline PDF reader OK')"],
                               capture_output=True, text=True, timeout=60)
        if probe.returncode:
            raise RuntimeError("Missing local PDF reader: " + probe.stderr[-300:])
        print(probe.stdout.strip(), flush=True)
    else:
        for exe in ("pdflatex",):
            if not shutil.which(exe):
                raise RuntimeError(f"Required executable not found on PATH: {exe}")
    # Validate the primary runtime before hours of work are queued.
    code = (
        "import importlib.metadata as m; "
        "from google.genai import types; "
        "import google.cloud.texttospeech, PyPDF2, imageio_ffmpeg, contractions, fitz; "
        "print('google-genai='+m.version('google-genai')); "
        "print('ThinkingConfig='+','.join(getattr(types.ThinkingConfig,'model_fields',{}).keys()))"
    )
    if not figure_extraction_only:
        proc = subprocess.run([main_py, "-c", code], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Primary Python environment failed preflight: {proc.stderr}")
        print(proc.stdout.strip(), flush=True)

    docling_code = "import docling, pdf2image, PIL; print('Docling environment OK')"
    proc2 = subprocess.run([docling_py, "-c", docling_code], capture_output=True, text=True)
    if proc2.returncode != 0:
        raise RuntimeError(f"Docling Python environment failed preflight: {proc2.stderr}")
    print(proc2.stdout.strip(), flush=True)


@contextlib.contextmanager
def subchapter_ownership(args, subchapter: str):
    """Crash-recoverable kernel lock plus optional strong cross-PC GCS lease.

    The lock inode/file is deliberately retained: removing an unlocked file
    risks two processes holding locks on *different* recreated file inodes.
    Kernel locks are released automatically when a process exits or crashes.
    """
    local = args.work_root / f".microgen_{subchapter}.owner.lock"
    local.parent.mkdir(parents=True, exist_ok=True)
    with open(local, "a+b") as handle:
        locked = False
        grace_text = os.environ.get("MICROGEN_LOCAL_LOCK_WAIT_SECONDS", "5.0")
        try:
            grace = float(grace_text)
        except ValueError as exc:
            raise RuntimeError("MICROGEN_LOCAL_LOCK_WAIT_SECONDS must be numeric") from exc
        if not 0 <= grace <= 60:
            raise RuntimeError("Local lock wait must be between 0 and 60 seconds")
        deadline = time.monotonic() + grace
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            if local.stat().st_size == 0:
                handle.write(b"\0")
                handle.flush()
        else:
            import fcntl
        while not locked:
            try:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except (OSError, BlockingIOError) as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Subchapter {subchapter} has another active local worker; "
                        f"kernel lock unavailable at {local}. Verify other workers "
                        "before modifying locks."
                    ) from exc
                time.sleep(min(0.15, max(0.01, deadline-time.monotonic())))
        try:
            # Avoid overwriting the byte locked by Windows msvcrt.locking.
            # The lock file records a human-readable owner after the first byte.
            handle.seek(1)
            handle.truncate()
            handle.write(json.dumps({
                "subchapter": subchapter, "pid": os.getpid(),
                "created_utc": utc_now(),
            }).encode("utf-8"))
            handle.flush()
            if args.multi_pc:
                with DriveAssignedOwner(
                    args.assignments_file, args.assignments_sha256,
                    args.campaign_id, args.source_root, subchapter,
                ) as lease:
                    yield lease
            else:
                yield None
        finally:
            if locked:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def process_one(args, subchapter: str, report: list[dict], lease=None) -> None:
    if lease is not None:
        lease.assert_held()
    stage, cp, checkpoint_path = prepare_stage(
        args.repo,
        args.source_root,
        args.work_root,
        subchapter,
        args.source_wait,
        args.commit,
    )
    dest = destination_for(args.source_root, subchapter)
    offline_mapping = bool(getattr(args, "offline_figure_mapping", False))
    log_path = args.work_root / f"{subchapter}.log"
    # Existing source-adjacent MP4s are protected unless a user explicitly
    # authorizes revalidation/rebuild under the upgraded quality contract.
    bounded = getattr(args, "stop_after", None) is not None
    verified = False if bounded else quality.published_manifest_valid(dest)
    published_mode_ready = not args.multipart
    if verified and args.multipart:
        final_receipt = json.loads(
            (dest / ".microgen_verified_completion.json").read_text(encoding="utf-8")
        )
        published_mode_ready = bool(final_receipt.get("multipart_parts"))
    if verified and published_mode_ready:
        print(f"[{subchapter}] verified receipt and source hashes; skipping", flush=True)
        report.append({"subchapter": subchapter, "status": "success",
                       "resumed": True, "verified": True})
        return
    if (not bounded and nonempty(dest / "slides.mp4") and
            not verified and not args.rebuild_unverified):
        raise RuntimeError(
            "An existing MP4 has no current verified completion receipt. "
            "Preserved unchanged. Review it or run with --rebuild-unverified "
            "to explicitly permit replacement after full verification."
        )

    if (published_mode_ready and cp.get("completed", {}).get("published")
            and stage_valid(stage, "published", dest)):
        print(f"[{subchapter}] already published and verified; skipping", flush=True)
        report.append({"subchapter": subchapter, "status": "success", "resumed": True})
        return

    commands = {
        "figure_extraction": (args.docling_py, "crop_figs_v3.py", "figure extraction"),
        "figure_mapping": (args.main_py,
                           "microgen_offline_pdf_figure_map.py" if offline_mapping else "map_and_rename_v5.py",
                           "offline figure mapping" if offline_mapping else "figure mapping"),
        "figure_merge": (args.main_py, "merge_lettered_figs_v2.py", "lettered figure merge"),
        "slides": (args.main_py, "gen_slides_v20.py", "slide generation"),
        "narration": (args.main_py, "gen_script_v13.py", "narration"),
        "tts": (args.main_py, "text_to_speech_v25.py", "TTS"),
        "slide_slicing": (args.main_py, "slice_pdf_v21.py", "slide slicing"),
        "video": (args.main_py, "gen_video_v22.py", "video assembly"),
    }

    for stage_name in STAGES:
        if bounded and STAGES.index(stage_name) > STAGES.index(args.stop_after):
            if not stage_valid(stage, args.stop_after, dest):
                raise RuntimeError("Bounded campaign ended without verified target stage")
            report.append({"subchapter": subchapter,
                           "status": "bounded_stage_complete",
                           "stop_after": args.stop_after,
                           "checkpoint": str(checkpoint_path),
                           "published": False})
            print(f"[{subchapter}] BOUNDED_{args.stop_after.upper()}_COMPLETE; protected publication NOT run",flush=True)
            return
        if args.figure_extraction_only and stage_name != "figure_extraction":
            if not source_page_extraction_valid(stage):
                raise RuntimeError("Offline extraction incomplete; do not continue")
            report.append({"subchapter": subchapter,
                           "status": "offline_figure_extraction_complete",
                           "source_pages_complete": True,
                           "checkpoint": str(checkpoint_path),
                           "gemini_or_tts_invoked": False,
                           "published": False})
            print(f"[{subchapter}] OFFLINE_FIGURE_EXTRACTION_COMPLETE; paid stages NOT run", flush=True)
            return
        if lease is not None:
            lease.assert_held()
        if args.multipart and stage_name == "narration":
            from microgen_multipart import validate_scenes
            count = quality.check_slide_pdf(stage / "slides.pdf")["pages"]
            validate_scenes(stage, durations=[1.0] * count)
        completed = bool(cp.get("completed", {}).get(stage_name))
        fingerprint_ok = False
        if completed and stage_valid(stage, stage_name, dest):
            try:
                current = quality.dependency_fingerprint(stage, stage_name)
                fingerprint_ok = cp.get("dependency_fingerprints", {}).get(stage_name) == current
            except (OSError, quality.QualityError):
                fingerprint_ok = False
        if completed and fingerprint_ok:
            print(f"[{subchapter}] resume: {stage_name} and dependencies verified", flush=True)
            continue

        invalidate_from(cp, stage_name)
        save_checkpoint(checkpoint_path, cp)
        print(f"[{subchapter}] START {stage_name}", flush=True)
        try:
            if stage_name == "published":
                if lease is not None:
                    lease.assert_held()
                publish(stage, dest, lease=lease)
            else:
                py, script, label = commands[stage_name]
                run_subprocess(
                    py,
                    script,
                    stage,
                    log_path,
                    label,
                    gemini_stage=(stage_name in GEMINI_STAGES and not
                                  (offline_mapping and stage_name == "figure_mapping")),
                    retries=args.stage_retries,
                    lease=lease,
                )
                if lease is not None:
                    lease.assert_held()
                if not stage_valid(stage, stage_name, dest):
                    raise RuntimeError(f"{stage_name} completed but output validation failed")
            mark_complete(cp, checkpoint_path, stage_name, stage)
        except Exception as exc:
            cp["last_error"] = {
                "stage": stage_name,
                "type": type(exc).__name__,
                "message": str(exc),
                "utc": utc_now(),
            }
            save_checkpoint(checkpoint_path, cp)
            raise

    cleanup_intermediates(stage)
    sc = slide_count(stage)
    report.append(
        {
            "subchapter": subchapter,
            "status": "success",
            "slides": sc,
            "video_bytes": (stage / "slides.mp4").stat().st_size,
            "checkpoint": str(checkpoint_path),
        }
    )
    print(f"[{subchapter}] SUCCESS", flush=True)


def write_report(path: Path, report: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    tmp.replace(path)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Resumable MicroGen_AI batch production")
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--work-root", type=Path, required=True)
    ap.add_argument("--targets", required=True, help="Comma-separated subchapters, e.g. 1.1,1.2,2.3")
    ap.add_argument("--main-py", default=sys.executable)
    ap.add_argument("--docling-py", default=None,
                    help="Existing Docling Python; falls back to MICROGEN_DOCLING_PY or known local Conda environments.")
    ap.add_argument("--commit", default="unknown")
    ap.add_argument("--stage-retries", type=int, default=1)
    ap.add_argument(
        "--source-wait",
        type=float,
        default=float(os.environ.get("MICROGEN_SOURCE_WAIT_SECONDS", "600")),
    )
    ap.add_argument("--fail-fast", action="store_true", help="Stop after the first subchapter failure.")
    ap.add_argument("--offline-figure-mapping", action="store_true",
                    help="Local source-PDF figure mapping only. Requires --stop-after figure_mapping or figure_merge; never calls Gemini/TTS.")
    ap.add_argument("--figure-extraction-only", action="store_true",
                    help="Run only local PDF page/figure extraction, then STOP before any Gemini/TTS or publication. Resume later from this checkpoint.")
    ap.add_argument("--stop-after", choices=STAGES[:-1],
                    help="Stage-bounded isolated campaign: stop after this verified stage, NEVER publish to source-root.")
    ap.add_argument("--authorize-provider-usage", action="store_true",
                    help="Explicitly allow Gemini/Cloud TTS requests in a bounded --stop-after campaign.")
    ap.add_argument("--rebuild-unverified", action="store_true",
                    help="Explicitly authorize rebuilding older MP4s that lack verified receipts.")
    ap.add_argument("--multi-pc", action="store_true",
                    help="Require pinned, disjoint, host-specific Drive assignment manifest (no GCS).")
    ap.add_argument("--lease-bucket", help="Deprecated GCS option, rejected by this runner.")
    ap.add_argument("--campaign-id", help="Stable campaign ID agreed by all PCs.")
    ap.add_argument("--assignments-file", type=Path,
                    help="Shared Drive JSON mapping each subchapter to exactly one host.")
    ap.add_argument("--assignments-sha256",
                    help="Pinned SHA256 of assignment file, identical on every worker.")
    ap.add_argument("--check-assignments", action="store_true",
                    help="Validate ownership without Docling, Gemini requests or generation.")
    ap.add_argument("--multipart", action="store_true",
                    help="Require approved source-cited lesson scenes and emit video parts.")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    args.repo = args.repo.resolve()
    args.source_root = args.source_root.resolve()
    args.work_root = args.work_root.resolve()
    # Unbounded normal production eventually reaches paid Gemini/TTS stages.
    # Enforce the same explicit provider authorization already required for
    # paid --stop-after campaigns; never silently rely on stored credentials.
    if (not args.figure_extraction_only and not args.check_assignments and
            args.stop_after is None and not args.authorize_provider_usage):
        raise SystemExit(
            "Unbounded production can call billed Gemini/Cloud TTS services; "
            "explicit --authorize-provider-usage is required. "
            "For no-cost work, use --figure-extraction-only or "
            "--offline-figure-mapping --stop-after figure_merge."
        )
    if args.multi_pc and not args.check_assignments:
        verified_sha = inspect_local_checkout(args.repo, expected_commit=args.commit)
        args.commit = verified_sha
        print(f"[batch] verified local code commit={verified_sha}", flush=True)
    args.work_root.mkdir(parents=True, exist_ok=True)
    # Fail before any paid API requests or multi-gigabyte extraction/rendering.
    disk = quality.require_scratch_space(args.work_root)
    print(f"[batch] scratch free={disk['free_gb']} GB "
          f"(minimum={disk['required_gb']} GB)", flush=True)
    targets = split_targets(args.targets)
    if not targets:
        raise SystemExit("No targets supplied.")
    if args.lease_bucket:
        raise SystemExit("GCS leasing is not the selected coordination strategy; use --assignments-file")
    if args.check_assignments and not args.multi_pc:
        raise SystemExit("--check-assignments requires --multi-pc")
    if args.figure_extraction_only and args.multi_pc:
        raise SystemExit("--figure-extraction-only is a single-host offline pilot; multi-PC is not supported")
    if args.offline_figure_mapping:
        if (args.figure_extraction_only or args.multi_pc or
                args.stop_after not in {"figure_mapping", "figure_merge"} or
                args.authorize_provider_usage or args.multipart):
            raise SystemExit("Offline figure mapping requires bounded figure_mapping/figure_merge only, without provider authorization or multi-PC/multipart")
    if args.stop_after is not None:
        if args.figure_extraction_only or args.multi_pc:
            raise SystemExit("--stop-after is exclusive with --figure-extraction-only/--multi-pc")
        offline_safe = (args.offline_figure_mapping and
                        args.stop_after in {"figure_mapping", "figure_merge"})
        if (STAGES.index(args.stop_after) >= STAGES.index("figure_mapping") and
                not args.authorize_provider_usage and not offline_safe):
            raise SystemExit("--stop-after billable stages require --authorize-provider-usage")
    if args.multi_pc and (not args.campaign_id or not args.assignments_file
                          or not args.assignments_sha256):
        raise SystemExit(
            "--multi-pc requires --campaign-id, --assignments-file, "
            "and --assignments-sha256; GCS is not required"
        )
    if args.multi_pc:
        if not args.assignments_file.is_absolute():
            raise SystemExit("The shared assignment file must have an absolute path")
        if args.assignments_file.resolve().is_relative_to(args.work_root):
            raise SystemExit("Assignment file cannot live inside local scratch")
        for subchapter in targets:
            DriveAssignedOwner(
                args.assignments_file, args.assignments_sha256,
                args.campaign_id, args.source_root, subchapter,
            ).assert_held()
        print(f"[batch] Drive-assigned host targets verified: {targets}", flush=True)
    if args.check_assignments:
        print("[batch] Assignment-only check PASSED; no generation or cloud calls", flush=True)
        return 0
    if args.multi_pc:
        lane_raw = configured_gemini_lane()
        if lane_raw and not os.environ.get("MICROGEN_GEMINI_LANE_DIR"):
            # Stale automation processes might not inherit the user setting.
            # The child Gemini stage scripts must inherit the resolved lane.
            os.environ["MICROGEN_GEMINI_LANE_DIR"] = lane_raw
        if not lane_raw:
            raise SystemExit(
                "--multi-pc requires a configured shared MICROGEN_GEMINI_LANE_DIR "
                "for existing Drive-based Gemini request serialization"
            )
        lane_path = Path(lane_raw)
        if not lane_path.is_absolute() or not lane_path.is_dir():
            raise SystemExit("Shared Gemini lane must be an existing absolute directory")
        if lane_path.resolve().is_relative_to(args.work_root):
            raise SystemExit("Gemini lane may not be inside per-PC private scratch")
        parts = {segment.casefold() for segment in args.work_root.parts}
        if (args.work_root.is_relative_to(args.source_root)
                or parts.intersection({"my drive", "google drive", "onedrive", "dropbox"})):
            raise SystemExit(
                "Multi-PC work root must be a private local scratch folder, not "
                "inside source root or a recognized synced-drive folder."
            )
    if args.multipart:
        os.environ["MICROGEN_MULTIPART"] = "1"
    else:
        os.environ.pop("MICROGEN_MULTIPART", None)
    args.docling_py = resolve_docling_python(args.docling_py,
                                                   main_python=args.main_py)
    preflight(args.main_py, args.docling_py,
              figure_extraction_only=(args.figure_extraction_only or args.offline_figure_mapping))
    report: list[dict] = []
    report_path = args.work_root / "batch_report.json"
    print(f"[batch] targets={targets}", flush=True)
    for subchapter in targets:
        try:
            with subchapter_ownership(args, subchapter) as lease:
                process_one(args, subchapter, report, lease=lease)
        except Exception as exc:
            print(f"[{subchapter}] FAILED: {type(exc).__name__}: {exc}", flush=True)
            report.append(
                {
                    "subchapter": subchapter,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            write_report(report_path, report)
            if args.fail_fast:
                return 1
        write_report(report_path, report)
    print(f"[batch] report={report_path}", flush=True)
    acceptable = ("success", "offline_figure_extraction_complete", "bounded_stage_complete")
    return 0 if all(x.get("status") in acceptable for x in report) else 2


if __name__ == "__main__":
    raise SystemExit(main())
