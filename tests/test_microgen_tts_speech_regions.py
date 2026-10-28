import unittest
from microgen_tts_speech_regions import candidate_regions, RegionError

def datum(values):
    return {"wav_sha256":"a"*64,"frame_ms":20,
            "duration_seconds":len(values)*.02,"frame_rms":values}

class SegmentTests(unittest.TestCase):
    def test_spans_bridge_small_gaps_but_no_word_claim(self):
        values=[0.0]*10+[.1]*10+[0]*3+[.1]*10+[0]*10
        result=candidate_regions(datum(values),min_ms=100,bridge_ms=80)
        self.assertEqual(result["region_count"],1)
        self.assertAlmostEqual(result["candidate_regions"][0]["start_seconds"],.2)
        self.assertFalse(result["speech_or_phoneme_labels_verified"])
    def test_silence_not_reported_as_clean_audio(self):
        result=candidate_regions(datum([0]*100))
        self.assertEqual(result["candidate_regions"],[])
        self.assertFalse(result["no_regions_is_clean_audio"])
    def test_short_click_is_not_speech_region(self):
        result=candidate_regions(datum([0]*40+[.6]*2+[0]*20),min_ms=100)
        self.assertEqual(result["region_count"],0)
    def test_reject_nonfinite_or_unbounded_input(self):
        with self.assertRaises(RegionError):
            candidate_regions(datum([float("nan")]))
        with self.assertRaises(RegionError):
            candidate_regions(datum([0.2]*50),bridge_ms=900)
