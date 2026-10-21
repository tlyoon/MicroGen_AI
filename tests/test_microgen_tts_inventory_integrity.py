import tempfile,unittest
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_real_wav_discovery import discover_wavs
from microgen_tts_inventory_integrity import revalidate_inventory,InventoryIntegrityError

class InventoryTests(unittest.TestCase):
    def case(self,root):
        make(root/"a.wav",2000)
        return discover_wavs(root)
    def test_clean_inventory_revalidates_without_claiming_accuracy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);snapshot=self.case(root)
            verified=revalidate_inventory(snapshot)
            self.assertEqual(verified["verified_wav_count"],1)
            self.assertFalse(verified["phonetic_benchmark_ready"])
            self.assertFalse(verified["publication_performed"])
    def test_source_wave_change_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);snapshot=self.case(root);make(root/"a.wav",3000)
            with self.assertRaisesRegex(InventoryIntegrityError,"Stale"):
                revalidate_inventory(snapshot)
    def test_new_wave_or_removed_wave_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);snapshot=self.case(root);make(root/"b.wav",1500)
            with self.assertRaises(InventoryIntegrityError):
                revalidate_inventory(snapshot)
            (root/"b.wav").unlink();(root/"a.wav").unlink()
            with self.assertRaises(InventoryIntegrityError):
                revalidate_inventory(snapshot)
    def test_invented_phonetic_labels_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);snapshot=self.case(root)
            snapshot["real_wav_candidates"][0]["phoneme_label"]="WHY"
            with self.assertRaises(InventoryIntegrityError):
                revalidate_inventory(snapshot)
    def test_forged_checksums_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);snapshot=self.case(root)
            snapshot["real_wav_candidates"][0]["source_pcm_sha256"]="0"*64
            with self.assertRaises(InventoryIntegrityError):
                revalidate_inventory(snapshot)
