"""No-cloud post-TTS evidence capture and glossary-candidate classification."""
from __future__ import annotations
import json
import tempfile
import unittest
import wave
from pathlib import Path

import microgen_pronunciation_evidence_pipeline as p
from text_to_speech_v25 import normalize_scientific_speech as normalize


def make_stage(root):
    stage=root/"stage"
    stage.mkdir()
    slides=[
        {"slide":1,"tts_text":"Take the derivative at c. Next, integrate two functions."},
        {"slide":2,"tts_text":"The root of f(x) is positive."},
    ]
    (stage/"script_tts.json").write_text(json.dumps({"slides":slides}),encoding="utf8")
    (stage/".microgen_tts_provenance.json").write_text('{"schema_version":1}')
    for i in range(1,3):
        with wave.open(str(stage/f"slide{i}.wav"),"wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x01\x00"*16000)
    return stage,slides


def observation(words,wav_hash):
    return {"source_wav_sha256":wav_hash,
        "words":[{"word":s,"conf":0.9,"start":i*.1,"end":(i+1)*.1}
                 for i,s in enumerate(words.split())],
        "phonetic_identity_verified":False,
        "semantic_word_alignment_certified":False}


class PronunciationPipelineTests(unittest.TestCase):
    def test_integration_source_only_no_provider_and_immutable_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,slides=make_stage(root)
            data=p.build_post_tts_evidence(stage,slides,normalize)
            self.assertEqual(data["slide_count"],2)
            self.assertEqual(len(data["slide_wav_sha256"]),2)
            self.assertFalse(data["asr_evidence_attached"])
            self.assertFalse(data["publication_allowed"])
            self.assertEqual(data["candidate_count"],0)
            self.assertEqual(data["provider_calls"],0)
            self.assertIsNotNone(data["tts_provenance_manifest_sha256"])
            save=p.save_stage_evidence(stage,data)
            self.assertEqual(p.save_stage_evidence(stage,data),save)
            self.assertTrue(save.is_file())
            self.assertTrue(save.name.startswith("pronunciation_evidence_"))
            self.assertEqual(len(list(save.parent.glob("pronunciation_evidence*"))),1)
            self.assertEqual((stage/"script_tts.json").read_text(encoding="utf8"),
                             json.dumps({"slides":slides}))

    def test_actual_wav_asr_word_differences_are_not_acoustic_proof(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,slides=make_stage(root)
            sha=[p.sha_file(stage/f"slide{i}.wav") for i in (1,2)]
            obs=[
                observation("take the derivative at see next integrate to functions",sha[0]),
                observation("the route of eff of ex is positive",sha[1]),
            ]
            report=p.build_post_tts_evidence(stage,slides,normalize,observations=obs)
            self.assertTrue(report["asr_evidence_attached"])
            self.assertGreater(report["candidate_count"],0)
            self.assertGreater(report["potential_homophone_or_asr_variant_count"],0)
            pairs={(c["expected"],c["recognized"]):c for c in
                   report["unverified_word_pair_candidates"]}
            self.assertEqual(pairs[("two","to")]["priority"],
                             "POSSIBLE_HOMOPHONE_OR_ASR_VARIANT")
            self.assertEqual(pairs[("root","route")]["priority"],
                             "POSSIBLE_HOMOPHONE_OR_ASR_VARIANT")
            self.assertFalse(any(c["mispronunciation_confirmed"] for c in pairs.values()))
            self.assertFalse(report["phonetic_identity_verified"])
            self.assertEqual(report["high_confidence_diagnostic_candidate_slides"],[])

    def test_deletions_and_insertions_are_preserved_as_advisory_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            stage, slides = make_stage(Path(td))
            sha = [p.sha_file(stage / f"slide{i}.wav") for i in (1, 2)]
            obs = [
                observation("take derivative at see next integrate two functions well", sha[0]),
                observation("the root of eff of ex is positive", sha[1]),
            ]
            report = p.build_post_tts_evidence(stage, slides, normalize, observations=obs)
            rows = report["unverified_word_pair_candidates"]
            self.assertIn(("the", ""), {(x["expected"], x["recognized"]) for x in rows})
            self.assertIn(("", "well"), {(x["expected"], x["recognized"]) for x in rows})
            self.assertGreaterEqual(report["alignment_only_candidate_count"], 2)
            for row in rows:
                if not row["expected"] or not row["recognized"]:
                    self.assertEqual(row["priority"], "ALIGNMENT_INSERTION_OR_OMISSION_UNVERIFIED")
                    self.assertFalse(row["mispronunciation_confirmed"])
                    self.assertFalse(row["automatic_rule_authorized"])
                    self.assertEqual(row["examples"][0]["wav_sha256"], sha[0])
            self.assertFalse(report["publication_allowed"])

    def test_technical_term_difference_is_prioritized_but_never_auto_fixed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,slides=make_stage(root)
            sha=[p.sha_file(stage/f"slide{i}.wav") for i in (1,2)]
            obs=[
                observation("take the divide at sea next integrate two functions",sha[0]),
                observation("the root of eff of ex is positive",sha[1]),
            ]
            report=p.build_post_tts_evidence(stage,slides,normalize,observations=obs)
            ranked=report["unverified_word_pair_candidates"]
            self.assertEqual(ranked[0]["expected"],"derivative")
            self.assertEqual(ranked[0]["recognized"],"divide")
            self.assertEqual(ranked[0]["priority"],
                "POTENTIAL_TECHNICAL_TERM_DIFFERENCE_UNVERIFIED")
            self.assertGreaterEqual(report["review_priority_count"],1)
            self.assertFalse(ranked[0]["mispronunciation_confirmed"])
            self.assertFalse(ranked[0]["automatic_rule_authorized"])
            self.assertFalse(report["publication_allowed"])

    def test_real_wav_hash_drift_or_broken_source_list_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,slides=make_stage(root)
            corrupted=[dict(x) for x in slides]
            corrupted[0]["tts_text"]="Not the original"
            with self.assertRaises(p.PronunciationEvidenceError):
                p.build_post_tts_evidence(stage,corrupted,normalize)
            missing=[dict(x) for x in slides]
            missing[1]["slide"]=3
            with self.assertRaises(p.PronunciationEvidenceError):
                p.build_post_tts_evidence(stage,missing,normalize)
            (stage/"slide1.wav").unlink()
            with self.assertRaises(p.PronunciationEvidenceError):
                p.build_post_tts_evidence(stage,slides,normalize)

    def test_asr_is_sha_bound_and_not_arbitrarily_self_certified(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,slides=make_stage(root)
            h=p.sha_file(stage/"slide1.wav")
            obs=[observation("take derivative",h),observation("the root",h)]
            obs[0]["phonetic_identity_verified"]=True
            with self.assertRaises(Exception):
                p.build_post_tts_evidence(stage,slides,normalize,observations=obs)
            obs[0]["phonetic_identity_verified"]=False
            obs[1]["source_wav_sha256"]="a"*64
            with self.assertRaises(Exception):
                p.build_post_tts_evidence(stage,slides,normalize,observations=obs)

    def test_different_wav_receipt_does_not_overwrite_old_one(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,slides=make_stage(root)
            a=p.build_post_tts_evidence(stage,slides,normalize)
            old=p.save_stage_evidence(stage,a)
            with (stage/"slide1.wav").open("ab") as f:
                f.write(b"nonzero")
            b=p.build_post_tts_evidence(stage,slides,normalize)
            second=p.save_stage_evidence(stage,b)
            self.assertNotEqual(old,second)
            self.assertTrue(old.is_file())
            self.assertTrue(second.is_file())
            old.write_bytes(b"corrupt")
            with self.assertRaises(p.PronunciationEvidenceError):
                p.save_stage_evidence(stage,a)

    def test_no_write_to_my_drive(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage,slides=make_stage(root)
            with self.assertRaises(p.PronunciationEvidenceError):
                p.save_stage_evidence(stage,p.build_post_tts_evidence(stage,slides,normalize),
                                      output_directory=root/"My Drive"/"diagnostics")


if __name__=="__main__":
    unittest.main()
