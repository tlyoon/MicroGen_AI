import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_microgen_tts_audio_snippets import ClipTests
from microgen_tts_audio_snippets import extract_clips
from microgen_tts_pcm_features import file_sha256

class AtomicClipTests(unittest.TestCase):
    def test_no_incomplete_final_output_after_manifest_write_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src,sha=ClipTests().fixture(root)
            original=file_sha256(src);out=root/"complete"
            with patch("microgen_tts_audio_snippets.json.dump",side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    extract_clips(src,sha,[{"start_seconds":.1,"end_seconds":.4}],out)
            self.assertFalse(out.exists())
            self.assertEqual(list(root.glob(".microgen-clips-pending-*")),[])
            self.assertEqual(file_sha256(src),original)
    def test_no_incomplete_folder_after_rename_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src,sha=ClipTests().fixture(root)
            with patch("microgen_tts_audio_snippets.os.rename",side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    extract_clips(src,sha,[{"start_seconds":.1,"end_seconds":.4}],root/"complete")
            self.assertFalse((root/"complete").exists())
            self.assertEqual(list(root.glob(".microgen-clips-pending-*")),[])
    def test_happy_path_retains_new_manifest_and_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src,sha=ClipTests().fixture(root)
            out=root/"complete"
            receipt=extract_clips(src,sha,[{"start_seconds":.1,"end_seconds":.4}],out)
            self.assertEqual(len(receipt["snippets"]),1)
            self.assertTrue((out/"snippet_manifest.json").exists())
            self.assertEqual(list(root.glob(".microgen-clips-pending-*")),[])
