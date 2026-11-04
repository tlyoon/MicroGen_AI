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
            with self.assertRaises(gate.AutonomousAcousticError):
                gate.audit_stage(stage,engines=(outage,outage),
                                 models=("A","B"))
            self.assertEqual(len(calls),2)
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
