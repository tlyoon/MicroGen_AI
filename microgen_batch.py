#!/usr/bin/env python3
"""Resumable multi-subchapter production runner for MicroGen_AI.

Each subchapter has a persistent checkpoint. A failed narration/TTS/video stage
therefore resumes at that stage instead of repeating Docling, figure mapping,
and slide generation. Gemini billing circuit events pause Gemini stages rather
than burning retry attempts across every worker.
"""
from __future__ import annotations

import argparse
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


def stage_valid(stage: Path, name: str, dest: Path) -> bool:
    if name == "figure_extraction":
        pages = stage / "pages"
        return pages.is_dir() and any(pages.glob("page_*"))
    if name in {"figure_mapping", "figure_merge"}:
        # These stages may legitimately produce no Figure*.png. Their durable
        # checkpoint is therefore the authority.
        return True
    if name == "slides":
        return nonempty(stage / "slides.pdf") and nonempty(stage / "slides.tex")
    if name == "narration":
        return nonempty(stage / "script.txt") and nonempty(stage / "script_tts.json")
    if name == "tts":
        count = slide_count(stage)
        return bool(count) and len(numbered_files(stage, "wav")) == count
    if name == "slide_slicing":
        count = slide_count(stage)
        return bool(count) and len(numbered_files(stage, "pdf")) == count
    if name == "video":
        return nonempty(stage / "slides.mp4")
    if name == "published":
        return all(nonempty(dest / n) for n in ("slides.pdf", "script.txt", "slides.mp4"))
    return False


def invalidate_from(cp: dict, stage_name: str) -> None:
    completed = cp.setdefault("completed", {})
    idx = STAGES.index(stage_name)
    for name in STAGES[idx:]:
        completed.pop(name, None)


def mark_complete(cp: dict, checkpoint_path: Path, stage_name: str) -> None:
    cp.setdefault("completed", {})[stage_name] = utc_now()
    cp["last_error"] = None
    cp["updated_utc"] = utc_now()
    save_checkpoint(checkpoint_path, cp)


def wait_for_gemini_circuit() -> None:
    """Pause while the shared billing/capacity circuit is open."""
    last = 0.0
    while True:
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
        time.sleep(min(60.0, wait))


def run_subprocess(
    python_exe: str,
    script: str,
    stage: Path,
    log_path: Path,
    label: str,
    *,
    gemini_stage: bool,
    retries: int,
) -> None:
    attempt = 0
    while True:
        if gemini_stage:
            wait_for_gemini_circuit()
        with log_path.open("a", encoding="utf-8", errors="replace") as log:
            log.write(f"\n===== {label} :: {script} :: attempt {attempt + 1} =====\n")
            log.flush()
            proc = subprocess.run(
                [python_exe, script],
                cwd=str(stage),
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            log.write(f"\n[{label}] exit={proc.returncode}\n")
        if proc.returncode == 0:
            return

        # If the request tripped the shared circuit, this is an external pause,
        # not a stage failure and must not consume the retry count.
        if gemini_stage:
            opened, _ = circuit_is_open()
            if opened:
                print(f"[{stage.name}] {label}: Gemini circuit opened; pausing", flush=True)
                wait_for_gemini_circuit()
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
        time.sleep(delay)


def atomic_publish_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".microgen.tmp")
    shutil.copy2(src, tmp)
    tmp.replace(dest)


def publish(stage: Path, dest: Path) -> None:
    required = ("slides.pdf", "script.txt", "slides.mp4")
    for name in required:
        if not nonempty(stage / name):
            raise RuntimeError(f"required output missing/empty: {name}")
    for name in ("slides.pdf", "slides.tex", "script.txt", "script_tts.json", "slides.mp4"):
        src = stage / name
        if src.is_file():
            atomic_publish_file(src, dest / name)
    for pattern in ("Figure*.png", "FIGURE*.png"):
        for src in stage.glob(pattern):
            atomic_publish_file(src, dest / src.name)
    if not stage_valid(stage, "published", dest):
        raise RuntimeError("published output verification failed")


def cleanup_intermediates(stage: Path) -> None:
    for dirname in ("pages", "crops"):
        shutil.rmtree(stage / dirname, ignore_errors=True)
    for suffix in ("pdf", "wav"):
        for path in numbered_files(stage, suffix):
            try:
                path.unlink()
            except OSError:
                pass


