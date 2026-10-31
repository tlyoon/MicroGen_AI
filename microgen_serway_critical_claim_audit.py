"""Independently check critical source-bound physics claims in Serway §1.1.

This is deterministic, limited-scope academic fact checking. A passing critical
claim checklist is not a blanket scientific or publication certification.
"""
from __future__ import annotations
import argparse
import json
import math
import re
from pathlib import Path
import pymupdf as fitz
from microgen_offline_source_slide_draft import normal, OFFICIAL_SI_URL
from microgen_pronunciation_closed_loop import sha_file

class ClaimAuditError(ValueError):pass

# Explicit facts and required *independent* evidence on original PDF pages.
PAGE_ANCHORS=(
    (0, ("three fundamental quantities are length, mass, and time",)),
    (0, ("standard must be readily accessible",)),
    (1, ("speed of light in vacuum is precisely 299 792 458", "light-year")),
    (1, ("platinum", "kilogram")),
    (1, ("figure 1.1", "cesium")),
    (2, ("9 192 631 770", "cesium-133")),
    (2, ("time interval", "reference time")),
    (3, ("density", "aluminum", "iron")),
)
NARRATION_TERMS=(
    ("length","mass","time","speed"),
    ("measurement","reproduced","si","meter"),
    ("light","meter","second","light-year"),
    ("mass","weight","historical","planck","since may twentieth, twenty nineteen"),
    ("panel","prototype","atomic","twenty nineteen"),
    ("cesium","second","period","nine billion"),
    ("time","interval","millisecond","nanosecond"),
    ("density","mass","volume","aluminum","iron"),
)
VISUAL_TERMS=(
    ("length","mass","time"),
    ("measurement","si","meter"),
    ("light","meter","light-year"),
    ("mass","kilogram","2019","planck"),
    ("panel (a)","panel (b)","clock"),
    ("cesium","second","9,192,631,770"),
    ("interval","milli","nano"),
    ("density","mass","aluminum","iron"),
)

