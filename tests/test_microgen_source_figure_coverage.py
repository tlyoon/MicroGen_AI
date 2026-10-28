"""Adversarial figure-name normalization and missing-source gate tests."""
import pytest
from microgen_source_figure_coverage import (
    _id,_referenced_images,build_current_figure_coverage,FigureCoverageError)


@pytest.mark.parametrize("name,expected",[
    ("Figure 2.38.png","2.38"),
    ("FIGURE 2.34.PNG","2.34"),
    ("Figure 2.40a.png","2.40a"),
    ("Fig 2.40.png",None),
    ("Figure ../../hidden.png",None),
    ("Figure 2.99 missing", "2.99"),
])
def test_only_exact_figure_label_is_recognized(name,expected):
    assert _id(name)==expected


def test_only_actual_latex_image_references_are_used():
    text=r"\includegraphics[width=.5\textwidth]{Figure 2.38.png}"+"\n"+r"\includegraphics{FIGURE 2.42.PNG}"
    assert _referenced_images(text)==["Figure 2.38.png","FIGURE 2.42.PNG"]


def test_missing_true_source_rejected(tmp_path):
    with pytest.raises((FigureCoverageError,FileNotFoundError)):
        build_current_figure_coverage(tmp_path,tmp_path/"output")
