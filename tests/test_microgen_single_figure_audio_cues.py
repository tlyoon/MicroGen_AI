"""No-network tests: figure candidates require unique real image + spoken anchor."""
import unittest
import pymupdf as fitz
from microgen_single_figure_audio_cues import (
    image_anchor_cues, exact_stage_figure_asset, SingleFigureCueError,
)
from PIL import Image

PAGE = fitz.Rect(0, 0, 400, 240)
BOX = [120, 60, 260, 160]


class SingleFigureAudioCueTests(unittest.TestCase):
    def word(self, **changes):
        data={"word":"curve","start":4.2,"end":4.7,"conf":.99}
        data.update(changes)
        return data

    def test_exact_source_image_pixels_and_sha_required(self):
        embedded=Image.new("RGB",(40,35),(22,75,130))
        clone=embedded.copy()
        match=exact_stage_figure_asset(embedded,[("Figure 2.34.png","abc",clone)])
        self.assertEqual(match,("Figure 2.34.png","abc"))
        wrong=Image.new("RGB",(40,35),(23,75,130))
        self.assertIsNone(exact_stage_figure_asset(embedded,[("wrong.png","def",wrong)]))

    def test_two_identical_source_images_are_ambiguous(self):
        embedded=Image.new("RGB",(40,35),(22,75,130))
        aliases=[("a.png","shaA",embedded.copy()),("b.png","shaB",embedded.copy())]
        self.assertIsNone(exact_stage_figure_asset(embedded,aliases))

    def test_exact_word_and_unique_image_produce_timed_box(self):
        cues=image_anchor_cues([self.word()], "Observe the curve now.",
             [BOX],wav_seconds=30,page_rect=PAGE)
        self.assertEqual(len(cues),1)
        self.assertEqual(cues[0]["box"],BOX)
        self.assertAlmostEqual(cues[0]["start"],4.08)
        self.assertAlmostEqual(cues[0]["end"],5.15)
        self.assertFalse(cues[0]["figure_semantics_verified"])

    def test_two_panels_do_not_get_arbitrary_binding(self):
        self.assertEqual(image_anchor_cues([self.word()],"curve",[BOX,[1,1,100,100]],
                             wav_seconds=10,page_rect=PAGE),[])

    def test_narration_does_not_name_anchor(self):
        self.assertEqual(image_anchor_cues([self.word()],"Inspect the function",
                             [BOX],wav_seconds=10,page_rect=PAGE),[])

    def test_low_confidence_does_not_highlight(self):
        self.assertEqual(image_anchor_cues([self.word(conf=.4)],"curve",
                             [BOX],wav_seconds=10,page_rect=PAGE),[])

    def test_generic_line_is_not_semantically_assumed_figure(self):
        self.assertEqual(image_anchor_cues([self.word(word="line")],"line",
                             [BOX],wav_seconds=10,page_rect=PAGE),[])

    def test_out_of_bounds_word_clock_not_accepted(self):
        self.assertEqual(image_anchor_cues([self.word(start=10,end=11)],"curve",
                             [BOX],wav_seconds=9,page_rect=PAGE),[])

    def test_off_page_and_tiny_images_not_auto_bound(self):
        for invalid in ([390,220,420,260],[1,1,20,15]):
            with self.subTest(invalid=invalid):
                self.assertEqual(image_anchor_cues([self.word()],"curve",
                    [invalid],wav_seconds=10,page_rect=PAGE),[])

    def test_malformed_asr_cue_fails_closed(self):
        with self.assertRaises(SingleFigureCueError):
            image_anchor_cues(["curve"],"curve",[BOX],wav_seconds=10,page_rect=PAGE)

    def test_three_cue_limit_and_audio_end_clamping(self):
        words=[self.word(start=1+i,end=1.5+i) for i in range(5)]
        cues=image_anchor_cues(words,"This curve is on the graph.",
            [BOX],wav_seconds=10,page_rect=PAGE)
        self.assertEqual(len(cues),3)
        near_end=image_anchor_cues([self.word(start=9.8,end=9.99)],"curve",
            [BOX],wav_seconds=10,page_rect=PAGE)
        self.assertEqual(near_end[0]["end"],10)


if __name__=="__main__":
    unittest.main()
