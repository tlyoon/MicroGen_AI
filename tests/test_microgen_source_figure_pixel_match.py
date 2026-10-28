"""Unittest-discoverable optional OpenCV tests for textbook pixel evidence."""
import unittest
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

from microgen_source_figure_pixel_match import best_match, FigurePixelAuditError


@unittest.skipUnless(cv2 is not None and np is not None,
                     "Optional OpenCV/NumPy absent from minimal CI runner")
class FigureMatchTests(unittest.TestCase):
    def picture(self):
        rng=np.random.default_rng(357)
        template=rng.integers(0,255,(70,56),dtype=np.uint8)
        page=np.full((260,330),255,dtype=np.uint8)
        page[90:160,120:176]=template
        return page,template

    def test_exact_source_crop_localized(self):
        page,fig=self.picture()
        score,scale,xy=best_match(page,fig,scales=[1.0])
        self.assertGreater(score,.99)
        self.assertEqual(scale,1.0)
        self.assertEqual(xy,(120,90))

    def test_wrong_figure_does_not_look_identical(self):
        page,_=self.picture()
        wrong=np.random.default_rng(159).integers(0,255,(70,56),dtype=np.uint8)
        score,_,_=best_match(page,wrong,scales=[1.0])
        self.assertLess(score,.4)

    def test_blank_figure_fails(self):
        page,_=self.picture()
        with self.assertRaisesRegex(FigurePixelAuditError,"Blank"):
            best_match(page,np.full((30,40),255,dtype=np.uint8))

    def test_illegal_scale_fails(self):
        page,fig=self.picture()
        with self.assertRaisesRegex(FigurePixelAuditError,"Unbounded"):
            best_match(page,fig,scales=[15.0])

    def test_no_viable_size_fails(self):
        page,fig=self.picture()
        with self.assertRaisesRegex(FigurePixelAuditError,"No valid"):
            best_match(page,np.tile(fig,(2,3)),scales=[3.0])


if __name__=="__main__":
    unittest.main()
