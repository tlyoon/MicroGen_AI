import copy
import unittest
from microgen_tts_review_trust import (
 sign_review_receipt,verify_review_receipt,TrustError
)

class TrustedReviewTests(unittest.TestCase):
    def setUp(self):
        self.keys={"listening":{"k":b"l"*40},
                   "academic":{"k":b"a"*40},
                   "figures":{"k":b"f"*40},
                   "highlights":{"k":b"h"*40}}
        self.payload={"role":"academic","key_id":"k","reviewer":"external person",
            "reviewed_at":"2026-10-20T09:00:00+08:00","approved":True,
            "video_sha256":"1"*64}
    def sign(self):
        return sign_review_receipt(self.payload,self.keys["academic"]["k"],"academic")
    def test_valid_role_specific_signature(self):
        self.assertTrue(verify_review_receipt(self.sign(),"academic",self.keys))
    def test_plain_approval_without_signature_cannot_pass(self):
        self.assertFalse(verify_review_receipt(self.payload,"academic",self.keys))
        self.assertFalse(verify_review_receipt(self.sign(),"academic",None))
    def test_wrong_role_key_cannot_authorize(self):
        self.assertFalse(verify_review_receipt(self.sign(),"figures",self.keys))
    def test_tamper_video_sha_invalidates_signature(self):
        signed=self.sign()
        signed["video_sha256"]="0"*64
        self.assertFalse(verify_review_receipt(signed,"academic",self.keys))
    def test_tamper_reviewer_identity_invalidates_signature(self):
        signed=self.sign();signed["reviewer"]="somebody else"
        self.assertFalse(verify_review_receipt(signed,"academic",self.keys))
    def test_tamper_listening_rows_invalidates_signature(self):
        payload={**self.payload,"role":"listening",
            "slides":[{"slide":1,"wav_sha256":"1"*64,"approved":True,"reviewer":"person"}]}
        signed=sign_review_receipt(payload,self.keys["listening"]["k"],"listening")
        signed["slides"][0]["wav_sha256"]="2"*64
        self.assertFalse(verify_review_receipt(signed,"listening",self.keys))
    def test_missing_role_or_weak_key_cannot_sign(self):
        with self.assertRaises(TrustError):
            sign_review_receipt(self.payload,b"weak","academic")
        with self.assertRaises(TrustError):
            sign_review_receipt(self.payload,b"a"*40,"not-a-role")
    def test_missing_external_keys_fail_closed(self):
        self.assertFalse(verify_review_receipt(self.sign(),"academic",{"academic":{}}))
        self.assertFalse(verify_review_receipt(self.sign(),"academic",{"academic":{"k":b"?"*40}}))
