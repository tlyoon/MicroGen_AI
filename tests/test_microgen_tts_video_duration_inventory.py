import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from microgen_tts_video_duration_inventory import audit_videos,DurationInventoryError

class DurationTests(unittest.TestCase):
 def fixture(self,root):
  a=root/"test.mp4";a.write_bytes(b"not actual video")
  return a
 def test_video_at_599_point_99_is_technically_within_limit(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.fixture(Path(td))
   with patch("microgen_tts_video_duration_inventory.check_video",
              return_value={"seconds":599.99}):
    result=audit_videos([p])
   self.assertTrue(result["all_videos_under_600_seconds"])
   self.assertFalse(result["highlight_sync_verified"])
   self.assertFalse(result["publication_performed"])
 def test_exactly_600_or_older_623_seconds_fail(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.fixture(Path(td))
   for sec in (600.,623.):
    with patch("microgen_tts_video_duration_inventory.check_video",
               return_value={"seconds":sec}):
     result=audit_videos([p])
    self.assertFalse(result["all_videos_under_600_seconds"])
    self.assertEqual(result["videos"][0]["blocking_defect"],"NOT_STRICTLY_UNDER_600_SECONDS")
 def test_no_fake_green_on_invalid_streams(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.fixture(Path(td))
   result=audit_videos([p])
   self.assertFalse(result["all_videos_under_600_seconds"])
 def test_reject_duplicate_video(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.fixture(Path(td))
   with self.assertRaises(DurationInventoryError):audit_videos([p,p])
