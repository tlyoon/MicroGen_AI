import tempfile,unittest
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_real_wav_discovery import discover_wavs
from microgen_tts_inventory_integrity import revalidate_inventory,InventoryIntegrityError

class InventorySummaryTests(unittest.TestCase):
 def sample(self,root):
  make(root/"real.wav",1234)
  return discover_wavs(root)
 def test_skipped_file_count_not_accepted_if_forged(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);x=self.sample(root);x["files_skipped"]+=1
   with self.assertRaisesRegex(InventoryIntegrityError,"summary"):revalidate_inventory(x)
 def test_publication_misstatement_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);x=self.sample(root);x["publication_performed"]=True
   with self.assertRaisesRegex(InventoryIntegrityError,"summary"):revalidate_inventory(x)
 def test_missing_summary_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);x=self.sample(root);x.pop("files_skipped")
   with self.assertRaises(InventoryIntegrityError):revalidate_inventory(x)
