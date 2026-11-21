"""Fault injection for private, no-provider vector-region candidate extraction."""
import json
import pymupdf as fitz
import pytest

from microgen_figure_composition import sha256
from microgen_vector_region_proposals import (
    PROPOSAL_DIR, VectorProposalError, propose_regions,
)

def _source(tmp_path, *, multicolor=True, has_drawing=True, duplicate=False):
    pdf = fitz.open()
    page = pdf.new_page()
    if has_drawing:
        page.draw_line((30, 30), (135, 65), color=(0, .68, .94), width=2)
        if multicolor:
            page.draw_line((35, 90), (140, 105), color=(.93, .09, .28), width=2)
    page.insert_text((30, 160), "FIGURE 2.34  Example diagram")
    if duplicate:
        other = pdf.new_page()
        other.insert_text((30, 160), "FIGURE 2.34  Another diagram")
    pdf.save(tmp_path / "source.pdf")
    pdf.close()
    return tmp_path

def test_private_vector_candidate_is_source_bound_not_accepted(tmp_path):
    stage = _source(tmp_path)
    original = sha256(stage / "source.pdf")
    receipt = propose_regions(stage)
    assert receipt["formal_caption_count"] == 1
    assert len(receipt["proposals"]) == 1
    assert receipt["blocked"] == []
    assert receipt["mapping_accepted"] is False
    assert receipt["publication_allowed"] is False
    assert receipt["scientific_qa_accepted"] is False
    candidate = stage / PROPOSAL_DIR / "Figure 2.34.png"
    assert sha256(candidate) == receipt["proposals"][0]["png_sha256"]
    assert sha256(stage / "source.pdf") == original
    assert propose_regions(stage) == receipt

def test_png_corruption_and_source_changes_fail_closed(tmp_path):
    stage = _source(tmp_path)
    propose_regions(stage)
    candidate = stage / PROPOSAL_DIR / "Figure 2.34.png"
    original = candidate.read_bytes()
    candidate.write_bytes(b"corrupt")
    with pytest.raises(VectorProposalError, match="Unverifiable"):
        propose_regions(stage)
    candidate.write_bytes(original)
    with fitz.open(stage / "source.pdf") as old:
        pdf = fitz.open()
        pdf.insert_pdf(old)
        pdf[0].draw_line((50, 50), (150, 95), color=(0, .68, .94))
        pdf.save(stage / "modified.pdf")
        pdf.close()
    (stage / "source.pdf").unlink()
    (stage / "modified.pdf").rename(stage / "source.pdf")
    with pytest.raises(VectorProposalError, match="Unverifiable"):
        propose_regions(stage)

def test_crash_state_is_not_silently_reused(tmp_path):
    stage = _source(tmp_path)
    (stage / ("." + PROPOSAL_DIR + ".pending")).mkdir()
    with pytest.raises(VectorProposalError, match="Interrupted"):
        propose_regions(stage)

def test_duplicate_caption_does_not_create_accepted_mapping(tmp_path):
    stage = _source(tmp_path, duplicate=True)
    with pytest.raises(VectorProposalError, match="Duplicate"):
        propose_regions(stage)
    assert not (stage / PROPOSAL_DIR).exists()

def test_noncolored_figure_is_explicitly_blocked(tmp_path):
    stage = _source(tmp_path, has_drawing=False)
    receipt = propose_regions(stage)
    assert receipt["blocked"][0]["reason"] == "NO_COLOR_ANCHOR"
    assert receipt["proposals"] == []
    assert receipt["mapping_accepted"] is False

def test_production_offline_mapper_emits_candidates_but_never_accepts(monkeypatch, tmp_path):
    import microgen_offline_pdf_figure_map as mapper
    stage = _source(tmp_path)
    page = stage / "pages" / "page_1"
    page.mkdir(parents=True)
    (page / "fig_1.png").write_bytes(b"extractor produced vector fragment")
    (stage / "figure_extraction_receipt.json").write_text(
        json.dumps({"page_count": 1}), encoding="utf-8")
    monkeypatch.setattr(mapper, "source_page_extraction_valid", lambda _: True)
    before = sha256(stage / "source.pdf")
    for _ in range(2):
        with pytest.raises(mapper.OfflineFigureMapError, match="Vector-only source"):
            mapper.map_source_figures(stage)
    assert (stage / PROPOSAL_DIR / "Figure 2.34.png").is_file()
    from microgen_vector_proposal_qa import QA_RECEIPT
    qa = json.loads((stage / QA_RECEIPT).read_text("utf-8"))
    assert qa["mapping_accepted"] is False
    assert qa["scientific_qa_accepted"] is False
    assert qa["publication_allowed"] is False
    assert not (stage / "figure_composition_receipt.json").exists()
    assert not (stage / "Figure 2.34.png").exists()
    assert sha256(stage / "source.pdf") == before
    (stage / PROPOSAL_DIR / "Figure 2.34.png").write_bytes(b"tampered")
    with pytest.raises(mapper.OfflineFigureMapError, match="requires reconciliation"):
        mapper.map_source_figures(stage)

def test_sidebar_right_edge_adapts_only_when_ink_touches(tmp_path):
    pdf = fitz.open()
    page = pdf.new_page()
    page.draw_line((40, 40), (140, 80), color=(0, .68, .94), width=2)
    page.draw_line((165, 48), (165, 112), color=(0, 0, 0), width=2)
    page.insert_text((30, 160), "FIGURE 2.34  Sidebar axis")
    pdf.save(tmp_path / "source.pdf")
    pdf.close()
    report = propose_regions(tmp_path)
    assert len(report["proposals"]) == 1
    clip = report["proposals"][0]["source_clip_bbox"]
    assert clip[2] > 175, "Right-hand axis was not recovered within sidebar"
    assert report["mapping_accepted"] is False
    assert report["publication_allowed"] is False
    assert propose_regions(tmp_path) == report
