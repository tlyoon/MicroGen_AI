import tempfile,unittest,wave
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_pcm_features import file_sha256
from microgen_tts_audio_snippets import extract_clips,ClipError

class ClipTests(unittest.TestCase):
    def fixture(self,root):
        stage=root/"source";stage.mkdir()
        wav=stage/"slide.wav";make(wav,1200,frames=24000)
        return wav,file_sha256(wav)
    def test_sample_accurate_sha_bound_excerpts(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);wav,h=self.fixture(root)
            receipt=extract_clips(wav,h,[
                {"start_seconds":.2,"end_seconds":.4},
                {"start_seconds":.6,"end_seconds":.8}],root/"clips")
            self.assertEqual(len(receipt["snippets"]),2)
            self.assertEqual(receipt["snippets"][0]["start_sample"],4800)
            self.assertIsNone(receipt["snippets"][0]["phoneme_label"])
            self.assertTrue((root/"clips"/"candidate_01.wav").exists())
            self.assertEqual(file_sha256(wav),h)
    def test_source_child_path_and_overwrite_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);wav,h=self.fixture(root)
            with self.assertRaises(ClipError):
                extract_clips(wav,h,[{"start_seconds":0,"end_seconds":.2}],wav.parent/"clips")
            extract_clips(wav,h,[{"start_seconds":0,"end_seconds":.2}],root/"clips")
            with self.assertRaises(ClipError):
                extract_clips(wav,h,[{"start_seconds":0,"end_seconds":.2}],root/"clips")
    def test_bad_source_sha_or_bad_bounds_prevent_all_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);wav,h=self.fixture(root)
            with self.assertRaises(ClipError):
                extract_clips(wav,"0"*64,[{"start_seconds":0,"end_seconds":.2}],root/"clips")
            with self.assertRaises(ClipError):
                extract_clips(wav,h,[{"start_seconds":.9,"end_seconds":1.2}],root/"clips")
            self.assertFalse((root/"clips").exists())
    def test_overlapping_unsorted_ranges_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);wav,h=self.fixture(root)
            with self.assertRaises(ClipError):
                extract_clips(wav,h,[{"start_seconds":.1,"end_seconds":.5},
                                     {"start_seconds":.4,"end_seconds":.7}],root/"clips")
