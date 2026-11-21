"""Independent structural crop-boundary checks, no science acceptance."""
import json
import pytest
import pymupdf as fitz

from microgen_figure_composition import sha256
from microgen_vector_region_proposals import PROPOSAL_DIR, propose_regions
from microgen_vector_proposal_qa import (
    QA_RECEIPT, VectorScreenError, screen_vector_proposals,
)

def _stage(tmp_path, *, near_caption=False):
    doc = fitz.open()
    p = doc.new_page()
    end = 143 if near_caption else 85
    p.draw_line((40, 50), (120, end), color=(0, .68, .94), width=2)
    p.insert_text((30, 160), "FIGURE 2.34  Example plot")
    doc.save(tmp_path / "source.pdf")
    doc.close()
    return tmp_path

def test_independent_qa_screen_preserves_source_and_is_restart_safe(tmp_path):
    stage = _stage(tmp_path)
    before = sha256(stage / "source.pdf")
    propose_regions(stage)
    result = screen_vector_proposals(stage)
    assert result["figures_screened"] == 1
    assert result["structural_screen_passed"] is True
    assert result["figures_flagged"] == []
    assert result["mapping_accepted"] is False
    assert result["scientific_qa_accepted"] is False
    assert result["publication_allowed"] is False
    assert result["provider_calls"] == 0
    assert screen_vector_proposals(stage) == result
    assert (stage / QA_RECEIPT).exists()
    assert sha256(stage / "source.pdf") == before

def test_edge_ink_produces_review_required_not_acceptance(tmp_path, monkeypatch):
    stage = _stage(tmp_path, near_caption=True)
    receipt = propose_regions(stage)
    assert len(receipt["proposals"]) == 1
    # Inject a proven ink-at-boundary condition. The synthetic line by itself
    # does not reliably reach the rendered PNG edge after safety padding.
    import microgen_vector_proposal_qa as vet
    monkeypatch.setattr(vet, "_ink_edge_counts", lambda _: {
        "left": 30, "right": 0, "top": 0, "bottom": 0})
    qa = screen_vector_proposals(stage)
    assert qa["figures_screened"] == 1
    assert qa["figures_flagged"] == ["2.34"]
    assert not qa["structural_screen_passed"]
    assert not qa["publication_allowed"]

def test_changed_candidate_is_rejected_even_with_existing_source(tmp_path):
    stage = _stage(tmp_path)
    propose_regions(stage)
    candidate = stage / PROPOSAL_DIR / "Figure 2.34.png"
    candidate.write_bytes(b"spoofed vector output")
    with pytest.raises(VectorScreenError, match="changed"):
        screen_vector_proposals(stage)

def test_existing_qa_receipt_cannot_be_overwritten(tmp_path):
    stage = _stage(tmp_path)
    propose_regions(stage)
    screen_vector_proposals(stage)
    (stage / QA_RECEIPT).write_text("{}", encoding="utf-8")
    with pytest.raises(VectorScreenError, match="differs"):
        screen_vector_proposals(stage)
