import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path
from microgen_offline_neural_voice import inspect_local_voice, inspect_voice_probe, OfflineVoiceError, MODEL_BASENAME

def fixture(root):
    model=root/"model";model.mkdir()
    (model/MODEL_BASENAME).write_bytes(b"n"*12000)
    (model/(MODEL_BASENAME+".json")).write_text(json.dumps({
      "audio":{"sample_rate":22050},"num_speakers":1,
      "language":{"code":"en_US"}}))
    (model/"MODEL_CARD").write_text(
        "Model card for ljspeech. US English female voice. "
        "License: public domain. Trained from scratch.")
    t=root/"handoff.json"
    requests=[]
    for i in range(1,9):
        s="This is a reliable physics passage about mass "+str(i)
        requests.append({"slide":i,"input_text":s,"text_sha256":hashlib.sha256(s.encode()).hexdigest(),
                         "production_tts_authorized":False})
    t.write_text(json.dumps({"status":"FORMAL_TTS_INPUT_BUNDLE_READY_PRODUCTION_BLOCKED",
       "formal_voice_provider":None,"formal_voice_name":None,"publication_allowed":False,
       "formal_production_ready":False,"slide_count":8,"requests":requests}))
    return model,t

class OfflinePiperTests(unittest.TestCase):
    def test_eligible_voice_is_still_not_approved_formal(self):
        with tempfile.TemporaryDirectory() as d:
            model,hand=fixture(Path(d))
            report=inspect_local_voice(model,hand)
            self.assertEqual(report["spoken_slide_count"],8)
            self.assertEqual(report["sample_rate_hz"],22050)
            self.assertFalse(report["formal_voice_selected"])
            self.assertFalse(report["publication_allowed"])
            self.assertEqual(report["provider_calls"],0)

    def test_license_restriction_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            model,hand=fixture(Path(d))
            (model/"MODEL_CARD").write_text("License: CC BY-NC-SA 4.0; trained from scratch")
            with self.assertRaises(OfflineVoiceError):inspect_local_voice(model,hand)

    def test_forged_formal_narrator_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            model,hand=fixture(Path(d))
            j=json.loads(hand.read_text());j["formal_voice_name"]="Microsoft Zira Desktop"
            hand.write_text(json.dumps(j))
            with self.assertRaises(OfflineVoiceError):inspect_local_voice(model,hand)

    def test_spoken_text_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            model,hand=fixture(Path(d))
            j=json.loads(hand.read_text());j["requests"][3]["input_text"]="change without hash"
            hand.write_text(json.dumps(j))
            with self.assertRaises(OfflineVoiceError):inspect_local_voice(model,hand)

    def test_pcm_probe_rejects_digital_silence(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"silent.wav"
            with wave.open(str(f),"wb") as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050)
                w.writeframes(bytes(22050*2*3))
            with self.assertRaises(OfflineVoiceError):inspect_voice_probe(f)

if __name__=="__main__":unittest.main()
