import tempfile
import unittest
from pathlib import Path
from microgen_tts_blind_phoneme import (
  probe_wav,canonical_label,PhonemeProbeError,PROMPT,
)

class PhoneticProbeTests(unittest.TestCase):
    def test_blind_probe_never_passes_expected_script(self):
        with tempfile.TemporaryDirectory() as td:
            wav=Path(td)/"tiny.wav";wav.write_bytes(b"audio")
            prompts=[]
            result=probe_wav(wav,lambda p,s:prompts.append(s) or "YAY",
                             model_identity="audio-judge-1")
            self.assertEqual(result["label"],"YAY")
            self.assertEqual(len(prompts),1)
            self.assertNotIn("The y-value is continuous",prompts[0])
            self.assertFalse(result["used_expected_narration"])
            self.assertFalse(result["phonetic_accuracy_certified"])
    def test_closed_labels_fail_to_unknown_not_conventional_spelling(self):
        for val in ("y-value","Both might be why.","why","YAY.","",None):
            with self.subTest(val=val):
                self.assertEqual(canonical_label(val),"UNKNOWN")
        self.assertEqual(canonical_label("WHY"),"WHY")
    def test_provider_outage_yields_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"wav";f.write_bytes(b"audio")
            def unavailable(*args):raise ConnectionError("model unavailable")
            r=probe_wav(f,unavailable,model_identity="offline")
            self.assertEqual(r["label"],"UNKNOWN")
    def test_concurrent_wave_change_invalidates_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"wav";f.write_bytes(b"audio")
            def tamper(p,_):p.write_bytes(b"changed");return "WHY"
            with self.assertRaisesRegex(PhonemeProbeError,"changed"):
                probe_wav(f,tamper,model_identity="judge")
    def test_prompt_is_phonetic_not_textbook_cloze(self):
        self.assertIn("ACTUAL SOUND",PROMPT)
        self.assertIn("Do not correct pronunciation",PROMPT)
        self.assertNotIn("The y-value",PROMPT)
