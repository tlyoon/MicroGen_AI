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


def figure_display_warnings(slides_pdf: Path, *,
                            min_width_fraction: float = 0.12,
                            max_height_fraction: float = 0.27) -> list[dict]:
    """Flag extremely narrow, tall textbook images that are hard to read.

    This is advisory rather than an automatic cropping or figure-replacement
    algorithm: preserve all original scientific panels and have the lecturer
    check layout before release. Many single diagrams are appropriately small;
    the most concerning case is a vertically stacked composite rendered as
    a tiny, narrow strip on a wide slide.
    """
    # Structural PDF validation already ran before this advisory. Some
    # older unit-test fixtures mock it without creating any actual PDF.
    if not Path(slides_pdf).is_file() or Path(slides_pdf).stat().st_size == 0:
        return []
    issues = []
    import pymupdf
    try:
        # In-memory inspection avoids lingering read handles on Windows Drive
        # and on TemporaryDirectory fixtures.
        with pymupdf.open(stream=Path(slides_pdf).read_bytes(), filetype="pdf") as doc:
            for index, page in enumerate(doc):
                for entry in page.get_images(full=True):
                    if int(entry[2]) < 100 or int(entry[3]) < 100:
                        continue
                    for rect in page.get_image_rects(entry[0]):
                        fraction_w = rect.width / page.rect.width
                        fraction_h = rect.height / page.rect.height
                        if (fraction_w < min_width_fraction
                                and fraction_h < max_height_fraction):
                            issues.append({
                                "slide": index + 1,
                                "display_width_fraction": round(fraction_w, 4),
                                "display_height_fraction": round(fraction_h, 4),
                                "review_required": True,
                            })
    except pymupdf.FileDataError:
        # Existing main PDF gate is authoritative and already rejects
        # corrupt real output. Legacy mocked manifest fixtures may contain
        # placeholder bytes rather than a real PDF.
        return []
    except (OSError, ValueError, RuntimeError) as exc:
        raise QualityError(f"Could not inspect embedded slide figure geometry: {exc}") from exc
    return issues


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
        # Catch cases where Gemini echoes only the prefix of a long slide-1
        # course title (e.g. omits "Fractions" after "by Partial"). The
        # false-positive risk is low because arbitrary introductions that
        # are not literal title prefixes are not rejected.
        tex = script.parent / "slides.tex"
        if tex.is_file():
            match = re.search(r"\\title\{([^{}]+)\}", tex.read_text(encoding="utf-8-sig"))
            if match:
                expected_title = " ".join(match.group(1).split())
                announced_title = " ".join(str(slides[0].get("narration") or "").split())
                if (len(announced_title) >= 12
                        and expected_title.casefold().startswith(announced_title.casefold())
                        and len(expected_title) - len(announced_title) >= 4):
                    raise QualityError("Slide 1 narration truncates the title given in slides.tex")
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


def canonical_figure_hashes(figures: list[Path]) -> dict[str, str]:
    """Use the real on-disk filename case, collapsing equivalent references.

    Windows PDF/LaTeX generation may reference FIGURE 8.2.png even when the
    actual source is Figure 8.2.png. Both spellings resolve to one file on
    Windows and must not become two distinct publication candidates.
    Distinct files colliding after casefold must fail on every platform.
    """
    normalized: dict[str, tuple[Path, str]] = {}
    for entry in figures:
        actual = Path(entry).resolve(strict=True)
        digest = sha256(actual)
        key = actual.name.casefold()
        previous = normalized.get(key)
        if previous is not None:
            if previous[0] != actual or previous[1] != digest:
                raise QualityError(
                    f"Case-insensitive figure filename collision: "
                    f"{previous[0]} vs {actual}"
                )
            continue
        normalized[key] = (actual, digest)
    return {path.name: digest for path, digest in normalized.values()}


