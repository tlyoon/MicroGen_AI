"""Independent real Serway 1.1 source PDF to rendered draft fidelity audit.

All output remains unapproved. Excerpt coverage is not academic completeness.
"""
import argparse, json
from pathlib import Path
import pymupdf as fitz
from microgen_offline_source_slide_draft import normal, sha, OFFICIAL_SI_URL

class SerwayDraftAuditError(ValueError): pass

def audit_serway_draft(stage:Path,draft:Path)->dict:
    stage=Path(stage);draft=Path(draft)
    if (stage.is_symlink() or draft.is_symlink() or not stage.is_dir() or not draft.is_dir()
        or stage.resolve()==draft.resolve()):
        raise SerwayDraftAuditError("Distinct trusted source and draft folders required")
    files={"source":stage/"source.pdf", "figure":stage/"Figure 1.1.png",
           "figure_receipt":stage/"offline_figure_mapping_receipt.json",
           "slides":draft/"slides_source_draft.pdf",
           "draft_receipt":draft/"slide_draft_receipt.json"}
    if any(p.is_symlink() or not p.is_file() for p in files.values()):
        raise SerwayDraftAuditError("Missing or linked evidence")
    hashes={name:sha(path) for name,path in files.items()}
    record=json.loads(files["draft_receipt"].read_text(encoding="utf8"))
    if (record.get("source_pdf_sha256")!=hashes["source"]
        or record.get("source_figure_sha256")!=hashes["figure"]
        or record.get("source_figure_receipt_sha256")!=hashes["figure_receipt"]
        or record.get("slideshow_sha256")!=hashes["slides"]
        or record.get("status")!="OFFLINE_SOURCE_EXCERPT_SLIDE_DRAFT_NOT_FINAL_LECTURE"
        or record.get("generated_wavs") is not False
        or record.get("narration_generated") is not False
        or record.get("publication_allowed") is not False
        or record.get("full_academic_coverage_verified") is not False):
        raise SerwayDraftAuditError("Source or pending-acceptance receipt not valid")
    rows=record.get("slides")
    if not isinstance(rows,list) or not rows or record.get("slide_count")!=len(rows):
        raise SerwayDraftAuditError("Invalid slide inventory")
    pages=set(); coverage_chars=0; summaries=[]
    with fitz.open(files["source"]) as source,fitz.open(files["slides"]) as rendered:
        if source.page_count!=4 or rendered.page_count!=len(rows):
            raise SerwayDraftAuditError("Four real source pages and matching draft expected")
        original=[normal(page.get_text()) for page in source]
        for n,row in enumerate(rows,1):
            page=row.get("source_page"); quote=row.get("source_excerpt")
            title=row.get("title")
            if (type(page)!=int or not 1<=page<=4 or not isinstance(quote,str)
                or not quote or not isinstance(title,str) or not title
                or row.get("source_sha256")!=hashes["source"]
                or row.get("excerpt_verbatim_verified") is not True):
                raise SerwayDraftAuditError("Invalid source text mapping")
            if normal(quote) not in original[page-1]:
                raise SerwayDraftAuditError("Quoted text is not on claimed source page")
            slide=rendered[n-1]
            if (normal(title) not in normal(slide.get_text())
                or abs(slide.rect.width/slide.rect.height-16/9)>.015):
                raise SerwayDraftAuditError("Rendered draft slide/title/aspect mismatch")
            if n==5 and not slide.get_images():
                raise SerwayDraftAuditError("Real source Figure 1.1 not embedded")
            if n==4 and (normal("IMPORTANT SI UPDATE") not in normal(slide.get_text())
                or OFFICIAL_SI_URL not in [x.get("uri") for x in slide.get_links()]):
                raise SerwayDraftAuditError("Historical kilogram definition is not corrected")
            pages.add(page);coverage_chars+=len(normal(quote))
            summaries.append({"slide":n,"source_page":page,"title":title,
                "source_excerpt_confirmed":True,"rendered_title_confirmed":True})
        source_chars=sum(map(len,original))
    if pages!={1,2,3,4} or record.get("outdated_source_warning_slide")!=4:
        raise SerwayDraftAuditError("Source page / SI warning coverage incomplete")
    if any(sha(path)!=hashes[key] for key,path in files.items()):
        raise SerwayDraftAuditError("Source or draft changed during independent QA")
    return {"schema_version":1,"status":"DRAFT_SOURCE_VERIFIED_NOT_COMPLETE_LECTURE",
        "source_pdf_sha256":hashes["source"],"draft_pdf_sha256":hashes["slides"],
        "draft_receipt_sha256":hashes["draft_receipt"],
        "source_pages_verified":sorted(pages),"slide_count":len(rows),
        "verbatim_excerpt_characters":coverage_chars,
        "source_text_characters":source_chars,
        "excerpt_char_fraction_upper_bound":round(coverage_chars/source_chars,5),
        "excerpt_fraction_does_not_certify_academic_completeness":True,
        "embedded_figure_present":True,"historical_SI_warning_present":True,
        "slides":summaries,"full_narration_generated":False,
        "figure_academic_accuracy_verified":False,
        "formal_tts_provider_selected":False,"generated_wavs":False,
        "generated_mp4s":False,"end_to_end_lecture_complete":False,
        "publication_allowed":False,"provider_calls":0}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",type=Path,required=True)
    parser.add_argument("--draft",type=Path,required=True)
    parser.add_argument("--new-output",type=Path,required=True)
    opts=parser.parse_args(argv)
    out=opts.new_output;resolved=out.resolve(strict=False)
    if (out.is_symlink() or out.exists() or not resolved.parent.is_dir()
        or opts.stage.resolve(strict=True) in resolved.parents
        or opts.draft.resolve(strict=True) in resolved.parents
        or any(p.casefold()=="my drive" for p in resolved.parts)):
        raise SerwayDraftAuditError("External immutable audit file required")
    result=audit_serway_draft(opts.stage,opts.draft)
    with resolved.open("x",encoding="utf8") as f:json.dump(result,f,indent=2)
    print(json.dumps({"output":str(resolved),"slides":result["slide_count"],
        "end_to_end_lecture_complete":False,"publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
