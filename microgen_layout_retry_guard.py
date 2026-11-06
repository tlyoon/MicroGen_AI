"""Bounded, source-preserving non-repetition guard for Beamer repair loops.

No external model requests or local models. Identical TeX plus identical
layout error after structural reflow is a stable defect, not a reason for
another paid PDF-specific campaign. Allow retry after the source, TeX, or
general producer/reflow algorithm changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class LayoutRepairRepeated(RuntimeError):
    """No changed source, TeX or repair code since a previous failure."""


_PRODUCER_FILES=(
    "gen_slides_v20.py", "microgen_slide_reflow.py", "fix_latex.py",
    "gen_slides_prompt_v20_hybrid.txt",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stage_identity(stage: Path) -> dict[str,str]:
    stage=Path(stage)
    source=stage/"source.pdf"
    source_digest=_sha(source.read_bytes()) if source.is_file() else ""
    h=hashlib.sha256()
    for filename in _PRODUCER_FILES:
        path=stage/filename
        h.update(filename.encode("utf8")+b"\x00")
        h.update(path.read_bytes() if path.is_file() else b"<not-present>")
    return {"source_pdf_sha256":source_digest,
            "producer_sha256":h.hexdigest()}


def prevent_repeated_paid_layout_retry(stage: Path) -> None:
    """Check before new LLM generation; no false release or source edits."""
    stage=Path(stage)
    tex=stage/"slides.tex"
    if not tex.is_file() or not (stage/"source.pdf").is_file():
        return
    context=_stage_identity(stage)
    tex_digest=_sha(tex.read_bytes())
    for record_path in sorted(stage.glob("layout_repeat_guard_*.json"))[:30]:
        try:
            info=json.loads(record_path.read_text(encoding="utf8"))
        except (OSError,ValueError):
            continue
        if (info.get("status")=="UNRESOLVED_IDENTICAL_SLIDE_LAYOUT_REPAIR"
            and info.get("source_pdf_sha256")==context["source_pdf_sha256"]
            and info.get("producer_sha256")==context["producer_sha256"]
            and info.get("latex_content_sha256")==tex_digest):
            raise LayoutRepairRepeated(
                "Previously verified identical slide-layout failure for the same "
                "source, TeX and producer code. Refusing another paid Gemini "
                "generation loop; change the global structural reflow code or "
                f"source and then retry. Diagnostic: {record_path.name}")


class LayoutRetryGuard:
    def __init__(self, tex_file: Path) -> None:
        self.tex_file=Path(tex_file)
        self.seen: dict[tuple[str,str],int]={}

    def reject_duplicate(self, diagnostic: str, attempt: int) -> None:
        raw=self.tex_file.read_bytes()
        tex_digest=_sha(raw)
        signature=_sha(str(diagnostic).encode("utf8"))
        key=(tex_digest,signature)
        prior=self.seen.get(key)
        if prior is None:
            self.seen[key]=attempt
            return
        context=_stage_identity(self.tex_file.parent)
        record={
            "status":"UNRESOLVED_IDENTICAL_SLIDE_LAYOUT_REPAIR",
            "source_preserving_reflow_tried":True,
            **context,
            "latex_content_sha256":tex_digest,
            "diagnostic_sha256":signature,
            "first_failed_attempt":prior,
            "repeated_attempt":attempt,
            "stop_not_retry":True,
            "publication_allowed":False,
        }
        filename=("layout_repeat_guard_"+
                  context["source_pdf_sha256"][:12]+"_"+
                  context["producer_sha256"][:12]+".json")
        diagnostic_path=self.tex_file.with_name(filename)
        if not diagnostic_path.is_file():
            with diagnostic_path.open("x",encoding="utf8") as out:
                json.dump(record,out,indent=2)
        raise LayoutRepairRepeated(
            "Identical slide-layout quality failure recurred on unchanged TeX after "
            f"attempts {prior} and {attempt}. Stop this PDF's repair loop. "
            f"See {filename}; improve the global reflow algorithm before "
            "retrying with a changed producer revision.")
