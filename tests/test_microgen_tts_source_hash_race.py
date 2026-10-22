import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_microgen_tts_pcm_features import make
from microgen_tts_real_wav_discovery import discover_wavs

class StableDiscoveryTests(unittest.TestCase):
 def test_wav_changed_between_hash_and_pcm_stops_valid_claim(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);wav=root/"lecture.wav";make(wav,1000)
   def change_file(p):
    make(Path(p),1500)
    return "0"*64
   with patch("microgen_tts_real_wav_discovery.decoded_pcm_sha256",side_effect=change_file):
    r=discover_wavs(root)
   self.assertEqual(r["candidate_count"],0)
   self.assertEqual(r["files_skipped"],1)
   self.assertFalse(r["discovery_complete"])
 def test_stable_pcm_has_normal_candidate(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);make(root/"valid.wav",1000)
   r=discover_wavs(root)
   self.assertEqual(r["candidate_count"],1)
   self.assertTrue(r["discovery_complete"])
