"""Fail-closed future missing textbook vector figure recovery tests."""
import json
from pathlib import Path
from microgen_quality import QualityError
import pymupdf
import pytest
from microgen_missing_source_figure_candidates import (
    SourceFigureRecoveryError,missing_slide_figures,_label,
    propose_missing_figures,check_graphics_with_source_candidates)


def synthetic_source(tmp_path):
    pdf=pymupdf.open();p=pdf.new_page(width=595,height=842)
    shape=p.new_shape()
    shape.draw_line((80,110),(80,210))
    shape.draw_line((80,210),(190,210))
    shape.draw_line((135,210),(135,150))
    shape.finish(color=(0,0,0));shape.commit()
    p.insert_text((75,245),"FIGURE 2.38")
    pdf.save(tmp_path/"source.pdf");pdf.close()
    (tmp_path/"slides.tex").write_text(
        r"\includegraphics[width=.8\textwidth]{Figure 2.38.png}")
    return tmp_path


def test_real_missing_reference_generates_unapproved_source_regions(tmp_path):
    base=synthetic_source(tmp_path)
    assert missing_slide_figures(base)==["Figure 2.38.png"]
    dest=tmp_path.parent/"new_candidates"
    out=propose_missing_figures(base,dest)
    assert out["requested"]==1 and out["candidates"]>=1
    receipt=json.loads((dest/"recovery_candidates_receipt.json").read_text())
    assert receipt["publication_allowed"] is False
    assert receipt["source_crop_accepted"] is False
    assert all((dest/x["name"]).is_file() for x in receipt["images"])
    assert not (base/"Figure 2.38.png").exists()


def test_graphics_fail_still_preserves_candidates_without_auto_repair(tmp_path):
    base=synthetic_source(tmp_path)
    with pytest.raises((ValueError,FileNotFoundError,QualityError)):
        check_graphics_with_source_candidates(base/"slides.tex")
    assert (base/".microgen_missing_source_figures_review"/
            "recovery_candidates_receipt.json").is_file()
    assert not (base/"Figure 2.38.png").exists()


@pytest.mark.parametrize("n,expected",[
    ("../../Figure 2.38.png",None),("foo.pdf",None),
    ("Figure 2.38.png","2.38"),("Figure 0.0a.png","0.0a")])
def test_unsafe_and_nonnumeric_names(n,expected):
    assert _label(n)==expected


def test_missing_textbook_caption_is_rejected(tmp_path):
    base=synthetic_source(tmp_path)
    (base/"slides.tex").write_text(r"\includegraphics{Figure 2.39.png}")
    with pytest.raises(SourceFigureRecoveryError):
        propose_missing_figures(base,tmp_path.parent/"unused_candidate")
