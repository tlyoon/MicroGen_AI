"""Private timed-highlight acceptance: fail-closed visual QA and legacy safety.

Pure offline unit fixtures. For actual decoded pixels see the independent
PR #285 video regression. This file uses no provider, machine or real media.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import microgen_autonomous_acceptance as acceptance
import microgen_batch
from microgen_timed_highlight_contract import MANIFEST
from microgen_measured_highlight_video_qa import RECEIPT as VISUAL


def private_stage(root: Path) -> Path:
    stage=root/"private"
    stage.mkdir()
    names=[
        "source.pdf","slides.pdf","slides.tex","script.txt","script_tts.json",
        "slides.mp4",".microgen_autonomous_science_qa.json",
        ".microgen_autonomous_acoustic_qa.json",".microgen_tts_provenance.json",
        "slide1.pdf","slide2.pdf","slide1.wav","slide2.wav",
    ]
    for name in names:
        (stage/name).write_bytes(("private:"+name).encode())
    return stage


def visual_evidence(**overrides):
    report={
        "status":"SOURCE_PCM_TIMED_VISUAL_HIGHLIGHTS_INDEPENDENTLY_CHECKED",
        "slide_count":2,"cue_count":2,
        "checked_cues":[{"element_id":"one"},{"element_id":"two"}],
        "visual_highlight_rendering_verified":True,
        "spoken_word_to_element_alignment_verified":False,
        "academic_correctness_verified":False,
        "publication_allowed":False,
    }
    return {**report,**overrides}


class TimedVisualAcceptanceTests(unittest.TestCase):
    def test_static_lecture_stays_exempt(self):
        with tempfile.TemporaryDirectory() as td:
            s=private_stage(Path(td))
            self.assertIsNone(acceptance._verified_timed_visual(s,2))
            self.assertNotIn(VISUAL,acceptance._snap(s,2))

    def test_missing_timed_receipt_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            s=private_stage(Path(td))
            (s/MANIFEST).write_text("{}",encoding="utf8")
            with mock.patch(
                "microgen_runtime_preflight.find_h264_ffmpeg",
                return_value=sys.executable,
            ):
                with self.assertRaisesRegex(
                    acceptance.AutonomousAcceptanceError,
                    "independently verified visual QA receipt",
                ):
                    acceptance._verified_timed_visual(s,2)

    def test_timed_visual_forged_flags_and_wrong_slide_count(self):
        with tempfile.TemporaryDirectory() as td:
            s=private_stage(Path(td))
            (s/MANIFEST).write_text("{}",encoding="utf8")
            with mock.patch(
                "microgen_runtime_preflight.find_h264_ffmpeg",
                return_value=sys.executable,
            ), mock.patch(
                "microgen_measured_highlight_video_qa.verify_receipt",
                return_value=visual_evidence(),
            ):
                self.assertEqual(
                    acceptance._verified_timed_visual(s,2),visual_evidence())
            for key,value in (
                ("slide_count",1),
                ("cue_count",3),
                ("visual_highlight_rendering_verified",False),
                ("spoken_word_to_element_alignment_verified",True),
                ("academic_correctness_verified",True),
                ("publication_allowed",True),
            ):
                with self.subTest(key=key), mock.patch(
                    "microgen_runtime_preflight.find_h264_ffmpeg",
                    return_value=sys.executable,
                ), mock.patch(
                    "microgen_measured_highlight_video_qa.verify_receipt",
                    return_value=visual_evidence(**{key:value}),
                ):
                    with self.assertRaisesRegex(
                        acceptance.AutonomousAcceptanceError,
                        "declared private evidence",
                    ):
                        acceptance._verified_timed_visual(s,2)

    def test_receipt_and_audio_cues_in_immutable_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            s=private_stage(Path(td))
            (s/MANIFEST).write_text(json.dumps({"slides":[
                {"cues":[{"audio_chunk":"highlight_chunks/slide1_cue1.wav"}]},
                {"cues":[{"audio_chunk":"highlight_chunks/slide2_cue1.wav"}]},
            ]}),encoding="utf8")
            chunks=s/"highlight_chunks"
            chunks.mkdir()
            for i in (1,2):
                (chunks/f"slide{i}_cue1.wav").write_bytes(b"test-PCM")
            with mock.patch(
                "microgen_timed_highlight_contract.inspect_timed_highlights",
                return_value={"slide_count":2},
            ):
                with self.assertRaisesRegex(
                    acceptance.AutonomousAcceptanceError,
                    "Missing independent visual highlight receipt",
                ):
                    acceptance._snap(s,2)
                proof=s/VISUAL
                proof.write_bytes(b"private decoded frame audit")
                first=acceptance._snap(s,2)
                self.assertIn(VISUAL,first)
                self.assertIn(MANIFEST,first)
                self.assertIn("highlight_chunks/slide2_cue1.wav",first)
                proof.write_bytes(b"tampered private proof")
                second=acceptance._snap(s,2)
                self.assertNotEqual(first[VISUAL],second[VISUAL])

    def test_checkpoint_reuse_demands_visual_receipt_only_for_cues(self):
        with tempfile.TemporaryDirectory() as td:
            s=private_stage(Path(td))
            with (
                mock.patch.object(microgen_batch.quality,"check_slide_pdf",
                                  return_value={"pages":2}),
                mock.patch.object(microgen_batch.quality,"check_wavs",
                                  return_value={"total_seconds":8.0}),
                mock.patch.object(microgen_batch.quality,"check_video",
                                  return_value={"seconds":8.0}),
            ):
                self.assertTrue(microgen_batch.stage_valid(s,"video",s))
                (s/MANIFEST).write_text("{}",encoding="utf8")
                with (
                    mock.patch("microgen_autonomous_video_parts._cache_segments",
                               return_value=[]),
                    mock.patch.object(
                        acceptance,"_verified_timed_visual",
                        side_effect=acceptance.AutonomousAcceptanceError(
                            "Missing independent visual timing evidence"),
                    ),
                ):
                    self.assertFalse(microgen_batch.stage_valid(s,"video",s))


if __name__=="__main__":
    unittest.main()
