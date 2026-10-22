import unittest
from unittest.mock import patch
from microgen_tts_release_matrix import verify_release_matrix,ReleaseMatrixFailure
from microgen_tts_release_policy import decide_release

class ExhaustiveReleasePolicyTests(unittest.TestCase):
 def test_all_2048_contract_scenarios(self):
  result=verify_release_matrix()
  self.assertEqual(result["truth_table_scenarios"],2048)
  self.assertEqual(result["ready_scenarios_by_policy"]["autonomous"],16)
  self.assertEqual(result["ready_scenarios_by_policy"]["human-certified"],1)
  self.assertFalse(result["phonetic_correctness_proven"])
 def test_detects_illegal_bypass_of_machine_blocker(self):
  def corrupted(checks,policy):
   result=decide_release(checks,policy)
   result["ready_for_separate_promotion"]=True
   return result
  with patch("microgen_tts_release_matrix.decide_release",side_effect=corrupted):
   with self.assertRaises(ReleaseMatrixFailure):verify_release_matrix()
