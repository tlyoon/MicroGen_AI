"""Offline diagnostic mux inputs cannot count as a formal lecture."""
import json
import tempfile
import unittest
import wave
from pathlib import Path

from test_microgen_source_teaching_slide_render import prepare
from microgen_source_teaching_slide_render import render_teaching_candidate
from microgen_offline_diagnostic_av import inspect_inputs, OfflineDemoError


def fixture(root):
    stage,narration,plan=prepare(root)
    qa=json.loads(narration.read_text())
    qa["formal_voice_authorized"]=False
    narration.write_text(json.dumps(qa))
    render_teaching_candidate(stage,narration,plan,root/"slides")
    audio=root/"audio";audio.mkdir()
    for n in range(1,9):
        with wave.open(str(audio/f"slide{n:02d}.wav"),"wb") as item:
            item.setnchannels(1);item.setsampwidth(2);item.setframerate(16000)
            item.writeframes(b"\x01\x00"*16000)
    return root/"slides",narration,audio


class DiagnosticMuxTests(unittest.TestCase):
    def test_valid_source_bound_audio_is_not_formal_voice_or_publishable(self):
        with tempfile.TemporaryDirectory() as td:
            slides,narration,audio=fixture(Path(td))
            report=inspect_inputs(slides,narration,audio,declared_diagnostic_voice="Local voice")
            self.assertEqual(report["slide_count"],8)
            self.assertAlmostEqual(report["total_input_audio_seconds"],8.0)
            self.assertFalse(report["voice_is_formal"])
            self.assertFalse(report["technical_word_pronunciation_verified"])
            self.assertFalse(report["publication_allowed"])
            self.assertEqual(report["provider_calls"],0)

    def test_missing_audio_or_forged_formal_acceptance_refused(self):
        with tempfile.TemporaryDirectory() as td:
            slides,narration,audio=fixture(Path(td))
            (audio/"slide08.wav").unlink()
            with self.assertRaises(OfflineDemoError):
                inspect_inputs(slides,narration,audio,declared_diagnostic_voice="Local")
            with wave.open(str(audio/"slide08.wav"),"wb") as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
                f.writeframes(b"\x01\x00"*16000)
            manifest=slides/"teaching_slide_receipt.json"
            record=json.loads(manifest.read_text());record["formal_voice_authorized"]=True
            manifest.write_text(json.dumps(record))
            with self.assertRaises(OfflineDemoError):
                inspect_inputs(slides,narration,audio,declared_diagnostic_voice="Local")

    def test_source_pdf_hash_and_slide_mapping_required(self):
        with tempfile.TemporaryDirectory() as td:
            slides,narration,audio=fixture(Path(td))
            manifest=slides/"teaching_slide_receipt.json"
            record=json.loads(manifest.read_text())
            record["slides"][2]["narration_sha256"]="0"*64
            manifest.write_text(json.dumps(record))
            with self.assertRaises(OfflineDemoError):
                inspect_inputs(slides,narration,audio,declared_diagnostic_voice="Local")

    def test_empty_diagnostic_voice_declaration_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            slides,narration,audio=fixture(Path(td))
            with self.assertRaises(OfflineDemoError):
                inspect_inputs(slides,narration,audio,declared_diagnostic_voice="")

if __name__=="__main__":
    unittest.main()
