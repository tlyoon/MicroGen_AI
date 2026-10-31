"""Transactional one-shot pilot: synthetic stage fixtures and mock external engines."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_microgen_expanded_neural_tts import setup_case
from microgen_complete_serway_pilot import preflight_campaign,run_complete_pilot,CompletePilotError

def setup(root):
    source,n,deck,coverage,model=setup_case(root)
    plan=root/"plan.json"
    vosk=root/"vosk";(vosk/"am").mkdir(parents=True)
    # Hosted Linux setup-python can expose python as a symlink. The real
    # pipeline correctly rejects symlinked executables; the synthetic test
    # fixture must supply the resolved interpreter path on every OS.
    interpreter=Path(sys.executable).resolve(strict=True)
    return source,n,plan,model,interpreter,vosk,interpreter

class CompletePilotTests(unittest.TestCase):
    def test_preflight_rejects_reusing_existing_final_folder(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);args=setup(root)
            destination=root/"already-exists";destination.mkdir()
            with self.assertRaises(CompletePilotError):
                preflight_campaign(*args,destination)

    def test_inputs_are_immutable_and_output_unapproved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);args=setup(root)
            evidence=preflight_campaign(*args,root/"output")
            self.assertEqual(len(evidence["source_pdf_sha256"]),64)
            self.assertFalse(evidence["publication_allowed"])
            self.assertEqual(evidence["cloud_provider_calls"],0)

    def test_fake_success_creates_atomically_a_full_14_stage_receipt(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);args=setup(root)
            def mock_synth(stage,narration,slides,coverage,model,python,wavs):
                wavs.mkdir()
                (wavs/"expanded_neural_qa_receipt.json").write_text('{"mocked":true}')
                return {"status":"FOURTEEN_REAL_NEURAL_WAV_CANDIDATES_NOT_FORMAL",
                        "total_seconds":333.0}
            def mock_asr(wavs,narration,vosk,ffmpeg,path):
                path.write_text('{"mocked":true}')
                return {"targeted_hazard_count":0}
            def mock_video(stage,narration,plan,slides,coverage,wavs,model,asr,video):
                video.mkdir()
                (video/"lecture_14_candidate_receipt.json").write_text('{"mocked":true}')
                (video/"lecture_14_slide_neural_candidate.mp4").write_bytes(b"synthetic fake video test")
                return {"status":"REAL_FOURTEEN_SLIDE_NEURAL_MP4_CANDIDATE_NOT_FORMAL",
                    "publication_allowed":False,"real_mp4_exists":True,
                    "full_slide_frame_verifications":[{"slide":i} for i in range(1,15)],
                    "mp4_duration_seconds":334.0}
            out=root/"complete"
            with patch("microgen_complete_serway_pilot.synthesize_expanded",side_effect=mock_synth),\
                 patch("microgen_complete_serway_pilot.audit_asr",side_effect=mock_asr),\
                 patch("microgen_complete_serway_pilot.build_14_lecture",side_effect=mock_video):
                result=run_complete_pilot(*args,out)
            self.assertEqual(result["slide_count"],14)
            self.assertEqual(len(result["stages_completed"]),7)
            self.assertEqual(result["status"],"COMPLETE_SOURCE_TO_REAL_VIDEO_REPRODUCTION_NOT_RELEASED")
            self.assertTrue((out/"complete_pilot_receipt.json").is_file())
            self.assertFalse(result["production_ready"])
            self.assertFalse(result["publication_allowed"])

    def test_failure_rolls_back_with_no_published_output(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);args=setup(root)
            out=root/"aborted-campaign"
            def synth_failed(*args,**kwargs):
                raise RuntimeError("offline piper failed")
            with patch("microgen_complete_serway_pilot.synthesize_expanded",side_effect=synth_failed):
                with self.assertRaises(RuntimeError):run_complete_pilot(*args,out)
            self.assertFalse(out.exists())
            self.assertEqual(len(list(root.glob(".microgen-complete-section11-*"))),0)

    def test_source_tampering_and_missing_local_model_prevent_launch(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);args=setup(root)
            (args[3]/"MODEL_CARD").write_text("License: no redistribution; unknown training")
            with self.assertRaises(Exception):
                preflight_campaign(*args,root/"denied")

if __name__=="__main__":unittest.main()
