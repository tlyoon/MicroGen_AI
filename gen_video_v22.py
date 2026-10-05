from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_FILE = Path("slides.mp4")
FFMPEG_PATH_ENV = "MICROVID_FFMPEG"
FFMPEG_TIMEOUT_ENV = "MICROVID_FFMPEG_TIMEOUT_SECONDS"
DEFAULT_FFMPEG_TIMEOUT_SECONDS = 300.0


def ffmpeg_executable() -> str | None:
    configured = os.environ.get(FFMPEG_PATH_ENV)
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
    try:
        import imageio_ffmpeg
        candidate = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if candidate.is_file():
            return str(candidate.resolve())
    except (ImportError, OSError, RuntimeError):
        pass
    return shutil.which("ffmpeg")


def _timeout() -> float:
    raw = os.environ.get(FFMPEG_TIMEOUT_ENV)
    if not raw:
        return DEFAULT_FFMPEG_TIMEOUT_SECONDS
    value = float(raw)
    if value <= 0:
        raise RuntimeError(f"{FFMPEG_TIMEOUT_ENV} must be positive.")
    return value


def _tail(value: str | bytes | None, limit: int = 2000) -> str:
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    return (value or "").strip()[-limit:]


def _run_ffmpeg(arguments: list[str], operation: str) -> None:
    executable = ffmpeg_executable()
    if not executable:
        raise RuntimeError(
            "ffmpeg is not available. Install imageio-ffmpeg, put ffmpeg on PATH, "
            f"or set {FFMPEG_PATH_ENV}."
        )
    command = [executable, "-nostdin", "-hide_banner", "-loglevel", "error", *arguments]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=_timeout())
    except subprocess.TimeoutExpired as exc:
        detail = _tail(exc.stderr)
        raise RuntimeError(f"{operation} timed out after {_timeout():g} seconds. {detail}") from exc
    except subprocess.CalledProcessError as exc:
        detail = _tail(exc.stderr or exc.stdout)
        raise RuntimeError(f"{operation} failed with exit code {exc.returncode}. {detail}") from exc


def _numbered(pattern: str) -> list[Path]:
    files = []
    rx = re.compile(r"^slide(\d+)\." + re.escape(pattern) + r"$", re.I)
    for path in Path.cwd().iterdir():
        match = rx.match(path.name)
        if match:
            files.append((int(match.group(1)), path))
    return [path for _, path in sorted(files)]


def _ensure_slide_pdfs() -> list[Path]:
    pdfs = _numbered("pdf")
    if pdfs:
        return pdfs
    slides_pdf = Path("slides.pdf")
    if not slides_pdf.is_file():
        raise FileNotFoundError("Neither slideN.pdf files nor slides.pdf are available.")
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to split slides.pdf.") from exc
    source = fitz.open(slides_pdf)
    try:
        for index in range(source.page_count):
            target = Path(f"slide{index + 1}.pdf")
            one = fitz.open()
            try:
                one.insert_pdf(source, from_page=index, to_page=index)
                one.save(target)
            finally:
                one.close()
            print(f"Slide {index + 1} saved to: {target}")
    finally:
        source.close()
    return _numbered("pdf")


def _render_pdf_page(pdf: Path, png: Path) -> None:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to render v7 PDF slides for video generation.") from exc
    doc = fitz.open(pdf)
    try:
        if doc.page_count < 1:
            raise RuntimeError(f"{pdf} has no pages.")
        page = doc[0]
        target_width = 1920.0
        zoom = target_width / max(1.0, float(page.rect.width))
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(str(png))
    finally:
        doc.close()


def _make_segment(pdf: Path, audio: Path, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="microvid_v7_segment_") as tmp:
        staging = Path(tmp)
        image = staging / "slide.png"
        staged_audio = staging / audio.name
        staged_output = staging / "segment.mp4"
        _render_pdf_page(pdf, image)
        shutil.copy2(audio, staged_audio)
        with wave.open(str(staged_audio), "rb") as wav_file:
            audio_duration = wav_file.getnframes() / float(wav_file.getframerate())
        _run_ffmpeg(
            [
                "-y", "-loop", "1", "-framerate", "30", "-i", str(image),
                "-i", str(staged_audio), "-t", f"{audio_duration:.6f}",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white",
                "-c:v", "libx264", "-tune", "stillimage", "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", str(staged_output),
            ],
            f"Building media segment for {pdf.name}",
        )
        shutil.copy2(staged_output, output)


def _concat(segments: list[Path], output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="microvid_v7_concat_") as tmp:
        staging = Path(tmp)
        staged = []
        for index, segment in enumerate(segments, start=1):
            target = staging / f"segment_{index:04d}.mp4"
            shutil.copy2(segment, target)
            staged.append(target)
        listing = staging / "segments.concat.txt"
        listing.write_text("\n".join(f"file '{p.resolve()}'" for p in staged), encoding="utf-8")
        staged_output = staging / "slides.mp4"
        _run_ffmpeg(["-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(staged_output)], "Concatenating final slides.mp4")
        shutil.copy2(staged_output, output)


def main() -> None:
    pdfs = _ensure_slide_pdfs()
    wavs = _numbered("wav")
    if not pdfs or not wavs:
        raise RuntimeError("No slide PDF/WAV pairs found.")
    pdf_indices = [int(re.search(r"\d+", p.stem).group()) for p in pdfs]
    wav_indices = [int(re.search(r"\d+", p.stem).group()) for p in wavs]
    if pdf_indices != wav_indices:
        raise RuntimeError(f"PDF/WAV slide indices do not match: pdf={pdf_indices}; wav={wav_indices}")
    print(f"len(pdf_files)={len(pdfs)}; len(wav_files)={len(wavs)}")
    print("Number of PDF and WAV files tallies. To generate video with pri FFmpeg media engine ...")

    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()
    with tempfile.TemporaryDirectory(prefix="microvid_v7_segments_") as tmp:
        segment_dir = Path(tmp)
        segments = []
        for index, (pdf, wav) in enumerate(zip(pdfs, wavs), start=1):
            segment = segment_dir / f"slide{index}.mp4"
            _make_segment(pdf, wav, segment)
            segments.append(segment)
            print(f"processing ({pdf.name}, {wav.name})")
        _concat(segments, OUTPUT_FILE)
    if not OUTPUT_FILE.is_file() or OUTPUT_FILE.stat().st_size == 0:
        raise RuntimeError("slides.mp4 was not created successfully.")
    print(f"Video created successfully: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
