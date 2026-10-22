import tempfile,unittest,wave
from pathlib import Path
from microgen_tts_pcm_features import pcm_envelope
from microgen_tts_clip_quality import screen_clip

class WeightedQualityTests(unittest.TestCase):
 def test_one_sample_clipping_does_not_count_as_full_second_frame(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"partial.wav"
   with wave.open(str(p),"wb") as f:
    f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
    f.writeframes(b"\x10\x27"*480 + b"\xff\x7f")
   features=pcm_envelope(p)
   self.assertEqual(features["frame_sample_counts"],[480,1])
   quality=screen_clip(p)
   self.assertLess(quality["mean_clipping_fraction"],.01)
   self.assertNotIn("HIGH_CLIPPING_AUDIO",quality["dataset_readiness_blockers"])
 def test_all_samples_clipped_still_flags_blocker(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"all.wav"
   with wave.open(str(p),"wb") as f:
    f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
    f.writeframes(b"\xff\x7f"*481)
   quality=screen_clip(p)
   self.assertIn("HIGH_CLIPPING_AUDIO",quality["dataset_readiness_blockers"])
 def test_full_pcm_count_matches_total_frames(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"short.wav"
   with wave.open(str(p),"wb") as f:
    f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
    f.writeframes(b"\x00\x00"*481)
   x=pcm_envelope(p)
   self.assertEqual(sum(x["frame_sample_counts"]),x["sample_count"])
