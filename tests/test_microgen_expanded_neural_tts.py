"""Tests use only synthetic PDF, narration, model and audio; no paid calls."""
import json
import hashlib
import math
import tempfile
import unittest
import wave
from pathlib import Path
from array import array

from microgen_pronunciation_closed_loop import sha_file
from microgen_section_academic_coverage import audit_section_11
from microgen_source_teaching_slide_render import render_teaching_candidate
from microgen_expanded_neural_tts import (
    prepare_spoken_text,prepare_request,verify_audio,ExpandedTtsError)
from test_microgen_section_academic_coverage import fixture

def setup_case(root):
    stage,n,v=fixture(root)
    slides=root/"slides"
    render_teaching_candidate(stage,n,v,slides,figure_slide=7,historical_si_slide=6)
    rep=root/"report.json"
    rep.write_text(json.dumps(audit_section_11(stage,n,v,slides)))
    model=root/"model";model.mkdir()
    (model/"en_US-ljspeech-medium.onnx").write_bytes(b"M"*20000)
    (model/"en_US-ljspeech-medium.onnx.json").write_text(json.dumps({
        "audio":{"sample_rate":22050},"num_speakers":1,
        "language":{"code":"en_US"}}))
    (model/"MODEL_CARD").write_text(
        "Model card for ljspeech, US English female voice; "
        "License: public domain; trained from scratch")
    return stage,n,slides,rep,model

class ExpandedTtsTests(unittest.TestCase):
    def test_fourteen_source_bound_requests_never_formal(self):
        with tempfile.TemporaryDirectory() as td:
            stage,n,deck,report,model=setup_case(Path(td))
            before=sha_file(stage/"source.pdf")
            r=prepare_request(stage,n,deck,report,model)
            self.assertEqual(r["slide_count"],14)
            self.assertEqual(len({x["topic_id"] for x in r["requests"]}),14)
            self.assertFalse(r["qualified_voice_for_formal_production"])
            self.assertFalse(r["publication_allowed"])
            self.assertFalse(r["voice_weights_redistribution_independently_cleared"])
            self.assertEqual(sha_file(stage/"source.pdf"),before)

    def test_math_symbol_markers_are_conservative(self):
        said,changed=prepare_spoken_text(r"Velocity \\dot{C} and \\dot{y} plus C-dot and \\rho.")
        self.assertIn("C dot",said)
        self.assertIn("y dot",said)
        self.assertIn("rho",said)
        self.assertTrue(changed)
        with self.assertRaises(ExpandedTtsError):
            prepare_spoken_text("Value C. is ambiguous and requires clarification")

    def test_scientific_name_only_changed_in_spoken_context(self):
        original='Planck constant; Planck studied theoretical physics.'
        voiced,edits=prepare_spoken_text(original)
        self.assertEqual(voiced,'Plank constant; Planck studied theoretical physics.')
        self.assertTrue(edits)

    def test_source_or_academic_report_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage,n,deck,report,model=setup_case(Path(td))
            j=json.loads(report.read_text())
            j["rendered_teaching_pdf_sha256"]="bad"
            report.write_text(json.dumps(j))
            with self.assertRaises(ExpandedTtsError):
                prepare_request(stage,n,deck,report,model)

    def test_false_formal_state_or_modified_narration_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage,n,deck,report,model=setup_case(Path(td))
            z=json.loads(n.read_text())
            z["formal_voice_authorized"]=True
            n.write_text(json.dumps(z))
            with self.assertRaises(ExpandedTtsError):
                prepare_request(stage,n,deck,report,model)
        with tempfile.TemporaryDirectory() as td:
            stage,n,deck,report,model=setup_case(Path(td))
            z=json.loads(n.read_text())
            z["slides"][2]["narration"]="another sentence"
            n.write_text(json.dumps(z))
            with self.assertRaises(ExpandedTtsError):
                prepare_request(stage,n,deck,report,model)

    def test_bogus_license_card_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage,n,deck,report,model=setup_case(Path(td))
            (model/"MODEL_CARD").write_text("License: CC BY-NC; trained from scratch")
            with self.assertRaises(ExpandedTtsError):
                prepare_request(stage,n,deck,report,model)

    def test_wave_receipt_rejects_missing_or_silent_slide(self):
        with tempfile.TemporaryDirectory() as td:
            stage,n,deck,report,model=setup_case(Path(td))
            order=prepare_request(stage,n,deck,report,model)
            out=Path(td)/"audio";out.mkdir()
            payload=array("h",[int(1250*math.sin(2*math.pi*i/80)) for i in range(80)])
            for i in range(1,15):
                p=out/f"slide{i:02d}.wav"
                with wave.open(str(p),"wb") as f:
                    f.setnchannels(1);f.setsampwidth(2);f.setframerate(22050)
                    f.writeframes(payload.tobytes()*(22050*21//80))
            result=verify_audio(out,order)
            self.assertEqual(result["slide_count"],14)
            self.assertGreater(result["total_seconds"],285)
            (out/"slide06.wav").unlink()
            with self.assertRaises(Exception):verify_audio(out,order)

if __name__=="__main__":unittest.main()
