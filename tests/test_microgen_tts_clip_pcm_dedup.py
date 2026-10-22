import tempfile,unittest,wave
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_pcm_features import file_sha256
from microgen_tts_grouped_holdout import partition_corpus,HoldoutError
from microgen_tts_audio_identity import decoded_pcm_sha256
from microgen_tts_audio_snippets import extract_clips
from microgen_tts_corpus_readiness import audit_corpus

class ClipPcmDedupTests(unittest.TestCase):
 def test_distinct_containers_identical_decoded_clip_across_groups_fails(self):
  records=[
   {"source_wav_sha256":f"{i:064x}","source_pcm_sha256":f"{i+10:064x}",
    "clip_sha256":f"{i+20:064x}","clip_pcm_sha256":f"{99:064x}",
    "source_group_id":f"speaker-{i}","phoneme_label":None} for i in (1,2)]
  with self.assertRaisesRegex(HoldoutError,"Identical decoded clip"):
   partition_corpus(records)
 def test_complete_paired_clip_identity_is_present(self):
  rows=[{"source_wav_sha256":f"{i:064x}","source_pcm_sha256":f"{i+10:064x}",
         "clip_sha256":f"{i+20:064x}","clip_pcm_sha256":f"{i+30:064x}",
         "source_group_id":f"speaker-{i}","phoneme_label":None} for i in (1,2)]
  result=partition_corpus(rows)
  self.assertTrue(result["clip_pcm_identity_verified"])
  self.assertNotIn("CLIP_PCM_FINGERPRINTS_MISSING",result["scoring_blockers"])
 def test_missing_clip_pcm_is_explicitly_unverified(self):
  rows=[{"source_wav_sha256":f"{i:064x}","clip_sha256":f"{i+20:064x}",
         "source_group_id":f"speaker-{i}","phoneme_label":None} for i in (1,2)]
  result=partition_corpus(rows)
  self.assertFalse(result["clip_pcm_identity_verified"])
  self.assertIn("CLIP_PCM_FINGERPRINTS_MISSING",result["scoring_blockers"])
