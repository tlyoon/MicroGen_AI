"""Independent, resumable second original-PDF pilot readiness gate.

Read-only against original textbook and campaign stage. No provider, TTS,
recognition, publication, or inferred multimedia acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from microgen_batch import source_page_extraction_valid
from microgen_source_pdf_intake import create_intake_receipt, SourcePDFIntakeError


class SourceCampaignAcceptanceError(ValueError):
    pass


def sha(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def _read_json(file: Path) -> dict:
    if not file.is_file() or file.is_symlink():
        raise SourceCampaignAcceptanceError(f"Missing or unsafe evidence: {file.name}")
    raw = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SourceCampaignAcceptanceError("Invalid source-bound evidence schema")
    return raw


def verify_source_campaign(source_pdf: Path, stage: Path, output: Path,
                           *, expected_commit: str | None = None) -> dict:
    """Prove original-source immutable extraction and identify provider gate."""
    original = Path(source_pdf)
    scratch = Path(stage)
    target = Path(output)
    if (original.is_symlink() or not original.is_file() or
            scratch.is_symlink() or not scratch.is_dir() or
            target.is_symlink() or target == scratch or
            target.resolve(strict=False).is_relative_to(scratch.resolve(strict=True))
            or scratch.resolve(strict=True).is_relative_to(target.resolve(strict=False))):
        raise SourceCampaignAcceptanceError("Protected source and external QA paths required")
    original_hash = sha(original)
    staged = scratch / "source.pdf"
    if not staged.is_file() or staged.is_symlink() or sha(staged) != original_hash:
        raise SourceCampaignAcceptanceError("Scratch PDF differs from original textbook")
    if not source_page_extraction_valid(scratch):
        raise SourceCampaignAcceptanceError("Incomplete or tampered Docling page evidence")
    figures = _read_json(scratch / "figure_extraction_receipt.json")
    checkpoint = _read_json(scratch / ".microgen_checkpoint.json")
    extraction_at = checkpoint.get("completed", {}).get("figure_extraction")
    if (not isinstance(extraction_at, str) or not extraction_at or
            figures.get("gemini_invoked") is not False or
            figures.get("tts_invoked") is not False or
            figures.get("publication_allowed") is not False or
            checkpoint.get("source_signature", {}).get("size") != original.stat().st_size):
        raise SourceCampaignAcceptanceError("Source-only stage/contract not confirmed")
    code_commit = checkpoint.get("package_commit")
    if expected_commit and code_commit != expected_commit:
        raise SourceCampaignAcceptanceError("Campaign Git commit is unpinned or mismatched")
    # The intake is generated independently of Docling from the same source PDF.
    if target.exists():
        existing = _read_json(target / "source_campaign_readiness.json")
        intake = _read_json(target / "source_intake" / "source_intake_receipt.json")
        if (existing.get("source_sha256") != original_hash or
                existing.get("figure_extraction_sha256") != sha(
                    scratch / "figure_extraction_receipt.json") or
                existing.get("source_intake_sha256") != sha(
                    target / "source_intake" / "source_intake_receipt.json") or
                existing.get("stage_checkpoint_sha256") != sha(
                    scratch / ".microgen_checkpoint.json") or
                intake.get("source_pdf_sha256") != original_hash or
                sha(target / "source_intake" / "figure_geometry.json") !=
                intake.get("figure_evidence_sha256") or
                sha(target / "source_intake" / "equation_geometry.json") !=
                intake.get("math_evidence_sha256") or
                existing.get("publication_allowed") is not False or
                existing.get("gemini_or_tts_invoked") is not False):
            raise SourceCampaignAcceptanceError("Existing QA receipt mismatches source or evidence")
        return existing
    if target.parent.resolve(strict=False).is_relative_to(
            original.parent.resolve(strict=True)):
        raise SourceCampaignAcceptanceError("QA output must remain outside original textbook")
    # Create external report folder. A source failure leaves originals untouched.
    target.mkdir(parents=True, exist_ok=False)
    try:
        intake = create_intake_receipt(scratch, target / "source_intake")
        if (intake["source_pdf_sha256"] != original_hash or
                intake["page_count"] != figures["page_count"] or
                intake["source_text_readiness"] != "SOURCE_TEXT_READY" or
                sha(original) != original_hash or sha(staged) != original_hash):
            raise SourceCampaignAcceptanceError("Independent PDF intake is not source-ready")
        artifact = {
            "schema_version": 1,
            "status": "SOURCE_ONLY_STAGE_COMPLETE_PROVIDER_DEPENDENT_STAGES_PENDING",
            "source_original": str(original),
            "source_stage": str(scratch),
            "source_sha256": original_hash,
            "source_pages": figures["page_count"],
            "docling_extracted_figures": sum(len(x["figures"]) for x in figures["pages"]),
            "source_geometry_figure_candidates": intake["source_figure_candidates"],
            "source_geometry_math_line_candidates": intake["source_math_line_candidates"],
            "source_readiness": intake["source_text_readiness"],
            "figure_extraction_sha256": sha(scratch / "figure_extraction_receipt.json"),
            "source_intake_sha256": sha(target / "source_intake" / "source_intake_receipt.json"),
            "stage_checkpoint_sha256": sha(scratch / ".microgen_checkpoint.json"),
            "campaign_code_commit": code_commit,
            "code_commit_pinned": bool(code_commit and code_commit != "unknown"),
            "next_stage": "figure_mapping",
            "next_stage_uses_gemini": True,
            "slides_and_narration_use_gemini": True,
            "tts_requires_cloud_provider": True,
            "provider_authorized_by_this_report": False,
            "gemini_or_tts_invoked": False,
            "generated_slides": False,
            "generated_narration": False,
            "generated_wavs": False,
            "generated_mp4s": False,
            "second_end_to_end_generation_passed": False,
            "mathematics_verified": False,
            "phonetic_accuracy_verified": False,
            "element_level_synchronization_verified": False,
            "publication_allowed": False,
        }
        f = target / "source_campaign_readiness.json"
        with f.open("x", encoding="utf-8") as handle:
            json.dump(artifact, handle, indent=2, sort_keys=True)
        return artifact
    except Exception:
        # A failed local QA should never erase original data or prior stages.
        import shutil
        shutil.rmtree(target)
        raise


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-pdf", type=Path, required=True)
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--new-report-directory", type=Path, required=True)
    p.add_argument("--expected-commit")
    args = p.parse_args()
    result = verify_source_campaign(args.source_pdf, args.stage,
        args.new_report_directory, expected_commit=args.expected_commit)
    print(json.dumps({k:result[k] for k in (
        "status","source_pages","docling_extracted_figures",
        "source_geometry_figure_candidates","next_stage",
        "second_end_to_end_generation_passed","publication_allowed")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
