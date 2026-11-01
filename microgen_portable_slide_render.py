"""Section-agnostic source-audited lecture PDF renderer, not publication QA."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import pymupdf as fitz
from PIL import Image, ImageChops
from microgen_pronunciation_closed_loop import sha_file
from microgen_portable_section_contract import audit_portable_contract, clean
from microgen_portable_source_equations import checked_equations, SourceEquationError
from microgen_portable_source_figure_regions import checked_source_figure_regions
from microgen_portable_source_math_claims import verified_source_math_claims

class PortableSlideError(ValueError):pass

def checked_figures(stage:Path,manifest:dict,count:int)->dict:
    specs=manifest.get("figures",[])
    if not isinstance(specs,list) or len(specs)>count:
        raise PortableSlideError("Malformed source figure inventory")
    seen=set();found={}
    for row in specs:
        if not isinstance(row,dict):
            raise PortableSlideError("Malformed source figure evidence")
        idx=row.get("slide");name=row.get("filename");sha=row.get("sha256")
        cap=row.get("caption","Source figure")
        if (type(idx) is not int or not 1<=idx<=count or idx in seen
            or not isinstance(name,str) or len(name)>90
            or name in (".","..") or Path(name).name!=name
            or not name.lower().endswith((".png",".jpg",".jpeg"))
            or not isinstance(sha,str) or not re.fullmatch("[a-f0-9]{64}",sha)
            or not isinstance(cap,str) or not 10<=len(cap)<=90
            or not cap.isascii()):
            raise PortableSlideError("Source figure mapping unsafe or ambiguous")
        path=stage/name
        if path.is_symlink() or not path.is_file() or sha_file(path)!=sha:
            raise PortableSlideError("Referenced original figure missing or modified")
        with Image.open(path) as img:
            img.verify()
        seen.add(idx);found[idx]=(path,sha,cap)
    return found

def render_portable_slides(stage:Path,narration:Path,plan:Path,contract:Path,
                           output:Path)->dict:
    stage,narration,plan,contract,output=map(Path,(stage,narration,plan,contract,output))
    source=stage/"source.pdf"
    for p in (source,narration,plan,contract):
        if p.is_symlink() or not p.is_file():
            raise PortableSlideError("All original source/media input must be real files")
    academic=audit_portable_contract(source,narration,plan,contract)
    cfg=json.loads(contract.read_text(encoding="utf8"))
    n=json.loads(narration.read_text(encoding="utf8"))
    v=json.loads(plan.read_text(encoding="utf8"))
    if n.get("formal_voice_authorized") is not False:
        raise PortableSlideError("Explicit unapproved narration/voice state is required")
    count=academic["topic_count"]
    figures=checked_figures(stage,cfg,count)
    with fitz.open(source) as original_pdf:
        equations=checked_equations(original_pdf,cfg,n,set(figures))
        source_figure_evidence=checked_source_figure_regions(
            original_pdf,cfg.get("figures",[]),figures)
        source_math_evidence=verified_source_math_claims(
            original_pdf,cfg,equations,source_figure_evidence)
    dest=output.resolve(strict=False)
    if (output.exists() or output.is_symlink() or not dest.parent.is_dir()
        or stage.resolve(strict=True) in dest.parents
        or any(x.casefold()=="my drive" for x in dest.parts)):
        raise PortableSlideError("Fresh private candidate directory required")
    protected=[source,narration,plan,contract]+[p for p,_,_ in figures.values()]
    originals={str(p):sha_file(p) for p in protected}
    pdf=fitz.open();temporary=None
    try:
        rows=[]
        for idx,(visual,spoken) in enumerate(zip(v["slides"],n["slides"]),1):
            title=visual.get("title")
            bullets=visual.get("bullets")
            if (not isinstance(title,str) or not 4<=len(title)<=90
                or not title.isascii() or not isinstance(bullets,list)
                or any(not b.isascii() for b in bullets)
                or any("\\" in b or "$" in b for b in [title]+bullets)
                or (idx in equations and len(bullets)>3)
                or (idx in figures and (len(bullets)>3 or
                   any(len(b)>88 for b in bullets)))):
                raise PortableSlideError("Visible text needs reliable PDF fonts and nonoverlapping figure layout")
            p=pdf.new_page(width=960,height=540)
            p.draw_rect(fitz.Rect(0,0,960,540),fill=(.98,.985,.994),color=None)
            p.draw_rect(fitz.Rect(0,0,960,18),fill=(.09,.29,.48),color=None)
            if p.insert_textbox(fitz.Rect(52,42,900,100),title,
                                fontsize=27,color=(.08,.20,.32))<0:
                raise PortableSlideError("Title text overflow")
            image_info=None
            for j,bullet in enumerate(bullets):
                y=116+j*(80 if idx in figures else 68)
                x_end=495 if idx in figures else 910
                p.draw_circle(fitz.Point(68,y+10),6,fill=(.12,.42,.60),color=None)
                if p.insert_textbox(fitz.Rect(90,y-4,x_end,y+65),bullet,
                                    fontsize=17,color=(.12,.23,.34))<0:
                    raise PortableSlideError("Visible bullet cannot fit")
            if idx in figures:
                fig,sha,caption=figures[idx]
                p.insert_image(fitz.Rect(520,138,908,386),filename=str(fig),
                               keep_proportion=True)
                if p.insert_textbox(fitz.Rect(515,393,913,450),caption,
                                    fontsize=12,color=(.24,.28,.31))<0:
                    raise PortableSlideError("Figure caption overflow")
                image_info={"filename":fig.name,"sha256":sha,"caption":caption}
            if idx in equations:
                eq=equations[idx]
                with fitz.open(source) as original_pdf:
                    p.show_pdf_page(fitz.Rect(90,333,910,458),original_pdf,
                                    eq["source_page"]-1,
                                    clip=fitz.Rect(eq["source_bbox"]),
                                    keep_proportion=True)
            p.draw_line(fitz.Point(50,482),fitz.Point(910,482),
                        color=(.68,.75,.82),width=1)
            p.insert_text((50,510),"SOURCE-BOUND PRIVATE CANDIDATE - NOT FOR PUBLICATION",
                          fontsize=10,color=(.48,.26,.24))
            p.insert_text((760,510),f"{cfg['section_id']} | {idx}/{count}",
                          fontsize=11,color=(.2,.34,.44))
            rows.append({"slide":idx,"topic_id":spoken["topic_id"],
                "source_page":spoken["source_page"],"title":title,
                "bullets":bullets,"figure":image_info,
                "source_vector_equation":equations.get(idx),
                "source_pdf_figure_evidence":source_figure_evidence.get(idx),
                "source_typed_math_evidence":source_math_evidence.get(idx),
                "narration_sha256":spoken["spoken_text_sha256"],
                "independent_complete_academic_certification":False})
        temporary=Path(tempfile.mkdtemp(prefix=".microgen-portable-slides-",dir=dest.parent))
        result=temporary/"slides_teaching_candidate.pdf"
        pdf.save(result,garbage=4,deflate=True)
        with fitz.open(result) as actual:
            if len(actual)!=count:raise PortableSlideError("PDF slide count drift")
            for idx,row in enumerate(rows,1):
                page=actual[idx-1]
                txt=clean(page.get_text("text"))
                if clean(row["title"]) not in txt or any(
                    clean(b) not in txt for b in row["bullets"]):
                    raise PortableSlideError("PDF did not preserve source-checked visible concepts")
                if row["source_vector_equation"] and not page.get_xobjects():
                    raise PortableSlideError("Source equation PDF vector was not embedded")
                if row["figure"]:
                    imgs=page.get_images(full=True)
                    if len(imgs)!=1:
                        raise PortableSlideError("One original mapped figure must be embedded")
                    pm=fitz.Pixmap(actual,imgs[0][0])
                    if pm.n!=3:pm=fitz.Pixmap(fitz.csRGB,pm)
                    embedded=Image.frombytes("RGB",(pm.width,pm.height),pm.samples)
                    with Image.open(figures[idx][0]) as source_img:
                        original=source_img.convert("RGB")
                    if (embedded.size!=original.size or
                        ImageChops.difference(embedded,original).getbbox() is not None):
                        raise PortableSlideError("Figure embedded pixels are not source-identical")
        if any(sha_file(Path(p))!=sha for p,sha in originals.items()):
            raise PortableSlideError("Original source or figure changed during rendering")
        record={"schema_version":1,
            "status":"PORTABLE_SECTION_TEACHING_SLIDE_CANDIDATE_UNAPPROVED",
            "section_id":cfg["section_id"],"source_pdf_sha256":originals[str(source)],
            "narration_qa_sha256":originals[str(narration)],
            "visual_plan_sha256":originals[str(plan)],
            "portable_contract_sha256":originals[str(contract)],
            "rendered_pdf_sha256":sha_file(result),
            "slide_count":count,"slides":rows,
            "figures_exact_original_pixels_verified":True,
            "source_pdf_figures_with_geometric_provenance":len(source_figure_evidence),
            "all_figures_original_pdf_raster_and_nearby_caption_verified":(
                len(source_figure_evidence)==len(figures) and bool(figures)),
            "equation_source_geometry_sha_verified":True,
            "independently_checked_typed_math_claims_count":len(source_math_evidence),
            "mathematical_equation_semantics_proven":False,
            "complete_academic_correctness_proven":False,
            "formal_voice_authorized":False,"publication_allowed":False}
        (temporary/"teaching_slide_receipt.json").write_text(
            json.dumps(record,indent=2),encoding="utf8")
        if dest.exists():raise PortableSlideError("Destination appeared during render")
        os.rename(temporary,dest)
        return record
    finally:
        pdf.close()
        if temporary is not None and temporary.exists():shutil.rmtree(temporary)
