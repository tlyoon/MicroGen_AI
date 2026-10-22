import unittest
from microgen_tts_grouped_holdout import partition_corpus

def sample(group,item,label):
 return {"source_wav_sha256":f"{group:064x}",
  "source_pcm_sha256":f"{group+100:064x}",
  "clip_sha256":f"{group*1000+item:064x}",
  "clip_pcm_sha256":f"{group*1000+item+100:064x}",
  "source_group_id":f"session-{group}","phoneme_label":label}

class ClassBalanceTests(unittest.TestCase):
 def test_both_classes_reported_but_not_ground_truth(self):
  records=[sample(i,j,l) for i in range(1,7) for j,l in ((1,"WHY"),(2,"YAY"))]
  r=partition_corpus(records)
  self.assertTrue(r["claimed_class_balance_present"])
  self.assertFalse(r["claimed_labels_independently_validated"])
  self.assertFalse(r["scoring_allowed"])
 def test_only_why_in_holdout_flags_class_gap(self):
  records=[sample(i,1,"WHY") for i in range(1,7)]
  r=partition_corpus(records)
  self.assertFalse(r["claimed_class_balance_present"])
  self.assertIn("MISSING_BOTH_PHONEME_CLASSES_IN_TRAIN_OR_HOLDOUT",r["scoring_blockers"])
 def test_unlabelled_record_does_not_satisfy_balance(self):
  records=[sample(i,1,None) for i in range(1,7)]
  r=partition_corpus(records)
  self.assertFalse(r["claimed_class_balance_present"])
  self.assertIn("UNLABELLED_CLIPS_PRESENT",r["scoring_blockers"])