def audit_serway_critical_claims(stage:Path,narration_qa:Path,slide_dir:Path)->dict:
    stage=Path(stage);narration_qa=Path(narration_qa);slide_dir=Path(slide_dir)
    source=stage/"source.pdf"
    visual=slide_dir/"slides_teaching_candidate.pdf"
    manifest=slide_dir/"teaching_slide_receipt.json"
    inputs=(source,narration_qa,visual,manifest)
    if any(not p.is_file() or p.is_symlink() for p in inputs):
        raise ClaimAuditError("Missing original PDF, spoken draft or rendered teaching slides")
    hashes={str(path):sha_file(path) for path in inputs}
    n=json.loads(narration_qa.read_text(encoding="utf8"))
    m=json.loads(manifest.read_text(encoding="utf8"))
    if (n.get("source_pdf_sha256")!=hashes[str(source)]
        or m.get("source_pdf_sha256")!=hashes[str(source)]
        or m.get("narration_qa_sha256")!=hashes[str(narration_qa)]
        or m.get("rendered_pdf_sha256")!=hashes[str(visual)]
        or n.get("publication_allowed") is not False
        or m.get("publication_allowed") is not False
        or m.get("formal_voice_authorized") is not False
        or n.get("formal_voice_authorized") is not False
        or n.get("status")!="EIGHT_SLIDE_NARRATION_DRAFT_COMPLETE_UNAPPROVED"
        or m.get("status")!="FULLER_TEACHING_SLIDE_CANDIDATE_UNAPPROVED"
        or n.get("slide_count")!=8 or m.get("slide_count")!=8
        or len(n.get("slides",[]))!=8 or len(m.get("slides",[]))!=8):
        raise ClaimAuditError("Source hashes and nonpublished candidate contracts must agree")
    details=[]
    with fitz.open(source) as original,fitz.open(visual) as rendered:
        if len(original)!=4 or len(rendered)!=8:
            raise ClaimAuditError("The original four-page source and eight-slide lecture are required")
        source_pages=[normal(p.get_text("text")) for p in original]
        for i,((source_i,terms),required_audio,required_visual) in enumerate(
            zip(PAGE_ANCHORS,NARRATION_TERMS,VISUAL_TERMS),1):
            slide=m["slides"][i-1];spoken=n["slides"][i-1]
            if (slide.get("slide")!=i or spoken.get("slide")!=i
                or slide.get("narration_sha256")!=spoken.get("spoken_text_sha256")
                or spoken.get("source_page")!=source_i+1):
                raise ClaimAuditError(f"Slide {i} is not tied to original source page")
            source_found=[term for term in terms if normal(term) in source_pages[source_i]]
            if len(source_found)!=len(terms):
                raise ClaimAuditError(f"Original source fact anchor missing at slide {i}")
            speech=spoken.get("narration","").lower()
            slide_text=rendered[i-1].get_text().lower()
            if not all(term in speech for term in required_audio):
                raise ClaimAuditError(f"Source-supported spoken claims missing at slide {i}")
            if not all(term in slide_text for term in required_visual):
                raise ClaimAuditError(f"Source-supported slide claims missing at slide {i}")
            if i in (4,5) and re.search(
                r"kilogram (?:is|remains|still is) defined as (?:the )?mass of (?:a|the) (?:platinum|cylinder)",
                speech):
                raise ClaimAuditError("Historical kilogram artifact must not be the modern SI definition")
            if i==4 and OFFICIAL_SI_URL not in {l.get("uri") for l in rendered[3].get_links()}:
                raise ClaimAuditError("Historical SI caution requires linked official resolution")
            if i==5 and not rendered[4].get_images():
                raise ClaimAuditError("Source composite figure is absent")
            details.append({"slide":i,"original_page":source_i+1,
                "pdf_anchors":list(terms),"spoken_claim_terms":list(required_audio),
                "visible_claim_terms":list(required_visual),
                "critical_fact_spot_checks_passed":True,
                "all_academic_claims_verified":False})
    # Independent dimensional/numeric cross-checks, not OCR of equations.
    c=299792458
    year_seconds=365.25*24*3600
    ly=c*year_seconds
    if not math.isclose(ly,9.46e15,rel_tol=.001):raise ClaimAuditError("Light-year calculation mismatch")
    rho_al,rho_fe=2700,7860
    if not (rho_al<rho_fe and 1/rho_al>1/rho_fe):
        raise ClaimAuditError("Equal-mass density-volume demonstration inconsistent")
    if any(sha_file(file)!=digest for file,digest in (
        (p,hashes[str(p)]) for p in inputs)):
        raise ClaimAuditError("Source evidence changed during independent audit")
    return {"schema_version":1,"status":"EIGHT_CRITICAL_SOURCE_CLAIM_GROUPS_SPOT_CHECKED",
        "source_pdf_sha256":hashes[str(source)],
        "narration_qa_sha256":hashes[str(narration_qa)],
        "teaching_slides_sha256":hashes[str(visual)],
        "slide_receipt_sha256":hashes[str(manifest)],
        "source_pages":4,"slides_checked":8,"critical_claim_groups":details,
        "exact_speed_of_light_m_per_s":c,
        "derived_light_year_m":round(ly),
        "density_equal_mass_example_consistent":True,
        "current_SI_external_bipm_resolution_url":OFFICIAL_SI_URL,
        "mathematical_spot_checks_passed":True,
        "all_scientific_claims_verified":False,
        "figure_panel_semantics_independently_verified":False,
        "formal_voice_authorized":False,"provider_calls":0,
        "publication_allowed":False}

def main(argv=None):
    a=argparse.ArgumentParser()
    a.add_argument("--source-stage",type=Path,required=True)
    a.add_argument("--narration-qa",type=Path,required=True)
    a.add_argument("--teaching-slides",type=Path,required=True)
    a.add_argument("--new-report",type=Path,required=True)
    v=a.parse_args(argv)
    target=v.new_report.resolve(strict=False)
    if (v.new_report.exists() or v.new_report.is_symlink()
        or not target.parent.is_dir()
        or any(x.casefold()=="my drive" for x in target.parts)
        or v.source_stage.resolve(strict=True) in target.parents
        or v.teaching_slides.resolve(strict=True) in target.parents):
        raise ClaimAuditError("Fresh external report required")
    result=audit_serway_critical_claims(v.source_stage,v.narration_qa,v.teaching_slides)
    with target.open("x",encoding="utf8") as stream:json.dump(result,stream,indent=2)
    print(json.dumps({"report":str(target),"groups":len(result["critical_claim_groups"]),
                      "publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
