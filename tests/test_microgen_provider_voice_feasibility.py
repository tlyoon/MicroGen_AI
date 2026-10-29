"""No-cloud voice feasibility tests; synthetic tone != evidence of speech."""
from __future__ import annotations

import json
import math
import struct
import tempfile
import wave
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf as fitz

from microgen_provider_voice_feasibility import (
    SOURCE_EXCERPT, ORIGINAL_VOICE, DIAGNOSTIC_VOICE,
    VoiceFeasibilityError, check_diagnostic, digest, main,
)
from microgen_tts_provenance import (
    TTSProvenanceError, make_record, verify_record,
)


def fixtures(root: Path, *, text: str = SOURCE_EXCERPT,
             audible: bool = True):
    source = root / "source.pdf"
    with fitz.open() as doc:
        page=doc.new_page()
        page.insert_textbox(fitz.Rect(30,30,560,380),text,fontsize=11)
        doc.save(source)
    file = root / "sapi_diagnostic.wav"
    rate = 16000
    frames = [
        int(2000 * math.sin(2 * math.pi * 220 * n / rate)) if audible else 0
        for n in range(rate)
    ]
    with wave.open(str(file),"wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(struct.pack("<"+"h"*len(frames),*frames))
    return source, file


class OfflineVoiceFeasibilityTests(unittest.TestCase):
    def test_diagnostic_never_authenticates_production_narrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,wav=fixtures(Path(tmp))
            receipt=check_diagnostic(src,wav)
            self.assertEqual(receipt["source_page"],1)
            self.assertEqual(receipt["source_pdf_sha256"],digest(src))
            self.assertEqual(receipt["diagnostic_wav_sha256"],digest(wav))
            self.assertGreater(receipt["diagnostic_pcm_rms"],3)
            self.assertEqual(receipt["diagnostic_duration_seconds"],1)
            self.assertEqual(receipt["production_voice_name"],ORIGINAL_VOICE)
            self.assertEqual(receipt["diagnostic_voice_name"],DIAGNOSTIC_VOICE)
            self.assertTrue(receipt["voice_name_mismatch"])
            for field in ("cloud_tts_invoked","gemini_invoked","billed_provider_invoked",
                          "production_voice_identity_verified","publication_allowed",
                          "complete_serway_lecture_generated",
                          "speech_content_phonetically_verified"):
                with self.subTest(field=field):
                    self.assertIs(receipt[field],False)

    def test_matching_strings_alone_still_do_not_certify_acoustic_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,wav=fixtures(Path(tmp))
            receipt=check_diagnostic(src,wav,diagnostic_voice=ORIGINAL_VOICE)
            self.assertFalse(receipt["voice_name_mismatch"])
            self.assertFalse(receipt["production_voice_identity_verified"])
            self.assertFalse(receipt["publication_allowed"])

    def test_nonmatching_source_sentence_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,wav=fixtures(Path(tmp),text="A different book and lesson.")
            with self.assertRaises(VoiceFeasibilityError):
                check_diagnostic(src,wav)

    def test_silent_wav_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,wav=fixtures(Path(tmp),audible=False)
            with self.assertRaises(VoiceFeasibilityError):
                check_diagnostic(src,wav)

    def test_unreadable_wave_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            src,wav=fixtures(Path(tmp))
            wav.write_bytes(b"not audio")
            with self.assertRaises(VoiceFeasibilityError):
                check_diagnostic(src,wav)

    def test_no_overwrite_of_existing_feasibility_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src,wav=fixtures(root)
            existing=root/"report.json"
            existing.write_text("preserve old data")
            with patch("sys.argv",["probe","--source-pdf",str(src),
                    "--existing-diagnostic-wav",str(wav),
                    "--new-report",str(existing)]):
                with self.assertRaises(VoiceFeasibilityError):
                    main()
            self.assertEqual(existing.read_text(),"preserve old data")

    def test_existing_sapi_voice_is_rejected_by_real_production_provenance_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            _,wav=fixtures(root)
            record=make_record(
                slide=1,path=wav,text=SOURCE_EXCERPT,provider="sapi",
                key="diagnostic",voice_name=ORIGINAL_VOICE,
                language_code="en-US",speaking_rate=.8,location="global")
            self.assertFalse(record["voice_identity_verified"])
            self.assertIsNone(record["voice_name"])
            with self.assertRaises(TTSProvenanceError):
                verify_record(record,wav,slide=1,text=SOURCE_EXCERPT,
                    key="diagnostic",voice_name=ORIGINAL_VOICE,
                    language_code="en-US",speaking_rate=.8,location="global")


if __name__=="__main__":
    unittest.main()
