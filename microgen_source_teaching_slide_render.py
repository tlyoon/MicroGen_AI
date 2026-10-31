"""Render a fuller, source-bound teaching-slide candidate from private verified inputs.

The PDF is a teaching draft, not final academic or pronunciation approval.
No TTS/network calls; original source and figure assets remain immutable.
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import tempfile
import os
from pathlib import Path

import pymupdf as fitz
from microgen_pronunciation_closed_loop import sha_file
from microgen_offline_source_slide_draft import normal, OFFICIAL_SI_URL


class SourceSlideRenderError(ValueError):
    pass


def render_teaching_candidate(source_stage:Path, narration_qa:Path, plan_file:Path,
                              new_output:Path, *, figure_slide:int=5,
                              historical_si_slide:int=4)->dict:
    source_stage=Path(source_stage);narration_qa=Path(narration_qa)
    plan_file=Path(plan_file);new_output=Path(new_output)
    source=source_stage/"source.pdf"
    figure=source_stage/"Figure 1.1.png"
    if any(p.is_symlink() or not p.is_file() for p in (source, figure, narration_qa, plan_file)):
        raise SourceSlideRenderError("Real immutable source, figure and narration inputs required")
    report=json.loads(narration_qa.read_text(encoding="utf8"))
    plan=json.loads(plan_file.read_text(encoding="utf8"))
    if (report.get("status")!="EIGHT_SLIDE_NARRATION_DRAFT_COMPLETE_UNAPPROVED"
        or report.get("source_pdf_sha256")!=sha_file(source)
        or report.get("academic_accuracy_independently_verified") is not False
        or report.get("publication_allowed") is not False
        or not isinstance(plan.get("slides"),list)
        or len(plan["slides"])!=report.get("slide_count")
        or len(report.get("slides",[]))!=len(plan["slides"])
        or not 1<=len(plan["slides"])<=30):
        raise SourceSlideRenderError("Narration and actual source inputs do not agree")
    if (type(figure_slide) is not int or type(historical_si_slide) is not int
        or not 1<=figure_slide<=len(plan["slides"])
        or not 1<=historical_si_slide<=len(plan["slides"])):
        raise SourceSlideRenderError("Invalid historical figure/SI slide mapping")
    dest=new_output.resolve(strict=False)
    if (new_output.exists() or new_output.is_symlink() or not dest.parent.is_dir()
        or source_stage.resolve(strict=True) in dest.parents
        or any(s.casefold()=="my drive" for s in dest.parts)):
        raise SourceSlideRenderError("Fresh external slide candidate output required")
    source_hash=sha_file(source);figure_hash=sha_file(figure)
    qa_hash=sha_file(narration_qa);plan_hash=sha_file(plan_file)
    rendered=fitz.open()
    rows=[]
    temp=None
    try:
        for i,(visual,narration) in enumerate(zip(plan["slides"],report["slides"]),1):
            title=visual.get("title");bullets=visual.get("bullets")
            if (visual.get("slide")!=i or narration.get("slide")!=i
                or not isinstance(title,str) or not 4<=len(title)<=90
                or not isinstance(bullets,list) or len(bullets)!=3
                or any(not isinstance(x,str) or not 12<=len(x)<=95 for x in bullets)):
                raise SourceSlideRenderError("Invalid three-concept slide mapping")
            page=rendered.new_page(width=960,height=540)
            page.draw_rect(fitz.Rect(0,0,960,540),fill=(.98,.985,.994),color=None)
            page.draw_rect(fitz.Rect(0,0,960,18),fill=(.09,.29,.48),color=None)
            if page.insert_textbox(fitz.Rect(50,42,910,100),title,fontsize=28,color=(.08,.20,.32))<0:
                raise SourceSlideRenderError("Heading overflow")
            for j,bullet in enumerate(bullets):
                y=122+j*68
                page.draw_circle(fitz.Point(67,y+10),6,fill=(.12,.42,.60),color=None)
                if page.insert_textbox(fitz.Rect(89,y-5,890,y+52),bullet,
                    fontsize=19,color=(.12,.23,.34))<0:
                    raise SourceSlideRenderError("Bullet text would overflow")
            if i==figure_slide:
                page.insert_image(fitz.Rect(480,307,885,455),filename=str(figure),
                                  keep_proportion=True)
                page.insert_textbox(fitz.Rect(72,316,450,450),
                    "Historical mass reference and atomic clock\nSource figure from original textbook PDF",
                    fontsize=16,color=(.21,.32,.41))
            if i==historical_si_slide:
                warning="SI UPDATE: Since 2019, the kilogram is defined using the fixed Planck constant."
                page.draw_rect(fitz.Rect(58,380,902,450),fill=(.99,.93,.89),color=None)
                if page.insert_textbox(fitz.Rect(72,391,885,442),warning,
                    fontsize=18,color=(.48,.19,.12))<0:
                    raise SourceSlideRenderError("SI caution would overflow")
                page.insert_link({"kind":fitz.LINK_URI,
                    "from":fitz.Rect(58,380,902,450),"uri":OFFICIAL_SI_URL})
            page.draw_line(fitz.Point(50,482),fitz.Point(910,482),
                           color=(.68,.75,.82),width=1)
            page.insert_text((50,511),"SOURCE-BOUND CANDIDATE - NOT FOR PUBLICATION",
                             fontsize=11,color=(.48,.26,.24))
            page.insert_text((780,511),f"Serway 1.1 | {i}/{len(plan['slides'])}",
                             fontsize=11,color=(.2,.34,.44))
            rows.append({"slide":i,"title":title,"source_page":narration["source_page"],
                         "bullets":bullets,"narration_sha256":narration["spoken_text_sha256"],
                         "draft_rendered":True,"academic_quality_verified":False})
        temp=Path(tempfile.mkdtemp(prefix=".microgen-teaching-slides-pending-",
                                   dir=dest.parent))
        pdf=temp/"slides_teaching_candidate.pdf"
        rendered.save(pdf,garbage=4,deflate=True)
        with fitz.open(pdf) as actual:
            if actual.page_count!=len(rows):raise SourceSlideRenderError("Generated slide count mismatch")
            for i,row in enumerate(rows,1):
                txt=normal(actual[i-1].get_text("text"))
                if (normal(row["title"]) not in txt or
                    any(normal(term) not in txt for term in row["bullets"])):
                    raise SourceSlideRenderError("Visible teaching points missing from PDF")
                if i==figure_slide and not actual[i-1].get_images():
                    raise SourceSlideRenderError("Figure missing from source-bound teaching slide")
                if i==historical_si_slide and OFFICIAL_SI_URL not in [
                    link.get("uri") for link in actual[i-1].get_links()]:
                    raise SourceSlideRenderError("Historical SI correction citation missing")
        receipt={"schema_version":1,"status":"FULLER_TEACHING_SLIDE_CANDIDATE_UNAPPROVED",
            "source_pdf_sha256":source_hash,"figure_sha256":figure_hash,
            "narration_qa_sha256":qa_hash,"visual_plan_sha256":plan_hash,
            "rendered_pdf_sha256":sha_file(pdf),"slide_count":len(rows),
            "slides":rows,"figure_slide":figure_slide,
            "historical_si_slide":historical_si_slide,
            "figure_semantics_independently_verified":False,
            "academic_accuracy_independently_verified":False,
            "formal_voice_authorized":False,"generated_wavs":False,
            "generated_mp4s":False,"provider_calls":0,"publication_allowed":False}
        (temp/"teaching_slide_receipt.json").write_text(
            json.dumps(receipt,indent=2),encoding="utf8")
        if any(sha_file(path)!=digest for path,digest in (
            (source,source_hash),(figure,figure_hash),
            (narration_qa,qa_hash),(plan_file,plan_hash))):
            raise SourceSlideRenderError("Input changed while rendering")
        if dest.exists():raise SourceSlideRenderError("Output appeared during render")
        os.rename(temp,dest);return receipt
    finally:
        rendered.close()
        if temp is not None and temp.exists():shutil.rmtree(temp)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--narration-qa",type=Path,required=True)
    p.add_argument("--visual-plan",type=Path,required=True)
    p.add_argument("--new-dir",type=Path,required=True)
    a=p.parse_args(argv)
    result=render_teaching_candidate(a.stage,a.narration_qa,a.visual_plan,a.new_dir)
    print(json.dumps({"slides":result["slide_count"],"directory":str(a.new_dir),
                      "publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
