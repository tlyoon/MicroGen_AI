"""Fail-closed quality checks and crash-safe publication for MicroGen.

These checks are independent of any particular textbook, PC, or source root.
Existing lecture folders are never modified during validation. The final
manifest is the acceptance marker; an MP4's mere existence is not one.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path


class QualityError(RuntimeError):
    """The output does not meet the machine-checkable acceptance contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path) -> None:
    path = Path(path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise QualityError(f"Missing or empty artifact: {path}")


def numbered_files(directory: Path, extension: str, count: int) -> list[Path]:
    pattern = re.compile(r"slide([1-9]\d*)\." + re.escape(extension) + r"$", re.I)
    matches: dict[int, Path] = {}
    for item in Path(directory).iterdir():
        found = pattern.fullmatch(item.name)
        if found:
            num = int(found.group(1))
            if num in matches:
                raise QualityError(f"Duplicate numbered {extension} index {num}")
            matches[num] = item
    expected = set(range(1, count + 1))
    if set(matches) != expected:
        raise QualityError(
            f"Numbered {extension} mismatch: missing={sorted(expected-set(matches))}, "
            f"unexpected={sorted(set(matches)-expected)}"
        )
    for item in matches.values():
        require_file(item)
    return [matches[i] for i in range(1, count + 1)]


def check_slide_pdf(path: Path, *, require_footer: bool = False) -> dict:
    """Inspect actual rendered slide pages; geometry checks are conservative.

    Does not claim that all raster figures are semantically correct. Review
    composite panel cropping and small text separately when needed.
    """
    require_file(path)
    try:
        import fitz
        with fitz.open(str(path)) as doc:
            count = doc.page_count
            if count < 1:
                raise QualityError("Slide PDF has no pages")
            bad_footers = []
            blank = []
            out_of_page = []
            for i, page in enumerate(doc, 1):
                txt = page.get_text()
                if not txt.strip():
                    blank.append(i)
                counters = re.findall(r"\b\d+\s*/\s*\d+\b", txt)
                if (require_footer or counters) and not re.search(
                    rf"\b{i}\s*/\s*{count}\b", txt
                ):
                    bad_footers.append((i, counters[-3:]))
                for block in page.get_text("blocks"):
                    rect = fitz.Rect(block[:4])
                    if rect.is_empty or rect.get_area() < 12:
                        continue
                    boundary = page.rect + (-2, -2, 2, 2)
                    if not boundary.contains(rect):
                        out_of_page.append(i)
            if blank or bad_footers or out_of_page:
                raise QualityError(
                    f"Slide PDF failed: blank={blank}, counters={bad_footers}, "
                    f"out_of_bounds={sorted(set(out_of_page))}"
                )
            return {"pages": count, "sha256": sha256(path), "page_text_present": True}
    except QualityError:
        raise
    except Exception as exc:
        raise QualityError(f"Unreadable slide PDF {path}: {exc}") from exc


def check_graphics(tex: Path) -> list[Path]:
    """Fail closed rather than silently removing a missing includegraphics."""
    require_file(tex)
    source = Path(tex).read_text(encoding="utf-8-sig")
    names = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", source)
    found = []
    for name in names:
        candidate = Path(tex).parent / name
        if not candidate.is_file():
            # TeX permits omitting a standard image extension.
            resolved = next(
                (candidate.with_suffix(ext) for ext in (".png", ".jpg", ".jpeg", ".pdf")
                 if candidate.with_suffix(ext).is_file()), None
            ) if not candidate.suffix else None
            if resolved is None:
                raise QualityError(f"Missing figure referenced by {tex.name}: {name}")
            candidate = resolved
        require_file(candidate)
        found.append(candidate)
    return found


def check_narration(script: Path, sidecar: Path, pages: int) -> dict:
    require_file(script)
    require_file(sidecar)
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
        slides = raw["slides"]
        if not isinstance(slides, list) or len(slides) != pages:
            raise QualityError(f"Narration JSON slide count differs from PDF ({pages})")
        numbers = [item.get("slide") for item in slides]
        if numbers != list(range(1, pages + 1)):
            raise QualityError("Narration slide numbers are missing, duplicated or out of order")
        for item in slides:
            if not str(item.get("narration") or "").strip() or not str(
                item.get("tts_text") or item.get("narration") or ""
            ).strip():
                raise QualityError(f"Empty narration at slide {item.get('slide')}")
        text = script.read_text(encoding="utf-8")
        blocks = [int(x) for x in re.findall(r"(?m)^\*\*Slide\s+(\d+)\s*\[", text)]
        if blocks != numbers:
            raise QualityError("Human-readable narration and JSON sidecar disagree")
        return {"pages": pages, "script_sha256": sha256(script),
                "sidecar_sha256": sha256(sidecar)}
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise QualityError(f"Invalid narration sidecar: {exc}") from exc


def check_wavs(directory: Path, pages: int) -> dict:
    files = numbered_files(directory, "wav", pages)
    seconds = []
    for item in files:
        try:
            with wave.open(str(item), "rb") as wav:
                if wav.getframerate() <= 0 or wav.getnframes() <= 0:
                    raise QualityError(f"Empty audio: {item}")
                seconds.append(wav.getnframes() / wav.getframerate())
        except (OSError, EOFError, wave.Error) as exc:
            raise QualityError(f"Invalid WAV {item.name}: {exc}") from exc
    return {"seconds": seconds, "total_seconds": sum(seconds),
            "sha256": [sha256(p) for p in files]}


def check_video(path: Path, *, expected_seconds: float | None = None,
                ffmpeg: str | None = None) -> dict:
    require_file(path)
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, RuntimeError):
            ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise QualityError("FFmpeg required for media stream verification")
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, errors="replace", timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QualityError(f"Cannot probe MP4: {exc}") from exc
    output = result.stderr + result.stdout
    if "Video:" not in output or "Audio:" not in output:
        raise QualityError("MP4 must contain both audio and video streams")
    match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", output)
    if not match:
        raise QualityError("MP4 has no measurable duration")
    seconds = 3600 * int(match.group(1)) + 60 * int(match.group(2)) + float(match.group(3))
    if seconds <= 0:
        raise QualityError("MP4 has zero duration")
    if expected_seconds is not None:
        if not (expected_seconds * 0.96 <= seconds <= expected_seconds +
                max(10.0, expected_seconds * 0.03)):
            raise QualityError(
                f"MP4 duration {seconds:.2f}s differs from WAVs {expected_seconds:.2f}s"
            )
    return {"seconds": seconds, "sha256": sha256(path),
            "audio": True, "video": True}


