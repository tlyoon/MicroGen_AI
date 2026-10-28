import hashlib,unittest
from microgen_tts_grouped_holdout import partition_corpus

def row(group,item,label):
 return {"source_wav_sha256":f"{group:064x}",
         "source_pcm_sha256":f"{100+group:064x}",
         "clip_sha256":f"{group*1000+item:064x}",
         "clip_pcm_sha256":f"{group*1000+item+100:064x}",
         "source_group_id":f"lecture-{group}","phoneme_label":label}
class PhonemeGroupCoverageTests(unittest.TestCase):
 def test_two_classes_each_represented_in_two_groups_per_split(self):
  records=[row(i,j,label) for i in range(1,7)
            for j,label in ((1,"WHY"),(2,"YAY"))]
  result=partition_corpus(records)
  self.assertTrue(result["claimed_per_class_two_group_coverage"])
  self.assertFalse(result["scoring_allowed"])
 def test_both_classes_exist_but_single_group_per_class_is_not_enough(self):
  # Six source groups with YAY in just one train and one holdout group.
  records=[row(i,1,"WHY") for i in range(1,7)]
  ordered=sorted(range(1,7),key=lambda i:hashlib.sha256(f"lecture-{i}".encode()).hexdigest())
  yay_groups={ordered[0],ordered[1]}
  for i in range(1,7):
   records.append(row(i,2,"YAY") if i in yay_groups else row(i,2,"WHY"))
  result=partition_corpus(records)
  self.assertFalse(result["claimed_per_class_two_group_coverage"])
  self.assertIn("TOO_FEW_GROUPS_PER_PHONEME_CLASS",result["scoring_blockers"])
 def test_unlabelled_data_never_qualifies(self):
  r=partition_corpus([row(i,1,None) for i in range(1,7)])
  self.assertFalse(r["claimed_per_class_two_group_coverage"])
  self.assertFalse(r["scoring_allowed"])
