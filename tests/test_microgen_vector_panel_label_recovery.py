"""Real/synthetic omitted panel-key recovery; no academic approval or publication."""
import json
import os
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_figure_composition import sha256
from microgen_vector_region_proposals import (
    PROPOSAL_DIR, propose_regions,
)
from microgen_vector_proposal_qa import screen_vector_proposals


def _panel_source(stage):
    stage.mkdir(parents=True)
    pdf = fitz.open()
    page = pdf.new_page(width=599.28, height=771)
    page.draw_line((40, 60), (140, 110), color=(0.0, .68, .94), width=2)
    page.draw_line((32, 140), (166, 140), color=(0, 0, 0), width=1)
    page.insert_text((94, 198), "(b)")
    page.insert_text((24, 234), "FIGURE 2.48  Source graph panel")
    pdf.save(stage / "source.pdf")
    pdf.close()
    return stage


def test_panel_key_below_white_edge_is_preserved_in_private_source_crop(tmp_path):
    stage = _panel_source(tmp_path / "private")
    original = sha256(stage / "source.pdf")
    report = propose_regions(stage)
    assert len(report["proposals"]) == 1
    candidate = report["proposals"][0]
    assert candidate["label"] == "2.48"
    assert candidate["source_clip_bbox"][3] > 198
    assert candidate["source_clip_bbox"][3] <= candidate["caption_bbox"][1] - 2.9
    qa = screen_vector_proposals(stage)
    assert qa["structural_screen_passed"]
    assert qa["figures_flagged"] == []
    assert qa["findings"][0]["missing_source_panel_labels"] == []
    assert qa["publication_allowed"] is False
    assert qa["scientific_qa_accepted"] is False
    assert sha256(stage / "source.pdf") == original


def test_independent_qa_detects_missing_panel_key_even_with_clean_image_edges(tmp_path):
    stage = _panel_source(tmp_path / "private")
    receipt = propose_regions(stage)
    path = stage / PROPOSAL_DIR / "proposal_receipt.json"
    assert receipt["proposals"][0]["source_clip_bbox"][3] > 198
    receipt["proposals"][0]["source_clip_bbox"][3] = 175
    path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    qa = screen_vector_proposals(stage)
    assert qa["figures_flagged"] == ["2.48"]
    assert qa["findings"][0]["missing_source_panel_labels"][0]["label"] == "(b)"
    assert qa["mapping_accepted"] is False
    assert qa["publication_allowed"] is False


def test_actual_thomas_248_recovery_and_old_clip_fault_injection(tmp_path):
    root = Path(os.environ.get("LOCALAPPDATA", "/missing")) / "MicroGen_AI_Checkpoints"
    source = root / "20261121_HP_THOMAS25_V71_PRIVATE" / "2.5" / "source.pdf"
    if not source.is_file():
        pytest.skip("Actual private Thomas 2.5 source is unavailable on this host")
    import shutil
    stage = tmp_path / "private"
    stage.mkdir()
    shutil.copy2(source, stage / "source.pdf")
    original = sha256(source)
    receipt = propose_regions(stage)
    qa = screen_vector_proposals(stage)
    assert len(receipt["proposals"]) == 15 and qa["figures_flagged"] == []
    fig = next(row for row in receipt["proposals"] if row["label"] == "2.48")
    assert fig["source_clip_bbox"][3] > 622.6
    manifest = stage / PROPOSAL_DIR / "proposal_receipt.json"
    fig["source_clip_bbox"][3] = 612.17
    manifest.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    # In this *disposable test fixture* remove the first QA receipt so the
    # independent QA can screen a separately forged input. Production
    # intentionally refuses to overwrite an existing immutable receipt.
    from microgen_vector_proposal_qa import QA_RECEIPT
    (stage / QA_RECEIPT).unlink()
    rejected = screen_vector_proposals(stage)
    result = next(row for row in rejected["findings"] if row["label"] == "2.48")
    assert result["boundary_review_required"]
    assert any(row["label"] == "(b)" for row in result["missing_source_panel_labels"])
    assert rejected["publication_allowed"] is False
    assert sha256(stage / "source.pdf") == original == sha256(source)
