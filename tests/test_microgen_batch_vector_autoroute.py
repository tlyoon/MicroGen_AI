"""Production batch mapper automatically chooses local source vectors, no Gemini."""
from pathlib import Path
import os

import pymupdf as fitz
import pytest

import microgen_batch as batch
from microgen_figure_composition import sha256


def make_stage(folder: Path, *, raster=False, caption=True):
    folder.mkdir(exist_ok=True)
    pdf = fitz.open()
    page = pdf.new_page()
    page.draw_line((40, 45), (145, 90), color=(0.0, .68, .94), width=2)
    page.draw_line((32, 100), (158, 100), color=(0, 0, 0), width=2)
    if caption:
        page.insert_text((30, 150), "FIGURE 2.34  Example graph")
    if raster:
        from PIL import Image
        import io
        image = Image.new("RGB", (18, 18), "blue")
        bytes_out = io.BytesIO()
        image.save(bytes_out, format="PNG")
        page.insert_image(fitz.Rect(190, 70, 220, 100), stream=bytes_out.getvalue())
    pdf.save(folder / "source.pdf")
    pdf.close()
    crop = folder / "pages" / "page_1"
    crop.mkdir(parents=True)
    (crop / "fig_1.png").write_bytes(b"synthetic docling crop marker")
    return folder


@pytest.mark.parametrize("raster,caption,local", [
    (False, True, True),
    (False, False, True),
    (True, True, False),
])
def test_autoroute_classifies_vector_only_vs_raster(monkeypatch, tmp_path,
                                                     raster, caption, local):
    stage = make_stage(tmp_path / "stage", raster=raster, caption=caption)
    monkeypatch.setattr(batch, "source_page_extraction_valid", lambda _: True)
    before = sha256(stage / "source.pdf")
    py, command, label, offline = batch.select_figure_mapping_command(
        stage, "python", offline_requested=False)
    assert py == "python"
    assert offline is local
    assert command == ("microgen_offline_pdf_figure_map.py" if local
                       else "map_and_rename_v5.py")
    assert sha256(stage / "source.pdf") == before
    assert not (stage / "figure_composition_receipt.json").exists()


def test_user_requested_offline_mapping_never_selects_gemini(tmp_path):
    stage = make_stage(tmp_path / "stage", raster=True)
    assert batch.select_figure_mapping_command(
        stage, "python", offline_requested=True)[-1] is True


def test_missing_or_unverified_extraction_cannot_pretend_vector_ready(tmp_path):
    stage = make_stage(tmp_path / "stage")
    assert batch.source_vector_only_mapping_candidate(stage) is False


def test_actual_thomas_private_source_selects_local_mapper_and_preserves_mapping():
    root = Path(os.environ.get("LOCALAPPDATA", "/nonexistent")) / "MicroGen_AI_Checkpoints"
    stage = root / "20261121_HP_THOMAS25_V71_PRIVATE" / "2.5"
    if not (stage / ".microgen_vector_source_mapping.json").is_file():
        pytest.skip("The private HP Thomas checkpoint is not on this host")
    before = sha256(stage / "source.pdf")
    assert batch.source_vector_only_mapping_candidate(stage)
    result = batch.select_figure_mapping_command(
        stage, "python", offline_requested=False)
    assert result[1] == "microgen_offline_pdf_figure_map.py"
    assert result[3] is True
    # This historical mapping was sealed under the PREVIOUS exact proposer
    # code SHA. New, repaired code must not re-accept the old crop implicitly:
    # the next private campaign regenerates source pixels from scratch.
    assert batch.stage_valid(stage, "figure_mapping", stage.parent) is False
    assert sha256(stage / "source.pdf") == before


def test_slide_preflight_enforces_actual_formal_figure_coverage(tmp_path):
    from microgen_vector_region_proposals import propose_regions, PROPOSAL_DIR
    from microgen_vector_proposal_qa import screen_vector_proposals
    from microgen_vector_technical_mapping import promote_vector_technical_mapping
    stage = make_stage(tmp_path / "stage")
    receipt = propose_regions(stage)
    assert len(receipt["proposals"]) == 1
    assert screen_vector_proposals(stage)["structural_screen_passed"]
    assert promote_vector_technical_mapping(stage)["figure_count"] == 1
    proof = batch.verify_vector_source_coverage_before_slides(stage)
    assert proof["figure_count"] == 1
    assert proof["receipt_sha256"]
    original_source = sha256(stage / "source.pdf")
    (stage / PROPOSAL_DIR / "Figure 2.34.png").write_bytes(b"tampered")
    with pytest.raises(Exception):
        batch.verify_vector_source_coverage_before_slides(stage)
    assert sha256(stage / "source.pdf") == original_source


def test_absent_vector_mapping_receipt_cannot_be_interpreted_as_accepted(tmp_path):
    stage = make_stage(tmp_path / "stage")
    assert batch.verify_vector_source_coverage_before_slides(stage) is None
