import unittest
from map_and_rename_v5 import has_numbered_figure_caption

class CaptionDetectionTests(unittest.TestCase):
    def test_unlabeled_skier(self):
        note='Based on the page layout, there are no formally labeled figures (e.g., "Figure 8.x").\n- **Unlabeled image:** A skier accompanying Exercise 58.'
        self.assertFalse(has_numbered_figure_caption(note))
    def test_labeled_caption(self):
        for text in ('Figure 8.2: Curve', '- Figure 8.3a: Schematic', '**Figure 8.4**: Circuit'):
            with self.subTest(text=text):
                self.assertTrue(has_numbered_figure_caption(text))
    def test_explanatory_reference_not_caption(self):
        self.assertFalse(has_numbered_figure_caption('This is not Figure 8.2; the illustration is unnumbered.'))
        self.assertFalse(has_numbered_figure_caption('Example: "Figure 8.x" would be formally numbered.'))

if __name__=='__main__':
    unittest.main()
