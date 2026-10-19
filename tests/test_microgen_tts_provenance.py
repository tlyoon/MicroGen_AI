"""Adversarial offline voice-provenance integration tests; no paid TTS calls."""
import json
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import microgen_tts_provenance as pv
import text_to_speech_v25 as tts


def fake_wav(path, frames=24000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\0\0" * frames)


def example_record(path, *, slide=1, text="At see.", provider="google_cloud_chirp3",
                   voice="en-US-Chirp-HD-F"):
    return pv.make_record(
        slide=slide, path=path, text=text, provider=provider, key=f"cachekey{slide}",
        voice_name=voice, language_code="en-US", speaking_rate=0.8, location="global",
    )


class VoiceProvenanceTests(unittest.TestCase):
    def test_round_trip_records_and_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            stage = Path(root)
            records = []
            inputs = ["Evaluate at see.", "Take the limit."]
            for i, text in enumerate(inputs, 1):
                p = stage / f"slide{i}.wav"
                fake_wav(p, frames=24000 + i)
                records.append(example_record(p, slide=i, text=text))
            receipt = pv.write_manifest(stage, records, inputs)
            verified = pv.verify_manifest(stage, inputs)
            self.assertEqual(verified["slide_count"], 2)
            self.assertEqual(verified["provider"], "google_cloud_chirp3")
            self.assertTrue(verified["technical_provenance_verified"])
            self.assertFalse(verified["listening_qa_verified"])
            self.assertFalse(verified["element_highlight_qa_verified"])
            self.assertNotIn("credentials", receipt.read_text(encoding="utf-8").lower())
            self.assertFalse((stage / (pv.MANIFEST_FILE+".tmp")).exists())

    def test_tampering_or_source_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            stage = Path(root)
            file = stage / "slide1.wav"
            fake_wav(file)
            rec = example_record(file)
            pv.write_manifest(stage, [rec], ["At see."])
            for text in ("At si.", "At c."):
                with self.subTest(text=text), self.assertRaises(pv.TTSProvenanceError):
                    pv.verify_manifest(stage, [text])
            with file.open("ab") as stream:
                stream.write(b"change")
            with self.assertRaisesRegex(pv.TTSProvenanceError, "SHA-256 drift"):
                pv.verify_manifest(stage, ["At see."])

    def test_wrong_voice_rate_provider_and_old_cache_fail(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "slide1.wav"
            fake_wav(p)
            rec = example_record(p)
            common = dict(slide=1, text="At see.", key="cachekey1",
                          voice_name="en-US-Chirp-HD-F", language_code="en-US",
                          speaking_rate=0.8, location="global")
            pv.verify_record(rec, p, **common)
            for data in ({"voice_name":"wrong"}, {"speaking_rate":1.0},
                         {"provider":"sapi"}, {"schema_version":0}):
                with self.subTest(data=data):
                    changed = {**rec, **data}
                    with self.assertRaises(pv.TTSProvenanceError):
                        pv.verify_record(changed, p, **common)

    def test_mixed_voice_and_audio_rate_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            stage = Path(root)
            a, b = stage/"slide1.wav",stage/"slide2.wav"
            fake_wav(a);fake_wav(b)
            ra, rb = example_record(a,slide=1), example_record(b,slide=2,voice="en-US-Chirp-HD-O")
            with self.assertRaisesRegex(pv.TTSProvenanceError, "Mixed"):
                pv.write_manifest(stage,[ra,rb],["At see."]*2)
            self.assertFalse((stage / pv.MANIFEST_FILE).exists())
            rb = example_record(b,slide=2)
            rb["sample_rate_hz"] = 16000
            with self.assertRaises(pv.TTSProvenanceError):
                pv.write_manifest(stage,[ra,rb],["At see."]*2)

    def test_unpinned_sapi_fallback_cannot_claim_verified_voice(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            output=folder/"slide1.wav"
            fake_wav(output)
            rec=example_record(output,provider="sapi")
            self.assertFalse(rec["voice_identity_verified"])
            self.assertIsNone(rec["voice_name"])
            with self.assertRaises(pv.TTSProvenanceError):
                pv.write_manifest(folder,[rec],["At see."])

    def test_actual_main_two_slide_cache_reuse_and_change(self):
        with tempfile.TemporaryDirectory() as root:
            prior=Path.cwd()
            os.chdir(root)
            try:
                path=Path("script_tts.json")
                def sidecar(second="Find the root."):
                    path.write_text(json.dumps({"slides":[
                        {"slide":1,"tts_text":"Evaluate at c. Next."},
                        {"slide":2,"tts_text":second},
                    ]}),encoding="utf-8")
                sidecar()
                calls=[]
                def synthesize(text, output):
                    calls.append(text)
                    fake_wav(output, frames=24000+len(text))
                    return "google_cloud_chirp3"
                with patch.object(tts,"_load_runtime_environment"), patch.object(tts,"synthesize",side_effect=synthesize):
                    tts.main()
                    self.assertEqual(len(calls),2)
                    first=pv.digest_file(Path("slide1.wav"))
                    tts.main()
                    self.assertEqual(len(calls),2)
                    sidecar("Find the derivative.")
                    tts.main()
                    self.assertEqual(len(calls),3)
                    self.assertEqual(pv.digest_file(Path("slide1.wav")),first)
                    rec=pv.verify_manifest(Path("."),[
                        tts.normalize_scientific_speech("Evaluate at c. Next."),
                        tts.normalize_scientific_speech("Find the derivative."),
                    ])
                    self.assertEqual(rec["slide_count"],2)
            finally:
                os.chdir(prior)

    def test_failed_second_provider_preserves_old_second_wav_and_no_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            prior=Path.cwd();os.chdir(root)
            try:
                Path("script_tts.json").write_text(json.dumps({"slides":[
                    {"slide":1,"tts_text":"At c. Now."},
                    {"slide":2,"tts_text":"At c. Then."},
                ]}),encoding="utf-8")
                fake_wav(Path("slide2.wav"),frames=22000)
                old=pv.digest_file(Path("slide2.wav"))
                providers=iter(["google_cloud_chirp3","sapi"])
                def synth(text, output):
                    fake_wav(output)
                    return next(providers)
                with patch.object(tts,"_load_runtime_environment"), patch.object(tts,"synthesize",side_effect=synth):
                    with self.assertRaisesRegex(pv.TTSProvenanceError, "Mixed"):
                        tts.main()
                self.assertEqual(pv.digest_file(Path("slide2.wav")),old)
                self.assertFalse(Path(pv.MANIFEST_FILE).exists())
            finally:
                os.chdir(prior)


if __name__=="__main__":
    unittest.main()
