"""Safe source-verified recovery when the title-card PDF wraps its heading.

Runs in the ordinary batch narration postflight, before quality validation.
Never asks Gemini to regenerate unchanged narration and never alters the
source PDF, slide art, mathematics, or body lecture. Fail closed unless the
literal full LaTeX title is visible in the rendered first PDF slide.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


class NarrationTitleRecoveryError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    with path.open("rb") as data:
        return hashlib.file_digest(data, "sha256").hexdigest()


def _read_safe(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise NarrationTitleRecoveryError("Required private source/sidecar is not a safe file")
    return path.read_text(encoding="utf-8-sig")


def recover_title_card(stage: Path) -> dict:
    """Restore only a proven line-wrapped, literally source-visible title.

    Re-running after an interruption is idempotent, including when only
    one of two output files was atomically replaced before power loss.
    """
    stage = Path(stage)
    if stage.is_symlink() or not stage.is_dir():
        raise NarrationTitleRecoveryError("Unsafe narration stage")
    tex = stage / "slides.tex"
    pdf = stage / "slides.pdf"
    script = stage / "script.txt"
    sidecar = stage / "script_tts.json"
    for file in (tex, pdf, script, sidecar):
        if file.is_symlink() or not file.is_file():
            raise NarrationTitleRecoveryError("Missing/unsafe title evidence")
    tex_text = _read_safe(tex)
    match = re.search(r"\\title\{([^{}]+)\}", tex_text)
    if not match:
        return {"status": "NO_LITERAL_TITLE_ABSTAINED", "changed": False}
    expected = " ".join(match.group(1).split())
    if not 12 <= len(expected) <= 200 or "\\" in expected:
        return {"status": "NONLITERAL_TITLE_ABSTAINED", "changed": False}
    try:
        import pymupdf
        with pymupdf.open(str(pdf)) as doc:
            if len(doc) < 1:
                raise NarrationTitleRecoveryError("No PDF title page")
            shown = " ".join((doc[0].get_text("text") or "").split())
    except NarrationTitleRecoveryError:
        raise
    except Exception as exc:
        raise NarrationTitleRecoveryError("Cannot attest first PDF page text") from exc
    if expected.casefold() not in shown.casefold():
        # Do not mutate (or needlessly stop) unrelated title styles.
        # The existing independent narration validator will still reject
        # any genuinely truncated title; no unverified text is inserted.
        return {"status": "TITLE_NOT_TEXT_ATTESTED_ABSTAINED",
                "changed": False}
    data = json.loads(_read_safe(sidecar))
    items = data.get("slides")
    if not isinstance(items, list) or not items or items[0].get("slide") != 1:
        raise NarrationTitleRecoveryError("No valid slide 1 sidecar")
    first = items[0]
    announced = str(first.get("narration") or "").strip()
    tts = str(first.get("tts_text") or "").strip()
    script_text = _read_safe(script)
    first_block = re.search(
        r"(?m)^(\*\*Slide\s+1\s+\[[^\]\n]+\]:\s*\n)"
        r"([^\n]+)(\*\*)", script_text)
    if not first_block:
        raise NarrationTitleRecoveryError("Slide 1 script block not found")
    spoken_in_script = first_block.group(2).strip()
    # All three values must be either the attested complete title, or its
    # genuine visible prefix; no arbitrary speech replacement is allowed.
    def admissible(text: str) -> bool:
        return (text == expected or (len(text) >= 12
                and expected.casefold().startswith(text.casefold())
                and len(expected) - len(text) >= 4))
    if not all(admissible(v) for v in (announced, tts, spoken_in_script)):
        return {"status": "UNRELATED_TITLE_ABSTAINED", "changed": False}
    if all(x == expected for x in (announced, tts, spoken_in_script)):
        return {"status": "ALREADY_FULL_SOURCE_TITLE", "changed": False}

    from microgen_reviewed_math_voice import voice_input_risk_status
    from text_to_speech_v25 import normalize_scientific_speech
    risk = voice_input_risk_status(expected, normalize_scientific_speech)
    if risk["unresolved_source_risk_count"] != 0:
        raise NarrationTitleRecoveryError("Full title has unresolved speech risks")
    first["narration"] = expected
    first["tts_text"] = normalize_scientific_speech(expected)
    first["title"] = expected
    first["tts_math_voice_preflight"] = risk
    replaced = (script_text[:first_block.start(2)] + expected +
                script_text[first_block.end(2):])
    new_sidecar = json.dumps(data, ensure_ascii=False, indent=2)
    # Write in two independently atomic file steps. A restart accepts
    # either already-repaired field and finishes the remainder.
    tmp_script = script.with_name(".microgen_title_script.tmp")
    tmp_sidecar = sidecar.with_name(".microgen_title_sidecar.tmp")
    if tmp_script.exists() or tmp_sidecar.exists():
        raise NarrationTitleRecoveryError("Unresolved previous title repair temp files")
    tmp_script.write_text(replaced, encoding="utf8")
    tmp_sidecar.write_text(new_sidecar, encoding="utf8")
    tmp_script.replace(script)
    tmp_sidecar.replace(sidecar)
    if first.get("narration") != expected or expected not in _read_safe(script):
        raise NarrationTitleRecoveryError("Incomplete title repair")
    receipt = {
        "status": "SOURCE_PDF_TITLE_WRAP_CORRECTED",
        "changed": True,
        "source_pdf_sha256": _sha(pdf),
        "slide_tex_sha256": _sha(tex),
        "script_sha256": _sha(script),
        "sidecar_sha256": _sha(sidecar),
        "title_sha256": hashlib.sha256(expected.encode("utf8")).hexdigest(),
        "publication_allowed": False,
    }
    receipt_path = stage / ".microgen_source_title_recovery.json"
    if receipt_path.exists() or receipt_path.is_symlink():
        raise NarrationTitleRecoveryError("Existing title recovery receipt cannot be overwritten")
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf8")
    return receipt
