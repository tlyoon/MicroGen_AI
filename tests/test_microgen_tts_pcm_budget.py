import tempfile,unittest,wave
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_audio_identity import decoded_pcm_sha256,PcmIdentityError

class FingerprintBudgetTests(unittest.TestCase):
 def test_large_input_refused_before_hash(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"big.wav";make(p,10)
   with self.assertRaisesRegex(PcmIdentityError,"budget"):
    decoded_pcm_sha256(p,max_bytes=1024)
 def test_duration_limit_refused(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"normal.wav";make(p,1000)
   with self.assertRaises(PcmIdentityError):
    decoded_pcm_sha256(p,max_seconds=.5)
 def test_regular_wav_identity_works(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"normal.wav";make(p,1000)
   self.assertEqual(len(decoded_pcm_sha256(p)),64)
 def test_invalid_limits_fail_closed(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"normal.wav";make(p,1000)
   for limit in (0,-2,True):
    with self.assertRaises(PcmIdentityError):
     decoded_pcm_sha256(p,max_bytes=limit)
