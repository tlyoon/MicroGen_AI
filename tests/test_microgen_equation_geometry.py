import pytest
import pymupdf as fitz
from microgen_equation_geometry import equation_region_inventory,EquationGeometryError

def test_actual_math_line_bbox_in_synthetic_source(tmp_path):
    protected=tmp_path/"protected";protected.mkdir()
    p=protected/"source.pdf"
    with fitz.open() as d:
        page=d.new_page(width=400,height=220)
        page.insert_text((30,40),"lim f(x) = f(c)")
        d.save(p)
    report_folder=tmp_path/"separate_reports";report_folder.mkdir()
    result=equation_region_inventory(p,report_folder/"math.json")
    assert result["regions"]>=1 and result["slides"]==1
    assert not result["publication_allowed"]

def test_refuse_original_location_overwrite(tmp_path):
    p=tmp_path/"source.pdf"
    with fitz.open() as d:d.new_page();d.save(p)
    with pytest.raises(EquationGeometryError):
        equation_region_inventory(p,tmp_path/"unsafe.json")
