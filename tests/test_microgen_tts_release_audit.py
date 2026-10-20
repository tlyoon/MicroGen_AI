import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import microgen_tts_release_audit as a
from microgen_tts_provenance import make_record,write_manifest

def wav(path):
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
        f.writeframes(b"\x01\x00"*24000)

def acoustic_fixture(stage,digest,risk=True):
    from microgen_tts_acoustic_qa import mismatch_details
    speech="The why value exists."
    status=("REVIEW_REQUIRED_SOURCE_PRONUNCIATION_RISK"
            if risk else "ASR_SCREEN_PASS_LISTENING_REQUIRED")
    return {"schema_version":1,"slide_count":1,
            "recognition_models":["model-A","model-B"],
            "voice_provenance_sha256":a.file_hash(
                stage/".microgen_tts_provenance.json"),
            "unavailable_recognizer_passes":[],
            "review_required_slides":[1] if risk else [],
            "human_listening_approved":False,"publishable":False,
            "slides":[{"slide":1,"audio_sha256":digest,
                       "expected_spoken_sha256":__import__("hashlib").sha256(
                           speech.encode("utf8")).hexdigest(),
                       "transcripts":[speech,speech],
                       "comparisons":[mismatch_details(speech,speech)]*2,
                       "source_pronunciation_risks":[{"code":"math_letter_compound"}] if risk else [],
                       "assessment":status}]}

def setup(folder):
    (folder/"script_tts.json").write_text(json.dumps(
        {"slides":[{"slide":1,"tts_text":"The y-value exists."}]}),encoding="utf8")
    path=folder/"slide1.wav";wav(path)
    rec=make_record(slide=1,path=path,text="The why value exists.",
        provider="google_cloud_chirp3",key="case1",
        voice_name="en-US-Chirp-HD-F",language_code="en-US",
        speaking_rate=0.8,location="global")
    write_manifest(folder,[rec],["The why value exists."])
    (folder/"slides.mp4").write_bytes(b"placeholder-fixture")
    return a.file_hash(path)

class ReleaseAuditTests(unittest.TestCase):
    def test_missing_approvals_never_pass(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);setup(p)
            with patch.object(a,"check_video",return_value={"seconds":1.5}):
                result=a.audit_stage(p)
            self.assertTrue(result["checks"]["voice_bound_wav_provenance"])
            self.assertTrue(result["checks"]["video_duration_and_av_integrity"])
            self.assertFalse(result["ready_for_separate_promotion"])
            self.assertFalse(result["publication_performed"])
            self.assertIn("all_slide_listening_approved",result["blockers"])
    def test_full_explicit_receipt_set_only_enables_separate_promotion(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);digest=setup(p)
            video_sha=a.file_hash(p/"slides.mp4")
            acoustic=acoustic_fixture(p,digest)
            from microgen_tts_review_trust import sign_review_receipt
            trust={role:{"test-key":(role.encode()*40)[:40]}
                   for role in ("listening","academic","figures","highlights")}
            def signed(role,**extra):
                return sign_review_receipt({"role":role,"key_id":"test-key",
                    "reviewed_at":"2026-10-20T09:00:00+08:00",
                    "reviewer":"external human","approved":True,**extra},
                    trust[role]["test-key"],role)
            listening=signed("listening",slides=[{"slide":1,"wav_sha256":digest,
                                                "reviewer":"external human","approved":True}])
            academic=signed("academic",video_sha256=video_sha)
            figures=signed("figures",video_sha256=video_sha)
            highlight=signed("highlights",video_sha256=video_sha)
            with patch.object(a,"check_video",return_value={"seconds":1.5}):
                result=a.audit_stage(p,acoustic_report=acoustic,listening_receipt=listening,
                     academic_receipt=academic,figure_receipt=figures,
                     highlight_receipt=highlight,reviewer_trust=trust)
            self.assertTrue(result["ready_for_separate_promotion"])
            self.assertFalse(result["publication_performed"])
            listening["slides"][0]["wav_sha256"]="tampered"
            with patch.object(a,"check_video",return_value={"seconds":1.5}):
                self.assertFalse(a.audit_stage(p,acoustic_report=acoustic,
                    listening_receipt=listening,academic_receipt=academic,
                    figure_receipt=figures,highlight_receipt=highlight,
                    reviewer_trust=trust)["ready_for_separate_promotion"])
    def test_at_or_above_600_seconds_never_passes(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);setup(p)
            with patch.object(a,"check_video",return_value={"seconds":600}):
                r=a.audit_stage(p)
            self.assertFalse(r["checks"]["video_duration_and_av_integrity"])
    def test_source_wav_drift_invalidates_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);setup(p)
            wav(p/"slide1.wav")
            with (p/"slide1.wav").open("ab") as f:f.write(b"x")
            with patch.object(a,"check_video",return_value={"seconds":1.5}):
                r=a.audit_stage(p)
            self.assertFalse(r["checks"]["voice_bound_wav_provenance"])
    def test_wrong_video_hash_or_partial_listening_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);digest=setup(p)
            self.assertFalse(a._approval({"approved":True,"video_sha256":"wrong",
                        "reviewer":"person"},a.file_hash(p/"slides.mp4")))
            self.assertFalse(a._listening({"slides":[]},[digest]))
    def test_acoustic_receipt_with_wrong_hash_or_outage_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);digest=setup(p)
            base=acoustic_fixture(p,digest)
            self.assertTrue(a._acoustic(base,p,[digest],["The why value exists."]))
            base["unavailable_recognizer_passes"]=[0]
            self.assertFalse(a._acoustic(base,p,[digest],["The why value exists."]))
    def test_video_missing_remains_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);setup(p)
            (p/"slides.mp4").unlink()
            r=a.audit_stage(p)
            self.assertFalse(r["checks"]["video_duration_and_av_integrity"])
