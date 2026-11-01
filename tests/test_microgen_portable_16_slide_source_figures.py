"""Sixteen-slide, four-figure, original-vector-math generic regression fixture.

This synthetic test proves reusable section scale; real textbook assets stay off GitHub.
"""
import hashlib
import json
import tempfile
from pathlib import Path

import pymupdf as fitz
from PIL import Image

from microgen_portable_slide_render import render_portable_slides
from microgen_portable_source_equations import crop_sha
from microgen_pronunciation_closed_loop import sha_file
from test_microgen_portable_lecture_pipeline import setup


def sixteen_topic_source(root):
    stage, narration, plan, contract, *_ = setup(root)
    pdf_file = stage / "source.pdf"
    with fitz.open(pdf_file) as pdf:
        page=pdf[0]
        page.insert_text((47,310), "h = 50 tan(25)", fontsize=23)
        pdf.saveIncr()
    with fitz.open(pdf_file) as pdf:
        rect=pdf[0].search_for("h = 50 tan(25)")[0] + (-2,-2,2,2)
        box=[float(x) for x in rect]
        math_sha=crop_sha(pdf[0],fitz.Rect(box))
    n=json.loads(narration.read_text())
    v=json.loads(plan.read_text())
    m=json.loads(contract.read_text())
    for number in range(4,17):
        label=f"replica_{number:02d}"
        text=" ".join([
           "The ratio describes a consistent conceptual relation in this synthetic scientific example."
        ] * 10)
        assert 60<=len(text.split())<=160
        n["slides"].append({
            "slide":number,"topic_id":label,"source_page":1,
            "narration":text,"spoken_text_sha256":hashlib.sha256(text.encode()).hexdigest()
        })
        v["slides"].append({
            "slide":number,"topic_id":label,"source_page":1,
            "title":f"Ratio model example {number}",
            "bullets":["A ratio compares two quantities",
                       "Check source identity and source-aligned evidence"]
        })
        m["topics"].append({
            "topic_id":label,"source_page":1,
            "source_anchors":["A ratio expresses"],
            "required_terms":["ratio"]
        })
    images=[]
    for idx in (6,13,14,15):
        path=stage/f"synthetic_figure_{idx}.png"
        Image.new("RGB",(90+idx,95+idx),(40+idx,120,190)).save(path)
        images.append({
            "slide":idx,"filename":path.name,"sha256":sha_file(path),
            "caption":f"Synthetic original figure number {idx}"
        })
    m["figures"]=images
    m["source_equations"]=[{
        "slide":7,"source_page":1,
        "source_bbox":box,"source_crop_sha256":math_sha
    }]
    narration.write_text(json.dumps(n))
    plan.write_text(json.dumps(v))
    m["source_pdf_sha256"]=sha_file(pdf_file)
    m["narration_sha256"]=sha_file(narration)
    m["visual_plan_sha256"]=sha_file(plan)
    contract.write_text(json.dumps(m))
    return stage,narration,plan,contract


def test_sixteen_slide_multiple_source_figure_math_source_identity():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        paths=sixteen_topic_source(root)
        original_hash=sha_file(paths[0]/"source.pdf")
        rendered=render_portable_slides(*paths,root/"slides")
        assert rendered["slide_count"]==16
        assert rendered["figures_exact_original_pixels_verified"]
        assert rendered["equation_source_geometry_sha_verified"]
        assert rendered["formal_voice_authorized"] is False
        assert rendered["publication_allowed"] is False
        assert rendered["mathematical_equation_semantics_proven"] is False
        assert [r["slide"] for r in rendered["slides"] if r["figure"]]==[6,13,14,15]
        with fitz.open(root/"slides"/"slides_teaching_candidate.pdf") as pages:
            assert len(pages)==16
            for idx in (6,13,14,15):
                assert len(pages[idx-1].get_images())==1
            assert pages[6].get_xobjects()
        assert sha_file(paths[0]/"source.pdf")==original_hash
