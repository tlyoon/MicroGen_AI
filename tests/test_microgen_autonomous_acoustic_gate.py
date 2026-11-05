"""Offline autonomous acoustic-QA acceptance, failure and same-voice repair."""
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave

import microgen_autonomous_acoustic_gate as gate
from microgen_tts_provenance import make_record,write_manifest,verify_manifest,digest_file
from text_to_speech_v25 import normalize_scientific_speech

WORDS=[
    "The orange engine spins steadily in open space.",
    "The purple engine moves steadily around the laboratory."
]


def make_wav(path:Path,frequency:int=233):
    rate=24000
    samples=b"".join(struct.pack("<h",int(9500*math.sin(2*math.pi*
                                   frequency*i/rate))) for i in range(rate*2))
    with wave.open(str(path),"wb") as audio:
        audio.setparams((1,2,rate,0,"NONE","not compressed"))
        audio.writeframes(samples)


def audio_stage(root:Path, texts:list[str]=WORDS)->Path:
    stage=root/"test_stage"
    stage.mkdir()
    (stage/".microgen_tts_cache").mkdir()
    sidecar={"slides":[{"slide":i,"narration":raw,"tts_text":raw}
                 for i,raw in enumerate(texts,1)]}
    (stage/"script_tts.json").write_text(json.dumps(sidecar),encoding="utf8")
    records=[]
    spoken=list(map(normalize_scientific_speech,texts))
    for i,words in enumerate(spoken,1):
        path=stage/f"slide{i}.wav"
        make_wav(path,frequency=230+i)
        record=make_record(
            slide=i,path=path,text=words,provider="gemini_flash_lite_tts",
            key=f"Gemini-private-key-identity-{i}",
            voice_name="Kore",language_code="en-US",
            speaking_rate=1.0,location="global")
        records.append(record)
        (stage/".microgen_tts_cache"/f"slide{i}.json").write_text(
            json.dumps(record),encoding="utf8")
    write_manifest(stage,records,spoken)
    return stage