def manifest_for(stage: Path, *, require_footer: bool = False) -> dict:
    stage = Path(stage)
    pdf = check_slide_pdf(stage / "slides.pdf", require_footer=require_footer)
    small_figures = figure_display_warnings(stage / "slides.pdf")
    figures = check_graphics(stage / "slides.tex")
    # Keep the actual crop-to-caption provenance with every published deck.
    # This validates both used figures and any unused mapped figures before
    # publication, preventing receipt/artifact drift.
    figure_provenance = None
    provenance_file = stage / "figure_composition_receipt.json"
    if provenance_file.is_file():
        from microgen_figure_composition import validate_figure_receipt
        # Source-crop integrity is not equivalent to composite-panel approval.
        # Publishing a multi-panel figure requires a hash-bound human receipt.
        figure_provenance = validate_figure_receipt(stage, require_review=True)
        figures.extend(stage / f["destination"] for f in figure_provenance["figures"])
    unmapped_source_crops = []
    if figure_provenance is not None:
        from microgen_figure_composition import audit_unmapped_source_crops
        unmapped_source_crops = audit_unmapped_source_crops(stage, receipt=figure_provenance)
    narration = check_narration(stage / "script.txt", stage / "script_tts.json", pdf["pages"])
    wav = check_wavs(stage, pdf["pages"])
    video = check_video(stage / "slides.mp4", expected_seconds=wav["total_seconds"])
    multipart = None
    if os.environ.get("MICROGEN_MULTIPART", "0") == "1":
        multipart = check_multipart_receipt(stage)
    result = {
        "schema_version": 1,
        "validation": "structural-media-v1; does not certify scientific fidelity",
        "source_sha256": sha256(stage / "source.pdf"),
        "slides_pdf_sha256": pdf["sha256"],
        "slides_tex_sha256": sha256(stage / "slides.tex"),
        "script_sha256": narration["script_sha256"],
        "sidecar_sha256": narration["sidecar_sha256"],
        "wav_sha256": wav["sha256"],
        "figure_sha256": canonical_figure_hashes(figures),
        "mp4_sha256": video["sha256"],
        "slide_count": pdf["pages"],
        "audio_seconds": wav["total_seconds"],
        "video_seconds": video["seconds"],
    }
    if small_figures:
        result["figure_display_warnings"] = small_figures
        result["scientific_review_pending"] = True
    if unmapped_source_crops:
        result["unmapped_source_crops"] = unmapped_source_crops
        result["scientific_review_pending"] = True
    if figure_provenance is not None:
        result["figure_composition_receipt_sha256"] = sha256(provenance_file)
        if any(item.get("review_required") for item in figure_provenance["figures"]):
            result["figure_review_approval_sha256"] = sha256(stage / "figure_review_approval.json")
    if multipart is not None:
        result["multipart_receipt_sha256"] = multipart["receipt_sha256"]
        result["multipart_parts"] = multipart["parts"]
        result["scene_manifest_sha256"] = sha256(stage / "lesson_scenes.json")
    return result


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
        figure_sha256 = data.get("figure_sha256", {})
        if len(figure_sha256) != len({name.casefold() for name in figure_sha256}):
            return False
        for name, digest in figure_sha256.items():
            if sha256(dest / name) != digest:
                return False
        if "figure_composition_receipt_sha256" in data:
            if sha256(dest / "figure_composition_receipt.json") != data["figure_composition_receipt_sha256"]:
                return False
            from microgen_figure_composition import validate_figure_receipt
            evidence = validate_figure_receipt(dest, require_review=True)
            if any(item.get("review_required") for item in evidence["figures"]):
                if data.get("figure_review_approval_sha256") != sha256(dest / "figure_review_approval.json"):
                    return False
        if "multipart_receipt_sha256" in data:
            if (sha256(dest / ".microgen_multipart_receipt.json") != data["multipart_receipt_sha256"]
                or sha256(dest / "lesson_scenes.json") != data["scene_manifest_sha256"]):
                return False
            for name, digest in data.get("multipart_parts", {}).items():
                if sha256(dest / name) != digest:
                    return False
        return True
    except (OSError, KeyError, ValueError, TypeError, RuntimeError):
        return False


