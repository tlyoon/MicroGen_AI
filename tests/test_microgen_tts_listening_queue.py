import json
import hashlib
import tempfile
import unittest
import wave
from pathlib import Path
from microgen_tts_listening_queue import prepare_listening_queue,ListeningQueueError
from microgen_tts_provenance import digest_file

def wav(path,sample=500):
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
        f.writeframes(int(sample).to_bytes(2,"little",signed=True)*24000)

def stage(root):
    root.mkdir()
    (root/"script_tts.json").write_text(json.dumps({"slides":[
      {"slide":1,"tts_text":"The y-value is continuous."},
      {"slide":2,"tts_text":"Welcome to the lesson."},
    ]}),encoding="utf8")
    wav(root/"slide1.wav");wav(root/"slide2.wav")
    return root

class ListeningQueueTests(unittest.TestCase):
    def test_every_slide_including_no_risk_must_be_reviewed(self):
        with tempfile.TemporaryDirectory() as td:
            p=stage(Path(td)/"stage")
            queue=prepare_listening_queue(p)
            self.assertEqual(queue["slide_count"],2)
            self.assertEqual(queue["slides_requiring_listening"],[1,2])
            self.assertEqual(queue["rows"][1]["priority"],"WHOLE_SLIDE_SPOT_CHECK")
            self.assertFalse(queue["listening_approved"])
            self.assertFalse(queue["publishable"])
    def test_y_letter_risk_receives_high_priority(self):
        with tempfile.TemporaryDirectory() as td:
            p=stage(Path(td)/"stage")
            queue=prepare_listening_queue(p)
            self.assertEqual(queue["rows"][0]["priority"],"HIGH_CONFIRMED_RISK_CLASS")
            self.assertIn("why value",[x["expected_spoken"] for x in queue["rows"][0]["risk_expressions"]])
    def test_all_source_audio_sha_bound(self):
        with tempfile.TemporaryDirectory() as td:
            p=stage(Path(td)/"stage")
            q=prepare_listening_queue(p)
            self.assertEqual(q["rows"][0]["wav_sha256"],digest_file(p/"slide1.wav"))
            self.assertEqual(q["source_script_sha256"],digest_file(p/"script_tts.json"))
    def test_linked_review_clip_requires_same_source_audio(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=stage(root/"stage");clips=root/"clips";clips.mkdir()
            wav(clips/"cue.wav")
            manifest={"excerpts":[{"slide":1,"clip_name":"cue.wav","clip_sha256":digest_file(clips/"cue.wav"),
                       "input_sha256":digest_file(p/"slide1.wav"),
                       "source_excerpt":"y-value"}]}
            q=prepare_listening_queue(p,clip_manifest=manifest,clip_folder=clips)
            self.assertEqual(q["rows"][0]["suggested_review_clips"][0]["filename"],"cue.wav")
            manifest["excerpts"][0]["input_sha256"]="0"*64
            with self.assertRaisesRegex(ListeningQueueError,"source audio hash drift"):
                prepare_listening_queue(p,clip_manifest=manifest,clip_folder=clips)
    def test_tampered_clip_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=stage(root/"stage");clips=root/"clips";clips.mkdir()
            (clips/"cue.wav").write_bytes(b"not the expected WAV")
            manifest={"excerpts":[{"slide":1,"clip_name":"cue.wav","clip_sha256":"1"*64,
                       "input_sha256":digest_file(p/"slide1.wav")}]}
            with self.assertRaisesRegex(ListeningQueueError,"Clip hash mismatch"):
                prepare_listening_queue(p,clip_manifest=manifest,clip_folder=clips)
    def test_refuses_bad_slide_order(self):
        with tempfile.TemporaryDirectory() as td:
            p=stage(Path(td)/"stage")
            (p/"script_tts.json").write_text(json.dumps({"slides":[{"slide":4,"tts_text":"x"}]}))
            with self.assertRaisesRegex(ListeningQueueError,"slide order"):
                prepare_listening_queue(p)
    def test_no_auto_approval_even_with_clean_wording(self):
        with tempfile.TemporaryDirectory() as td:
            p=stage(Path(td)/"stage")
            report=prepare_listening_queue(p)
            self.assertTrue(all(x["review_status"]=="NOT_REVIEWED" for x in report["rows"]))
            self.assertFalse(report["signed_review_receipt_created"])