class AutonomousAudioTests(unittest.TestCase):
    def test_two_independent_recognizers_pass_and_sha_pin(self):
        with tempfile.TemporaryDirectory() as td:
            stage=audio_stage(Path(td))
            clean={f"slide{i}.wav":normalize_scientific_speech(words)
                   for i,words in enumerate(WORDS,1)}
            def recognize(path):
                return clean[path.name]
            receipt=gate.audit_stage(stage,engines=(recognize,recognize),
                                     models=("model-A","model-B"))
            self.assertEqual(receipt["slide_count"],2)
            self.assertEqual(receipt["repaired_audio_slides"],0)
            self.assertFalse(receipt["human_approval_required"])
            self.assertFalse(receipt["publication_allowed"])
            self.assertEqual(gate.verify_receipt(stage)["slide_count"],2)
            with (stage/"slide1.wav").open("ab") as f:
                f.write(b"corruption")
            with self.assertRaises((gate.AutonomousAcousticError,ValueError)):
                gate.verify_receipt(stage)

    def test_distinct_model_identities_mandatory(self):
        with tempfile.TemporaryDirectory() as td:
            stage=audio_stage(Path(td))
            with self.assertRaises(gate.AutonomousAcousticError):
                gate.audit_stage(stage,engines=(lambda p:WORDS[0],lambda p:WORDS[0]),
                                 models=("same","same"))
            self.assertFalse((stage/gate.RECEIPT).exists())

    def test_outage_is_bounded_and_never_passed(self):
        with tempfile.TemporaryDirectory() as td:
            stage=audio_stage(Path(td))
            calls=[]
            def outage(_):
                calls.append("fail")
                raise RuntimeError("503 provider unavailable")
            with self.assertRaisesRegex(
                    gate.AutonomousAcousticError, "transcription unavailable"):
                gate.audit_stage(stage,engines=(outage,outage),
                                 models=("A","B"))
            self.assertEqual(len(calls),2)
            self.assertFalse((stage/gate.RECEIPT).exists())
            blocked=list(stage.glob(".microgen_acoustic_blocked_*.json"))
            self.assertEqual(len(blocked),1)
            evidence=json.loads(blocked[0].read_text())
            self.assertEqual(evidence["unavailable_recognizer_passes"],[0,1])
            self.assertEqual(set(evidence["slide_assessments"].values()),
                             {"REVIEW_REQUIRED_TRANSCRIPTION_UNAVAILABLE"})

    def test_repeated_failed_audits_keep_fresh_status_only_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            stage=audio_stage(Path(td))
            before=[digest_file(stage/f"slide{i}.wav") for i in (1,2)]
            def unavailable(_):
                raise RuntimeError("503 UNAVAILABLE")
            for _ in range(2):
                with self.assertRaises(gate.AutonomousAcousticError):
                    gate.audit_stage(stage,engines=(unavailable,unavailable),
                                     models=("model-A","model-B"))
            records=sorted(stage.glob(".microgen_acoustic_blocked_*.json"))
            self.assertEqual(len(records),2)
            for record in records:
                data=json.loads(record.read_text())
                self.assertEqual(data["review_required_slides"],[1,2])
                self.assertEqual(data["unavailable_recognizer_passes"],[0,1])
                self.assertEqual(data["recognition_models"],["model-A","model-B"])
                self.assertEqual(data["model_difference_fractions"]["1"],[])
                self.assertFalse(data["accepted_for_video"])
                self.assertNotIn("transcripts",data)
            self.assertEqual(before,[digest_file(stage/f"slide{i}.wav")
                                     for i in (1,2)])

    def test_partial_asr_is_rechecked_once_without_exposing_script(self):
        with tempfile.TemporaryDirectory() as td:
            sentence="The orange engine spins steadily in open space. "
            spoken=sentence*5
            stage=audio_stage(Path(td),texts=[spoken])
            calls=[]
            def first(_):
                calls.append("first")
                return "The orange engine" if calls.count("first")==1 else spoken
            def second(_):
                calls.append("second")
                return spoken
            report=gate._transcripts(stage,[normalize_scientific_speech(spoken)],
                                     (first,second),("model-A","model-B"),memo={})
            self.assertEqual(report["review_required_slides"],[])
            self.assertEqual(calls,["first","first","second"])

    def test_still_truncated_after_one_recheck_remains_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            spoken="The purple engine moves steadily around the laboratory. "*5
            stage=audio_stage(Path(td),texts=[spoken])
            calls=[]
            def first(_):
                calls.append("first")
                return "The purple engine"
            def second(_):
                calls.append("second")
                return spoken
            report=gate._transcripts(stage,[normalize_scientific_speech(spoken)],
                                     (first,second),("model-A","model-B"),memo={})
            self.assertEqual(report["review_required_slides"],[1])
            self.assertEqual(calls,["first","first","second"])

    def test_disagreement_resolves_only_after_two_blind_model_retakes(self):
        with tempfile.TemporaryDirectory() as td:
            stage=audio_stage(Path(td))
            originals=[digest_file(stage/f"slide{i}.wav") for i in (1,2)]
            calls=[]
            def first(wav):
                calls.append(("A",wav.name))
                if wav.name=="slide1.wav" and calls.count(("A","slide1.wav"))==1:
                    return "The orange engine sinks steadily in open space."
                return WORDS[int(wav.stem.removeprefix("slide"))-1]
            def second(wav):
                calls.append(("B",wav.name))
                return WORDS[int(wav.stem.removeprefix("slide"))-1]
            receipt=gate.audit_stage(stage,engines=(first,second),
                                     models=("model-A","model-B"))
            review=receipt["independent_report"]["independent_disagreement_rechecks"]
            self.assertEqual(review["attempted_slides"],[1])
            self.assertEqual(review["resolved_slides"],[1])
            self.assertEqual(receipt["repaired_audio_slides"],0)
            self.assertEqual(calls.count(("A","slide1.wav")),2)
            self.assertEqual(calls.count(("B","slide1.wav")),2)
            self.assertEqual(originals,[digest_file(stage/f"slide{i}.wav")
                                        for i in (1,2)])

    def test_persistent_disagreement_fails_after_one_bounded_retaken_pair(self):
        with tempfile.TemporaryDirectory() as td:
            stage=audio_stage(Path(td))
            calls=[]
            def first(wav):
                calls.append(("A",wav.name))
                return ("The orange engine sinks steadily in open space."
                        if wav.name=="slide1.wav" else WORDS[1])
            def second(wav):
                calls.append(("B",wav.name))
                return WORDS[int(wav.stem.removeprefix("slide"))-1]
            with self.assertRaises(gate.AutonomousAcousticError):
                gate.audit_stage(stage,engines=(first,second),
                                 models=("model-A","model-B"))
            self.assertEqual(calls.count(("A","slide1.wav")),2)
            self.assertEqual(calls.count(("B","slide1.wav")),2)
            self.assertFalse((stage/gate.RECEIPT).exists())

    def test_more_than_two_disputed_slides_never_triggers_retakes(self):
        with tempfile.TemporaryDirectory() as td:
            stage=audio_stage(Path(td),texts=[WORDS[0]]*3)
            calls=[]
            def first(wav):
                calls.append(("A",wav.name))
                return "The orange engine sinks steadily in open space."
            def second(wav):
                calls.append(("B",wav.name))
                return WORDS[0]
            with self.assertRaises(gate.AutonomousAcousticError):
                gate.audit_stage(stage,engines=(first,second),
                                 models=("model-A","model-B"))
            self.assertEqual(len(calls),6)
            self.assertFalse((stage/gate.RECEIPT).exists())

    def test_same_voice_bounded_local_rerender_passes_two_model_recheck(self):
        with tempfile.TemporaryDirectory() as td:
            stage=audio_stage(Path(td))
            before_script=digest_file(stage/"script_tts.json")
            old=digest_file(stage/"slide1.wav")
            renders=[]
            def recognize(path):
                if path.name=="slide1.wav" and digest_file(path)==old:
                    return "The orange engine sinks steadily in open space."
                if path.name=="slide1.wav":
                    return WORDS[0]
                return WORDS[1]
            def synthesize(text,destination,record):
                renders.append((text,record["provider"],record["voice_name"]))
                make_wav(destination,frequency=311)
            receipt=gate.audit_stage(
                stage,engines=(recognize,recognize),
                models=("asr-A","asr-B"),synthesize=synthesize)
            self.assertEqual(len(renders),1)
            self.assertEqual(receipt["repaired_audio_slides"],1)
            self.assertNotEqual(digest_file(stage/"slide1.wav"),old)
            self.assertEqual(digest_file(stage/"script_tts.json"),before_script)
            verify_manifest(stage,list(map(normalize_scientific_speech,WORDS)))
            self.assertEqual(gate.verify_receipt(stage)["slide_count"],2)

    def test_ambiguous_models_disagree_do_not_repair(self):
        with tempfile.TemporaryDirectory() as td:
            stage=audio_stage(Path(td))
            before=digest_file(stage/"slide1.wav")
            def recognizer_a(path):
                if path.name=="slide1.wav":
                    return "The orange engine sinks steadily in open space."
                return WORDS[1]
            def recognizer_b(path):
                return WORDS[0] if path.name=="slide1.wav" else WORDS[1]
            with self.assertRaises(gate.AutonomousAcousticError):
                gate.audit_stage(stage,engines=(recognizer_a,recognizer_b),
                                 models=("A","B"),
                                 synthesize=lambda *args: self.fail(
                                     "Ambiguous recognizers must not trigger TTS"))
            self.assertEqual(digest_file(stage/"slide1.wav"),before)
            self.assertFalse((stage/gate.RECEIPT).exists())


if __name__=="__main__":
    unittest.main()
