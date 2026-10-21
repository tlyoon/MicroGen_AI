import tempfile,unittest,json
from pathlib import Path
from test_microgen_tts_pcm_features import make
from microgen_tts_pcm_features import file_sha256
from microgen_tts_audio_snippets import extract_clips
from microgen_tts_corpus_readiness import audit_corpus,main

class CorpusReadinessTests(unittest.TestCase):
    def entry(self,root,index=1):
        lesson=root/f"source_{index}";lesson.mkdir()
        source=lesson/"slide.wav";make(source,index*1000)
        folder=root/f"snips_{index}"
        extract_clips(source,file_sha256(source),
                      [{"start_seconds":.1,"end_seconds":.3}],folder)
        return {"source_wav":str(source),"snippet_directory":str(folder),
                "source_group_id":f"lesson_{index}"}
    def test_single_source_cannot_claim_phonetic_accuracy(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r=audit_corpus([self.entry(p)])
            self.assertEqual(r["status"],"CORPUS_NOT_READY_FOR_PHONETIC_SCORING")
            self.assertIn("INSUFFICIENT_DISTINCT_SOURCE_GROUPS",
                          r["technical_blockers_to_phonetic_benchmark"])
            self.assertFalse(r["phonetic_accuracy_verified"])
            self.assertFalse(r["publication_performed"])
    def test_two_sources_still_need_real_labels(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);r=audit_corpus([self.entry(p,1),self.entry(p,2)])
            self.assertTrue(r["grouped_holdout"]["grouped_holdout_available"])
            self.assertIn("UNLABELLED_CLIPS_PRESENT",r["technical_blockers_to_phonetic_benchmark"])
    def test_tampered_clip_fails_audit(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);entry=self.entry(p)
            with (Path(entry["snippet_directory"])/"candidate_01.wav").open("ab") as f:f.write(b"x")
            with self.assertRaises(Exception):audit_corpus([entry])
    def test_cli_report_readonly_and_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);e=self.entry(p);source_list=p/"sources.json"
            source_list.write_text(json.dumps([e]));output=p/"report.json"
            self.assertEqual(main([str(source_list),str(output)]),0)
            report=json.loads(output.read_text())
            self.assertFalse(report["release_gate_modified"])
            self.assertFalse(report["publication_performed"])
            with self.assertRaises(SystemExit):main([str(source_list),str(output)])
