"""Fail-closed candidate renderer for source-verbatim slide TEXT correction.

Only text in a single slide is replaceable. Equations with TeX markup and
graphics are deliberately NOT rewritten; the caller must treat them as
unresolved scientific issues, not 'corrected' or 'human approved'.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from microgen_quality import check_slide_pdf


class SlideRepairError(ValueError):
    pass


_UNSAFE = set("\\{}$%&#_^~\n\r")
_FORBIDDEN_TEX = (r"\\write18", r"\\openout", r"\\input", r"\\include{")


def _safe_text(value: str) -> bool:
    return (8 <= len(value) <= 220 and value.strip() == value
            and all(ch not in _UNSAFE for ch in value))


def candidate_slide_edit(stage: Path, slide_no: int, old: str, new: str,
                         work_root: Path) -> tuple[Path, Path, list[str]]:
    """Compile a candidate in caller-controlled private scratch, without writes.

    PDF source and images are reused read-only. The unique literal replacement
    must change exactly one slide; all others retain the same extracted text.
    Caller is responsible for second independent science-review before commit.
    """
    import fitz
    stage, work_root = Path(stage), Path(work_root)
    if not (_safe_text(old) and _safe_text(new) and old != new):
        raise SlideRepairError("Equation/macro/markup/unsafe text changes require a separate verifier")
    tex = (stage / "slides.tex").read_text(encoding="utf-8-sig")
    if tex.count(old) != 1 or any(term in tex for term in _FORBIDDEN_TEX):
        raise SlideRepairError("Target is not unique plain text in isolated TeX")
    with fitz.open(stage / "slides.pdf") as old_pdf:
        if not 1 <= slide_no <= old_pdf.page_count:
            raise SlideRepairError("Target slide number out of range")
        old_pages = [p.get_text("text") for p in old_pdf]
        image_snapshots = [[hashlib.sha256(old_pdf.extract_image(e[0])["image"]).hexdigest()
                            for e in p.get_images(full=True)] for p in old_pdf]
    if old_pages[slide_no-1].count(old) != 1:
        raise SlideRepairError("TeX passage does not occur exactly once in target rendered slide")
    if any(old in value for i, value in enumerate(old_pages) if i != slide_no-1):
        raise SlideRepairError("Same text appears on other slides; ambiguous repair")
    work_root.mkdir(parents=True,exist_ok=True)
    candidate = work_root / "slides.tex"
    pdf_candidate = work_root / "slides.pdf"
    if candidate.exists() or pdf_candidate.exists():
        raise SlideRepairError("Refusing to overwrite another repair candidate")
    candidate.write_text(tex.replace(old,new,1),encoding="utf8")
    exe = shutil.which("pdflatex")
    if not exe:
        raise SlideRepairError("pdflatex unavailable; cannot safely render candidate")
    for attempt in range(2):
        try:
            result = subprocess.run(
                [exe,"-no-shell-escape","-interaction=nonstopmode",
                 "-halt-on-error","-file-line-error",
                 "-output-directory",str(work_root),str(candidate)],
                cwd=stage,capture_output=True,text=True,timeout=120)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise SlideRepairError("Bounded candidate TeX compilation unavailable") from exc
        if result.returncode:
            raise SlideRepairError(
                f"Candidate TeX compile failed safely: {(result.stderr+result.stdout)[-250:]}")
    if not pdf_candidate.is_file():
        raise SlideRepairError("Candidate PDF missing after successful TeX compile")
    check_slide_pdf(pdf_candidate,require_footer=True)
    with fitz.open(pdf_candidate) as new_pdf:
        pages=[p.get_text("text") for p in new_pdf]
        images=[[hashlib.sha256(new_pdf.extract_image(e[0])["image"]).hexdigest()
                 for e in p.get_images(full=True)] for p in new_pdf]
    if len(pages)!=len(old_pages) or (new not in pages[slide_no-1]):
        raise SlideRepairError("Candidate did not preserve slide count or visible replacement")
    if any(a!=b for i,(a,b) in enumerate(zip(old_pages,pages))
           if i!=slide_no-1):
        raise SlideRepairError("Candidate unexpectedly changed unrelated slide content")
    if images!=image_snapshots:
        raise SlideRepairError("Candidate changed source figure image stream")
    return candidate, pdf_candidate, pages
