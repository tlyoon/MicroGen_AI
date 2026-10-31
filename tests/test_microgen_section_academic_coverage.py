"""Coverage and expanded academic deck tests with synthetic source only."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pymupdf as fitz
from PIL import Image

from microgen_pronunciation_closed_loop import sha_file
from microgen_section_academic_coverage import (
    TOPICS, STATUS, CoverageError, bounded_pages, audit_section_11)
from microgen_source_teaching_slide_render import (
    render_teaching_candidate, SourceSlideRenderError)

def fixture(root:Path):
    stage=root/"source";stage.mkdir()
    p=fitz.open()
    for j in range(1,5):
        pg=p.new_page()
        anchors=[word for _,page,terms,_ in TOPICS if page==j for word in terms]
        if j==4:
            anchors.extend(["density", "Quick Quiz 1.1"])
            anchors.extend(["1.2 Modeling and Alternative Representations",
                            "COMPLETELY DIFFERENT CHAPTER DATA"])
        txt="\n".join(anchors)
        assert pg.insert_textbox(fitz.Rect(25,25,590,800),txt,fontsize=10)>=0
    source=stage/"source.pdf";p.save(source);p.close()
    Image.new("RGB",(100,120),"navy").save(stage/"Figure 1.1.png")
    narr=[]
    visual=[]
    for i,(name,page,anchors,concepts) in enumerate(TOPICS,1):
        intro=" ".join(concepts)
        if i==6:intro+=" Since twenty nineteen, this definition changed."
        if i==14:intro+=" An aluminum cam is larger at equal mass."
        spoken=intro+" "+("The physical meaning of this quantity must be compared with its unit. "*30)
        spoken=" ".join(spoken.split()[:156])
        if i==14:spoken+=" A larger aluminum cam has a larger volume."
        assert 140<=len(spoken.split())<=180,(i,len(spoken.split()))
        narr.append({"slide":i,"source_page":page,"topic_id":name,"narration":spoken,
            "spoken_text_sha256":hashlib.sha256(spoken.encode()).hexdigest()})
        t=" ".join(concepts)
        numeric={
          4:"Speed 299,792,458 meters per second; distance 9.46 x 10^15 meters",
          5:"Earth is 6.37 million meters across in scale; atom 10^-10 meters",
          9:"Exactly 9,192,631,770 cesium cycles define the second",
          12:"SI prefixes include powers 10^-3, 10^-9 and 10^3"}
        visual.append({"slide":i,"source_page":page,"topic_id":name,
          "title":"Concept: "+name.replace("_"," "),
          "bullets":["Key physical concepts: "+t+" in the measurement description",
            numeric.get(i,"Check these quantities with appropriate original units"),
            "Compare the numerical result with a reasonable scale"]})
    n=root/"narration.json"
    v=root/"plan.json"
    n.write_text(json.dumps({"status":STATUS,"slide_count":14,
         "source_pdf_sha256":sha_file(source),
         "academic_accuracy_independently_verified":False,
         "publication_allowed":False,"formal_voice_authorized":False,
         "slides":narr}))
    v.write_text(json.dumps({"schema_version":1,"section_id":"1.1",
         "source_pdf_sha256":sha_file(source),"publication_allowed":False,
         "slides":visual}))
    return stage,n,v

class CompleteSectionTests(unittest.TestCase):
    def test_all_14_topics_with_real_rendered_pdf_and_citations(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stage,n,v=fixture(root)
            snap=sha_file(stage/"source.pdf")
            out=audit_section_11(stage,n,v)
            self.assertEqual(out["slide_count"],14)
            self.assertTrue(out["section_scope_end_before_next_section"])
            self.assertFalse(out["full_scientific_academic_certification"])
            self.assertNotIn("COMPLETELY DIFFERENT",bounded_pages(stage/"source.pdf")[3])
            rendered=render_teaching_candidate(stage,n,v,root/"rendered",
                 figure_slide=7,historical_si_slide=6)
            self.assertEqual(rendered["slide_count"],14)
            confirmed=audit_section_11(stage,n,v,root/"rendered")
            self.assertEqual(len(confirmed["topic_groups"]),14)
            with fitz.open(root/"rendered"/"slides_teaching_candidate.pdf") as doc:
                self.assertEqual(len(doc),14)
                self.assertEqual(len(doc[6].get_images()),1)
            self.assertEqual(sha_file(stage/"source.pdf"),snap)

    def test_missing_source_anchor_does_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stage,n,v=fixture(root)
            pdf=stage/"source.pdf"
            doc=fitz.open(pdf)
            doc[0].add_redact_annot(doc[0].rect)
            doc[0].apply_redactions()
            new=root/"changed.pdf";doc.save(new);doc.close();new.replace(pdf)
            j=json.loads(n.read_text());j["source_pdf_sha256"]=sha_file(pdf)
            n.write_text(json.dumps(j))
            j=json.loads(v.read_text());j["source_pdf_sha256"]=sha_file(pdf)
            v.write_text(json.dumps(j))
            with self.assertRaises(CoverageError):
                audit_section_11(stage,n,v)

    def test_missing_concept_or_bogus_math_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stage,n,v=fixture(root)
            data=json.loads(n.read_text());data["slides"][11]["narration"]="No scientific concepts."
            data["slides"][11]["spoken_text_sha256"]=hashlib.sha256(
                b"No scientific concepts.").hexdigest()
            n.write_text(json.dumps(data))
            with self.assertRaises(CoverageError):audit_section_11(stage,n,v)

    def test_missing_boundary_rejected_even_if_page_four_contains_density(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stage,n,v=fixture(root)
            with fitz.open(stage/"source.pdf") as old:
                nextdoc=fitz.open()
                for page in old:
                    p=nextdoc.new_page()
                    text=page.get_text().replace("1.2 Modeling and Alternative Representations","Missing section heading")
                    p.insert_textbox(fitz.Rect(25,25,590,800),text,fontsize=10)
                x=root/"new.pdf";nextdoc.save(x);nextdoc.close()
            x.replace(stage/"source.pdf")
            with self.assertRaises(CoverageError):bounded_pages(stage/"source.pdf")

    def test_wrong_light_speed_or_prefix_exponent_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stage,n,v=fixture(root)
            visual=json.loads(v.read_text())
            visual["slides"][3]["bullets"][1]=visual["slides"][3]["bullets"][1].replace(
                "299,792,458","299,792,459")
            v.write_text(json.dumps(visual))
            with self.assertRaises(CoverageError):audit_section_11(stage,n,v)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stage,n,v=fixture(root)
            visual=json.loads(v.read_text())
            visual["slides"][11]["bullets"][1]=visual["slides"][11]["bullets"][1].replace(
                "10^-9","10^-8")
            v.write_text(json.dumps(visual))
            with self.assertRaises(CoverageError):audit_section_11(stage,n,v)

    def test_legacy_eight_slide_rendering_still_supported(self):
        from test_microgen_source_teaching_slide_render import prepare
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);stage,n,v=prepare(root)
            result=render_teaching_candidate(stage,n,v,root/"eight")
            self.assertEqual(result["slide_count"],8)
            self.assertEqual(result["status"],"FULLER_TEACHING_SLIDE_CANDIDATE_UNAPPROVED")
            self.assertFalse(result["section_11_coverage_spot_checked"])

if __name__=="__main__": unittest.main()