def manifest_for(stage: Path, *, require_footer: bool = False) -> dict:
    stage = Path(stage)
    pdf = check_slide_pdf(stage / "slides.pdf", require_footer=require_footer)
    figures = check_graphics(stage / "slides.tex")
    narration = check_narration(stage / "script.txt", stage / "script_tts.json", pdf["pages"])
    wav = check_wavs(stage, pdf["pages"])
    video = check_video(stage / "slides.mp4", expected_seconds=wav["total_seconds"])
    return {
        "schema_version": 1,
        "validation": "structural-media-v1; does not certify scientific fidelity",
        "source_sha256": sha256(stage / "source.pdf"),
        "slides_pdf_sha256": pdf["sha256"],
        "slides_tex_sha256": sha256(stage / "slides.tex"),
        "script_sha256": narration["script_sha256"],
        "sidecar_sha256": narration["sidecar_sha256"],
        "wav_sha256": wav["sha256"],
        "figure_sha256": {p.name: sha256(p) for p in figures},
        "mp4_sha256": video["sha256"],
        "slide_count": pdf["pages"],
        "audio_seconds": wav["total_seconds"],
        "video_seconds": video["seconds"],
    }


def published_manifest_valid(dest: Path) -> bool:
    """Never accept a legacy nonempty MP4 as a verified new completion."""
    dest = Path(dest)
    p = dest / ".microgen_verified_completion.json"
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1:
            return False
        pairs = (("slides.pdf", "slides_pdf_sha256"),
                 ("slides.tex", "slides_tex_sha256"),
                 ("source.pdf", "source_sha256"),
                 ("script.txt", "script_sha256"),
                 ("script_tts.json", "sidecar_sha256"),
                 ("slides.mp4", "mp4_sha256"))
        if not all(sha256(dest / name) == data[key] for name, key in pairs):
            return False
        for index, digest in enumerate(data.get("wav_sha256", []), start=1):
            if sha256(dest / f"slide{index}.wav") != digest:
                return False
        for name, digest in data.get("figure_sha256", {}).items():
            if sha256(dest / name) != digest:
                return False
        return True
    except (OSError, KeyError, ValueError, TypeError):
        return False


