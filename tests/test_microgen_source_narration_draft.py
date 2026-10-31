import json
import tempfile
import unittest
from pathlib import Path
from microgen_source_narration_draft import assess_narration_draft, NarrationDraftError

def fixture(root, *, slides=2):
    h={"status":"HANDOFF_CREATED_MEDIA_NOT_READY","publication_allowed":False,
       "formal_voice_authorized":False,"generated_wavs":False,"generated_mp4s":False,
       "slide_count":slides,"source_pdf_sha256":"f"*64,"draft_pdf_sha256":"d"*64,
       "narration_work_order":[{"slide":i,"title":"Concept", "source_page":1,
       "source_pdf_sha256":"f"*64,"draft_pdf_sha256":"d"*64,"publication_allowed":False}
       for i in range(1,slides+1)]}
    n={"schema_version":1,"narrations":[{"slide":i,"text":" ".join(
       ["Scientific measurement uses consistent units for interpreting nature."]*18),
       "academic_review_status":"AUTOMATED_SOURCE_CHECK_PENDING"}
       for i in range(1,slides+1)]}
    a=root/"handoff.json";b=root/"narration.json"
    a.write_text(json.dumps(h));b.write_text(json.dumps(n))
    return a,b

class DraftTests(unittest.TestCase):
    def test_full_draft_is_not_voice_or_academic_approval(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=fixture(Path(td))
            outcome=assess_narration_draft(a,b)
            self.assertEqual(outcome["slide_count"],2)
            self.assertTrue(outcome["all_slide_texts_present"])
            self.assertFalse(outcome["academic_accuracy_independently_verified"])
            self.assertFalse(outcome["formal_voice_authorized"])
            self.assertFalse(outcome["publication_allowed"])

    def test_short_or_missing_slide_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=fixture(Path(td))
            n=json.loads(b.read_text());n["narrations"][0]["text"]="too short"
            b.write_text(json.dumps(n))
            with self.assertRaises(NarrationDraftError):
                assess_narration_draft(a,b)
            n["narrations"].pop()
            b.write_text(json.dumps(n))
            with self.assertRaises(NarrationDraftError):
                assess_narration_draft(a,b)

    def test_wrong_slide_identity_and_forged_voice_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=fixture(Path(td))
            h=json.loads(a.read_text());h["formal_voice_authorized"]=True
            a.write_text(json.dumps(h))
            with self.assertRaises(NarrationDraftError):
                assess_narration_draft(a,b)
            h["formal_voice_authorized"]=False;a.write_text(json.dumps(h))
            n=json.loads(b.read_text());n["narrations"][1]["slide"]=1
            b.write_text(json.dumps(n))
            with self.assertRaises(NarrationDraftError):
                assess_narration_draft(a,b)

    def test_rejects_unsafe_tts_markups(self):
        with tempfile.TemporaryDirectory() as td:
            a,b=fixture(Path(td))
            n=json.loads(b.read_text());n["narrations"][0]["text"] += " <script>oops</script>"
            b.write_text(json.dumps(n))
            with self.assertRaises(NarrationDraftError):
                assess_narration_draft(a,b)

if __name__=="__main__":
    unittest.main()
