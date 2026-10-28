import unittest
from microgen_tts_grouped_holdout import partition_corpus,HoldoutError

def row(i,group="lesson-A",clip_pcm="a"):
 return {"source_wav_sha256":f"{1:064x}",
         "source_pcm_sha256":f"{2:064x}",
         "clip_sha256":f"{i+100:064x}",
         "clip_pcm_sha256":clip_pcm*64,
         "source_group_id":group,"phoneme_label":None}

class SameGroupDuplicatePcmTests(unittest.TestCase):
 def test_same_group_copied_audio_is_not_second_sample(self):
  with self.assertRaisesRegex(HoldoutError,"reused"):
   partition_corpus([row(1),row(2)])
 def test_unique_clip_pcm_can_recur_only_if_distinct(self):
  r=partition_corpus([row(1,clip_pcm="a"),row(2,clip_pcm="b")])
  self.assertEqual(r["total_clips"],2)
  self.assertTrue(r["clip_pcm_identity_verified"])
  self.assertFalse(r["scoring_allowed"])
 def test_source_pcm_identity_still_checked(self):
  a=row(1,clip_pcm="a");b=row(2,group="lesson-B",clip_pcm="b")
  b["source_wav_sha256"]=f"{3:064x}"
  with self.assertRaises(HoldoutError):partition_corpus([a,b])