def preflight(main_py: str, docling_py: str) -> None:
    print(f"[batch] main Python: {main_py}", flush=True)
    print(f"[batch] Docling Python: {docling_py}", flush=True)
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
    proc = subprocess.run([main_py, "-c", code], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Primary Python environment failed preflight: {proc.stderr}")
    print(proc.stdout.strip(), flush=True)

    docling_code = "import docling, pdf2image, PIL; print('Docling environment OK')"
    proc2 = subprocess.run([docling_py, "-c", docling_code], capture_output=True, text=True)
    if proc2.returncode != 0:
        raise RuntimeError(f"Docling Python environment failed preflight: {proc2.stderr}")
    print(proc2.stdout.strip(), flush=True)


def process_one(args, subchapter: str, report: list[dict]) -> None:
    stage, cp, checkpoint_path = prepare_stage(
        args.repo,
        args.source_root,
        args.work_root,
        subchapter,
        args.source_wait,
        args.commit,
    )
    dest = destination_for(args.source_root, subchapter)
    log_path = args.work_root / f"{subchapter}.log"

    if cp.get("completed", {}).get("published") and stage_valid(stage, "published", dest):
        print(f"[{subchapter}] already published and verified; skipping", flush=True)
        report.append({"subchapter": subchapter, "status": "success", "resumed": True})
        return

    commands = {
        "figure_extraction": (args.docling_py, "crop_figs_v3.py", "figure extraction"),
        "figure_mapping": (args.main_py, "map_and_rename_v5.py", "figure mapping"),
        "figure_merge": (args.main_py, "merge_lettered_figs_v2.py", "lettered figure merge"),
        "slides": (args.main_py, "gen_slides_v20.py", "slide generation"),
        "narration": (args.main_py, "gen_script_v13.py", "narration"),
        "tts": (args.main_py, "text_to_speech_v25.py", "TTS"),
        "slide_slicing": (args.main_py, "slice_pdf_v21.py", "slide slicing"),
        "video": (args.main_py, "gen_video_v22.py", "video assembly"),
    }

    for stage_name in STAGES:
        completed = bool(cp.get("completed", {}).get(stage_name))
        if completed and stage_valid(stage, stage_name, dest):
            print(f"[{subchapter}] resume: {stage_name} already valid", flush=True)
            continue

        invalidate_from(cp, stage_name)
        save_checkpoint(checkpoint_path, cp)
        print(f"[{subchapter}] START {stage_name}", flush=True)
        try:
            if stage_name == "published":
                publish(stage, dest)
            else:
                py, script, label = commands[stage_name]
                run_subprocess(
                    py,
                    script,
                    stage,
                    log_path,
                    label,
                    gemini_stage=stage_name in GEMINI_STAGES,
                    retries=args.stage_retries,
                )
                if not stage_valid(stage, stage_name, dest):
                    raise RuntimeError(f"{stage_name} completed but output validation failed")
            mark_complete(cp, checkpoint_path, stage_name)
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
    ap.add_argument("--docling-py", default=sys.executable)
    ap.add_argument("--commit", default="unknown")
    ap.add_argument("--stage-retries", type=int, default=1)
    ap.add_argument(
        "--source-wait",
        type=float,
        default=float(os.environ.get("MICROGEN_SOURCE_WAIT_SECONDS", "600")),
    )
    ap.add_argument("--fail-fast", action="store_true", help="Stop after the first subchapter failure.")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    args.repo = args.repo.resolve()
    args.source_root = args.source_root.resolve()
    args.work_root = args.work_root.resolve()
    args.work_root.mkdir(parents=True, exist_ok=True)
    targets = split_targets(args.targets)
    if not targets:
        raise SystemExit("No targets supplied.")
    preflight(args.main_py, args.docling_py)
    report: list[dict] = []
    report_path = args.work_root / "batch_report.json"
    print(f"[batch] targets={targets}", flush=True)
    for subchapter in targets:
        try:
            process_one(args, subchapter, report)
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
    return 0 if all(x.get("status") == "success" for x in report) else 2


if __name__ == "__main__":
    raise SystemExit(main())
