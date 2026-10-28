import pytest
from microgen_figure_pixel_evidence import render_source_figure_review_crops,FigurePixelError

def test_untrusted_source_is_not_rasterized(tmp_path):
    dest=tmp_path/"out"
    with pytest.raises((FileNotFoundError,FigurePixelError)):
        render_source_figure_review_crops(tmp_path/"source.pdf",tmp_path/"manifest.json",dest)
    assert not dest.exists()
