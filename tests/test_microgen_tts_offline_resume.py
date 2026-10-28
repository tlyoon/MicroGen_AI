"""Offline unattended progression must never fabricate phonetic acceptance."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import microgen_tts_autonomous_campaign as auto
from test_microgen_tts_release_audit import setup
from microgen_tts_provenance import digest_file


class OfflineContinuationTests(unittest.TestCase):
    def test_no_model_calls_and_immutable_original_wav(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); stage=base/"lesson";stage.mkdir()
            setup(stage)
            before=digest_file(stage/"slide1.wav")
            with patch("microgen_tts_release_audit.check_video",return_value={"seconds":1.5}),\
                 patch.object(auto,"gemini_audio_recognizer",side_effect=AssertionError("Billed call")):
                result=auto.continue_media_without_paid_recognition(stage,base/"offline-qa")
            self.assertTrue(result["audio_generation_progression"]["can_continue_media_generation"])
            self.assertEqual(result["execution_mode"],"OFFLINE_NO_ASR_NO_TTS_BILLING")
            self.assertTrue(result["video_technical_av"])
            self.assertFalse(result["ready_for_separate_promotion"])
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(result["independent_phonetics_verified"])
            self.assertEqual(digest_file(stage/"slide1.wav"),before)
            self.assertTrue((base/"offline-qa"/"TTS_MEDIA_GENERATION_PROGRESSION.json").is_file())
            self.assertTrue((base/"offline-qa"/"QA_CAMPAIGN_COMPLETE_NOT_PUBLISHED.json").is_file())

    def test_bad_or_missing_source_voice_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);stage=base/"lesson";stage.mkdir()
            setup(stage)
            (stage/".microgen_tts_provenance.json").unlink()
            with patch("microgen_tts_release_audit.check_video",return_value={"seconds":1.5}):
                with self.assertRaisesRegex(auto.AutonomousCampaignError,"Critical"):
                    auto.continue_media_without_paid_recognition(stage,base/"qa")
            self.assertFalse((base/"qa").exists())

    def test_missing_one_multipart_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);stage=base/"lesson";stage.mkdir()
            setup(stage)
            with self.assertRaisesRegex(auto.AutonomousCampaignError,"Both"):
                auto.continue_media_without_paid_recognition(stage,base/"qa",
                                           multipart_receipt=base/"one.json")
            self.assertFalse((base/"qa").exists())

    def test_existing_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);stage=base/"lesson";stage.mkdir()
            setup(stage)
            existing=base/"qa";existing.mkdir()
            with self.assertRaisesRegex(auto.AutonomousCampaignError,"Fresh"):
                auto.continue_media_without_paid_recognition(stage,existing)

    def test_paid_preflight_uses_both_multipart_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);stage=base/"lesson";stage.mkdir()
            setup(stage)
            with patch.object(auto,"audit_stage",return_value={
                "technical_blockers":["independent_acoustic_screen"],"slide_count":1,
                "video_duration_seconds":None,"wav_sha256":["x"],"video_sha256":None,
            }) as audited, patch.object(auto,"plan_recognition",return_value={"count":2}):
                report=auto.preflight_before_paid_recognition(stage,base/"qa",
                    multipart_receipt=base/"part.json",independent_av_receipt=base/"independent.json")
            self.assertTrue(report["prepaid_checks_passed"])
            audited.assert_called_once()
            self.assertEqual(audited.call_args.kwargs["multipart_receipt"],base/"part.json")


if __name__=="__main__":
    unittest.main()
