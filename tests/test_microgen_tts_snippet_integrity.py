import tempfile,unittest,json,wave
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_pcm_features import file_sha256
from microgen_tts_audio_snippets import extract_clips
from microgen_tts_snippet_integrity import verify_snippets,SnippetIntegrityError

class SnippetIntegrityTests(unittest.TestCase):
    def setup(self,root):
        lesson=root/"lesson";lesson.mkdir();source=lesson/"slide.wav";make(source,1300)
        out=root/"qa";extract_clips(source,file_sha256(source),
             [{"start_seconds":.1,"end_seconds":.3}],out)
        return source,out
    def test_real_byte_exact_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            source,out=self.setup(Path(td))
            check=verify_snippets(source,out)
            self.assertTrue(check["structural_integrity_passed"])
            self.assertFalse(check["phonetic_accuracy_certified"])
    def test_output_wav_changed_does_not_sneak_through(self):
        with tempfile.TemporaryDirectory() as td:
            source,out=self.setup(Path(td))
            with (out/"candidate_01.wav").open("ab") as f:f.write(b"x")
            with self.assertRaises(SnippetIntegrityError):
                verify_snippets(source,out)
    def test_manifest_false_labels_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            source,out=self.setup(Path(td))
            p=out/"snippet_manifest.json";m=json.loads(p.read_text())
            m["snippets"][0]["phoneme_label"]="WHY"
            p.write_text(json.dumps(m))
            with self.assertRaisesRegex(SnippetIntegrityError,"falsely labeled"):
                verify_snippets(source,out)
    def test_invalid_sample_interval_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            source,out=self.setup(Path(td))
            p=out/"snippet_manifest.json";m=json.loads(p.read_text())
            m["snippets"][0]["start_sample"]=-1
            p.write_text(json.dumps(m))
            with self.assertRaises(SnippetIntegrityError):
                verify_snippets(source,out)
