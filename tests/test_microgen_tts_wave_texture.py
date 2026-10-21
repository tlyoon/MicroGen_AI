import tempfile, unittest,wave
from pathlib import Path
from microgen_tts_pcm_features import pcm_envelope

def write(p,pattern,repeat=480):
    with wave.open(str(p),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
        w.writeframes(b"".join(int(v).to_bytes(2,"little",signed=True)
                               for v in pattern*repeat))
class WaveTextureTests(unittest.TestCase):
    def test_continuous_tone_smoother_than_alternating_signal(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"voice.wav"
            write(p,[12000]*4)
            smooth=pcm_envelope(p)
            write(p,[12000,-12000,12000,-12000])
            alternating=pcm_envelope(p)
            self.assertEqual(smooth["frame_zero_crossing_fraction"][0],0)
            self.assertGreater(alternating["frame_zero_crossing_fraction"][0],0.99)
            self.assertGreater(alternating["frame_mean_abs_step"][0],
                               smooth["frame_mean_abs_step"][0])
            self.assertFalse(alternating["phonetic_correctness_proven"])
    def test_quiet_frame_has_no_zero_crossing(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"quiet.wav";write(p,[0]*4)
            r=pcm_envelope(p)
            self.assertTrue(all(z==0 for z in r["frame_zero_crossing_fraction"]))
            self.assertTrue(all(z==0 for z in r["frame_mean_abs_step"]))
    def test_frame_arrays_have_equal_lengths(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"w.wav";write(p,[-500,500,1000,500])
            d=pcm_envelope(p)
            self.assertEqual(len(d["frame_rms"]),len(d["frame_zero_crossing_fraction"]))
            self.assertEqual(len(d["frame_rms"]),len(d["frame_mean_abs_step"]))
