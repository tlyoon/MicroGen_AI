#!/usr/bin/env python3
"""Fixed-owner, resumable local visual-video repair campaign for MicroGen_AI.

Drive is a shared manifest DISTRIBUTION channel, not a distributed mutex.
Owners are predetermined. A single process per PC works serially; jobs are
never automatically reassigned or published into the course tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from microgen_drive_assignments import DriveAssignedOwner, manifest_digest
from microgen_legacy_video_repair import audio_stream_hash
from microgen_quality import check_video, sha256

SHA = re.compile(r"[a-f0-9]{64}\Z")
SECTION = re.compile(r"\d+\.\d+\Z")
LOCAL_FORBIDDEN = {"my drive", "google drive", "onedrive", "dropbox"}


class BatchError(RuntimeError):
    pass


def read_pinned(path: Path, expected: str) -> dict:
    if not SHA.fullmatch(expected.lower()):
        raise BatchError("An explicit 64-character pinned SHA256 is mandatory")
    try:
        content = path.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected.lower():
            raise BatchError("Pinned file differs; no work or reassignment allowed")
        result = json.loads(content.decode("utf-8-sig"))
        if not isinstance(result, dict):
            raise ValueError("Expected JSON object")
        return result
    except (OSError, ValueError, UnicodeError) as exc:
        raise BatchError(f"Cannot read pinned JSON: {exc}") from exc


def verify_code(root: Path, expected_commit: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{40}", expected_commit.lower()):
        raise BatchError("Full 40-character Git commit is required")
    if any(x.casefold() in LOCAL_FORBIDDEN for x in root.resolve().parts):
        raise BatchError("Runnable code must not be in a synchronized Drive folder")
    try:
        actual = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.PIPE, timeout=30
        ).strip()
        state = subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain"],
            text=True, stderr=subprocess.PIPE, timeout=30
        ).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise BatchError(f"Could not verify local Git checkout: {exc}") from exc
    if actual != expected_commit.lower() or state:
        raise BatchError("Code checkout changed or is dirty; stop before using source media")


def local_path(path: Path, what: str) -> Path:
    resolved = path.resolve()
    if any(x.casefold() in LOCAL_FORBIDDEN for x in resolved.parts):
        raise BatchError(f"{what} must be on the local disk")
    return resolved


def candidate_info(entry: dict, source_root: Path, pdf_root: Path) -> tuple[str, Path, Path]:
    section = entry.get("section")
    if not isinstance(section, str) or not SECTION.fullmatch(section):
        raise BatchError("Invalid section in candidate manifest")
    if entry.get("status") != "TECHNICAL_PDF_CANDIDATE_PASS":
        raise BatchError(f"PDF is not a verified candidate for {section}")
    candidate_sha = entry.get("new_pdf_sha256")
    if not isinstance(candidate_sha, str) or not SHA.fullmatch(candidate_sha):
        raise BatchError(f"Candidate lacks pinned SHA256 for {section}")
    folder = source_root / section.split(".")[0] / section
    candidate = pdf_root / section.replace(".", "_") / "slides.pdf"
    return section, folder, candidate


def validate_candidate(entry: dict, source_root: Path, pdf_root: Path) -> tuple[str, Path, Path]:
    section, folder, candidate = candidate_info(entry, source_root, pdf_root)
    if not folder.is_dir() or not (folder / "slides.mp4").is_file():
        raise BatchError(f"Missing source MP4 for {section}")
    if not candidate.is_file() or sha256(candidate) != entry["new_pdf_sha256"]:
        raise BatchError(f"Candidate PDF drift or missing: {section}")
    return section, folder, candidate


def load_candidate_rows(document: dict) -> dict[str, dict]:
    if document.get("schema_version") != 1:
        raise BatchError("Unsupported PDF-candidate manifest")
    rows = document.get("sections")
    if not isinstance(rows, list) or not rows:
        raise BatchError("PDF candidate manifest has no sections")
    by_section = {}
    for entry in rows:
        if not isinstance(entry, dict) or not isinstance(entry.get("section"), str):
            raise BatchError("Invalid PDF candidate manifest entry")
        sec = entry["section"]
        if sec in by_section or not SECTION.fullmatch(sec):
            raise BatchError("Duplicate or invalid section in manifest")
        by_section[sec] = entry
    return by_section


def validate_completed(output: Path, *, expected_pdf_sha: str, source: Path) -> dict:
    """Do not skip stale partial outputs or old source versions."""
    report_path = output / "video_repair_report.json"
    mp4 = output / "corrected_slides.mp4"
    if not report_path.is_file() or not mp4.is_file():
        raise BatchError(f"Unverified previous output: {output}")
    try:
        record = json.loads(report_path.read_text(encoding="utf-8-sig"))
        if record.get("status") != "VIDEO_CANDIDATE_PASS_NOT_PUBLISHED":
            raise BatchError("Existing candidate did not pass all checks")
        originals = record["old_media_sha256"]
        if originals["old_mp4"] != sha256(source / "slides.mp4"):
            raise BatchError("Original MP4 has changed since rendering")
        if originals["old_pdf"] != sha256(source / "slides.pdf"):
            raise BatchError("Original PDF has changed since rendering")
        if originals["corrected_pdf"] != expected_pdf_sha:
            raise BatchError("Existing video references a different corrected PDF")
        if sha256(mp4) != record["corrected_mp4_sha256"]:
            raise BatchError("Existing MP4 changed since verification")
        if record["original_audio_sha256"] != record["candidate_audio_sha256"]:
            raise BatchError("Audio was not preserved")
        if audio_stream_hash(mp4) != record["original_audio_sha256"]:
            raise BatchError("Actual encoded AAC stream hash changed")
        if not isinstance(record.get("candidate_video_verification"), dict):
            raise BatchError("No post-render pixel and transition verification record")
        check_video(mp4)
        return record
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise BatchError(f"Cannot validate existing output {output}: {exc}") from exc


class LocalExclusiveRun:
    """Local O_EXCL sentinel; never auto-remove another worker's lock."""
    def __init__(self, directory: Path):
        self.path = directory / ".microgen_video_batch.lock"
        self.handle: int | None = None

    def __enter__(self):
        try:
            self.handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise BatchError(
                f"Another worker or a crash owns local lock {self.path}; inspect manually"
            ) from exc
        try:
            os.write(self.handle, json.dumps({
                "pid": os.getpid(), "host": socket.gethostname(),
                "created_unix_seconds": time.time()
            }).encode("utf-8"))
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_args):
        if self.handle is not None:
            os.close(self.handle)
            self.handle = None
            self.path.unlink(missing_ok=True)


