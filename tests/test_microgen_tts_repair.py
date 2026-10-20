import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

import microgen_tts_repair as repair
import microgen_tts_risk_register as reg
from text_to_speech_v25 import normalize_scientific_speech as normalize

def wav(path):
    with wave.open(str(path),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
        w.writeframes(b"\x01\x00"*24000)

class BoundedRepairTests(unittest.TestCase):
    def stage(self,root,raw="The y-value is continuous."):
        root.mkdir()
        (root/"script_tts.json").write_text(json.dumps(
            {"slides":[{"slide":1,"tts_text":raw}]}),encoding="utf8")
        wav(root/"slide1.wav")
        report=reg.build_risk_register(
            [{"slide":1,"tts_text":raw}],normalize,[1.0],
            wav_sha256=[hashlib.sha256((root/"slide1.wav").read_bytes()).hexdigest()])
        return report
    def test_uncreated_child_output_is_rejected_without_touching_lecture(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            before=(stage/"slide1.wav").read_bytes()
            for output in (stage/"scratch_candidates",
                           stage/"subfolder"/"scratch_candidates",
                           stage/"."/"scratch"):
                with self.subTest(output=str(output)):
                    with self.assertRaisesRegex(repair.RepairError,
                                                "outside the source tree"):
                        repair.stage_repair(stage,regis,1,output,
                                            lambda *args: self.fail(
                                                "Synthesizer must not run"),normalize)
                    self.assertFalse(output.exists())
            self.assertEqual((stage/"slide1.wav").read_bytes(),before)

    def test_parent_of_lecture_not_usable_as_repair_root(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            with self.assertRaisesRegex(repair.RepairError,"outside the source tree"):
                repair.stage_repair(stage,regis,1,p,
                                    lambda *args: self.fail("Synthesis must not run"),
                                    normalize)

    def test_symlink_to_source_tree_does_not_bypass_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            alias=p/"alias"
            try:
                alias.symlink_to(stage,target_is_directory=True)
            except (OSError,NotImplementedError) as exc:
                self.skipTest(f"Symlink creation not permitted: {exc}")
            with self.assertRaisesRegex(repair.RepairError,"outside the source tree"):
                repair.stage_repair(stage,regis,1,alias/"candidate",
                                    lambda *args: self.fail("Synthesis must not run"),
                                    normalize)

    def test_two_defective_then_correct_diagnostics_are_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            sha=hashlib.sha256((stage/"slide1.wav").read_bytes()).hexdigest()
            seq=iter(["defect","clear"])
            calls=[]
            def synth(text,output):
                calls.append(text);wav(output);return "google_cloud_chirp3"
            outcome=repair.stage_repair(stage,regis,1,p/"new",synth,normalize,
                                        acoustic_gate=lambda w,t:next(seq))
            self.assertEqual(len(calls),2)
            self.assertEqual(outcome["status"],"CANDIDATE_REVIEW_REQUIRED")
            self.assertFalse(outcome["publishable"])
            self.assertEqual(sha,hashlib.sha256((stage/"slide1.wav").read_bytes()).hexdigest())
    def test_no_acoustic_gate_is_not_a_pass_or_retry_loop(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            def synth(text,output):
                wav(output);return "google_cloud_chirp3"
            r=repair.stage_repair(stage,regis,1,p/"new",synth,normalize)
            self.assertEqual(r["attempt_count"],1)
            self.assertFalse(r["technical_candidate_ready"])
            self.assertEqual(r["status"],"ACOUSTIC_QA_UNAVAILABLE")
    def test_unknown_or_unreviewed_expression_is_not_autofixed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage,"Evaluate f(x).")
            self.assertEqual(repair.authorized_slides(regis),[])
            with self.assertRaises(repair.RepairError):
                repair.stage_repair(stage,regis,1,p/"new",lambda *a:None,normalize)
            self.assertFalse((p/"new").exists())
    def test_provider_switch_cannot_sneak_into_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            def synth(text,output):
                wav(output);return "sapi"
            outcome=repair.stage_repair(stage,regis,1,p/"new",synth,normalize)
            self.assertEqual(outcome["status"],"REPAIR_UNRESOLVED")
            self.assertEqual(outcome["attempt_count"],1)
    def test_digital_silence_candidate_is_blocked_before_acoustic_gate(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            original=hashlib.sha256((stage/"slide1.wav").read_bytes()).hexdigest()
            called=[]
            def synth(text,target):
                with wave.open(str(target),"wb") as writer:
                    writer.setnchannels(1);writer.setsampwidth(2)
                    writer.setframerate(24000);writer.writeframes(b"\0\0"*24000)
                return "google_cloud_chirp3"
            outcome=repair.stage_repair(stage,regis,1,p/"candidate",synth,normalize,
                acoustic_gate=lambda wav,txt:called.append(1) or "clear")
            self.assertEqual(outcome["status"],"REPAIR_UNRESOLVED")
            self.assertEqual(outcome["attempt_count"],1)
            self.assertEqual(called,[])
            self.assertFalse(outcome["publishable"])
            self.assertEqual(hashlib.sha256((stage/"slide1.wav").read_bytes()).hexdigest(),
                             original)
    def test_hash_drift_blocks_without_writing(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            (stage/"slide1.wav").write_bytes(b"corrupted")
            with self.assertRaisesRegex(repair.RepairError,"SHA drift"):
                repair.stage_repair(stage,regis,1,p/"new",lambda *a:None,normalize)
            self.assertFalse((p/"new").exists())
    def test_existing_target_and_attempt_limits_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            (p/"new").mkdir()
            with self.assertRaises(repair.RepairError):
                repair.stage_repair(stage,regis,1,p/"new",lambda *a:None,normalize)
            with self.assertRaises(repair.RepairError):
                repair.stage_repair(stage,regis,1,p/"other",lambda *a:None,normalize,
                                    max_attempts=20)
    def test_staged_candidate_keeps_same_approved_voice_and_source(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);stage=p/"stage";regis=self.stage(stage)
            seen=[]
            def synth(text,out):
                seen.append(text);wav(out);return "google_cloud_chirp3"
            result=repair.stage_repair(stage,regis,1,p/"new",synth,normalize,
                                       acoustic_gate=lambda w,t:"clear")
            self.assertEqual(seen,["The why value is continuous."])
            self.assertEqual(result["attempts"][0]["voice"],"en-US-Chirp-HD-F")
            self.assertFalse(result["human_listening_approved"])
