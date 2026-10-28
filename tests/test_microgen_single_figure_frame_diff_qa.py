"""Differential frame checks distinguish image overlays from codec noise."""
import unittest

from PIL import Image, ImageDraw
from microgen_single_figure_frame_diff_qa import (
    FigureFrameDiffError, frame_difference_metrics, figure_change_visible,
)


class FigureFrameDiffTests(unittest.TestCase):
    def frames(self):
        old = Image.new("RGB", (640, 360), "white")
        return old, old.copy()

    def test_actual_figure_region_difference_passes(self):
        old, new = self.frames()
        draw = ImageDraw.Draw(new)
        draw.rectangle((150, 80, 330, 230), fill=(255, 130, 15))
        figure, global_mae = frame_difference_metrics(old, new, (150, 80, 330, 230))
        self.assertTrue(figure_change_visible(figure, global_mae))

    def test_global_low_noise_does_not_fake_figure_overlay(self):
        old = Image.new("RGB", (640, 360), (250, 250, 250))
        new = Image.new("RGB", (640, 360), (248, 248, 248))
        figure, whole = frame_difference_metrics(old, new, (100, 100, 200, 200))
        self.assertFalse(figure_change_visible(figure, whole))

    def test_change_elsewhere_does_not_pass_target_box(self):
        old, new = self.frames()
        ImageDraw.Draw(new).rectangle((400, 200, 620, 320), fill="black")
        figure, whole = frame_difference_metrics(old, new, (100, 20, 250, 150))
        self.assertLess(figure, 1.)
        self.assertFalse(figure_change_visible(figure, whole))

    def test_image_wrong_size_or_invalid_box_rejected(self):
        old, new = self.frames()
        with self.assertRaises(FigureFrameDiffError):
            frame_difference_metrics(old, Image.new("RGB", (100, 100)), (1,2,3,4))
        with self.assertRaises(FigureFrameDiffError):
            frame_difference_metrics(old, new, (-2,0,10,10))

    def test_non_finite_metric_cannot_pass(self):
        for invalid in (float("nan"), float("inf")):
            self.assertFalse(figure_change_visible(invalid, 1.0))
            self.assertFalse(figure_change_visible(35., invalid))


if __name__ == "__main__":
    unittest.main()
