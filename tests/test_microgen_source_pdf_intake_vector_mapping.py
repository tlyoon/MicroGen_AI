"""Source intake cannot confuse generic vector geometry with formal caption coverage."""
import json
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_source_pdf_intake import (
    SourcePDFIntakeError, create_intake_receipt,
)
from microgen_vector_region_proposals import propose_regions, PROPOSAL_DIR
from microgen_vector_proposal_qa import screen_vector_proposals
from microgen_vector_technical_mapping import promote_vector_technical_mapping
from microgen_figure_composition import sha256


def _make_source(root: Path, *, duplicate=False):
    source_dir = root / "original"
    source_dir.mkdir()
    doc = fitz.open()
    for n in range(2 if duplicate else 1):
        page = doc.new_page(width=600, height=770)
        page.insert_text((30, 35),
                         "Continuity of a function and the value of the limit near a point")
        page.draw_line((45, 50), (145, 95), color=(0, .68, .94), width=2)
        page.draw_line((30, 110), (155, 110), color=(0, 0, 0), width=1)
        page.insert_text((25, 170), "FIGURE 2.34  Continuity graph")
        page.insert_text((215, 270), "See Figure 2.34 for an explanation of the graph.")
    doc.save(source_dir / "source.pdf")
    doc.close()
    return source_dir


def test_formal_source_figure_without_verified_mapping_holds_slide_intake(tmp_path):
    source = _make_source(tmp_path)
    original = sha256(source / "source.pdf")
    info = create_intake_receipt(source, tmp_path / "unmapped")
    assert info["formal_source_figure_count"] == 1
    assert info["verified_private_vector_figure_count"] == 0
    assert info["technical_figure_mapping_complete"] is False
    assert info["next_action"] == "VERIFY_SOURCE_FIGURE_MAPPING_BEFORE_SLIDES"
    assert info["figure_caption_semantics_verified"] is False
    assert info["publication_allowed"] is False
    assert sha256(source / "source.pdf") == original


def test_verified_vector_source_has_complete_mapping_not_generic_only(tmp_path):
    source = _make_source(tmp_path)
    proposal = propose_regions(source)
    assert len(proposal["proposals"]) == 1
    assert screen_vector_proposals(source)["structural_screen_passed"]
    assert promote_vector_technical_mapping(source)["figure_count"] == 1
    original = sha256(source / "source.pdf")
    info = create_intake_receipt(source, tmp_path / "verified")
    assert info["formal_source_figure_count"] == 1
    assert info["verified_private_vector_figure_count"] == 1
    assert info["technical_figure_mapping_complete"] is True
    assert info["private_vector_mapping_receipt_sha256"]
    assert info["next_action"] == "PROCEED_TO_GROUNDED_SLIDES_AND_NARRATION"
    assert info["source_math_correctness_verified"] is False
    assert info["figure_caption_semantics_verified"] is False
    assert info["publication_allowed"] is False
    assert sha256(source / "source.pdf") == original


def test_tampered_vector_map_fails_closed_and_writes_no_intake(tmp_path):
    source = _make_source(tmp_path)
    propose_regions(source)
    assert screen_vector_proposals(source)["structural_screen_passed"]
    promote_vector_technical_mapping(source)
    receipt = source / ".microgen_vector_source_mapping.json"
    original_pdf_sha = sha256(source / "source.pdf")
    tampered = json.loads(receipt.read_text("utf-8"))
    tampered["source_pdf_sha256"] = "0" * 64
    receipt.write_text(json.dumps(tampered), encoding="utf-8")
    output = tmp_path / "tamper-intake"
    with pytest.raises(SourcePDFIntakeError, match="Untrusted"):
        create_intake_receipt(source, output)
    assert not output.exists()
    assert sha256(source / "source.pdf") == original_pdf_sha


def test_duplicate_formal_caption_fails_closed_even_if_generic_geometry_exists(tmp_path):
    source = _make_source(tmp_path, duplicate=True)
    output = tmp_path / "duplicate-intake"
    with pytest.raises(SourcePDFIntakeError, match="Duplicate formal"):
        create_intake_receipt(source, output)
    assert not output.exists()
