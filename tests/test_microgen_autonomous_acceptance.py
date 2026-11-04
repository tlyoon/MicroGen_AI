"""PR275: adversarial autonomous technical acceptance, no API or manual gates."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock

import microgen_autonomous_acceptance as acceptance


def stage_files(root:Path,n:int=2):
    stage=root/"lesson"
    stage.mkdir()
    names=[
        "source.pdf","slides.pdf","slides.tex","script.txt",
        "script_tts.json","slides.mp4",
        ".microgen_autonomous_science_qa.json",
        ".microgen_autonomous_acoustic_qa.json",
        ".microgen_tts_provenance.json",
    ]
    for i in range(1,n+1):
        names.extend((f"slide{i}.wav",f"slide{i}.pdf"))
    for name in names:
        (stage/name).write_bytes(("PRIVATE_TEST:"+name).encode())
    return stage


def technical_evidence(n=2):
    return {
        "slide_count":n,"source_sha256":"abc",
        "scientific_screen_status":"SOURCE_GROUNDED_MODEL_SCREEN_PASSED",
        "scientific_advisory_slide_count":0,
        "acoustic_screen_status":"AUTONOMOUS_INDEPENDENT_ASR_SCREEN_PASSED",
        "acoustic_recognition_models":["gemini-A","gemini-B"],
        "repaired_wav_slide_count":0,
        "mapped_source_figure_count":0,
        "unmapped_source_crop_count":0,
        "total_wav_seconds":8.0,
        "complete_video_seconds":8.2,
        "deliverable_video_parts":[],
        "accepted_media_count":1,
        "production_quality_checks":{"independent_acoustic_screen":True},
        "unproven_quality_dimensions":["all_spoken_phonemes_correct"],
        "scope":"source-grounded automated TECHNICAL screening only",
        "scientific_correctness_certain":False,
        "pronunciation_perfection_certified":False,
        "copyright_distribution_authorized":False,
        "human_approval_required":False,
        "publication_allowed":False,
    }


class AutonomousAcceptanceUnitTest(unittest.TestCase):
    def test_full_immutable_receipt_rejects_source_audio_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            stage=stage_files(Path(td))
            with mock.patch.object(acceptance,"inspect_stage",
                                   return_value=technical_evidence()):
                report=acceptance.audit_stage(stage)
                self.assertEqual(report["status"],
                    "PRIVATE_AUTONOMOUS_TECHNICAL_ACCEPTANCE_PASSED")
                self.assertFalse(report["publication_allowed"])
                self.assertFalse(report["human_approval_required"])
                self.assertEqual(acceptance.verify_receipt(stage),report)
                (stage/"slide1.wav").write_bytes(b"tampered-wav")
                with self.assertRaises(acceptance.AutonomousAcceptanceError):
                    acceptance.verify_receipt(stage)

    def test_no_manual_review_or_distribution_authorization_forgery(self):
        with tempfile.TemporaryDirectory() as td:
            stage=stage_files(Path(td))
            with mock.patch.object(acceptance,"inspect_stage",
                                   return_value=technical_evidence()):
                acceptance.audit_stage(stage)
                path=stage/acceptance.RECEIPT
                record=json.loads(path.read_text())
                for field in ("publication_allowed","human_approval_required",
                              "copyright_distribution_authorized"):
                    with self.subTest(field=field):
                        altered=json.loads(json.dumps(record))
                        altered[field]=True
                        path.write_text(json.dumps(altered))
                        with self.assertRaises(acceptance.AutonomousAcceptanceError):
                            acceptance.verify_receipt(stage)

    def test_upstream_review_change_during_acceptance_blocks_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            stage=stage_files(Path(td))
            first=technical_evidence()
            second=technical_evidence()
            second["acoustic_screen_status"]="BLOCKED"
            with mock.patch.object(acceptance,"inspect_stage",
                                   side_effect=[first,second]):
                with self.assertRaises(acceptance.AutonomousAcceptanceError):
                    acceptance.audit_stage(stage)
            self.assertFalse((stage/acceptance.RECEIPT).exists())

    def test_missing_science_evidence_blocks_before_media_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            stage=stage_files(Path(td))
            with mock.patch(
                "microgen_autonomous_science_qa.verify_receipt",
                side_effect=RuntimeError("No real source-bound science receipt")
            ), mock.patch.object(acceptance,"check_slide_pdf",
                return_value={"pages":2}
            ), mock.patch.object(acceptance,"check_graphics"
            ), mock.patch.object(acceptance,"check_narration"
            ), mock.patch.object(acceptance,"check_wavs",
                return_value={"total_seconds":8.0}
            ), mock.patch.object(acceptance,"numbered_files"):
                with self.assertRaisesRegex(RuntimeError,"science receipt"):
                    acceptance.inspect_stage(stage)
            self.assertFalse((stage/acceptance.RECEIPT).exists())

    def test_missing_acoustic_evidence_blocks_technical_gate(self):
        with tempfile.TemporaryDirectory() as td:
            stage=stage_files(Path(td))
            with mock.patch(
                "microgen_autonomous_science_qa.verify_receipt",
                return_value={"slide_count":2,"unresolved_blocking_issues":0}
            ), mock.patch(
                "microgen_autonomous_acoustic_gate.verify_receipt",
                side_effect=RuntimeError("No source-bound acoustic receipts")
            ), mock.patch.object(acceptance,"check_slide_pdf",
                return_value={"pages":2}
            ), mock.patch.object(acceptance,"check_graphics"
            ), mock.patch.object(acceptance,"check_narration"
            ), mock.patch.object(acceptance,"check_wavs",
                return_value={"total_seconds":8.0}
            ), mock.patch.object(acceptance,"numbered_files"):
                with self.assertRaisesRegex(RuntimeError,"acoustic"):
                    acceptance.inspect_stage(stage)

    def test_technical_pass_is_only_private_not_academic_certification(self):
        with tempfile.TemporaryDirectory() as td:
            stage=stage_files(Path(td))
            evidence=technical_evidence()
            with mock.patch.object(acceptance,"inspect_stage",return_value=evidence):
                record=acceptance.audit_stage(stage)
                self.assertFalse(record["evidence"]["scientific_correctness_certain"])
                self.assertFalse(record["evidence"]["pronunciation_perfection_certified"])
                self.assertFalse(record["copyright_distribution_authorized"])
                self.assertEqual(acceptance.audit_stage(stage),record)


if __name__=="__main__":
    unittest.main()
