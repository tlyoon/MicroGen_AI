"""Synthetic superscript/body-block vs PDF line reflow regression tests."""
import json
import tempfile
from pathlib import Path

import pytest

from microgen_portable_private_authoring_gate import (
    AuthoringGateError,_line_safe_source_anchor,write_validated_stage)
from test_microgen_portable_private_authoring_gate import construct


def test_source_superscript_merge_trim_restores_unambiguous_real_sentence_prefix():
    source=("Therefore, a person takes on the order of 109 breaths in a lifetime. "
            "That is a rough approximation.")
    pdf_lines=("Therefore, a person takes on the order of 10 9 breaths in a lifetime. "
               "That is a rough approximation.")
    original=source[:61]
    candidate,repaired=_line_safe_source_anchor(original,source,pdf_lines)
    assert repaired
    assert candidate.startswith("Therefore, a person takes on")
    assert "109" not in candidate
    assert len(candidate)>=24
    assert candidate in source
    assert candidate in pdf_lines
    assert original!=candidate


def test_exact_source_line_anchor_preserved_and_no_repair_claimed():
    source="A model of the system is used to compare measured data and expected behavior."
    anchor="A model of the system is used"
    corrected,repaired=_line_safe_source_anchor(anchor,source,source)
    assert corrected==anchor and repaired is False


@pytest.mark.parametrize("source,line,anchor",[
    ("A model describes forces.", "A model describes forces.", "Source about photons."),
    ("The model gives a speed 109 m/s.", "The model gives a speed 10 9 m/s.",
      "109 m/s."),
    ("A model describes speed 109 m/s.", "A model describes speed 10 9 m/s. "
     "A model describes speed 10 9 m/s.", "A model describes speed 109 m/s."),
])
def test_unverified_or_ambiguous_shortening_refused(source,line,anchor):
    with pytest.raises(AuthoringGateError):
        _line_safe_source_anchor(anchor,source,line)


def test_existing_synthetic_source_authoring_still_passes_without_alteration():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);source,packet,draft=construct(root)
        original=source.read_bytes()
        out=root/"fresh"
        qa=write_validated_stage(source,packet,draft,out)
        assert qa["source_anchor_line_reflow_repair_count"]==0
        assert qa["source_anchor_line_reflow_repairs"]==[]
        assert source.read_bytes()==original
        assert (out/"contract.json").is_file()
        assert not qa["publication_allowed"]
