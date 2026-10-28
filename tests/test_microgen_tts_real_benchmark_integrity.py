import hashlib
import tempfile
import unittest
import wave
from pathlib import Path
from microgen_tts_acoustic_benchmark import (
    run_dual_model_benchmark,preflight_benchmark,main,
)
from microgen_tts_benchmark import BenchmarkError

def cases(folder):
    results=[]
    for filename,label in (("before.wav","defect"),("after.wav","correct")):
        file=folder/filename
        with wave.open(str(file),"wb") as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
            w.writeframes(b"\x08\x00"*24000)
        results.append({"id":filename,"label":label,"filename":filename,
                        "sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
                        "expected_occurrences":2})
    return {"schema_version":1,"samples":results}

class RealBenchmarkSafetyTests(unittest.TestCase):
    def test_input_duration_and_call_budget(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);source=cases(folder)
            result=preflight_benchmark(source,folder)
            self.assertEqual(result["planned_requests"],4)
            self.assertEqual(result["planned_input_audio_seconds"],4.)
            self.assertIsNone(result["monetary_cost_estimate"])
            with self.assertRaisesRegex(BenchmarkError,"duration"):
                preflight_benchmark(source,folder,max_audio_seconds=3.99)
            with self.assertRaisesRegex(BenchmarkError,"request"):
                preflight_benchmark(source,folder,max_calls=3)
    def test_wav_mutated_during_model_inference_cannot_be_scored(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);source=cases(folder)
            def recognize(path):
                with path.open("ab") as stream:stream.write(b"tampered")
                return "yay value why value"
            with self.assertRaisesRegex(BenchmarkError,"changed during recognition"):
                run_dual_model_benchmark(source,folder,recognize,
                    lambda _:"yay value why value",model_names=("one","two"))
    def test_cli_requires_external_unused_output_even_offline(self):
        with tempfile.TemporaryDirectory() as td:
            import json
            root=Path(td);wavdir=root/"wavs";wavdir.mkdir()
            source=cases(wavdir);manifest=root/"manifest.json"
            manifest.write_text(json.dumps(source))
            with self.assertRaisesRegex(Exception,"outside the source"):
                main([str(manifest),str(wavdir),str(wavdir/"report.json")])
            self.assertFalse((wavdir/"report.json").exists())
            out=root/"report.json"
            self.assertEqual(main([str(manifest),str(wavdir),str(out)]),2)
            self.assertTrue(out.exists())
            old=out.read_bytes()
            with self.assertRaises(Exception):
                main([str(manifest),str(wavdir),str(out)])
            self.assertEqual(out.read_bytes(),old)
