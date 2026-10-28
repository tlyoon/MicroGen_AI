import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from microgen_tts_multipart_contract import audit_topic_parts,MultipartContractError
def videos(root):
 a=root/"p1.mp4";b=root/"p2.mp4";a.write_bytes(b"a");b.write_bytes(b"b")
 return [{"part_number":1,"video":str(a)},{"part_number":2,"video":str(b)}]
class TopicMultipartTests(unittest.TestCase):
 def test_two_short_parts_are_only_duration_cleared(self):
  with tempfile.TemporaryDirectory() as td:
   p=videos(Path(td))
   with patch("microgen_tts_multipart_contract.audit_videos",return_value={
        "all_videos_under_600_seconds":True,
        "videos":[{"video_sha256":"a"*64},{"video_sha256":"b"*64}]}):
    result=audit_topic_parts(p)
   self.assertTrue(result["multipart_technical_duration_pass"])
   self.assertFalse(result["narration_element_highlights_verified"])
   self.assertFalse(result["publication_performed"])
 def test_one_oversized_part_requires_split(self):
  with tempfile.TemporaryDirectory() as td:
   p=videos(Path(td))
   with patch("microgen_tts_multipart_contract.audit_videos",return_value={
        "all_videos_under_600_seconds":False,
        "videos":[{"video_sha256":"a"*64},{"video_sha256":"b"*64}]}):
    result=audit_topic_parts(p)
   self.assertFalse(result["multipart_technical_duration_pass"])
   self.assertEqual(result["further_action"],"SPLIT_LONG_PARTS")
 def test_duplicated_audio_video_content_not_distinct_parts(self):
  with tempfile.TemporaryDirectory() as td:
   p=videos(Path(td))
   with patch("microgen_tts_multipart_contract.audit_videos",return_value={
        "all_videos_under_600_seconds":True,
        "videos":[{"video_sha256":"a"*64},{"video_sha256":"a"*64}]}):
    self.assertFalse(audit_topic_parts(p)["multipart_technical_duration_pass"])
 def test_missing_or_skipped_part_refused(self):
  with tempfile.TemporaryDirectory() as td:
   p=videos(Path(td));p[1]["part_number"]=3
   with self.assertRaises(MultipartContractError):audit_topic_parts(p)
