import tempfile, unittest,wave
from pathlib import Path
from microgen_tts_pcm_features import pcm_envelope,compare_format,AcousticFeatureError

def make(path,amplitude=1000,frames=24000):
    with wave.open(str(path),"wb") as sound:
        sound.setnchannels(1);sound.setsampwidth(2);sound.setframerate(24000)
        sound.writeframes(int(amplitude).to_bytes(2,"little",signed=True)*frames)

class PcmFeatureTests(unittest.TestCase):
    def test_measure_synthetic_rms_without_making_phoneme_claim(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a.wav";make(p,16384)
            r=pcm_envelope(p)
            self.assertEqual(r["frames"],50)
            self.assertAlmostEqual(r["whole_rms"],0.5,places=4)
            self.assertFalse(r["phonetic_correctness_proven"])
            self.assertEqual(r["signal_label"],"UNCLASSIFIED_ACOUSTIC_MEASUREMENTS")
    def test_silence_and_clipping(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a.wav";make(p,0)
            r=pcm_envelope(p)
            self.assertEqual(r["frame_zero_fraction"][0],1.)
            make(p,32767)
            r=pcm_envelope(p)
            self.assertEqual(r["frame_clipping_fraction"][0],1.)
    def test_format_and_duration_limits_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a.wav";make(p,10)
            with self.assertRaises(AcousticFeatureError):pcm_envelope(p,frame_ms=7)
            with self.assertRaises(AcousticFeatureError):pcm_envelope(p,max_seconds=0.5)
            with self.assertRaises(AcousticFeatureError):compare_format(
                {"sample_rate_hz":24000,"frame_ms":20},
                {"sample_rate_hz":44100,"frame_ms":20})
    def test_source_file_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a.wav";make(p)
            before=p.read_bytes();a=pcm_envelope(p)
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual(len(a["wav_sha256"]),64)
