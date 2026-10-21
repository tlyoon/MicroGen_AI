import unittest
from microgen_tts_acoustic_divergence import rank_divergent_regions,DivergenceError

def feat(w,tag):
    return {"frame_rms":w,"sample_rate_hz":24000,"frame_ms":20,
        "duration_seconds":len(w)*.02,"wav_sha256":tag*64,
        "frame_zero_crossing_fraction":[.05]*len(w),
        "frame_mean_abs_step":[.01]*len(w)}
class DivergenceTests(unittest.TestCase):
    def test_low_alignment_must_abstain_not_force_hotspots(self):
        a=feat(([.2]*20+[.01]*20)*3,"a")
        b=feat(([.01]*20+[.2]*20)*3,"b")
        from unittest.mock import patch
        with patch("microgen_tts_acoustic_divergence.align_envelopes",
                   return_value={"status":"LOW_SIMILARITY_UNALIGNABLE"}):
            r=rank_divergent_regions(a,b)
        self.assertEqual(r["status"],"ABSTAIN_INSUFFICIENT_ALIGNMENT")
        self.assertEqual(r["hotspots"],[])
        self.assertFalse(r["phonetic_error_identified"])
    def test_local_texture_defect_highlighted_for_comparable_audio(self):
        shape=([.005]*15+[.2]*50+[.005]*20+[.13]*50+[.004]*15)
        a=feat(shape,"a");b=feat(list(shape),"b")
        for k in range(45,57):
            b["frame_zero_crossing_fraction"][k]=.98
            b["frame_mean_abs_step"][k]=.5
        r=rank_divergent_regions(a,b,window_seconds=.2,step_seconds=.1)
        self.assertEqual(r["status"],"LOCAL_ACOUSTIC_DIFFERENCES_ONLY")
        self.assertTrue(r["hotspots"])
        self.assertTrue(.6<=r["hotspots"][0]["first_start_s"]<=1.2)
        self.assertFalse(r["phonetic_error_identified"])
        self.assertFalse(r["publication_approved"])
    def test_missing_texture_fails_closed(self):
        a=feat([.002]*10+[.3]*40+[.001]*10,"a")
        b=feat(list(a["frame_rms"]),"b");del b["frame_mean_abs_step"]
        with self.assertRaisesRegex(DivergenceError,"Incomplete"):
            rank_divergent_regions(a,b)
    def test_size_budget_and_invalid_values(self):
        a=feat([.002]*10+[.3]*40+[.001]*10,"a")
        b=feat(list(a["frame_rms"]),"b")
        with self.assertRaises(DivergenceError):
            rank_divergent_regions(a,b,max_candidates=40)
        with self.assertRaises(DivergenceError):
            rank_divergent_regions(a,b,step_seconds=3)
