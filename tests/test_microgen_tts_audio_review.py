import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path
import microgen_tts_audio_review as ar
import microgen_tts_risk_register as register
from text_to_speech_v25 import normalize_scientific_speech

def wav(path,data=b"\x01\x00"*24000):
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
        f.writeframes(data)

class LocalizedAcousticTests(unittest.TestCase):
    def sample(self,root):
        text="The function is continuous for every y-value."
        slides=[{"slide":1,"tts_text":text}]
        file=root/"slide1.wav";wav(file)
        risk=register.build_risk_register(slides,normalize_scientific_speech,[1.0],
             wav_sha256=[ar.digest(file)])
        return slides,risk
    def test_excerpt_creates_bounded_read_only_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);slides,risks=self.sample(root)
            orig=ar.digest(root/"slide1.wav")
            report=ar.render_excerpts(root,slides,risks,root/"clips")
            self.assertEqual(report["clips_created"],1)
            entry=report["excerpts"][0]
            self.assertTrue((root/"clips"/entry["clip_name"]).exists())
            self.assertEqual(orig,ar.digest(root/"slide1.wav"))
            self.assertEqual(entry["alignment_method"],
                             "approximate_raw_character_fraction_not_word_alignment")
            self.assertFalse(report["publishable"])
    def test_source_drift_fail_before_creating_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);slides,risks=self.sample(root)
            slides[0]["tts_text"]="Something else."
            with self.assertRaisesRegex(ar.ExcerptError,"source SHA drift"):
                ar.render_excerpts(root,slides,risks,root/"clips")
            self.assertFalse((root/"clips").exists())
    def test_audio_drift_fail_before_creating_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);slides,risks=self.sample(root)
            wav(root/"slide1.wav",b"\x11\x00"*24000)
            with self.assertRaisesRegex(ar.ExcerptError,"Audio SHA drift"):
                ar.render_excerpts(root,slides,risks,root/"clips")
            self.assertFalse((root/"clips").exists())
    def test_reuse_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);slides,risks=self.sample(root)
            (root/"clips").mkdir()
            with self.assertRaisesRegex(ar.ExcerptError,"reuse"):
                ar.render_excerpts(root,slides,risks,root/"clips")
    def test_pcm_silence_and_clip_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            wav(root/"silent.wav",b"\0\0"*24000)
            metrics=ar.pcm_analysis(root/"silent.wav")
            self.assertTrue(metrics["silent_or_near_silent"])
            self.assertEqual(metrics["duration_seconds"],1.0)
            wav(root/"loud.wav",b"\xff\x7f"*24000)
            self.assertGreater(ar.pcm_analysis(root/"loud.wav")["clipping_fraction"],0.99)
    def test_bad_bounds_and_batch_limit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);slides,risks=self.sample(root)
            with self.assertRaises(ar.ExcerptError):
                ar.render_excerpts(root,slides,risks,root/"clips",clip_seconds=0.5)
            with self.assertRaises(ar.ExcerptError):
                ar.render_excerpts(root,slides,risks,root/"clips",max_excerpts=0)
            risks["slides"][0]["risks"][0]["end"]=999999
            with self.assertRaisesRegex(ar.ExcerptError,"Risk offset invalid"):
                ar.render_excerpts(root,slides,risks,root/"clips")
