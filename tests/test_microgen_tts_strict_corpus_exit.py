import json,tempfile,unittest
from pathlib import Path
from test_microgen_tts_corpus_readiness import CorpusReadinessTests
from microgen_tts_real_wav_discovery import discover_wavs
from microgen_tts_corpus_readiness import main

class StrictCorpusExitTests(unittest.TestCase):
 def test_unready_corpus_returns_nonzero_but_writes_truthful_report(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);entry=CorpusReadinessTests().entry(p)
   src=p/"inputs.json";src.write_text(json.dumps([entry]))
   snapshot=p/"inventory.json"
   snapshot.write_text(json.dumps(discover_wavs(Path(entry["source_wav"]).parent)))
   out=p/"strict.json"
   result=main([str(src),str(out),"--inventory",str(snapshot),"--require-ready"])
   self.assertEqual(result,2)
   report=json.loads(out.read_text())
   self.assertFalse(report["phonetic_accuracy_verified"])
   self.assertTrue(report["source_inventory_revalidated"])
   self.assertFalse(report["publication_performed"])
 def test_normal_read_only_report_still_returns_zero(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);entry=CorpusReadinessTests().entry(p)
   src=p/"inputs.json";src.write_text(json.dumps([entry]))
   out=p/"summary.json"
   self.assertEqual(main([str(src),str(out)]),0)
   self.assertEqual(json.loads(out.read_text())["status"],
                    "CORPUS_NOT_READY_FOR_PHONETIC_SCORING")
 def test_source_data_never_changed(self):
  with tempfile.TemporaryDirectory() as td:
   from microgen_tts_pcm_features import file_sha256
   p=Path(td);entry=CorpusReadinessTests().entry(p)
   wav=Path(entry["source_wav"]);sha=file_sha256(wav)
   src=p/"inputs.json";src.write_text(json.dumps([entry]))
   out=p/"strict.json"
   self.assertEqual(main([str(src),str(out),"--require-ready"]),2)
   self.assertEqual(file_sha256(wav),sha)
