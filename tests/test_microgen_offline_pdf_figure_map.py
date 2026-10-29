"""Provider-free figure pairing contract tests; not academic approval."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import pymupdf as fitz

from microgen_offline_pdf_figure_map import (
    OfflineFigureMapError, qualified_panel_matches, source_caption_and_panels,
)


class OfflineFigureMatchingContractTests(unittest.TestCase):
    def test_true_serway_style_strong_unique_visual_assignment(self):
        self.assertEqual(qualified_panel_matches([[257, 4], [5, 396]]), [0, 1])
        self.assertEqual(qualified_panel_matches([[2, 202], [190, 0]]), [1, 0])

    def test_nonunique_crop_to_image_is_refused(self):
        for data in ([[100, 2], [77, 4]], [[43, 39], [2, 99]],
                     [[5, 4], [1, 2]], [[40, 10], [1, 38]]):
            with self.subTest(scores=data):
                with self.assertRaises(OfflineFigureMapError):
                    qualified_panel_matches(data)

    def test_bad_score_shape_or_type_refused(self):
        for data in ([[1]], [[1, 2, 3], [3, 2, 1]], [[1, -3], [2, 4]],
                     [[True, 40], [40, 2]]):
            with self.subTest(scores=data):
                with self.assertRaises(OfflineFigureMapError):
                    qualified_panel_matches(data)

    def page(self, *, caption=True, labels=True, second_caption=False,
             wrong_label=False):
        doc = fitz.open()
        pg = doc.new_page(width=500, height=700)
        page_boxes = [fitz.Rect(35, 80, 160, 250),
                      fitz.Rect(35, 310, 160, 485)]
        if labels:
            pg.insert_text((55, 264), "a", fontsize=9)
            pg.insert_text((55, 499), "c" if wrong_label else "b", fontsize=9)
        if caption:
            pg.insert_text((35, 540), "Figure 1.1 (a) Primary weight. (b) Clock.", fontsize=10)
        if second_caption:
            pg.insert_text((35, 563), "Figure 1.2 Example 2", fontsize=10)
        return doc, pg, page_boxes

    def test_caption_and_panel_labels_geometrically_bound(self):
        doc, pg, boxes = self.page()
        with doc:
            number, order = source_caption_and_panels(pg, boxes)
            self.assertEqual(number, "1.1")
            self.assertEqual(order, [0, 1])

    def test_caption_and_panels_fail_without_unique_formal_number(self):
        for variants in ({"caption": False}, {"second_caption": True},
                         {"wrong_label": True}, {"labels": False}):
            with self.subTest(variant=variants):
                doc, pg, boxes = self.page(**variants)
                with doc:
                    with self.assertRaises(OfflineFigureMapError):
                        source_caption_and_panels(pg, boxes)

    def test_swapped_panel_image_boxes_does_not_assign_crop_order(self):
        doc, pg, boxes = self.page()
        with doc:
            number, order = source_caption_and_panels(pg, list(reversed(boxes)))
            self.assertEqual(number, "1.1")
            self.assertEqual(order, [1, 0])

    def test_one_or_three_image_boxes_refused(self):
        doc, pg, boxes = self.page()
        with doc:
            with self.assertRaises(OfflineFigureMapError):
                source_caption_and_panels(pg, boxes[:1])


if __name__ == "__main__":
    unittest.main()
