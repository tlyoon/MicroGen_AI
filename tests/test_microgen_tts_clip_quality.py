import tempfile,unittest
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_clip_quality import screen_clip,QualityError
from microgen_tts_corpus_readiness import audit_corpus
from microgen_tts_audio_snippets import extract_clips
from microgen_tts_pcm_features import file_sha256

class ClipQualityTests(unittest.TestCase):
    def test_good_signal_has_no_signal_quality_blocker_only(self):
        with tempfile.TemporaryDirectory() as td:
            wav=Path(td)/"good.wav";make(wav,8000)
            r=screen_clip(wav)
            self.assertTrue(r["training_sample_usable_by_signal_only"])
            self.assertFalse(r["phonetic_accuracy_certified"])
    def test_silent_clip_does_not_become_training_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            wav=Path(td)/"silent.wav";make(wav,0)
            r=screen_clip(wav)
            self.assertIn("LOW_INFORMATION_AUDIO",r["dataset_readiness_blockers"])
    def test_severely_clipped_clip_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            wav=Path(td)/"clipped.wav";make(wav,32767)
            r=screen_clip(wav)
            self.assertIn("HIGH_CLIPPING_AUDIO",r["dataset_readiness_blockers"])
    def test_invalid_budgets_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            wav=Path(td)/"w.wav";make(wav,100)
            with self.assertRaises(QualityError):
                screen_clip(wav,min_rms=-1)
    def test_corpus_report_propagates_clip_quality_blockers(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);lesson=root/"lesson";lesson.mkdir()
            wav=lesson/"source.wav";make(wav,0)
            external=root/"clips";extract_clips(wav,file_sha256(wav),
               [{"start_seconds":.1,"end_seconds":.3}],external)
            r=audit_corpus([{"source_wav":str(wav),"snippet_directory":str(external),
                             "source_group_id":"single"}])
            self.assertIn("LOW_INFORMATION_AUDIO_CLIPS",
                          r["technical_blockers_to_phonetic_benchmark"])
            self.assertFalse(r["phonetic_accuracy_verified"])
