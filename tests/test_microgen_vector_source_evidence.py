"""Fault-injection tests for real-source vector-only diagnostic recovery."""
import json
import pymupdf as fitz
import pytest

from microgen_vector_source_evidence import inspect_vector_source, record_vector_blocker

def _vector_stage(tmp_path, *, caption="FIGURE 2.34  Source graph"):
    page_dir = tmp_path / "pages" / "page_1"
    page_dir.mkdir(parents=True)
    (page_dir / "fig_1.png").write_bytes(b"immutable crop candidate")
    doc = fitz.open()
    page = doc.new_page()
    page.draw_line((20, 20), (110, 90))
    page.insert_text((30, 120), caption)
    doc.save(tmp_path / "source.pdf")
    doc.close()
    return tmp_path

def test_vector_source_evidence_is_diagnostic_not_approval(tmp_path):
    stage = _vector_stage(tmp_path)
    original = (stage / "source.pdf").read_bytes()
    receipt = inspect_vector_source(stage)
    assert receipt["formal_caption_count"] == 1
    assert receipt["cropped_region_count"] == 1
    assert receipt["pages"][0]["embedded_raster_count"] == 0
    assert receipt["pages"][0]["vector_drawing_count"] >= 1
    assert receipt["mapping_accepted"] is False
    assert receipt["publication_allowed"] is False
    target = record_vector_blocker(stage)
    assert json.loads(target.read_text())["source_pdf_sha256"] == receipt["source_pdf_sha256"]
    assert (stage / "source.pdf").read_bytes() == original
    assert record_vector_blocker(stage) == target
    assert sorted(stage.glob("offline_vector_mapping_blocker*.json")) == [target]

def test_duplicate_caption_numbers_fail_closed(tmp_path):
    stage = _vector_stage(tmp_path)
    with fitz.open(stage / "source.pdf") as old:
        doc = fitz.open()
        doc.insert_pdf(old)
        page = doc.new_page()
        page.insert_text((30, 120), "FIGURE 2.34 another caption")
        doc.save(stage / "other.pdf")
        doc.close()
    (stage / "source.pdf").unlink()
    (stage / "other.pdf").rename(stage / "source.pdf")
    receipt = inspect_vector_source(stage)
    assert receipt["duplicate_caption_numbers"] == ["2.34"]
    assert receipt["mapping_accepted"] is False

def test_prose_reference_is_not_formal_caption(tmp_path):
    stage = _vector_stage(tmp_path, caption="Figure 2.34 is discussed here.")
    receipt = inspect_vector_source(stage)
    assert receipt["formal_caption_count"] == 0
    # Only formal uppercase labels count; narrative references are not captions.
    with fitz.open(stage / "source.pdf") as old:
        doc = fitz.open()
        doc.insert_pdf(old)
        page = doc[0]
        page.insert_text((30, 160), "See Figure 2.35 for the next result")
        doc.save(stage / "modified.pdf")
        doc.close()
    (stage / "source.pdf").unlink()
    (stage / "modified.pdf").rename(stage / "source.pdf")
    assert inspect_vector_source(stage)["formal_caption_count"] == 0

def test_changed_source_creates_versioned_receipt_without_overwrite(tmp_path):
    stage = _vector_stage(tmp_path)
    original_path = record_vector_blocker(stage)
    original_bytes = original_path.read_bytes()
    with fitz.open(stage / "source.pdf") as old:
        doc = fitz.open()
        doc.insert_pdf(old)
        doc[0].insert_text((30, 160), "FIGURE 2.35 another graph")
        doc.save(stage / "changed.pdf")
        doc.close()
    (stage / "source.pdf").unlink()
    (stage / "changed.pdf").rename(stage / "source.pdf")
    successor = record_vector_blocker(stage)
    assert successor != original_path
    assert original_path.read_bytes() == original_bytes
    assert json.loads(successor.read_text())["formal_caption_count"] == 2
    assert record_vector_blocker(stage) == successor
