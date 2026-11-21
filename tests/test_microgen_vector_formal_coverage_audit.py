"""Prose references and lettered subpanels are not absent formal source figures."""
import json
import os
from pathlib import Path

import pytest

from microgen_source_figure_coverage import build_current_figure_coverage, FigureCoverageError


def real_stage():
    root = Path(os.environ.get("LOCALAPPDATA", "/missing")) / "MicroGen_AI_Checkpoints"
    stage = root / "THOMAS25_PRIVATE_ACCEPTANCE_20261122" / "2.5"
    if not (stage / ".microgen_vector_source_mapping.json").is_file():
        pytest.skip("HP Thomas source-vector private campaign unavailable")
    return stage


def test_real_thomas_formal_caption_coverage_excludes_prose_and_subpanels(tmp_path):
    stage = real_stage()
    output = tmp_path / "review"
    result = build_current_figure_coverage(stage, output)
    assert result["mapped"] == 15
    assert result["source_labels_unmapped"] == 0
    receipt = json.loads((output / "figure_coverage_receipt.json").read_text("utf-8"))
    assert receipt["recognized_vector_formal_caption_mapping_verified"] is True
    assert receipt["source_labels_unmapped"] == []
    assert set(receipt["unmapped_prose_or_panel_mentions_advisory"]) == {
        "1.10", "2.40a", "2.40b", "2.40c",
        "2.40d", "2.40e", "2.40f",
    }
    assert receipt["figure_semantics_verified"] is False
    assert receipt["source_figure_reference_coverage_academically_verified"] is False
    assert receipt["publication_allowed"] is False


@pytest.mark.parametrize("fault", ["tamper", "wrong_count", "wrong_page"])
def test_invalid_source_pinned_vector_receipt_cannot_claim_formal_coverage(
        tmp_path, monkeypatch, fault):
    stage = real_stage()
    import microgen_vector_technical_mapping as mapping
    original = mapping.verify_vector_technical_mapping

    def faulty(s):
        if fault == "tamper":
            raise ValueError("forged PNG source hash")
        result = original(s).copy()
        if fault == "wrong_count":
            result["figure_count"] = 14
        else:
            rows = [dict(r) for r in result["figures"]]
            rows[0]["source_page"] = 11
            result["figures"] = rows
        return result

    monkeypatch.setattr(mapping, "verify_vector_technical_mapping", faulty)
    out = tmp_path / "should-not-appear"
    with pytest.raises(FigureCoverageError, match="formal caption proof|disagree"):
        build_current_figure_coverage(stage, out)
    assert not out.exists()