def stop_child_tree(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(child.pid)],
                       capture_output=True, timeout=25)
    else:
        child.terminate()
    try:
        child.wait(timeout=15)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=10)


def run_one(*, source: Path, pdf: Path, output: Path, owner: DriveAssignedOwner,
            pdf_sha: str, log_root: Path, poll_seconds: float = 3.0) -> dict:
    owner.assert_held()
    if sha256(pdf) != pdf_sha:
        raise BatchError("PDF SHA changed before launching video repair")
    if output.exists():
        return {"status": "PREVIOUS_VALIDATED",
                "mp4_sha256": validate_completed(output, expected_pdf_sha=pdf_sha,
                                                 source=source)["corrected_mp4_sha256"]}
    log_file = log_root / f"{source.name}.log"
    command = [sys.executable, str(Path(__file__).resolve().parent /
                                    "microgen_legacy_video_repair.py"),
               "--source", str(source), "--corrected-pdf", str(pdf),
               "--output", str(output)]
    with log_file.open("w", encoding="utf-8") as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, cwd=Path(__file__).resolve().parent)
        try:
            while child.poll() is None:
                owner.assert_held()
                if sha256(pdf) != pdf_sha:
                    raise BatchError("Candidate PDF changed during execution")
                time.sleep(poll_seconds)
        except BaseException:
            stop_child_tree(child)
            raise
        if child.returncode != 0:
            raise BatchError(f"Video repair rejected candidate; see {log_file}")
    owner.assert_held()
    if sha256(pdf) != pdf_sha:
        raise BatchError("Candidate PDF changed during final check")
    record = validate_completed(output, expected_pdf_sha=pdf_sha, source=source)
    return {"status": "NEW_CANDIDATE_PASS_NOT_PUBLISHED",
            "mp4_sha256": record["corrected_mp4_sha256"]}


