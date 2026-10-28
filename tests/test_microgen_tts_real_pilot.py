import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from text_to_speech_v25 import normalize_scientific_speech
from microgen_tts_real_pilot import prepare_pilot,repair_and_prepare_video_stage,PilotError,file_digest

def wav(path,pattern=1):
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
        f.writeframes(bytes((pattern,0))*24000)

def setup(root):
    base=root/"original"
    base.mkdir()
    slides=[{"slide":1,"tts_text":"The y-value is continuous."},
            {"slide":2,"tts_text":"The theorem is useful."}]
    (base/"script_tts.json").write_text(json.dumps({"slides":slides}),encoding="utf8")
    (base/"slides.pdf").write_bytes(b"test_pdf")
    wav(base/"slide1.wav",2)
    wav(base/"slide2.wav",2)
    wav(base/"slide1.before.wav",1)
    return base

class GenuinePilotTests(unittest.TestCase):
    def prepare(self,root):
        base=setup(root);work=root/"scratch"
        info=prepare_pilot(base,base/"slide1.before.wav",work,slide=1,
            historical_bad_sha256=file_digest(base/"slide1.before.wav"),
            good_reference_sha256=file_digest(base/"slide1.wav"),
            normalize=normalize_scientific_speech)
        return base,work,info
    def test_preparation_copies_only_into_scratch(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,work,info=self.prepare(root)
            self.assertEqual(file_digest(work/"pre_repair"/"slide1.wav"),
                             file_digest(base/"slide1.before.wav"))
            self.assertEqual(file_digest(work/"pre_repair"/"slide2.wav"),
                             file_digest(base/"slide2.wav"))
            self.assertFalse(info["publishable"])
    def test_unknown_acoustic_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,work,_=self.prepare(root)
            old_hash=file_digest(base/"slide1.wav")
            def synth(text,target):
                self.assertIn("why value",text)
                wav(target,3);return "google_cloud_chirp3"
            result=repair_and_prepare_video_stage(
                work,normalize=normalize_scientific_speech,synthesize=synth,slide=1)
            self.assertTrue((work/"video_review_input"/"slide1.wav").is_file())
            self.assertFalse(result["publishable"])
            self.assertFalse(result["acoustic_qa_passed"])
            self.assertEqual(result["total_wav_seconds"],2)
            self.assertEqual(old_hash,file_digest(base/"slide1.wav"))
    def test_bad_historical_sha_blocks_no_work_created(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base=setup(root);dest=root/"stage"
            with self.assertRaisesRegex(PilotError,"checksum mismatch"):
                prepare_pilot(base,base/"slide1.before.wav",dest,slide=1,
                    historical_bad_sha256="0"*64,
                    good_reference_sha256=file_digest(base/"slide1.wav"),
                    normalize=normalize_scientific_speech)
            self.assertFalse(dest.exists())
    def test_refuses_existing_or_nested_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base=setup(root)
            with self.assertRaises(PilotError):
                prepare_pilot(base,base/"slide1.before.wav",base/"nested",
                    slide=1,historical_bad_sha256=file_digest(base/"slide1.before.wav"),
                    good_reference_sha256=file_digest(base/"slide1.wav"),
                    normalize=normalize_scientific_speech)
    def test_wrong_voice_provider_cannot_prepare_candidate_video(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,work,_=self.prepare(root)
            def wrong(text,target):
                wav(target);return "sapi"
            result=repair_and_prepare_video_stage(work,
                normalize=normalize_scientific_speech,
                synthesize=wrong,slide=1)
            self.assertFalse(result["video_stage_created"])
            self.assertFalse((work/"video_review_input").exists())
    def test_source_script_drift_refuses_actual_synthesis(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,work,_=self.prepare(root)
            (work/"pre_repair"/"script_tts.json").write_text("{}",encoding="utf8")
            with self.assertRaisesRegex(PilotError,"narration hash drift"):
                repair_and_prepare_video_stage(
                    work,normalize=normalize_scientific_speech,
                    synthesize=lambda *a:None,slide=1)
    def test_no_unverified_source_wav_replacement(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base=setup(root)
            with self.assertRaisesRegex(PilotError,"checksum changed"):
                prepare_pilot(base,base/"slide1.before.wav",root/"pilot",slide=1,
                    historical_bad_sha256=file_digest(base/"slide1.before.wav"),
                    good_reference_sha256="1"*64,normalize=normalize_scientific_speech)
