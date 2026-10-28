import json
import tempfile
import unittest
import wave
from pathlib import Path
from microgen_tts_quality_campaign import run_qa_campaign,QACampaignError
from microgen_tts_provenance import digest_file

def wav(p):
    with wave.open(str(p),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
        w.writeframes(b"\xe8\x03"*24000)

def stage(dir):
    dir.mkdir()
    (dir/"script_tts.json").write_text(json.dumps({"slides":[
       {"slide":1,"tts_text":"The y-value is continuous."},
       {"slide":2,"tts_text":"The theorem follows."}
    ]}),encoding="utf8")
    wav(dir/"slide1.wav");wav(dir/"slide2.wav")
    return dir

class QualityCampaignTests(unittest.TestCase):
    def test_complete_audit_packet_is_nonpublishing(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);lesson=stage(p/"lesson");out=p/"audit"
            old=digest_file(lesson/"slide1.wav")
            result=run_qa_campaign(lesson,out)
            self.assertEqual(result["slide_count"],2)
            self.assertEqual(result["all_slide_review_count"],2)
            self.assertEqual(result["review_clips"],1)
            self.assertFalse(result["release_ready"])
            self.assertFalse(result["published"])
            self.assertIn("independent_acoustic_screen",result["release_blockers"])
            self.assertTrue((out/"QA_CAMPAIGN_COMPLETE_NOT_PUBLISHED.json").is_file())
            self.assertEqual(digest_file(lesson/"slide1.wav"),old)
    def test_packet_source_audio_hashes_are_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);lesson=stage(p/"lesson");out=p/"audit"
            result=run_qa_campaign(lesson,out)
            self.assertEqual(result["source_file_sha256"]["slide1.wav"],
                             digest_file(lesson/"slide1.wav"))
            q=json.loads((out/"all_slide_listening_queue.json").read_text())
            self.assertEqual(q["rows"][0]["wav_sha256"],digest_file(lesson/"slide1.wav"))
    def test_reuse_and_nested_output_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);lesson=stage(p/"lesson");out=p/"audit"
            out.mkdir()
            with self.assertRaises(QACampaignError):
                run_qa_campaign(lesson,out)
            with self.assertRaises(QACampaignError):
                run_qa_campaign(lesson,lesson/"new")
    def test_untrusted_source_order_is_blocked_before_output(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);lesson=stage(p/"lesson");out=p/"audit"
            (lesson/"script_tts.json").write_text(json.dumps(
                {"slides":[{"slide":30,"tts_text":"y-value"}]}))
            with self.assertRaises(QACampaignError):
                run_qa_campaign(lesson,out)
            self.assertFalse(out.exists())
    def test_clip_cap_fails_closed_no_complete_marker(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);lesson=stage(p/"lesson");out=p/"audit"
            with self.assertRaises(QACampaignError):
                run_qa_campaign(lesson,out,max_review_clips=0)
            self.assertFalse(out.exists())
    def test_structural_silence_report_not_dubbed_pronunciation_pass(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);lesson=stage(p/"lesson");out=p/"audit"
            with wave.open(str(lesson/"slide1.wav"),"wb") as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
                w.writeframes(b"\0\0"*24000)
            result=run_qa_campaign(lesson,out)
            self.assertEqual(result["structurally_bad_slides"],[1])
            self.assertFalse(result["human_listening_signed"])
            self.assertFalse(result["release_ready"])