def campaign(*, manifest: Path, manifest_sha: str, candidate_manifest: Path,
             candidate_sha: str, campaign_id: str, source_root: Path,
             pdf_root: Path, output_root: Path, targets: list[str],
             code_commit: str, execute: bool = False) -> dict:
    code = Path(__file__).resolve().parent
    verify_code(code, code_commit)
    source_root = source_root.resolve()
    pdf_root = local_path(pdf_root, "Corrected PDF root")
    output_root = local_path(output_root, "Candidate MP4 root")
    if pdf_root == output_root or pdf_root in output_root.parents or output_root in pdf_root.parents:
        raise BatchError("PDF and video roots must be independent")
    raw_manifest = read_pinned(manifest, manifest_sha)
    docs = read_pinned(candidate_manifest, candidate_sha)
    sections = load_candidate_rows(docs)
    from microgen_drive_assignments import validated_manifest
    validated_manifest(manifest.read_bytes(), campaign=campaign_id, source_root=source_root)
    if not targets or len(targets) != len(set(targets)):
        raise BatchError("Nonempty unique targets required")
    if any(t not in sections for t in targets):
        raise BatchError("Unverified target in selected campaign")
    owners = {}
    for t in targets:
        owner = DriveAssignedOwner(manifest, manifest_sha, campaign_id, source_root, t)
        owner.assert_held()
        owners[t] = owner
    items = []
    for t in targets:
        name, src, pdf = validate_candidate(sections[t], source_root, pdf_root)
        output = output_root / t.replace(".", "_")
        if output.exists():
            info = validate_completed(output, expected_pdf_sha=sections[t]["new_pdf_sha256"],
                                      source=src)
            state = "PREVIOUS_VALIDATED"
        else:
            state = "READY_FOR_CANDIDATE_RENDER"
        items.append({"section": t, "source": str(src), "candidate_pdf": str(pdf),
                      "expected_pdf_sha256": sections[t]["new_pdf_sha256"],
                      "output": str(output), "status": state})
    report = {"campaign_id": campaign_id, "owner": socket.gethostname().upper(),
              "code_commit": code_commit, "manifest_sha256": manifest_sha,
              "candidate_manifest_sha256": candidate_sha,
              "mode": "EXECUTE_CANDIDATE_ONLY" if execute else "DRY_RUN",
              "items": items, "publication_allowed": False}
    if not execute:
        return report
    output_root.mkdir(parents=True, exist_ok=True)
    with LocalExclusiveRun(output_root):
        logs = output_root / "logs"
        logs.mkdir(exist_ok=True)
        summary = output_root / "local_checkpoint.json"
        for item in items:  # coordinator-prescribed FIFO, never auto-reassign
            sec = item["section"]
            owner = owners[sec]
            owner.assert_held()
            try:
                result = run_one(source=Path(item["source"]), pdf=Path(item["candidate_pdf"]),
                                 output=Path(item["output"]), owner=owner,
                                 pdf_sha=item["expected_pdf_sha256"], log_root=logs)
                item.update(result)
            except Exception as exc:
                item["status"] = "STOPPED_REQUIRES_OPERATOR"
                item["error"] = f"{type(exc).__name__}: {exc}"
                summary.write_text(json.dumps(report, indent=2), encoding="utf-8")
                raise
            summary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--candidate-manifest", type=Path, required=True)
    p.add_argument("--candidate-sha256", required=True)
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--pdf-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--targets", required=True, help="Comma-separated, explicit FIFO list")
    p.add_argument("--code-commit", required=True)
    p.add_argument("--execute", action="store_true", help="Default is read-only preflight")
    args = p.parse_args()
    targets = [x.strip() for x in args.targets.split(",") if x.strip()]
    result = campaign(
        manifest=args.manifest, manifest_sha=args.manifest_sha256,
        candidate_manifest=args.candidate_manifest, candidate_sha=args.candidate_sha256,
        campaign_id=args.campaign_id, source_root=args.source_root,
        pdf_root=args.pdf_root, output_root=args.output_root,
        targets=targets, code_commit=args.code_commit, execute=args.execute
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