def publish_bundle(stage: Path, dest: Path, *, manifest: dict | None = None) -> dict:
    """Preflight and stage every file before replacing any published artifact.

    Previous files are kept as backups. The marker is published last. If any
    replacement fails, roll back all changed files and keep the old receipt.
    """
    stage, dest = Path(stage), Path(dest)
    info = manifest or manifest_for(stage)
    files = ["slides.pdf", "slides.tex", "script.txt", "script_tts.json", "slides.mp4"]
    files += sorted(set(info.get("figure_sha256", {})))
    files += [f"slide{i}.wav" for i in range(1, len(info.get("wav_sha256", [])) + 1)]
    # Keep source-adjacent split-page PDFs where the legacy slicer generated them.
    count = int(info.get("slide_count", 0))
    if count and all((stage / f"slide{i}.pdf").is_file() for i in range(1, count + 1)):
        files += [f"slide{i}.pdf" for i in range(1, count + 1)]
    for name in files:
        require_file(stage / name)
    require_file(stage / "source.pdf")
    if dest.exists() and (not (dest / "source.pdf").is_file() or sha256(dest / "source.pdf") != info["source_sha256"]):
        raise QualityError("Destination source PDF has changed")
    dest.mkdir(parents=True, exist_ok=True)
    staged: dict[str, Path] = {}
    backups: dict[str, Path] = {}
    replaced: list[str] = []
    marker = ".microgen_verified_completion.json"
    token = os.urandom(8).hex()
    # Stage all outputs on the destination's own filesystem.
    try:
        for name in files:
            pending = dest / (name + f".microgen-{token}.candidate")
            shutil.copy2(stage / name, pending)
            if sha256(pending) != sha256(stage / name):
                raise QualityError(f"Copy hash mismatch: {name}")
            staged[name] = pending
        # Backups are retained for explicit recovery from previously published defects.
        for name in files:
            prior = dest / name
            if prior.is_file():
                backup = dest / (name + f".before-microgen-{token}.bak")
                shutil.copy2(prior, backup)
                if sha256(prior) != sha256(backup):
                    raise QualityError(f"Backup hash mismatch: {name}")
                backups[name] = backup
        old_marker = dest / marker
        previous_marker = old_marker.read_bytes() if old_marker.is_file() else None
        try:
            # Remove stale acceptance marker before changing the artifact set.
            old_marker.unlink(missing_ok=True)
            for name in files:
                staged[name].replace(dest / name)
                replaced.append(name)
            receipt = dest / (marker + f".microgen-{token}.tmp")
            receipt.write_text(json.dumps(info, indent=2, sort_keys=True), encoding="utf-8")
            receipt.replace(dest / marker)
            if not published_manifest_valid(dest):
                raise QualityError("Published manifest failed post-publication checksum check")
            return info
        except Exception:
            old_marker.unlink(missing_ok=True)
            for name in reversed(replaced):
                if name in backups:
                    shutil.copy2(backups[name], dest / name)
                else:
                    (dest / name).unlink(missing_ok=True)
            if previous_marker is not None:
                old_marker.write_bytes(previous_marker)
            raise
    finally:
        for pending in staged.values():
            pending.unlink(missing_ok=True)


def dependency_fingerprint(stage: Path, name: str) -> str:
    """Bind downstream stages to exact upstream artifacts and code revision.

    Earlier checkpoints without this fingerprint are treated as unverified,
    never silently promoted. Stage-specific input maps minimize rework.
    """
    stage = Path(stage)
    dependencies = {
        "slides": ("source.pdf", "gen_slides_v20.py",
                   "gen_slides_prompt_v20_hybrid.txt"),
        "narration": ("source.pdf", "slides.pdf", "gen_script_v13.py",
                      "gen_script_prompt_v8_hybrid.md"),
        "tts": ("script_tts.json", "text_to_speech_v25.py"),
        "slide_slicing": ("slides.pdf", "slice_pdf_v21.py"),
        "video": ("slides.pdf", "gen_video_v22.py"),
        "published": ("source.pdf", "slides.pdf", "slides.tex", "script.txt",
                      "script_tts.json", "slides.mp4"),
    }
    inputs = list(dependencies.get(name, ("source.pdf",)))
    if name == "slides":
        inputs += sorted(p.name for p in stage.glob("Figure*.png"))
    if name in {"video", "published"}:
        inputs += sorted(p.name for p in stage.glob("slide*.wav"))
    if name == "published":
        inputs += sorted(p.name for p in stage.glob("Figure*.png"))
    pairs = []
    for item in inputs:
        path = stage / item
        require_file(path)
        pairs.append((item, sha256(path)))
    # Changing TTS voice or speed invalidates audio, not upstream narration.
    if name in {"tts", "video", "published"}:
        pairs.append(("_voice", os.environ.get("MICROVID_TTS_VOICE", "en-US-Chirp-HD-F")))
        pairs.append(("_rate", os.environ.get("MICROVID_TTS_SPEAKING_RATE", "0.8")))
        pairs.append(("_language", os.environ.get("MICROVID_TTS_LANGUAGE", "en-US")))
    return hashlib.sha256(json.dumps(pairs, sort_keys=True).encode("utf-8")).hexdigest()


