"""Production handoff must never promote a diagnostic voice or video."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from microgen_pronunciation_closed_loop import sha_file
from microgen_formal_voice_handoff import (
    prepare_formal_voice_handoff, save_formal_voice_handoff, FormalVoiceHandoffError)

def setup(root):
    n=root/"n.json";a=root/"claims.json";f=root/"fig.json"
    d=root/"diagnostic";d.mkdir()
    mp4=d/"lecture_diagnostic_only.mp4";mp4.write_bytes(b"synthetic diagnostic output")
    narration=["The original conceptual explanation for verified source page "+str(i)
               for i in range(1,9)]
    entries=[{"slide":i,"source_page":1,
              "source_pdf_sha256":"a"*64,
              "review_state":"DRAFT_NEEDS_INDEPENDENT_ACADEMIC_QA",
              "narration":word,
              "spoken_text_sha256":hashlib.sha256(word.encode()).hexdigest()}
             for i,word in enumerate(narration,1)]
    n.write_text(json.dumps({
        "status":"EIGHT_SLIDE_NARRATION_DRAFT_COMPLETE_UNAPPROVED",
        "publication_allowed":False,"formal_voice_authorized":False,
        "slide_count":8,"slides":entries}))
    a.write_text(json.dumps({
        "status":"EIGHT_CRITICAL_SOURCE_CLAIM_GROUPS_SPOT_CHECKED",
        "narration_qa_sha256":sha_file(n),"source_pdf_sha256":"a"*64,
        "teaching_slides_sha256":"b"*64,"publication_allowed":False,
        "critical_claim_groups":[{"slide":i,"critical_fact_spot_checks_passed":True}
                                 for i in range(1,9)]}))
    f.write_text(json.dumps({
        "status":"ORIGINAL_TWO_PANEL_FIGURE_PIXEL_IDENTITY_VERIFIED",
        "narration_sha256":sha_file(n),"critical_claim_report_sha256":sha_file(a),
        "source_pdf_sha256":"a"*64,"teaching_pdf_sha256":"b"*64,
        "panels":[{"panel":name,"source_pixel_identity_verified":True,
                   "normalised_rgb_difference":0.0} for name in ("a_left","b_right")],
        "publication_allowed":False}))
    receipt=d/"diagnostic_av_receipt.json"
    receipt.write_text(json.dumps({
        "status":"DIAGNOSTIC_MP4_CREATED_NOT_FOR_PUBLICATION",
        "diagnostic_mp4_sha256":sha_file(mp4),
        "narration_qa_sha256":sha_file(n),"rendered_pdf_sha256":"b"*64,
        "publication_allowed":False,"voice_is_formal":False,
        "formal_voice_authorized":False,"all_slide_midpoints_source_pixel_checked":True,
        "slide_count":8,"total_input_audio_seconds":480.,
        "diagnostic_mp4_duration_seconds":481.,
        "declared_diagnostic_voice":"Microsoft Zira Desktop",
        "video_slide_frame_alignment":[
            {"slide":i,"matches_original_slide_under_8pct_threshold":True,
             "mean_absolute_rgb_fraction":0.001}
            for i in range(1,9)]}))
    return n,a,f,d

class VoiceHandoffTests(unittest.TestCase):
    def test_real_source_links_generate_eight_unapproved_requests(self):
        with tempfile.TemporaryDirectory() as td:
            n,a,f,d=setup(Path(td))
            o=prepare_formal_voice_handoff(n,a,f,d)
            self.assertEqual(o["slide_count"],8)
            self.assertEqual(len(o["blocking_conditions"]),5)
            self.assertTrue(o["diagnostic_voice_cannot_be_default_formal"])
            self.assertIsNone(o["formal_voice_provider"])
            self.assertFalse(o["formal_production_ready"])
            self.assertFalse(o["publication_allowed"])
            self.assertEqual(o["voice_synthesis_calls"],0)

    def test_edited_video_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            n,a,f,d=setup(Path(td))
            with (d/"lecture_diagnostic_only.mp4").open("ab") as h:h.write(b"tamper")
            with self.assertRaises(FormalVoiceHandoffError):
                prepare_formal_voice_handoff(n,a,f,d)

    def test_forged_formal_voice_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            n,a,f,d=setup(Path(td))
            receipt=d/"diagnostic_av_receipt.json"
            r=json.loads(receipt.read_text());r["voice_is_formal"]=True
            receipt.write_text(json.dumps(r))
            with self.assertRaises(FormalVoiceHandoffError):
                prepare_formal_voice_handoff(n,a,f,d)

    def test_wrong_text_sha_or_timing_drift_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            n,a,f,d=setup(Path(td))
            rec=d/"diagnostic_av_receipt.json"
            r=json.loads(rec.read_text());r["diagnostic_mp4_duration_seconds"]=600
            rec.write_text(json.dumps(r))
            with self.assertRaises(FormalVoiceHandoffError):
                prepare_formal_voice_handoff(n,a,f,d)
            r["diagnostic_mp4_duration_seconds"]=481.
            rec.write_text(json.dumps(r))
            items=json.loads(n.read_text());items["slides"][0]["narration"]="changed"
            n.write_text(json.dumps(items))
            with self.assertRaises(FormalVoiceHandoffError):
                prepare_formal_voice_handoff(n,a,f,d)

    def test_export_is_new_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);n,a,f,d=setup(root)
            out=root/"handoff.json"
            self.assertFalse(save_formal_voice_handoff(n,a,f,d,out)["publication_allowed"])
            with self.assertRaises(FormalVoiceHandoffError):
                save_formal_voice_handoff(n,a,f,d,out)

if __name__=="__main__":unittest.main()