def publish_bundle(stage: Path, dest: Path, *, manifest: dict | None = None, still_owner=None) -> dict:
    """Preflight and stage every file before replacing any published artifact.

    Previous files are kept as backups. The marker is published last. If any
    replacement fails, roll back all changed files and keep the old receipt.
    """
    stage, dest = Path(stage), Path(dest)
    info = manifest or manifest_for(stage)
    figure_names = list(info.get("figure_sha256", {}))
    if len(figure_names) != len({name.casefold() for name in figure_names}):
        raise QualityError("Case-insensitive duplicate figure names in publication manifest")
    files = ["slides.pdf", "slides.tex", "script.txt", "script_tts.json", "slides.mp4"]
    files += sorted(set(info.get("figure_sha256", {})))
    if info.get("figure_composition_receipt_sha256"):
        files.append("figure_composition_receipt.json")
    if info.get("figure_review_approval_sha256"):
        files.append("figure_review_approval.json")
    if info.get("multipart_parts"):
        files += ["lesson_scenes.json", ".microgen_multipart_receipt.json"]
        files += sorted(info["multipart_parts"])
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
    # A destination-local candidate can disappear between preflight and
    # promotion (e.g. a transient Windows filesystem/sync-agent race).
    # Hold the original digest so a bounded re-stage cannot silently
    # promote changed or partially copied upstream content.
    expected_hashes: dict[str, str] = {}
    backups: dict[str, Path] = {}
    replaced: list[str] = []
    marker = ".microgen_verified_completion.json"
    token = os.urandom(8).hex()
    # Stage all outputs on the destination's own filesystem.
    try:
        for name in files:
            pending = dest / (name + f".microgen-{token}.candidate")
            expected = sha256(stage / name)
            shutil.copy2(stage / name, pending)
            if sha256(pending) != expected:
                raise QualityError(f"Copy hash mismatch: {name}")
            expected_hashes[name] = expected
            staged[name] = pending
        # Backups are retained for explicit recovery from previously published defects.
        for name in files:
            if still_owner is not None:
                still_owner()
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
                if still_owner is not None:
                    still_owner()
                try:
                    staged[name].replace(dest / name)
                except FileNotFoundError:
                    # One bounded recovery only, and only for a missing
                    # *source candidate*. Never mask a missing destination
                    # directory or promote drifted upstream artifacts.
                    if staged[name].is_file():
                        raise
                    if sha256(stage / name) != expected_hashes[name]:
                        raise QualityError(f"Source changed during re-stage: {name}")
                    if still_owner is not None:
                        still_owner()
                    print(f"[publication] Candidate disappeared: {name}; "
                          "recopying once from verified stage", flush=True)
                    shutil.copy2(stage / name, staged[name])
                    if sha256(staged[name]) != expected_hashes[name]:
                        raise QualityError(f"Re-staged hash mismatch: {name}")
                    staged[name].replace(dest / name)
                replaced.append(name)
            if still_owner is not None:
                still_owner()
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
        "figure_extraction": ("source.pdf", "crop_figs_v3.py"),
        "figure_mapping": ("source.pdf", "map_and_rename_v5.py",
                           "microgen_figure_composition.py",
                           "figure_composition_receipt.json"),
        "figure_merge": ("source.pdf", "merge_lettered_figs_v2.py",
                         "figure_composition_receipt.json"),
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
        if (stage / "lesson_scenes.json").is_file():
            inputs.append("lesson_scenes.json")
        if (stage / ".microgen_multipart_receipt.json").is_file() and name == "published":
            inputs.append(".microgen_multipart_receipt.json")
            inputs += sorted(p.name for p in stage.glob("slides_part_*.mp4"))
    if name == "published":
        inputs += sorted(p.name for p in stage.glob("Figure*.png"))
        for review_name in ("figure_composition_receipt.json", "figure_review_approval.json"):
            if (stage / review_name).is_file():
                inputs.append(review_name)
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


