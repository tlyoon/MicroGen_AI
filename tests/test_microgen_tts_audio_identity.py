import tempfile,unittest
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_pcm_features import file_sha256
from microgen_tts_audio_identity import decoded_pcm_sha256
from microgen_tts_grouped_holdout import partition_corpus,HoldoutError
from microgen_tts_corpus_readiness import audit_corpus
from microgen_tts_audio_snippets import extract_clips

class PcmIdentityTests(unittest.TestCase):
    def test_distinct_container_bytes_same_pcm_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);a=p/"a.wav";b=p/"b.wav";make(a,4000);b.write_bytes(a.read_bytes()+b"trailing metadata")
            self.assertNotEqual(file_sha256(a),file_sha256(b))
            self.assertEqual(decoded_pcm_sha256(a),decoded_pcm_sha256(b))
    def test_different_sample_content_differs(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);a=p/"a.wav";b=p/"b.wav";make(a,1000);make(b,1001)
            self.assertNotEqual(decoded_pcm_sha256(a),decoded_pcm_sha256(b))
    def test_cross_group_pcm_duplicate_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);a=p/"a.wav";b=p/"b.wav";make(a,1000);b.write_bytes(a.read_bytes()+b"metadata")
            digest=decoded_pcm_sha256(a)
            records=[
                {"clip_sha256":f"{1:064x}","source_wav_sha256":file_sha256(a),"source_pcm_sha256":digest,"source_group_id":"lecture-A","phoneme_label":None},
                {"clip_sha256":f"{2:064x}","source_wav_sha256":file_sha256(b),"source_pcm_sha256":digest,"source_group_id":"lecture-B","phoneme_label":None}]
            with self.assertRaisesRegex(HoldoutError,"Identical decoded"):
                partition_corpus(records)
    def test_missing_pcm_identity_is_honestly_unverified(self):
        samples=[{"clip_sha256":f"{i+50:064x}","source_wav_sha256":f"{i:064x}","source_group_id":f"lesson-{i}","phoneme_label":None} for i in (1,2)]
        result=partition_corpus(samples)
        self.assertFalse(result["source_pcm_identity_verified"])
        self.assertIn("SOURCE_PCM_FINGERPRINTS_MISSING",result["scoring_blockers"])
    def test_real_corpus_requires_pcm_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);lesson=p/"lesson";lesson.mkdir();wav=lesson/"slide.wav";make(wav,1000)
            out=p/"clips";extract_clips(wav,file_sha256(wav),[{"start_seconds":.1,"end_seconds":.3}],out)
            report=audit_corpus([{"source_wav":str(wav),"snippet_directory":str(out),"source_group_id":"lecture"}])
            self.assertEqual(len(report["sources_verified"][0]["pcm_sha256"]),64)
            self.assertTrue(report["grouped_holdout"]["source_pcm_identity_verified"])
