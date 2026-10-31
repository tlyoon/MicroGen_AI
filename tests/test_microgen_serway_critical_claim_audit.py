"""Independent source math-claim audit regression tests: synthetic PDFs only."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import pymupdf as fitz
from microgen_pronunciation_closed_loop import sha_file
from microgen_offline_source_slide_draft import OFFICIAL_SI_URL
from microgen_serway_critical_claim_audit import (
    audit_serway_critical_claims, ClaimAuditError,
    PAGE_ANCHORS, NARRATION_TERMS, VISUAL_TERMS)

def inputs(root):
    stage=root/"source";stage.mkdir()
    draft=root/"slides";draft.mkdir()
    doc=fitz.open()
    for p in range(4):
        page=doc.new_page()
        txt="\n".join(term for src, terms in PAGE_ANCHORS
                      if src==p for term in terms)
        page.insert_textbox(fitz.Rect(35,35,560,500),txt,fontsize=13)
    pdf=stage/"source.pdf";doc.save(pdf);doc.close()
    fig=stage/"test.png";Image.new("RGB",(20,20),"red").save(fig)
    slidepdf=fitz.open()
    for i in range(1,9):
        page=slidepdf.new_page(width=960,height=540)
        txt="\n".join(VISUAL_TERMS[i-1])
        page.insert_textbox(fitz.Rect(45,45,950,360),txt,fontsize=17)
        if i==4:page.insert_link({"kind":fitz.LINK_URI,
            "from":fitz.Rect(40,40,240,90),"uri":OFFICIAL_SI_URL})
        if i==5:page.insert_image(fitz.Rect(400,370,460,430),filename=str(fig))
    slides=draft/"slides_teaching_candidate.pdf";slidepdf.save(slides);slidepdf.close()
    n=root/"narration.json"
    narrations=[{"slide":i,"source_page":PAGE_ANCHORS[i-1][0]+1,
                 "spoken_text_sha256":"a"*64,
                 "narration":" ".join(NARRATION_TERMS[i-1])}
                for i in range(1,9)]
    n.write_text(json.dumps({"status":"EIGHT_SLIDE_NARRATION_DRAFT_COMPLETE_UNAPPROVED",
        "source_pdf_sha256":sha_file(pdf),"publication_allowed":False,
        "formal_voice_authorized":False,"slide_count":8,"slides":narrations}))
    manifest=draft/"teaching_slide_receipt.json"
    manifest.write_text(json.dumps({
       "status":"FULLER_TEACHING_SLIDE_CANDIDATE_UNAPPROVED",
       "source_pdf_sha256":sha_file(pdf),"rendered_pdf_sha256":sha_file(slides),
       "narration_qa_sha256":sha_file(n),"publication_allowed":False,
       "formal_voice_authorized":False,"slide_count":8,
       "slides":[{"slide":i,"narration_sha256":"a"*64} for i in range(1,9)]}))
    return stage,n,draft

class ClaimTests(unittest.TestCase):
    def test_critical_facts_supported_but_never_full_approval(self):
        with tempfile.TemporaryDirectory() as td:
            stage,n,draft=inputs(Path(td))
            initial=sha_file(stage/"source.pdf")
            result=audit_serway_critical_claims(stage,n,draft)
            self.assertEqual(len(result["critical_claim_groups"]),8)
            self.assertEqual(result["exact_speed_of_light_m_per_s"],299792458)
            self.assertAlmostEqual(result["derived_light_year_m"]/1e15,9.4607,places=3)
            self.assertTrue(result["density_equal_mass_example_consistent"])
            self.assertFalse(result["all_scientific_claims_verified"])
            self.assertFalse(result["publication_allowed"])
            self.assertEqual(sha_file(stage/"source.pdf"),initial)

    def test_false_source_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage,n,draft=inputs(Path(td))
            with (stage/"source.pdf").open("ab") as stream:stream.write(b"altered")
            with self.assertRaises(ClaimAuditError):
                audit_serway_critical_claims(stage,n,draft)

    def test_wrong_narration_critical_number_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage,n,draft=inputs(Path(td))
            narr=json.loads(n.read_text())
            narr["slides"][5]["narration"]="cesium incorrect no period now"
            n.write_text(json.dumps(narr))
            with self.assertRaises(ClaimAuditError):
                audit_serway_critical_claims(stage,n,draft)

    def test_misleading_modern_artifact_definition_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            stage,n,draft=inputs(Path(td))
            narr=json.loads(n.read_text())
            narr["slides"][3]["narration"] += " kilogram is defined as mass of a platinum cylinder"
            n.write_text(json.dumps(narr))
            manifest=draft/"teaching_slide_receipt.json"
            d=json.loads(manifest.read_text());d["narration_qa_sha256"]=sha_file(n)
            manifest.write_text(json.dumps(d))
            with self.assertRaises(ClaimAuditError):
                audit_serway_critical_claims(stage,n,draft)

if __name__=="__main__":
    unittest.main()