def check_latex_overflow(log_path: Path, *, max_hbox_pt: float = 8.0,
                         max_vbox_pt: float = 5.0) -> dict:
    """Catch severe overfull Beamer boxes instead of trusting PDF compile exit.

    Mild theme-related hbox overflow may be tolerated. Geometry/semantic
    review is still needed for clipping not reported by TeX.
    """
    require_file(log_path)
    content = Path(log_path).read_text(encoding="utf-8", errors="replace")
    matches = re.findall(
        r"Overfull\s+\\(hbox|vbox)\s+\(([0-9]+(?:\.[0-9]+)?)pt\s+too\s+(?:wide|high)\)",
        content,
    )
    severe = [(kind, float(amount)) for kind, amount in matches
              if float(amount) > (max_hbox_pt if kind == "hbox" else max_vbox_pt)]
    if severe:
        raise QualityError(
            f"Severe LaTeX layout overflow in {log_path.name}: {severe[:12]}. "
            "Reflow the source-backed content; do not crop the PDF."
        )
    return {"all_overfull_count": len(matches), "severe_count": 0}


def normalize_latex_paragraphs(source: str) -> str:
    """Remove empty LaTeX paragraph tokens without altering nonempty lines.

    Empty paragraphs inside display math caused the Thomas 8.5 pilot to fail.
    Keep equations, symbols, labels, captions and all nonblank source lines.
    """
    lines = [line.rstrip() for line in source.splitlines() if line.strip()]
    return "\n".join(lines) + "\n"


def try_local_latex_repair(tex_path: Path, *, timeout: float = 180.0) -> bool:
    """Compile deterministic candidate twice *in an isolated job directory*.

    Only promotes the candidate if all quality gates pass. Returns False on
    ordinary TeX failures so the existing targeted repair path can continue.
    Does not make Gemini requests, remove figure references or publish to Drive.
    """
    tex_path = Path(tex_path)
    require_file(tex_path)
    original = tex_path.read_text(encoding="utf-8-sig")
    normalized = normalize_latex_paragraphs(original)
    build = tex_path.parent / ".microgen_deterministic_latex_repair"
    build.mkdir(parents=True, exist_ok=True)
    candidate = tex_path.parent / "slides_microgen_clean_candidate.tex"
    candidate.write_text(normalized, encoding="utf-8")
    check_graphics(candidate)
    output_dir = build / "pdf"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "pdflatex", "-interaction=nonstopmode", "-halt-on-error",
        "-file-line-error", "-jobname=slides",
        "-output-directory=" + str(output_dir), candidate.name,
    ]
    for attempt in (1, 2):
        try:
            result = subprocess.run(
                command, cwd=tex_path.parent, capture_output=True,
                text=True, errors="replace", timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            (build / "last_failure.txt").write_text(str(exc), encoding="utf-8")
            return False
        (build / f"pdflatex_pass_{attempt}.txt").write_text(
            result.stdout + "\n" + result.stderr, encoding="utf-8",
        )
        if result.returncode:
            return False
    compiled = output_dir / "slides.pdf"
    try:
        check_slide_pdf(compiled, require_footer=True)
        check_latex_overflow(output_dir / "slides.log")
    except QualityError as exc:
        (build / "last_failure.txt").write_text(str(exc), encoding="utf-8")
        return False
    prior = tex_path.with_name("slides.before_deterministic_repair.tex")
    if not prior.exists():
        shutil.copy2(tex_path, prior)
    # Candidate and PDFs are fully verified before any staged input is updated.
    target_pdf = tex_path.with_suffix(".pdf")
    temp_pdf = target_pdf.with_name(target_pdf.name + ".microgen.tmp")
    shutil.copy2(compiled, temp_pdf)
    if sha256(temp_pdf) != sha256(compiled):
        raise QualityError("Deterministic PDF staging hash mismatch")
    temp_tex = tex_path.with_name(tex_path.name + ".microgen.tmp")
    shutil.copy2(candidate, temp_tex)
    if sha256(temp_tex) != sha256(candidate):
        raise QualityError("Deterministic TeX staging hash mismatch")
    temp_pdf.replace(target_pdf)
    temp_tex.replace(tex_path)
    return True
