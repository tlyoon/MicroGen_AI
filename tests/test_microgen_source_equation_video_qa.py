"""Frame-differential math overlay guard tests, no model/API calls."""
import unittest
from PIL import Image,ImageDraw
from microgen_source_equation_video_qa import visible_equation_change
from microgen_single_figure_frame_diff_qa import frame_difference_metrics


class EquationPixelVisibilityTests(unittest.TestCase):
    def test_mathematics_line_region_changed(self):
        left=Image.new("RGB",(640,360),"white")
        right=left.copy()
        ImageDraw.Draw(right).rectangle((30,140,270,164),fill=(250,135,15))
        a,b=frame_difference_metrics(left,right,(30,140,270,164))
        self.assertTrue(visible_equation_change(a,b))

    def test_global_video_noise_is_not_mathematics_overlay(self):
        left=Image.new("RGB",(640,360),(240,240,240))
        right=Image.new("RGB",(640,360),(238,238,238))
        a,b=frame_difference_metrics(left,right,(30,140,270,164))
        self.assertFalse(visible_equation_change(a,b))

    def test_change_outside_equation_does_not_pass(self):
        left=Image.new("RGB",(640,360),"white")
        right=left.copy()
        ImageDraw.Draw(right).rectangle((350,280,590,350),fill="black")
        a,b=frame_difference_metrics(left,right,(30,140,270,164))
        self.assertFalse(visible_equation_change(a,b))

    def test_nonfinite_measurements_fail_closed(self):
        for item in (float("nan"),float("inf")):
            self.assertFalse(visible_equation_change(item,1.))
            self.assertFalse(visible_equation_change(30.,item))


if __name__=="__main__":
    unittest.main()
