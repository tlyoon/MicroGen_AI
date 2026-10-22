import unittest
from microgen_tts_grouped_holdout import partition_corpus,HoldoutError

def rows(n):
 return [{"source_wav_sha256":f"{i:064x}",
  "clip_sha256":f"{i+100:064x}",
  "source_pcm_sha256":f"{i+200:064x}",
  "clip_pcm_sha256":f"{i+300:064x}",
  "source_group_id":f"lecturer-session-{i}","phoneme_label":None} for i in range(1,n+1)]

class GroupCountTests(unittest.TestCase):
 def test_two_source_groups_not_credible_evaluation_sample(self):
  verdict=partition_corpus(rows(2))
  self.assertTrue(verdict["grouped_holdout_available"])
  self.assertFalse(verdict["minimum_group_count_met"])
  self.assertIn("TOO_FEW_GROUPS_FOR_ROBUST_EVALUATION",verdict["scoring_blockers"])
  self.assertFalse(verdict["scoring_allowed"])
 def test_six_claimed_groups_only_meet_count_not_ground_truth(self):
  verdict=partition_corpus(rows(6))
  self.assertTrue(verdict["minimum_group_count_met"])
  self.assertFalse(verdict["source_group_independence_independently_verified"])
  self.assertFalse(verdict["scoring_allowed"])
 def test_stricter_custom_requirement(self):
  verdict=partition_corpus(rows(6),min_source_groups=8)
  self.assertFalse(verdict["minimum_group_count_met"])
 def test_invalid_group_count_limits(self):
  with self.assertRaises(HoldoutError):
   partition_corpus(rows(6),min_source_groups=2)
