import tempfile
import unittest
import wave
from pathlib import Path

import microgen_tts_wave_integrity as qa

def write_wav(path,amplitude,frames=24000):
    with wave.open(str(path),"wb") as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000)
        wav.writeframes(int(amplitude).to_bytes(2,"little",signed=True)*frames)

class StreamingWaveTests(unittest.TestCase):
    def test_normal_pcm_has_no_blocking_defects(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"ok.wav";write_wav(p,1000)
            r=qa.require_structurally_usable_audio(p)
            self.assertEqual(r["blocking_defects"],[])
            self.assertEqual(r["metrics"]["samples"],24000)
            self.assertFalse(r["pronunciation_verified"])
    def test_all_zero_silence_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"silence.wav";write_wav(p,0)
            with self.assertRaisesRegex(qa.WaveIntegrityError,"digital_silence"):
                qa.require_structurally_usable_audio(p)
    def test_severe_clipping_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"clip.wav";write_wav(p,32767)
            with self.assertRaisesRegex(qa.WaveIntegrityError,"severe_clipping"):
                qa.require_structurally_usable_audio(p)
    def test_tiny_audio_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"short.wav";write_wav(p,1234,frames=200)
            with self.assertRaisesRegex(qa.WaveIntegrityError,"implausibly_short"):
                qa.require_structurally_usable_audio(p)
    def test_rejects_invalid_format(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"stereo.wav"
            with wave.open(str(p),"wb") as wav:
                wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(24000)
                wav.writeframes(b"\0"*96000)
            with self.assertRaisesRegex(qa.WaveIntegrityError,"mono"):
                qa.require_structurally_usable_audio(p)
    def test_near_silence_is_review_warning_not_phonetic_approval(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"quiet.wav";write_wav(p,1)
            r=qa.require_structurally_usable_audio(p)
            self.assertIn("very_low_signal_level",r["warnings"])
            self.assertFalse(r["listening_approved"])
    def test_chunk_sizes_match(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"ok.wav";write_wav(p,1000,frames=28019)
            first=qa.analyze_pcm(p,chunk_frames=128)
            second=qa.analyze_pcm(p,chunk_frames=16384)
            self.assertEqual(first["metrics"],second["metrics"])
    def test_padding_warnings_for_long_silence(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"padding.wav"
            with wave.open(str(p),"wb") as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000)
                wav.writeframes(b"\0\0"*210000+b"\xe8\x03"*30000)
            metrics=qa.analyze_pcm(p)
            self.assertIn("substantial_leading_silence",metrics["warnings"])
