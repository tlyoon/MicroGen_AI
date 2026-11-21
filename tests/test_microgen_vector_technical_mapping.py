"""Technical source-geometry mapping is restart-safe and never a science approval."""
import json
import pymupdf as fitz
import pytest

from microgen_figure_composition import sha256
from microgen_vector_region_proposals import propose_regions, PROPOSAL_DIR
from microgen_vector_proposal_qa import screen_vector_proposals
from microgen_vector_technical_mapping import (
    RECEIPT_NAME, STAGING, VectorMappingError,
    promote_vector_technical_mapping, verify_vector_technical_mapping,
)


def _stage(tmp_path):
    source = fitz.open()
    page = source.new_page()
    page.draw_line((45, 50), (145, 95), color=(0, .68, .94), width=2)
    page.draw_line((30, 110), (155, 110), color=(0, 0, 0), width=1)
    page.insert_text((25, 170), "FIGURE 2.34  Continuity graph")
    source.save(tmp_path / "source.pdf")
    source.close()
    return tmp_path


def _prepare(stage):
    proposals = propose_regions(stage)
    assert len(proposals["proposals"]) == 1
    screen = screen_vector_proposals(stage)
    assert screen["structural_screen_passed"] is True
    return proposals


def test_technical_promotion_is_source_bound_and_not_academic(tmp_path):
    stage = _stage(tmp_path)
    _prepare(stage)
    before = sha256(stage / "source.pdf")
    result = promote_vector_technical_mapping(stage)
    assert result["source_geometry_mapping_verified"] is True
    assert result["figure_count"] == 1
    assert result["scientific_qa_accepted"] is False
    assert result["publication_allowed"] is False
    assert result["provider_calls"] == 0
    assert (stage / "Figure 2.34.png").is_file()
    assert (stage / "figure_composition_receipt.json").is_file()
    assert (stage / RECEIPT_NAME).is_file()
    assert verify_vector_technical_mapping(stage) == result
    assert promote_vector_technical_mapping(stage) == result
    assert sha256(stage / "source.pdf") == before


def test_existing_wrong_figure_is_immutable(tmp_path):
    stage = _stage(tmp_path)
    _prepare(stage)
    output = stage / "Figure 2.34.png"
    output.write_bytes(b"user owned image")
    with pytest.raises(VectorMappingError, match="Existing figure is different"):
        promote_vector_technical_mapping(stage)
    assert output.read_bytes() == b"user owned image"
    assert not (stage / RECEIPT_NAME).exists()


def test_changed_technical_image_or_receipt_is_rejected(tmp_path):
    stage = _stage(tmp_path)
    _prepare(stage)
    promote_vector_technical_mapping(stage)
    image = stage / "Figure 2.34.png"
    image.write_bytes(b"tamper")
    with pytest.raises(Exception):
        verify_vector_technical_mapping(stage)


def test_changed_source_and_candidate_are_rejected(tmp_path):
    stage = _stage(tmp_path)
    _prepare(stage)
    proposed = stage / PROPOSAL_DIR / "Figure 2.34.png"
    proposed.write_bytes(b"changed")
    with pytest.raises(Exception):
        promote_vector_technical_mapping(stage)


def test_partial_private_output_can_be_resumed_without_overwrite(tmp_path):
    stage = _stage(tmp_path)
    _prepare(stage)
    import microgen_vector_technical_mapping as module
    original = module.validate_figure_receipt
    calls = 0
    def interrupted(directory):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("simulated crash before release")
        return original(directory)
    # First stage has no published figure; a crash cannot mark mapped.
    with pytest.raises(RuntimeError):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(module, "validate_figure_receipt", interrupted)
            promote_vector_technical_mapping(stage)
    assert not (stage / RECEIPT_NAME).exists()
    done = promote_vector_technical_mapping(stage)
    assert done["source_geometry_mapping_verified"] is True
    assert done["publication_allowed"] is False


def test_reject_unapproved_qa_report(monkeypatch, tmp_path):
    stage = _stage(tmp_path)
    _prepare(stage)
    import microgen_vector_technical_mapping as module
    original = module.screen_vector_proposals
    def blocked(folder):
        result = original(folder).copy()
        result["structural_screen_passed"] = False
        result["figures_flagged"] = ["2.34"]
        return result
    monkeypatch.setattr(module, "screen_vector_proposals", blocked)
    with pytest.raises(VectorMappingError, match="Unaccepted"):
        promote_vector_technical_mapping(stage)
    assert not (stage / RECEIPT_NAME).exists()
