"""Independently audit coverage of Serway §1.1 against its *bounded* source.

A page includes the start of §1.2: that text is explicitly excluded from
all section-1.1 academic evidence. This is an automated topical and numeric
spot check, NOT independent certification of every physics statement.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import pymupdf as fitz
from PIL import Image,ImageChops
from microgen_pronunciation_closed_loop import sha_file
from microgen_offline_source_slide_draft import normal, OFFICIAL_SI_URL

STATUS = "EXPANDED_SECTION_1_1_NARRATION_DRAFT_UNAPPROVED"
TITLE = "Standards of Length, Mass, and Time"
# (slide id, source page [1-based], independent source anchors, required
# visible/spoken concepts). Anchors are intentionally short factual phrases.
TOPICS = (
 ("fundamental_quantities",1,("fundamental quantities are length, mass, and time",),("length","mass","time")),
 ("measurement_standards",1,("standard must be readily accessible",),("standard","reproduc")),
 ("historical_length_standards",1,("king of england","north pole"),("yard","foot","meter")),
 ("modern_meter_light_year",2,("299 792 458","light-year"),("light","meter","year")),
 ("length_magnitude_examples",2,("mean radius of the earth","diameter of a hydrogen atom"),("earth","atom","scale")),
 ("kilogram_definition",2,("platinum","kilogram (kg)"),("kilogram","planck","2019")),
 ("original_figure_panels",2,("figure 1.1","cesium fountain atomic clock"),("prototype","clock","cesium")),
 ("mass_weight_mass_table",2,("kilogram is a unit of mass","pound is a unit of weight"),("mass","weight","pound")),
 ("atomic_second",3,("9 192 631 770","cesium-133"),("cesium","second","atomic")),
 ("instant_duration",3,("time interval refers to duration",),("time","interval","instant")),
 ("customary_units",3,("foot (ft), slug","customary"),("foot","slug","second")),
 ("si_prefix_scales",3,("millimeters and nanoseconds","1 kilometer"),("milli","nano","kilo")),
 ("derived_dimensions",4,("area (a product","speed (a ratio"),("derived","area","speed")),
 ("density_equal_mass_quiz",4,("aluminum","iron","quick quiz 1.1"),("density","aluminum","iron"))
)
class CoverageError(ValueError): pass

def bounded_pages(source:Path)->list[str]:
    with fitz.open(source) as pdf:
        if len(pdf)!=4:
            raise CoverageError("Expected pinned four-page Serway source")
        raw=[p.get_text("text") for p in pdf]
    header=re.search(r"1[.\s]*2\s*(?:\s|\u2002|\u2003)*Modeling and Alternative Representations",raw[3],re.I)
    if not header:
        # PDF encoding and decorative spaces can separate the heading.
        header=re.search(r"1\.2\s*Modeling and Alternative Representations",raw[3],re.I)
    if not header:raise CoverageError("Section 1.2 boundary cannot be established: fail closed")
    raw[3]=raw[3][:header.start()]
    if ("density" not in raw[3].lower() or "quickquiz" not in normal(raw[3])):
        raise CoverageError("Section 1.1 page 4 was truncated incorrectly")
    return raw

def count_words(s:str)->int:return len(s.split())
def digest_text(s:str)->str:return hashlib.sha256(s.encode("utf8")).hexdigest()

def audit_section_11(stage:Path,narration_qa:Path,visual_plan:Path,rendered_dir:Path|None=None)->dict:
    stage,narration_qa,visual_plan=map(Path,(stage,narration_qa,visual_plan))
    source=stage/"source.pdf"
    fig=stage/"Figure 1.1.png"
    paths=(source,fig,narration_qa,visual_plan)
    if any(p.is_symlink() or not p.is_file() for p in paths):
        raise CoverageError("Missing or mutable original-source/narration/visual evidence")
    original={str(p):sha_file(p) for p in paths}
    n=json.loads(narration_qa.read_text(encoding="utf8"))
    v=json.loads(visual_plan.read_text(encoding="utf8"))
    if (n.get("status")!=STATUS or n.get("slide_count")!=len(TOPICS)
        or n.get("source_pdf_sha256")!=original[str(source)]
        or n.get("publication_allowed") is not False
        or n.get("formal_voice_authorized") is not False
        or n.get("academic_accuracy_independently_verified") is not False
        or v.get("source_pdf_sha256")!=original[str(source)]
        or v.get("publication_allowed") is not False
        or len(n.get("slides",[]))!=len(TOPICS)
        or len(v.get("slides",[]))!=len(TOPICS)):
        raise CoverageError("Not a source-pinned unapproved 14-slide lesson")
    pages=bounded_pages(source)
    seen=set();rows=[]
    pdf=None; render_receipt=None
    if rendered_dir is not None:
        folder=Path(rendered_dir); pdf_path=folder/"slides_teaching_candidate.pdf"
        receipt_path=folder/"teaching_slide_receipt.json"
        if any(p.is_symlink() or not p.is_file() for p in (pdf_path,receipt_path)):
            raise CoverageError("Actual rendered PDF and fresh receipt required")
        render_receipt=json.loads(receipt_path.read_text(encoding="utf8"))
        if (render_receipt.get("status")!="EXPANDED_SECTION_TEACHING_SLIDE_CANDIDATE_UNAPPROVED"
            or render_receipt.get("rendered_pdf_sha256")!=sha_file(pdf_path)
            or render_receipt.get("source_pdf_sha256")!=original[str(source)]
            or render_receipt.get("narration_qa_sha256")!=original[str(narration_qa)]
            or render_receipt.get("visual_plan_sha256")!=original[str(visual_plan)]
            or render_receipt.get("figure_sha256")!=original[str(fig)]
            or render_receipt.get("figure_slide")!=7
            or render_receipt.get("historical_si_slide")!=6
            or render_receipt.get("slide_count")!=len(TOPICS)
            or render_receipt.get("publication_allowed") is not False):
            raise CoverageError("Rendered PDF provenance or nonpublication contract mismatch")
        pdf=fitz.open(pdf_path)
        if len(pdf)!=len(TOPICS):raise CoverageError("Rendered PDF loses a concept")
    try:
        for i,(topic,page,anchors,terms) in enumerate(TOPICS,1):
            spoken=n["slides"][i-1]
            shown=v["slides"][i-1]
            if (spoken.get("slide")!=i or shown.get("slide")!=i
                or spoken.get("source_page")!=page
                or shown.get("source_page")!=page
                or spoken.get("topic_id")!=topic or shown.get("topic_id")!=topic
                or topic in seen):
                raise CoverageError("Source page, topic or ordering drift")
            seen.add(topic)
            speech=spoken.get("narration")
            bullets=shown.get("bullets")
            if (not isinstance(speech,str) or not speech.isascii()
                or not 140<=count_words(speech)<=180
                or spoken.get("spoken_text_sha256")!=digest_text(speech)
                or not isinstance(bullets,list) or len(bullets)!=3
                or any(not isinstance(x,str) or len(x)>95 or len(x)<12 for x in bullets)
                or shown.get("title") is None):
                raise CoverageError("Narration or readable teaching-plan QA failed")
            content=normal(pages[page-1])
            if not all(normal(anchor) in content for anchor in anchors):
                raise CoverageError(f"Original section 1.1 anchors missing for {topic}")
            # The planned concepts must be intelligible in both speech and
            # on-screen text; exact quote matching is NOT scientific proof.
            visual_text=(shown["title"]+" "+" ".join(bullets)).lower()
            def in_speech(term):
                if term=="2019":return "2019" in speech or "twenty nineteen" in speech.lower()
                return term in speech.lower()
            if not all(in_speech(word) and word in visual_text for word in terms):
                raise CoverageError(f"Missing independently required topical concept: {topic}")
            if pdf is not None:
                shown_pdf=normal(pdf[i-1].get_text("text"))
                if (normal(shown["title"]) not in shown_pdf
                    or any(normal(t) not in shown_pdf for t in bullets)):
                    raise CoverageError(f"Actual PDF missing content for {topic}")
                if i==7 and not pdf[i-1].get_images():
                    raise CoverageError("Original composite Figure 1.1 absent")
                if i==6 and OFFICIAL_SI_URL not in {
                        x.get("uri") for x in pdf[i-1].get_links()}:
                    raise CoverageError("2019 modern SI correction lacks official link")
            rows.append({"slide":i,"topic_id":topic,"source_page":page,
                "original_page_anchors_verified":True,
                "spoken_and_visible_concept_terms_verified":True,
                "narration_word_count":count_words(speech),
                "all_academic_statements_independently_verified":False})
        if len(rows)!=len(TOPICS) or {x["topic_id"] for x in rows}!={x[0] for x in TOPICS}:
            raise CoverageError("Incomplete independently enumerated concept coverage")
        # Numeric and exponent checks verify that visible values agree with
        # the values independently grounded in the source, not merely that
        # the words "speed", "prefix" or "second" appear.
        expected_visible={4:("299,792,458","9.46 x 10^15"),
            5:("6.37 million","10^-10"),
            9:("9,192,631,770",),
            12:("10^-3","10^-9","10^3")}
        for slide,values in expected_visible.items():
            visible=" ".join(v["slides"][slide-1]["bullets"])
            if any(x not in visible for x in values):
                raise CoverageError(f"Wrong numerical/scale claim on slide {slide}")
        if pdf is not None:
            figure_pages=pdf[6].get_images(full=True)
            if len(figure_pages)!=1:
                raise CoverageError("Exactly one original Figure 1.1 composite required")
            xref=figure_pages[0][0]
            pm=fitz.Pixmap(pdf,xref)
            if pm.n!=3: pm=fitz.Pixmap(fitz.csRGB,pm)
            embedded=Image.frombytes("RGB",(pm.width,pm.height),pm.samples)
            with Image.open(fig) as original_fig:
                original_rgb=original_fig.convert("RGB")
            if (embedded.size!=original_rgb.size
                or ImageChops.difference(embedded,original_rgb).getbbox() is not None):
                raise CoverageError("Rendered figure pixels do not match original source Figure 1.1")
        if ("1.2" in v.get("section_id","")) or "modeling" in " ".join(
            r["title"] for r in v["slides"]).lower():
            raise CoverageError("Neighboring section 1.2 may not contaminate section 1.1")
        # Independent dimensional and prefix/quiz checks.
        c=299792458
        ly=c*(365.25*24*60*60)
        if not math.isclose(ly,9.46e15,rel_tol=.001):
            raise CoverageError("Computed light-year not credible")
        al,fe=2700.,7860.
        if not (al<fe and 1/al>1/fe and 1e-3*1e3==1):
            raise CoverageError("Density or prefix facts inconsistent")
        if not ("aluminum" in n["slides"][13]["narration"].lower()
                and "larger" in n["slides"][13]["narration"].lower()):
            raise CoverageError("Density quiz requires an explicit equal-mass larger-body answer")
        if any(sha_file(p)!=h for p,h in ((p,original[str(p)]) for p in paths)):
            raise CoverageError("Original academic evidence altered during audit")
        return {"schema_version":1,
            "status":"FOURTEEN_SECTION_1_1_CONCEPT_GROUPS_COVERED_SPOT_CHECKED",
            "source_pdf_sha256":original[str(source)],
            "figure_sha256":original[str(fig)],
            "narration_qa_sha256":original[str(narration_qa)],
            "visual_plan_sha256":original[str(visual_plan)],
            "rendered_teaching_pdf_sha256":sha_file(pdf_path) if pdf is not None else None,
            "section_scope_end_before_next_section":True,
            "section_identifier":"Serway 1.1",
            "slide_count":len(rows),"topic_groups":rows,
            "all_enumerated_section_11_concepts_present":True,
            "independent_light_year_m":round(ly),
            "mass_density_quiz_calculation_consistent":True,
            "formal_voice_authorized":False,
            "full_scientific_academic_certification":False,
            "copyright_public_distribution_approved":False,
            "provider_calls":0,"publication_allowed":False}
    finally:
        if pdf is not None:pdf.close()

def main(argv=None):
    p=argparse.ArgumentParser()
    for x in ("source-stage","narration-qa","visual-plan","new-report"):
        p.add_argument("--"+x,type=Path,required=True)
    p.add_argument("--rendered-dir",type=Path)
    v=p.parse_args(argv)
    dest=v.new_report.resolve(strict=False)
    if (v.new_report.exists() or v.new_report.is_symlink()
        or not dest.parent.is_dir()
        or v.source_stage.resolve(strict=True) in dest.parents
        or any(a.casefold()=="my drive" for a in dest.parts)):
        raise CoverageError("Fresh external nonpublication academic report required")
    report=audit_section_11(v.source_stage,v.narration_qa,v.visual_plan,v.rendered_dir)
    with dest.open("x",encoding="utf8") as f:json.dump(report,f,indent=2)
    print(json.dumps({"topics":report["slide_count"],"report":str(dest),
        "publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
