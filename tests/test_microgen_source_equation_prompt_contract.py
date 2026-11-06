"""Prevent regression of the source-safe equation layout prompt contract."""
from pathlib import Path


PROMPT=Path(__file__).resolve().parents[1]/"gen_slides_prompt_v20_hybrid.txt"


def test_long_numerical_equalities_must_be_broken_into_safe_lines():
    text=PROMPT.read_text(encoding="utf8")
    assert "long equality chain" in text
    assert "source-equivalent line breaks" in text
    assert "aligned/align*" in text
    assert "Beamer text width" in text
    assert "page-boundary and overflow acceptance" in text


def test_layout_does_not_authorize_algebraic_omissions():
    text=PROMPT.read_text(encoding="utf8")
    for required in ("every original sign", "denominator", "unit",
                     "square-root grouping", "Never shorten an expression",
                     "source number", "crop an equation"):
        assert required in text
