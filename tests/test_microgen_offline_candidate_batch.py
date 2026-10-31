import hashlib
import json
import math
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from microgen_offline_neural_voice import digest
from microgen_offline_candidate_batch import verify_candidate_audio,CandidateBatchError
from test_microgen_offline_neural_voice import fixture

def wav_file(path,seconds=22,rate=22050):
    pattern=array('h',[int(1000*math.sin(2*math.pi*i/100)) for i in range(100)])
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes(pattern.tobytes()*(int(rate*seconds)//100))

def setup(root):
    model,formal=fixture(root)
    j=json.loads(formal.read_text())
    for row in j["requests"]:
        row["source_pdf_sha256"]="f"*64
        row["teaching_pdf_sha256"]="d"*64
    formal.write_text(json.dumps(j))
    probe_dir=root/"probe";probe_dir.mkdir()
    probe_wav=probe_dir/"probe_local_neural_candidate.wav"
    wav_file(probe_wav,seconds=4)
    probe=probe_dir/"voice_probe_receipt.json"
    probe.write_text(json.dumps({
       "status":"OFFLINE_NEURAL_VOICE_PROBE_PASSED_NOT_FORMAL",
       "model_sha256":digest(model/"en_US-ljspeech-medium.onnx"),
       "formal_handoff_sha256":digest(formal),
       "probe_wav_sha256":digest(probe_wav),
       "formal_voice_authorized":False,
       "production_wavs_generated":False,"publication_allowed":False}))
    output=root/"audio";output.mkdir()
    for i in range(1,9):
        wav_file(output/f"slide{i:02d}.wav")
    return model,formal,probe,output

class BatchTests(unittest.TestCase):
    def test_eight_pcm_candidates_do_not_claim_production(self):
        with tempfile.TemporaryDirectory() as td:
            model,formal,probe,audio=setup(Path(td))
            out=verify_candidate_audio(audio,formal,probe,model)
            self.assertEqual(out["slide_count"],8)
            self.assertEqual(len(out["slides"]),8)
            self.assertTrue(all(s["rms_pcm"]>200 for s in out["slides"]))
            self.assertFalse(out["formal_voice_authorized"])
            self.assertFalse(out["acoustic_phoneme_accuracy_proven"])
            self.assertFalse(out["publication_allowed"])

    def test_mutated_probe_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            model,formal,probe,audio=setup(Path(td))
            with (probe.parent/"probe_local_neural_candidate.wav").open("ab") as f:
                f.write(b"tamper")
            with self.assertRaises(CandidateBatchError):
                verify_candidate_audio(audio,formal,probe,model)

    def test_missing_slide_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            model,formal,probe,audio=setup(Path(td))
            (audio/"slide03.wav").unlink()
            with self.assertRaises(CandidateBatchError):
                verify_candidate_audio(audio,formal,probe,model)

    def test_clipped_or_short_audio_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            model,formal,probe,audio=setup(Path(td))
            path=audio/"slide02.wav"
            with wave.open(str(path),"wb") as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050)
                w.writeframes((32767).to_bytes(2,'little',signed=True)*22050)
            with self.assertRaises(Exception):
                verify_candidate_audio(audio,formal,probe,model)

if __name__=="__main__":unittest.main()
