"""Conservative figure-pixel anomaly tests; no academic auto-approval."""
import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from microgen_source_figure_pixel_match import best_match, FigurePixelAuditError


def image():
    rng = np.random.default_rng(357)
    template = rng.integers(0, 255, (70, 56), dtype=np.uint8)
    page = np.full((260, 330), 255, dtype=np.uint8)
    page[90:160, 120:176] = template
    return page, template


def test_exact_source_crop_localized():
    page, figure = image()
    score, scale, xy = best_match(page, figure, scales=[1.0])
    assert score > .99
    assert scale == 1.0
    assert xy == (120, 90)


def test_wrong_figure_not_independently_approved():
    page, _ = image()
    rng = np.random.default_rng(159)
    wrong = rng.integers(0, 255, (70, 56), dtype=np.uint8)
    score, _, _ = best_match(page, wrong, scales=[1.0])
    assert score < .4


def test_blank_figure_fails_closed():
    page, _ = image()
    with pytest.raises(FigurePixelAuditError, match="Blank"):
        best_match(page, np.full((30, 40), 255, dtype=np.uint8))


def test_out_of_bounds_scale_rejected():
    page, figure = image()
    with pytest.raises(FigurePixelAuditError, match="Unbounded"):
        best_match(page, figure, scales=[15.0])


def test_no_raster_size_match_rejected():
    page, figure = image()
    with pytest.raises(FigurePixelAuditError, match="No valid"):
        best_match(page, np.tile(figure, (2, 3)), scales=[3.0])
