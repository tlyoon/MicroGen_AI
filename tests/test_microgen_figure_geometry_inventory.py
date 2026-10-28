import pytest
import pymupdf as fitz
from microgen_figure_geometry_inventory import figure_region_inventory,FigureGeometryError

def test_source_figure_candidate_has_geometry(tmp_path):
    original=tmp_path/"original";original.mkdir()
    p=original/"slides.pdf"
    with fitz.open() as d:
        page=d.new_page(width=640,height=360)
        page.draw_rect(fitz.Rect(60,60,330,280),color=(0,0,0),width=2)
        d.save(p)
    report=tmp_path/"result";report.mkdir()
    result=figure_region_inventory(p,report/"figure.json")
    assert result["slides"]==1
    assert result["figure_candidates"]>=1
    assert result["publication_allowed"] is False

def test_no_source_folder_writes(tmp_path):
    p=tmp_path/"slides.pdf"
    with fitz.open() as d:d.new_page();d.save(p)
    with pytest.raises(FigureGeometryError):
        figure_region_inventory(p,tmp_path/"figures.json")
