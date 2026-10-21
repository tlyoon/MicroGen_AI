import tempfile,unittest
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_real_wav_discovery import discover_wavs,DiscoveryError

class DiscoveryTests(unittest.TestCase):
    def test_real_wavs_discovered_as_unlabelled(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);lesson=root/"lesson";lesson.mkdir();make(lesson/"a.wav",1000)
            report=discover_wavs(root)
            self.assertEqual(report["candidate_count"],1)
            self.assertFalse(report["independent_source_groups_verified"])
            self.assertIsNone(report["real_wav_candidates"][0]["phoneme_label"])
    def test_storage_not_scanned(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);archive=root/"storage";archive.mkdir();make(archive/"archived.wav",1000)
            self.assertEqual(discover_wavs(root)["candidate_count"],0)
    def test_bounded_file_count_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);make(root/"a.wav",1000);make(root/"b.wav",1000)
            with self.assertRaises(DiscoveryError):
                discover_wavs(root,max_files=1)
    def test_pcm_duplicate_candidate_flag_not_independent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);make(root/"a.wav",1000);(root/"b.wav").write_bytes((root/"a.wav").read_bytes()+b"metadata")
            report=discover_wavs(root)
            self.assertEqual(report["candidate_count"],2)
            self.assertEqual(report["real_wav_candidates"][0]["source_pcm_sha256"],
                             report["real_wav_candidates"][1]["source_pcm_sha256"])
            self.assertFalse(report["independent_source_groups_verified"])