def check_multipart_receipt(stage: Path, *, expected_parts: int | None = None) -> dict:
    """Check the opt-in multipart proof against the exact source and video bytes."""
    stage = Path(stage)
    marker = stage / ".microgen_multipart_receipt.json"
    require_file(marker)
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise QualityError(f"Invalid multipart receipt: {exc}") from exc
    parts = data.get("parts")
    inputs = data.get("input_hashes", {})
    if data.get("schema_version") != 1 or not isinstance(parts, list) or not parts:
        raise QualityError("Invalid multipart receipt structure")
    if expected_parts is not None and len(parts) != expected_parts:
        raise QualityError("Incorrect multipart part count")
    if inputs.get("source_sha256") != sha256(stage / "source.pdf") or \
       inputs.get("slides_sha256") != sha256(stage / "slides.pdf") or \
       inputs.get("manifest_sha256") != sha256(stage / "lesson_scenes.json"):
        raise QualityError("Multipart source/deck/approved scene manifest changed")
    sequence = []
    digests = {}
    for i, item in enumerate(parts, 1):
        name = f"slides_part_{i:02d}.mp4"
        if item.get("file") != name or item.get("part") != i:
            raise QualityError("Invalid multipart filenames or order")
        if item.get("boundary_verified") is not True:
            raise QualityError("Multipart cut lacks an approved semantic boundary")
        expected = item.get("duration_seconds")
        if not isinstance(expected, (int, float)) or not 0 < expected <= 570:
            raise QualityError("Multipart part exceeds policy")
        current = check_video(stage / name, expected_seconds=expected)
        if current["seconds"] >= 600 or current["sha256"] != item.get("mp4_sha256"):
            raise QualityError("Multipart actual media mismatch")
        sequence.extend(item.get("slides", []))
        digests[name] = current["sha256"]
    import fitz
    with fitz.open(stage / "slides.pdf") as slides:
        n = slides.page_count
    if sequence != list(range(1, n+1)):
        raise QualityError("Multipart parts omit/reorder slide content")
    return {"parts": digests, "receipt_sha256": sha256(marker)}


def scratch_disk_status(path: Path, *, min_free_gb: float | None = None) -> dict:
    """Inspect actual scratch *volume* capacity, not Google Drive's virtual quota.

    Default protects Docling PDF conversion, slide PNGs, WAV caches and FFmpeg
    temporary segments. Users may deliberately override for smaller jobs.
    """
    if min_free_gb is None:
        raw=os.environ.get("MICROGEN_MIN_SCRATCH_FREE_GB","8.0")
        try:
            min_free_gb=float(raw)
        except ValueError as exc:
            raise QualityError("MICROGEN_MIN_SCRATCH_FREE_GB is not a number") from exc
    if not (isinstance(min_free_gb,(float,int))
            and __import__("math").isfinite(min_free_gb)
            and min_free_gb >= 0.5):
        raise QualityError("Minimum scratch capacity must be at least 0.5 GB")
    requested=Path(path).expanduser()
    probe=requested
    while not probe.exists():
        if probe == probe.parent:
            raise QualityError(f"Cannot resolve volume for scratch root: {requested}")
        probe=probe.parent
    usage=shutil.disk_usage(probe)
    free_gb=usage.free/(1024**3)
    return {
        "work_root":str(requested),
        "volume_checked":str(probe),
        "free_gb":round(free_gb,2),
        "required_gb":float(min_free_gb),
        "enough_space":free_gb>=min_free_gb,
    }


def require_scratch_space(path: Path, *, min_free_gb: float | None = None) -> dict:
    result=scratch_disk_status(path,min_free_gb=min_free_gb)
    if not result["enough_space"]:
        raise QualityError(
            f"Scratch drive has only {result['free_gb']} GB free; "
            f"at least {result['required_gb']} GB is required. "
            "Choose a different local work root or free disk space before "
            "starting Docling, TTS or FFmpeg. No API generation has started."
        )
    return result
