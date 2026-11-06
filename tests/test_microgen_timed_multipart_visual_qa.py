"""Offline regressions for source-grounded timed highlights across video parts.

The fake 602-second timing is deliberate: this tests routing/receipt logic
without rendering a 10-minute movie or making cloud calls. The PCM/sample
contract and actual H.264 pixels are checked by separate existing tests.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import ImageDraw

from test_microgen_timed_highlight_contract import stage as two_slide_stage
from microgen_timed_highlight_contract import inspect_timed_highlights
import microgen_measured_highlight_video_qa as visual


class TimedMultipartVisualTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage=two_slide_stage(Path(self.tmp.name))
        self.ffmpeg=Path(sys.executable)
        self.fake_timed=copy.deepcopy(inspect_timed_highlights(self.stage))
        for row in self.fake_timed["slides"]:
            row["duration_seconds"]=301.0
            row["elements"][0]["start_seconds"]=0.0
            row["elements"][0]["end_seconds"]=150.0
            row["elements"][1]["start_seconds"]=150.0
            row["elements"][1]["end_seconds"]=301.0
        (self.stage/"slides.mp4").write_bytes(b"full-archive-602-seconds")
        (self.stage/"slides_part_01.mp4").write_bytes(b"part-one-301")
        (self.stage/"slides_part_02.mp4").write_bytes(b"part-two-301")
        (self.stage/".microgen_autonomous_parts.json").write_text(
            "source-bound-part-receipt",encoding="utf8")
        self.inventory={"parts":[
            {"index":1,"file":"slides_part_01.mp4","slides":[1],
             "actual_seconds":301},
            {"index":2,"file":"slides_part_02.mp4","slides":[2],
             "actual_seconds":301},
        ]}
        self.frame_calls=[]

    def mock_video(self,path,*,expected_seconds=None):
        name=Path(path).name
        if name=="slides.mp4":
            self.assertAlmostEqual(expected_seconds,602.0)
            return {"seconds":602.0}
        self.assertIn(name,("slides_part_01.mp4","slides_part_02.mp4"))
        self.assertAlmostEqual(expected_seconds,301.0)
        return {"seconds":301.0}

    def mock_frame(self,ffmpeg,path,when):
        import fitz
        name=Path(path).name
        self.assertIn(name,("slides_part_01.mp4","slides_part_02.mp4"))
        self.assertGreaterEqual(when,0)
        self.assertLess(when,301)
        slide=1 if name=="slides_part_01.mp4" else 2
        self.frame_calls.append((name,round(when,6)))
        with fitz.open(self.stage/"slides.pdf") as doc:
            page=doc[slide-1]
            image=visual._pdf_reference(page)
            cue=self.fake_timed["slides"][slide-1]["elements"][
                0 if when<150 else 1]
            rect=visual._pixel_box(page,cue)
            ImageDraw.Draw(image).rectangle(rect,fill=(255,255,85))
            return image

    def _patch(self,parts=None,frame=None,video=None):
        from contextlib import ExitStack
        stack=ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(
            visual,"inspect_timed_highlights",return_value=self.fake_timed))
        stack.enter_context(mock.patch.object(
            visual,"check_video",side_effect=video or self.mock_video))
        stack.enter_context(mock.patch(
            "microgen_autonomous_video_parts.verify_receipt",
            side_effect=parts if isinstance(parts,Exception) else None,
            return_value=parts if parts is not None and
                not isinstance(parts,Exception) else self.inventory))
        stack.enter_context(mock.patch.object(
            visual,"_frame",side_effect=frame or self.mock_frame))
        return stack

    def test_every_cue_decoded_against_correct_part_local_clock(self):
        self._patch()
        report=visual.inspect_visual_timing(self.stage,ffmpeg=self.ffmpeg)
        self.assertEqual(report["cue_count"],4)
        self.assertEqual(report["verified_delivery_parts"],[
            {"file":"slides_part_01.mp4","slides":[1]},
            {"file":"slides_part_02.mp4","slides":[2]},
        ])
        self.assertEqual(self.frame_calls,[
            ("slides_part_01.mp4",75.0),
            ("slides_part_01.mp4",225.5),
            ("slides_part_02.mp4",75.0),
            ("slides_part_02.mp4",225.5),
        ])
        self.assertEqual(
            report["checked_cues"][2]["global_center_seconds"],376.0)
        self.assertEqual(
            report["checked_cues"][2]["part_center_seconds"],75.0)
        self.assertEqual(
            report["checked_cues"][2]["deliverable_video"],
            "slides_part_02.mp4")
        hashes=report["source_and_video_sha256"]
        self.assertIn("slides.mp4",hashes)
        self.assertIn("slides_part_01.mp4",hashes)
        self.assertIn("slides_part_02.mp4",hashes)
        self.assertIn(".microgen_autonomous_parts.json",hashes)
        self.assertFalse(report["publication_allowed"])
        self.assertFalse(report["spoken_word_to_element_alignment_verified"])

    def test_immutable_receipt_binds_all_part_bytes(self):
        self._patch()
        receipt=visual.audit_stage(self.stage,ffmpeg=self.ffmpeg)
        self.assertEqual(visual.verify_receipt(self.stage,ffmpeg=self.ffmpeg),
                         receipt)
        (self.stage/"slides_part_02.mp4").write_bytes(b"tampered-part")
        with self.assertRaisesRegex(
            visual.MeasuredVisualQAError,"changed|drifted"):
            visual.verify_receipt(self.stage,ffmpeg=self.ffmpeg)

    def test_missing_or_unverified_part_receipt_fails_closed(self):
        self._patch(parts=RuntimeError("invalid part provenance"))
        with self.assertRaisesRegex(RuntimeError,"invalid part provenance"):
            visual.inspect_visual_timing(self.stage,ffmpeg=self.ffmpeg)
        self.assertFalse((self.stage/visual.RECEIPT).exists())

    def test_missing_one_part_rejected(self):
        self._patch()
        (self.stage/"slides_part_02.mp4").unlink()
        with self.assertRaisesRegex(
            visual.MeasuredVisualQAError,"Missing or unsafe ordered video part"):
            visual.inspect_visual_timing(self.stage,ffmpeg=self.ffmpeg)

    def test_static_delivered_part_cannot_masquerade_as_highlighted(self):
        import fitz
        def static_frame(ffmpeg,path,when):
            with fitz.open(self.stage/"slides.pdf") as doc:
                slide=1 if path.name.endswith("_01.mp4") else 2
                return visual._pdf_reference(doc[slide-1])
        self._patch(frame=static_frame)
        with self.assertRaisesRegex(
            visual.MeasuredVisualQAError,"no independently visible"):
            visual.inspect_visual_timing(self.stage,ffmpeg=self.ffmpeg)

    def test_part_clock_drift_over_one_second_is_rejected(self):
        def shifted_video(path,*,expected_seconds=None):
            result=self.mock_video(path,expected_seconds=expected_seconds)
            if Path(path).name=="slides_part_02.mp4":
                return {"seconds":302.4}
            return result
        self._patch(video=shifted_video)
        with self.assertRaisesRegex(
            visual.MeasuredVisualQAError,
            "media clock drifts from source PCM timing"):
            visual.inspect_visual_timing(self.stage,ffmpeg=self.ffmpeg)

    def test_no_long_candidate_assumed_to_have_verified_parts(self):
        self._patch()
        with self.assertRaisesRegex(
            visual.MeasuredVisualQAError,
            "Long candidate needs independently verified"):
            visual.inspect_visual_timing(
                self.stage,ffmpeg=self.ffmpeg,
                video_override=self.stage/"slides.mp4")

    def test_part_exceeding_600_is_not_accepted(self):
        def too_long(path,*,expected_seconds=None):
            result=self.mock_video(path,expected_seconds=expected_seconds)
            if Path(path).name=="slides_part_02.mp4":
                return {"seconds":600.2}
            return result
        self._patch(video=too_long)
        with self.assertRaisesRegex(
            visual.MeasuredVisualQAError,"exceeds 600-second limit"):
            visual.inspect_visual_timing(self.stage,ffmpeg=self.ffmpeg)


if __name__=="__main__":
    unittest.main()
