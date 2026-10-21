import unittest
from microgen_tts_envelope_alignment import align_envelopes,EnvelopeAlignmentError

def feature(v,tag="x"):
    return {"frame_rms":v,"sample_rate_hz":24000,"frame_ms":20,"wav_sha256":tag*64,
            "duration_seconds":len(v)*0.02}

class EnvelopeAlignmentTests(unittest.TestCase):
    def test_known_shift_recovers_lag(self):
        pattern=[0.002]*18+[0.12]*15+[0.002]*12+[0.22]*10+[0.003]*18
        first=feature(pattern,tag="a")
        second=feature([0.002]*5+pattern,tag="b")
        result=align_envelopes(first,second,max_lag_seconds=0.3)
        self.assertEqual(result["lag_frames"],5)
        self.assertEqual(result["lag_seconds"],0.1)
        self.assertFalse(result["phoneme_verified"])
    def test_gain_change_is_not_called_phoneme_error(self):
        pattern=[.01]*15+[.12]*25+[.01]*20
        a=feature(pattern);b=feature([z*.7 for z in pattern],"b")
        result=align_envelopes(a,b)
        self.assertEqual(result["lag_frames"],0)
        self.assertFalse(result["phoneme_verified"])
    def test_incompatible_envelopes_are_marked_unalignable(self):
        a=feature(([.18]*15+[.01]*15)*3,tag="a")
        b=feature(([.01]*15+[.18]*15)*3,tag="b")
        verdict=align_envelopes(a,b,max_lag_seconds=0.06)
        self.assertEqual(verdict["status"],"LOW_SIMILARITY_UNALIGNABLE")
        self.assertIsNone(verdict["lag_seconds"])

    def test_incompatible_and_invalid_limits_rejected(self):
        a=feature([0.1]*30);b=feature([0.1]*30)
        b["sample_rate_hz"]=44100
        with self.assertRaises(Exception):align_envelopes(a,b)
        with self.assertRaises(EnvelopeAlignmentError):
            align_envelopes(a,a,max_lag_seconds=5)
    def test_no_acoustic_signal_returns_unalignable(self):
        a=feature([0.0]*80);b=feature([0.0]*80,"b")
        result=align_envelopes(a,b)
        self.assertEqual(result["status"],"UNALIGNABLE")
        self.assertIsNone(result["lag_seconds"])
