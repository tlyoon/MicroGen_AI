import unittest
from microgen_tts_grouped_holdout import partition_corpus,HoldoutError
def row(i,group=None,source=None,label=None):
    return {"source_wav_sha256":source or f"{i:064x}",
            "clip_sha256":f"{i+100:064x}",
            "source_group_id":group or f"speaker_lecture_{i}",
            "phoneme_label":label}
class HoldoutTests(unittest.TestCase):
    def test_two_independent_source_groups_split_without_leakage(self):
        r=partition_corpus([row(1),row(2)])
        self.assertTrue(r["grouped_holdout_available"])
        self.assertEqual(len(r["train_clip_sha256"]),1)
        self.assertEqual(len(r["holdout_clip_sha256"]),1)
        self.assertFalse(r["scoring_allowed"])
    def test_all_clips_from_one_lecture_not_a_test_set(self):
        same=f"{1:064x}"
        r=partition_corpus([row(i,group="one_course",source=same) for i in range(3)])
        self.assertFalse(r["grouped_holdout_available"])
        self.assertIn("INSUFFICIENT_DISTINCT_SOURCE_GROUPS",r["scoring_blockers"])
    def test_same_source_cannot_claim_two_speakers(self):
        samples=[row(1,group="A",source=f"{5:064x}"),row(2,group="B",source=f"{5:064x}")]
        with self.assertRaisesRegex(HoldoutError,"different groups"):
            partition_corpus(samples)
    def test_duplicate_samples_not_reused(self):
        with self.assertRaises(HoldoutError):
            partition_corpus([row(1),row(1)])
    def test_unverified_labels_not_automatically_truth(self):
        result=partition_corpus([row(1,label="WHY"),row(2,label="YAY")])
        self.assertFalse(result["scoring_allowed"])
        self.assertIn("PHONEME_LABEL_EVIDENCE_NOT_INDEPENDENTLY_VERIFIED",result["scoring_blockers"])
    def test_order_independence(self):
        a=[row(1),row(2),row(3),row(4)]
        x=partition_corpus(a);y=partition_corpus(list(reversed(a)))
        self.assertEqual(set(x["train_clip_sha256"]),set(y["train_clip_sha256"]))
    def test_invalid_labels_and_budget(self):
        with self.assertRaises(HoldoutError):partition_corpus([row(1,label="CORRECT")])
        with self.assertRaises(HoldoutError):partition_corpus([row(1),row(2)],max_items=1)
