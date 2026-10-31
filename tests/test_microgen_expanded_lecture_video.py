"""Synthetic 14-slide media/source-chain tests, no private textbook or API calls."""
import json
import math
import tempfile
import unittest
import wave
from array import array
from pathlib import Path

from microgen_pronunciation_closed_loop import sha_file
from microgen_expanded_neural_tts import prepare_request,verify_audio
from microgen_offline_diagnostic_av import inspect_inputs
from microgen_expanded_lecture_video import preflight,ExpandedLectureError
from test_microgen_expanded_neural_tts import setup_case

def make_case(folder):
    stage,n,deck,coverage,model=setup_case(folder)
    plan=folder/"plan.json"
    audio=folder/"wave";audio.mkdir()
    order=prepare_request(stage,n,deck,coverage,model)
    tone=array("h",[int(1800*math.sin(2*math.pi*x/96)) for x in range(96)])
    for idx in range(1,15):
        path=audio/f"slide{idx:02d}.wav"
        with wave.open(str(path),"wb") as output:
            output.setnchannels(1);output.setsampwidth(2);output.setframerate(22050)
            output.writeframes(tone.tobytes()*(22050*21//96))
    receipt=verify_audio(audio,order)
    receipt.update({"status":"FOURTEEN_REAL_NEURAL_WAV_CANDIDATES_NOT_FORMAL",
                    "formal_voice_authorized":False,"publication_allowed":False})
    receipt_file=audio/"expanded_neural_qa_receipt.json"
    receipt_file.write_text(json.dumps(receipt))
    asr=folder/"asr.json"
    asr.write_text(json.dumps({
        "status":"FOURTEEN_NEURAL_WAV_ASR_ADVISORY","slide_count":14,
        "slides":[{"slide":i,"wav_sha256":receipt["slides"][i-1]["probe_wav_sha256"]}
                  for i in range(1,15)],
        "audio_receipt_sha256":sha_file(receipt_file),
        "narration_sha256":sha_file(n),
        "recognizer_glossary_gaps":1,"targeted_hazard_count":0,
        "all_phonemes_independently_verified":False,
        "formal_voice_authorized":False,"publication_allowed":False}))
    return stage,n,plan,deck,coverage,audio,model,asr

class FourteenVideoTests(unittest.TestCase):
    def test_expanded_source_and_14_pcm_frames_preflight(self):
        with tempfile.TemporaryDirectory() as td:
            args=make_case(Path(td))
            info=preflight(*args)
            self.assertEqual(len(info["input_wav_sha256"]),14)
            self.assertTrue(info["academic_coverage_spot_check_14_of_14"])
            self.assertFalse(info["publication_allowed"])
            self.assertEqual(info["ASR_glossary_misses_advisory"],1)
            mux=inspect_inputs(args[3],args[1],args[5],
                  declared_diagnostic_voice="Piper test candidate not formal")
            self.assertEqual(mux["slide_count"],14)
            self.assertFalse(mux["voice_is_formal"])

    def test_swapped_wav_fails_without_false_release(self):
        with tempfile.TemporaryDirectory() as td:
            args=make_case(Path(td))
            (args[5]/"slide04.wav").write_bytes(b"swapped-wav-data")
            with self.assertRaises(Exception):preflight(*args)

    def test_forged_asr_source_or_phonetic_release_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            args=make_case(Path(td))
            receipt=json.loads(args[7].read_text())
            receipt["all_phonemes_independently_verified"]=True
            args[7].write_text(json.dumps(receipt))
            with self.assertRaises(ExpandedLectureError):preflight(*args)
        with tempfile.TemporaryDirectory() as td:
            args=make_case(Path(td))
            receipt=json.loads(args[7].read_text())
            receipt["audio_receipt_sha256"]="not-source-verified"
            args[7].write_text(json.dumps(receipt))
            with self.assertRaises(ExpandedLectureError):preflight(*args)

    def test_confirmed_math_term_hazard_cannot_silently_pass(self):
        with tempfile.TemporaryDirectory() as td:
            args=make_case(Path(td))
            receipt=json.loads(args[7].read_text())
            receipt["targeted_hazard_count"]=1
            args[7].write_text(json.dumps(receipt))
            with self.assertRaises(ExpandedLectureError):preflight(*args)

    def test_wrong_plan_pdf_and_voice_model_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            args=make_case(Path(td))
            data=json.loads(args[4].read_text())
            data["rendered_teaching_pdf_sha256"]="wrong"
            args[4].write_text(json.dumps(data))
            with self.assertRaises(Exception):preflight(*args)
        with tempfile.TemporaryDirectory() as td:
            args=make_case(Path(td))
            model=args[6]/"en_US-ljspeech-medium.onnx"
            model.write_bytes(b"TAMPER"*4500)
            with self.assertRaises(ExpandedLectureError):preflight(*args)

if __name__=="__main__":unittest.main()
