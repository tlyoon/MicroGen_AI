"""Synthetic direct original figure/equation math re-audit, no textbook assets."""
import copy
import tempfile
from pathlib import Path
import pytest

from microgen_private_original_figure_math_reaudit import audit_original_figure_math
from test_microgen_private_multisection_scientific_claim_audit import cases
from microgen_portable_slide_render import PortableSlideError
from microgen_portable_source_equations import SourceEquationError
from microgen_portable_source_math_claims import SourceMathClaimError


def input_from_case(row):
    import json
    st=Path(row["stage"]);source=Path(row["original_pdf"])
    return st,source,json.loads((st/"contract.json").read_text()),json.loads((st/"narration.json").read_text())


def test_no_figure_or_equation_has_explicit_zero_not_blanket_approval():
    with tempfile.TemporaryDirectory() as td:
        st,source,manifest,narration=input_from_case(cases(Path(td))[0])
        result=audit_original_figure_math(st,source,manifest,narration)
        assert result["original_figures_hashed"]==0
        assert result["original_source_raster_figures_checked"]==0
        assert result["source_vector_equation_crops_checked"]==0
        assert result["independently_recalculated_source_typed_math_claims"]==0
        assert result["all_math_semantics_proven"] is False
        assert result["figure_and_source_copyright_rights_cleared"] is False


def test_missing_original_image_rejected():
    with tempfile.TemporaryDirectory() as td:
        st,source,manifest,narration=input_from_case(cases(Path(td))[0])
        manifest["figures"]=[{"slide":1,"filename":"nonexistent.png",
            "sha256":"0"*64,"caption":"A mapped source figure"}]
        with pytest.raises((PortableSlideError,ValueError)):
            audit_original_figure_math(st,source,manifest,narration)


def test_unverifiable_vector_equation_crop_rejected():
    with tempfile.TemporaryDirectory() as td:
        st,source,manifest,narration=input_from_case(cases(Path(td))[0])
        manifest["source_equations"]=[{"slide":1,"source_page":1,
            "source_bbox":[10,10,25,30],"source_crop_sha256":"0"*64}]
        with pytest.raises(SourceEquationError):
            audit_original_figure_math(st,source,manifest,narration)


def test_fake_source_tangent_claim_cannot_be_approved():
    with tempfile.TemporaryDirectory() as td:
        st,source,manifest,narration=input_from_case(cases(Path(td))[0])
        manifest["source_math_claims"]=[{"slide":1,"figure_slide":2,
            "source_page":1,"formula":"right_triangle_tangent_height",
            "horizontal_distance_m":50.0,"elevation_degrees":25.0,
            "claimed_height_m":23.3,"precision_decimals":1,
            "source_figure_text_terms":["50.0 m","25.0"],
            "source_equation_answer_text":"23.3 m"}]
        with pytest.raises(SourceMathClaimError):
            audit_original_figure_math(st,source,manifest,narration)
