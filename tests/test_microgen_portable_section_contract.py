"""Synthetic second-section PDF proves manifest reader is not Serway-specific."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import pymupdf as fitz
from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_section_contract import audit_portable_contract,PortableSectionError

def create(root):
    pdf=fitz.open()
    for text in (
       "Section B.2: Abstract Measurement\nA fixed marker ensures consistent comparisons.\nA ratio expresses one quantity relative to another.",
       "A triangle can be characterized by its three sides.\nSection B.3: Neighboring Topic\nA secret concept is NOT part of section B.2."):
        p=pdf.new_page()
        assert p.insert_textbox(fitz.Rect(30,30,550,730),text,fontsize=12)>=0
    src=root/"source.pdf";pdf.save(src);pdf.close()
    topics=[("fixed_standard",1,"A fixed marker","fixed"),
            ("ratios",1,"A ratio expresses","ratio"),
            ("triangle",2,"A triangle can","triangle")]
    n={"publication_allowed":False,"slides":[]}
    v={"publication_allowed":False,"slides":[]}
    for i,(tid,page,anchor,term) in enumerate(topics,1):
        speech=(f"We use the {term} concept in this scientific example. ")*13
        speech=" ".join(speech.split())
        n["slides"].append({"slide":i,"topic_id":tid,"source_page":page,
            "narration":speech,"spoken_text_sha256":hashlib.sha256(speech.encode()).hexdigest()})
        v["slides"].append({"slide":i,"topic_id":tid,"source_page":page,
            "title":f"Meaning of {term}",
            "bullets":[f"The {term} statement follows the source",
                       "Independent visual reasoning is consistent with units"]})
    narr=root/"narration.json";narr.write_text(json.dumps(n))
    plan=root/"plan.json";plan.write_text(json.dumps(v))
    manifest=root/"contract.json"
    manifest.write_text(json.dumps({"schema_version":1,
      "section_id":"B.2","source_pdf_sha256":sha_file(src),
      "narration_sha256":sha_file(narr),"visual_plan_sha256":sha_file(plan),
      "start_marker":"Section B.2: Abstract Measurement",
      "next_section_marker":"Section B.3: Neighboring Topic",
      "min_narration_words":70,"max_narration_words":160,
      "topics":[{"topic_id":tid,"source_page":page,
                 "source_anchors":[anchor],"required_terms":[term]}
                  for tid,page,anchor,term in topics],
      "publication_allowed":False}))
    return src,narr,plan,manifest

class PortableContracts(unittest.TestCase):
    def test_independent_second_section_fully_checked(self):
        with tempfile.TemporaryDirectory() as td:
            files=create(Path(td))
            result=audit_portable_contract(*files)
            self.assertEqual(result["topic_count"],3)
            self.assertEqual(result["section_id"],"B.2")
            self.assertTrue(result["next_section_excluded"])
            self.assertFalse(result["independent_full_academic_certification"])
            self.assertFalse(result["publication_allowed"])

    def test_adjacent_section_cannot_be_a_borrowed_anchor(self):
        with tempfile.TemporaryDirectory() as td:
            files=create(Path(td))
            p=files[3];m=json.loads(p.read_text())
            m["topics"][2]["source_anchors"]=["A secret concept"]
            p.write_text(json.dumps(m))
            with self.assertRaises(PortableSectionError):
                audit_portable_contract(*files)

    def test_forged_narration_or_image_plan_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            files=create(Path(td))
            s=files[1];n=json.loads(s.read_text())
            n["slides"][1]["narration"]="changed"
            s.write_text(json.dumps(n))
            with self.assertRaises(PortableSectionError):
                audit_portable_contract(*files)

    def test_absent_adjacent_boundary_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            files=create(Path(td))
            m=json.loads(files[3].read_text())
            m["next_section_marker"]="This heading is not here"
            files[3].write_text(json.dumps(m))
            with self.assertRaises(PortableSectionError):
                audit_portable_contract(*files)

    def test_duplicate_topics_or_wrong_pdf_hash_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            files=create(Path(td))
            m=json.loads(files[3].read_text())
            m["topics"][1]["topic_id"]=m["topics"][0]["topic_id"]
            files[3].write_text(json.dumps(m))
            with self.assertRaises(PortableSectionError):
                audit_portable_contract(*files)
        with tempfile.TemporaryDirectory() as td:
            files=create(Path(td))
            m=json.loads(files[3].read_text())
            m["source_pdf_sha256"]="0"*64
            files[3].write_text(json.dumps(m))
            with self.assertRaises(PortableSectionError):
                audit_portable_contract(*files)

if __name__=="__main__":unittest.main()
