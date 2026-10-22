import tempfile,unittest
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_pcm_features import file_sha256
from microgen_tts_audio_snippets import extract_clips
from microgen_tts_real_wav_discovery import discover_wavs
from microgen_tts_corpus_readiness import audit_corpus,CorpusAuditError

class InventoryLinkedCorpusTests(unittest.TestCase):
 def prepare(self,root):
  lesson=root/"lesson";lesson.mkdir();wav=lesson/"src.wav";make(wav,3000)
  clips=root/"clips";extract_clips(wav,file_sha256(wav),[{"start_seconds":.2,"end_seconds":.4}],clips)
  return wav,[{"source_wav":str(wav),"snippet_directory":str(clips),"source_group_id":"set1"}],discover_wavs(lesson)
 def test_valid_inventory_verified_but_not_phonetic_ready(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);wav,entries,inventory=self.prepare(root)
   result=audit_corpus(entries,inventory_snapshot=inventory)
   self.assertTrue(result["source_inventory_revalidated"])
   self.assertFalse(result["phonetic_accuracy_verified"])
 def test_missing_inventory_is_explicit_blocker(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);wav,entries,inventory=self.prepare(root)
   result=audit_corpus(entries)
   self.assertFalse(result["source_inventory_revalidated"])
   self.assertIn("SOURCE_INVENTORY_NOT_CROSSCHECKED",result["technical_blockers_to_phonetic_benchmark"])
 def test_validated_inventory_not_containing_source_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);wav,entries,inventory=self.prepare(root)
   other=root/"other";other.mkdir();make(other/"else.wav",3000)
   wrong=discover_wavs(other)
   with self.assertRaisesRegex(CorpusAuditError,"absent"):
    audit_corpus(entries,inventory_snapshot=wrong)
 def test_incomplete_snapshot_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);wav,entries,inventory=self.prepare(root)
   (wav.parent/"invalid.wav").write_bytes(b"corrupt")
   inventory=discover_wavs(wav.parent)
   with self.assertRaisesRegex(CorpusAuditError,"Incomplete"):
    audit_corpus(entries,inventory_snapshot=inventory)
