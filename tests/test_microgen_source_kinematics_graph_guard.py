"""Independent G3 source vector calculus graph interpretation (not model guess).

The true original six-panel Serway §2.7 source figure is tested only in
opt-in HP private regression. Original PDF, failed campaigns and all old
accepted media are never mutated.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil

import pymupdf
import pytest

from microgen_source_kinematics_graph_guard import (
    SourceGraphError,
    _source_match,
    auto_repair_source_graph_reasoning,
    require_graph_source_evidence,
    verify_source_graph_repair,
)


def test_unrecognized_source_graph_abstains_without_forged_claim(tmp_path):
    pdf=pymupdf.open()
    page=pdf.new_page()
    page.insert_text((30,80),"A general source without six-panel matching")
    pdf.save(tmp_path/"source.pdf")
    pdf.close()
    (tmp_path/"slides.tex").write_text(
        "\\begin{document}\nRandom unrelated drawing.\n\\end{document}\n",
        encoding="utf8")
    original=(tmp_path/"slides.tex").read_bytes()
    assert _source_match(tmp_path) is None
    assert auto_repair_source_graph_reasoning(tmp_path) is None
    assert require_graph_source_evidence(tmp_path) is None
    assert (tmp_path/"slides.tex").read_bytes()==original


@pytest.mark.skipif(not os.getenv("MICROGEN_REAL_G3_SECTION27_STAGE"),
    reason="Requires private exact SHA bound source plus authentic failed PDF deck")
def test_actual_source_vectors_correct_graph_matching_and_verify(tmp_path):
    old=Path(os.environ["MICROGEN_REAL_G3_SECTION27_STAGE"])
    stage=tmp_path/"stage";stage.mkdir()
    for filename in ("source.pdf","slides.tex"):
        shutil.copy2(old/filename,stage/filename)
    before_source=hashlib.sha256((stage/"source.pdf").read_bytes()).hexdigest()
    assert before_source=="03676ed9dc5ded9e07874902c5e2d3689d4293cdc086b9819003770310293102"
    figure=_source_match(stage)
    assert figure is not None
    assert figure["panel_shapes"]=={
        "a":"linear_positive","b":"convex_positive",
        "c":"rise_then_flat","d":"linear_positive",
        "e":"flat_positive","f":"step_positive_zero"}
    assert figure["matching"]=={"a":"e","b":"d","c":"f"}
    with pytest.raises(SourceGraphError,match="SOURCE_GRAPH_REASONING_UNVERIFIED"):
        require_graph_source_evidence(stage)
    previous=(stage/"slides.tex").read_text("utf8")
    assert "Graph (b) has zero slope" in previous
    assert "Graph (c) has a constant negative slope" in previous
    proof=auto_repair_source_graph_reasoning(stage)
    assert proof["matching"]=={"a":"e","b":"d","c":"f"}
    assert require_graph_source_evidence(stage)==proof
    assert verify_source_graph_repair(stage)==proof
    assert auto_repair_source_graph_reasoning(stage)==proof
    tex=(stage/"slides.tex").read_text("utf8")
    assert tex.count(r"\item Graph (")==3
    assert "increasing positive slope" in tex
    assert "positive then zero acceleration" in tex
    assert "constant negative slope" not in tex
    assert "zero slope throughout" not in tex
    assert hashlib.sha256((stage/"source.pdf").read_bytes()).hexdigest()==before_source
    evidence=json.loads((stage/".microgen_source_kinematic_graph_audit.json").read_text("utf8"))
    assert evidence["independent_scientific_qa_required"] is True
    assert evidence["publication_allowed"] is False


@pytest.mark.skipif(not os.getenv("MICROGEN_REAL_G3_SECTION27_STAGE"),
    reason="Requires private exact SHA bound source plus authentic failed PDF deck")
def test_source_derivative_attestation_rejects_tampered_result(tmp_path):
    old=Path(os.environ["MICROGEN_REAL_G3_SECTION27_STAGE"])
    stage=tmp_path/"stage";stage.mkdir()
    for name in ("source.pdf","slides.tex"):
        shutil.copy2(old/name,stage/name)
    auto_repair_source_graph_reasoning(stage)
    path=stage/".microgen_source_kinematic_graph_audit.json"
    original=path.read_bytes()
    rec=json.loads(original)
    rec["source_derivative_matching"]["b"]="f"
    path.write_text(json.dumps(rec),encoding="utf8")
    with pytest.raises(SourceGraphError,match="changed"):
        verify_source_graph_repair(stage)
    path.write_bytes(original)
    assert verify_source_graph_repair(stage)
    tex=stage/"slides.tex"
    content=tex.read_text("utf8")
    tex.write_text(content.replace("increasing positive slope",
                                   "negative slope"),encoding="utf8")
    with pytest.raises(SourceGraphError,match="changed"):
        require_graph_source_evidence(stage)
