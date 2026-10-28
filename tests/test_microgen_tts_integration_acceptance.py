import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_microgen_tts_stack_audit import make
from microgen_tts_integration_acceptance import audit_integration

class IntegrationAcceptanceTests(unittest.TestCase):
 def test_good_commit_chain_and_mp4_duration_still_no_publication(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);base,head=make(p)
   vid=p/"slide.mp4";vid.write_bytes(b"test")
   # Temporary repo must be clean even in mocked video audit.
   from subprocess import run
   run(["git","-C",str(p),"add","slide.mp4"],check=True,capture_output=True)
   run(["git","-C",str(p),"commit","-qm","video"],check=True,capture_output=True)
   from microgen_tts_stack_audit import _git
   head=_git(p,"rev-parse","HEAD")
   with patch("microgen_tts_integration_acceptance.audit_videos",
              return_value={"all_videos_under_600_seconds":True,
                            "video_count":1,"videos":[]}):
    report=audit_integration(p,base,head,[vid])
   self.assertTrue(report["integration_subset_verified"])
   self.assertFalse(report["ready_for_publication"])
   self.assertFalse(report["phonetic_correctness_certified"])
   self.assertFalse(report["ci_result_for_head_commit_verified_by_this_tool"])
 def test_bad_video_duration_fails_technical_subset(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);base,head=make(p)
   with patch("microgen_tts_integration_acceptance.audit_videos",
              return_value={"all_videos_under_600_seconds":False,
                            "videos":[]}):
    r=audit_integration(p,base,head,[p/"fake.mp4"])
   self.assertFalse(r["integration_subset_verified"])
   self.assertFalse(r["publication_performed"])
 def test_dirty_git_checkout_cannot_fake_integrated_status(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);base,head=make(p)
   (p/"dirty").write_text("not committed")
   with self.assertRaises(Exception):audit_integration(p,base,head,[p/"fake.mp4"])
