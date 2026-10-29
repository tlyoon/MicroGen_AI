"""Offline *draft*, not finished courseware: source-PDF-verified excerpts.

No Gemini, speech/TTS, language-model summaries or remote calls. Each
excerpt must appear in the exact original source page, or generation fails.
The current-SI correction is explicitly external and never misattributed to
the older source PDF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import pymupdf as fitz
from PIL import Image

from microgen_figure_composition import validate_figure_receipt
from microgen_batch import source_page_extraction_valid

OFFICIAL_SI_URL = "https://www.bipm.org/en/committees/cg/cgpm/26-2018/resolution-1"
SLIDES = (
    (1, "Mechanics: three fundamental quantities",
     "In mechanics, the three fundamental quantities are length, mass, and time."),
    (1, "Why measurement standards matter",
     "Whatever is chosen as a standard must be readily accessible and must possess some property that can be measured reliably."),
    (2, "Length: the speed-of-light definition",
     "this latest definition establishes that the speed of light in vacuum is precisely 299 792 458 meters per second."),
    (2, "Mass: the prototype is historical",
     "The SI fundamental unit of mass, the kilogram (kg), is defined as the mass of a specific platinum–iridium alloy cylinder"),
    (2, "Figure 1.1: physical standards",
     "Figure 1.1"),
    (3, "Time: atomic definition of the second",
     "One second is now defined as 9 192 631 770 times the period of vibration of radiation from the cesium-133 atom."),
    (3, "Time versus time interval",
     "A time is a description of an instant relative to a reference time."),
    (4, "Fundamental and derived quantities",
     "The variables length, mass, and time are examples of fundamental quantities."),
)

class OfflineSlideDraftError(ValueError):
    pass

def sha(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()

def normal(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())

def verify_excerpt(text, excerpt):
    return bool(excerpt and normal(excerpt) in normal(text))

def _read_source(stage):
    doc=fitz.open(stage / "source.pdf")
    pages=[p.get_text("text") for p in doc]
    return doc,pages

def _ensure_receipts(stage):
    if not source_page_extraction_valid(stage):
        raise OfflineSlideDraftError("Incomplete or tampered source extraction")
    mapped=stage/"offline_figure_mapping_receipt.json"
    if not mapped.is_file() or mapped.is_symlink():
        raise OfflineSlideDraftError("Offline PDF figure map is required")
    proof=json.loads(mapped.read_text(encoding="utf-8"))
    if (proof.get("status")!="HIGH_CONFIDENCE_SOURCE_IMAGE_MAPPING_NOT_ACADEMIC_APPROVAL"
         or proof.get("source_pdf_sha256")!=sha(stage/"source.pdf")
         or proof.get("gemini_invoked") is not False
         or proof.get("publication_allowed") is not False
         or proof.get("figure_label")!="Figure 1.1"
         or proof.get("composed_image_sha256")!=sha(stage/"Figure 1.1.png")):
        raise OfflineSlideDraftError("Untrusted source figure proof")
    result=validate_figure_receipt(stage)
    if (len(result["figures"])!=1 or result["figures"][0]["panel_count"]!=2
         or result["figures"][0]["review_required"] is not True):
        raise OfflineSlideDraftError("Two-panel source figure needs explicit review flag")
    return proof

def _frame(page, title, number, count, font):
    W,H=page.rect.width,page.rect.height
    page.draw_rect(fitz.Rect(0,0,W,H),color=None,fill=(0.973,0.98,0.99))
    page.draw_rect(fitz.Rect(0,0,W,14),color=None,fill=(0.11,0.30,0.46))
    page.insert_text((52,70),title,fontsize=27,fontname=font,color=(0.09,.20,.32))
    page.draw_line((52,92),(W-52,92),color=(.70,.78,.84),width=1)
    page.draw_line((52,H-52),(W-52,H-52),color=(.70,.78,.84),width=1)
    page.insert_text((52,H-27),"OFFLINE DRAFT - NOT APPROVED FOR PUBLICATION",
                     fontsize=12,fontname=font,color=(.50,.27,.27))
    page.insert_text((W-140,H-27),f"{number} / {count}",fontsize=12,
                     fontname=font,color=(.28,.36,.41))

def _box(page, rect, text, font, size=19, color=(.18,.25,.31)):
    box=fitz.Rect(rect)
    if box.is_empty or not page.rect.contains(box):
        raise OfflineSlideDraftError("Unsafe text placement")
    # Fail rather than render clipped text and imply slide correctness.
    remaining=page.insert_textbox(box,text,fontname=font,fontsize=size,
                                  color=color,lineheight=1.34)
    if remaining < 0:
        raise OfflineSlideDraftError("Text does not fit slide")
    return remaining

def create_draft(stage: Path, output: Path) -> dict:
    scratch=Path(stage).resolve(strict=True)
    target=Path(output).resolve(strict=False)
    if (scratch.is_symlink() or target.exists() or target.is_symlink() or
            target==scratch or target.is_relative_to(scratch) or
            scratch.is_relative_to(target) or
            target.is_relative_to(Path.home()/"My Drive")):
        raise OfflineSlideDraftError("Use a NEW independent local draft directory")
    proof=_ensure_receipts(scratch)
    source=sha(scratch/"source.pdf")
    mapped=sha(scratch/"Figure 1.1.png")
    raw,lines=_read_source(scratch)
    try:
        if len(lines)<4:
            raise OfflineSlideDraftError("Expected all four real source pages")
        records=[]
        for page_no,title,excerpt in SLIDES:
            if page_no>len(lines) or not verify_excerpt(lines[page_no-1],excerpt):
                raise OfflineSlideDraftError(f"Verbatim source excerpt not present: {title}")
            records.append({"source_page":page_no,"title":title,
                "source_excerpt":excerpt,"excerpt_verbatim_verified":True,
                "source_sha256":source})
        output_doc=fitz.open()
        try:
            for n,rec in enumerate(records,1):
                slide=output_doc.new_page(width=960,height=540)
                fontpath=Path("C:/Windows/Fonts/arial.ttf")
                fontname="helv"
                if fontpath.is_file():
                    slide.insert_font(fontname="mg-arial",fontfile=str(fontpath))
                    fontname="mg-arial"
                _frame(slide,rec["title"],n,len(records),fontname)
                if n==5:
                    slide.insert_image(fitz.Rect(86,108,402,460),
                        filename=str(scratch/"Figure 1.1.png"),keep_proportion=True)
                    _box(slide,(438,134,888,295),
                        "Textbook Figure 1.1\nPanel (a): historical kilogram prototype\nPanel (b): atomic clock",
                        fontname,size=19)
                    _box(slide,(438,334,888,421),
                        "Figure source: textbook PDF page 2. Panel arrangement is source verified; academic figure review is pending.",
                        fontname,size=15)
                else:
                    _box(slide,(80,140,880,320),rec["source_excerpt"],
                        fontname,size=25 if len(rec["source_excerpt"])<110 else 21)
                    if n==4:
                        _box(slide,(80,349,880,445),
                            "IMPORTANT SI UPDATE: Since 20 May 2019, the kilogram is defined through the fixed Planck constant, not the physical prototype.",
                            fontname,size=17,color=(.57,.19,.14))
                    else:
                        _box(slide,(80,366,880,443),
                            f"Original textbook: Section 1.1, source PDF page {rec['source_page']}. This is an excerpt, not a complete narrated explanation.",
                            fontname,size=16)
                if n==4:
                    slide.insert_link({"kind":fitz.LINK_URI,
                                       "from":fitz.Rect(80,346,880,450),
                                       "uri":OFFICIAL_SI_URL})
            target.mkdir(parents=True,exist_ok=False)
            output_file=target/"slides_source_draft.pdf"
            output_doc.save(output_file,garbage=4,deflate=True)
        finally:
            output_doc.close()
        if sha(scratch/"source.pdf")!=source or sha(scratch/"Figure 1.1.png")!=mapped:
            raise OfflineSlideDraftError("Original source/figure mutated during rendering")
        with fitz.open(target/"slides_source_draft.pdf") as built:
            if (len(built)!=len(SLIDES)
                or any(not 1.7<p.rect.width/p.rect.height<1.8 for p in built)):
                raise OfflineSlideDraftError("Generated slides have wrong count/geometry")
            text=[p.get_text("text") for p in built]
            if (any(normal(rec["title"]) not in normal(text[i])
                    for i,rec in enumerate(records))
                or normal("IMPORTANT SI UPDATE") not in normal(text[3])):
                raise OfflineSlideDraftError("Source titles / SI correction not visible in rendered PDF")
        manifest={"schema_version":1,
            "status":"OFFLINE_SOURCE_EXCERPT_SLIDE_DRAFT_NOT_FINAL_LECTURE",
            "source_pdf_sha256":source,
            "source_figure_sha256":mapped,
            "source_figure_receipt_sha256":sha(scratch/"offline_figure_mapping_receipt.json"),
            "slideshow_sha256":sha(target/"slides_source_draft.pdf"),
            "slide_count":len(SLIDES),"slides":records,
            "outdated_source_warning_slide":4,
            "external_current_si_citation":OFFICIAL_SI_URL,
            "verbatim_source_excerpt_count":len(records),
            "generated_wavs":False,"narration_generated":False,
            "full_academic_coverage_verified":False,
            "phonetic_accuracy_verified":False,
            "actual_element_audio_sync_verified":False,
            "publication_allowed":False,
            "gemini_or_tts_invoked":False}
        (target/"slide_draft_receipt.json").write_text(
            json.dumps(manifest,indent=2),encoding="utf-8")
        return manifest
    except Exception:
        if target.exists():
            shutil.rmtree(target)
        raise
    finally:
        raw.close()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--new-output",type=Path,required=True)
    a=p.parse_args()
    result=create_draft(a.stage,a.new_output)
    print(json.dumps({"status":result["status"],"slide_count":result["slide_count"],
                      "gemini_or_tts_invoked":False,"publication_allowed":False}))
