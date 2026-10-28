import tempfile,unittest
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_real_wav_discovery import discover_wavs
from microgen_tts_inventory_integrity import revalidate_inventory,InventoryIntegrityError

class PartialDiscoveryTests(unittest.TestCase):
 def test_unsupported_wav_marks_inventory_partial(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);make(p/"valid.wav",1200);(p/"bad.wav").write_bytes(b"not a wav")
   report=discover_wavs(p)
   self.assertEqual(report["candidate_count"],1)
   self.assertEqual(report["files_skipped"],1)
   self.assertFalse(report["discovery_complete"])
   self.assertEqual(report["discovery_status"],"PARTIAL_UNINSPECTED_WAVS")
   verdict=revalidate_inventory(report)
   self.assertTrue(verdict["inventory_partial"])
   self.assertFalse(verdict["phonetic_benchmark_ready"])
 def test_complete_inventory_when_all_wavs_supported(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);make(p/"valid.wav",1200)
   report=discover_wavs(p)
   self.assertTrue(report["discovery_complete"])
   self.assertTrue(revalidate_inventory(report)["inventory_complete"])
 def test_false_completeness_claim_detected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);make(p/"valid.wav",1200);(p/"bad.wav").write_bytes(b"broken")
   report=discover_wavs(p);report["discovery_complete"]=True
   with self.assertRaisesRegex(InventoryIntegrityError,"coverage"):
    revalidate_inventory(report)
