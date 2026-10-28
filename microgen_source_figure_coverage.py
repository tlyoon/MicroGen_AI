"""Source-bound textbook figure coverage and auditable visual review packet.

Checks actual slide reference→mapped Figure→original source page caption/text,
immutable source/crop hashes, unassigned Docling candidates. Never mistakes
filename matching for figure *semantic* correctness. No publication approval.
"""
from __future__ import annotations
import csv
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

import pymupdf as fitz
from microgen_figure_composition import validate_figure_receipt
from microgen_source_safe_orchestrator import atomic_json,digest


class FigureCoverageError(ValueError):
    pass


def _id(name):
    match=re.search(r"(?i)\bfigure\s*(\d+)\.(\d+)([a-z]?)\b",name)
    return (f"{int(match.group(1))}.{int(match.group(2))}"+match.group(3).lower()
            if match else None)


def _referenced_images(tex):
    # Input is generated Beamer TeX only. Do not execute TeX from the review packet.
    return [Path(m.group(1)).name for m in
            re.finditer(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}",tex)]


def build_current_figure_coverage(stage,output):
    s=Path(stage).resolve(strict=True)
    out=Path(output).absolute()
    if out.exists() or out.is_symlink() or out==s or out.is_relative_to(s) or s.is_relative_to(out):
        raise FigureCoverageError("Unused independent review folder required")
    source=s/"source.pdf";slides=s/"slides.pdf";tex=s/"slides.tex"
    for p in (source,slides,tex,s/"figure_composition_receipt.json",
              s/"figure_extraction_receipt.json"):
        if p.is_symlink() or not p.is_file():
            raise FigureCoverageError("All real source/slide/figure inputs required")
    receipt=validate_figure_receipt(s)
    extr=json.loads((s/"figure_extraction_receipt.json").read_text(encoding="utf8"))
    if extr.get("source_sha256")!=digest(source):
        raise FigureCoverageError("PDF source not equal Docling figure inventory")
    with fitz.open(source) as book:
        if extr.get("page_count")!=len(book):
            raise FigureCoverageError("Source page inventory incomplete")
        pages=[p.get_text("text") for p in book]
    source_labels=[]
    for i,text in enumerate(pages,1):
        # Corpus-based, NOT proof that every reference is an illustrated caption.
        for label in sorted(set(re.findall(r"(?i)\bFigure\s+\d+\.\d+[a-z]?\b",text))):
            source_labels.append({"page":i,"label":_id(label)})
    mapped={}
    for record in receipt["figures"]:
        filename=record["destination"]; figure=_id(filename)
        try:page=int(record["source_page"].split("_")[-1])
        except Exception as exc:raise FigureCoverageError("Invalid source page") from exc
        p=s/filename
        if (not figure or not 1<=page<=len(pages) or
            p.is_symlink() or not p.is_file() or
            digest(p)!=record["output_sha256"] or
            figure in mapped):
            raise FigureCoverageError("Mapped figure missing, duplicate or altered")
        caption=bool(re.search(r"(?i)\bfigure\s+"+re.escape(figure)+r"\b",pages[page-1]))
        if not caption:
            raise FigureCoverageError("Mapped figure has NO label on claimed original source page")
        mapped[figure]={"figure":figure,"source_page":page,"filename":filename,
                        "sha256":digest(p),"source_text_label_exists":True,
                        "figural_semantics_verified":False,
                        "review_required":record.get("review_required",True)}
    references=_referenced_images(tex.read_text(encoding="utf8"))
    if not references:
        raise FigureCoverageError("No generated slide graphics references")
    referenced=[]
    for filename in references:
        figure=_id(filename)
        if not figure or figure not in mapped:
            raise FigureCoverageError("Slide references missing or unmapped source figure: "+filename)
        if Path(filename).name.casefold()!=mapped[figure]["filename"].casefold():
            raise FigureCoverageError("Generated TeX image does not match immutable mapping")
        referenced.append(figure)
    missed=sorted({x["label"] for x in source_labels}-set(mapped))
    seen_crops={(x["source_page"],f["filename"]) for x in receipt["figures"]
                for f in x.get("source_crops",[])
                if f["filename"].startswith("fig_")}
    extraction={(f"page_{row['page']}",f["name"]) for row in extr["pages"]
                for f in row.get("figures",[])}
    # A manual source-page raster recovery is not an original Docling crop.
    if not seen_crops.issubset(extraction):
        raise FigureCoverageError("Mapped Docling provenance unavailable in extraction")
    unlabeled=sorted(extraction-seen_crops)
    before={"source_pdf_sha256":digest(source),
            "slides_pdf_sha256":digest(slides),"slides_tex_sha256":digest(tex),
            "composition_receipt_sha256":digest(s/"figure_composition_receipt.json"),
            "extraction_receipt_sha256":digest(s/"figure_extraction_receipt.json")}
    out.mkdir(parents=True,exist_ok=False)
    try:
        pic=out/"figures";pic.mkdir()
        screenshot=out/"source_pages";screenshot.mkdir()
        with fitz.open(source) as book:
            for i,page in enumerate(book,1):
                # Render at the original source pixel scale for honest visual comparison.
                pix=page.get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False)
                pix.save(screenshot/f"source_page_{i:02d}.png")
        for record in mapped.values():
            shutil.copy2(s/record["filename"],pic/record["filename"])
            if digest(pic/record["filename"])!=record["sha256"]:
                raise FigureCoverageError("Figure copy not identical")
        with (out/"figure_source_mapping.csv").open("w",newline="",encoding="utf-8-sig") as f:
            writer=csv.DictWriter(f,fieldnames=list(next(iter(mapped.values()))))
            writer.writeheader();writer.writerows(mapped.values())
        cards=[]
        for row in mapped.values():
            src=f"source_pages/source_page_{row['source_page']:02d}.png"
            fig="figures/"+row["filename"]
            cards.append("<section><h2>Figure "+html.escape(row["figure"])+
               " — source page "+str(row["source_page"])+
               " (NOT APPROVED)</h2><img loading='lazy' width='360' src='"+
               html.escape(fig,quote=True)+"'><img loading='lazy' width='520' src='"+
               html.escape(src,quote=True)+"'></section>")
        (out/"index.html").write_text(
            "<!doctype html><meta charset='utf8'><title>Original §2.5 source figure audit</title>"
            "<h1>Mapped figures vs actual textbook pages — NOT semantic approval</h1>"
            "<p>Figure labels present in source text; pixels and spoken correspondence require review.</p>"+
            "".join(cards)+"<h2>Unmapped Docling crops</h2><pre>"+
            html.escape(json.dumps(unlabeled,indent=2))+"</pre>",encoding="utf8")
        if (before!={"source_pdf_sha256":digest(source),
                     "slides_pdf_sha256":digest(slides),"slides_tex_sha256":digest(tex),
                     "composition_receipt_sha256":digest(s/"figure_composition_receipt.json"),
                     "extraction_receipt_sha256":digest(s/"figure_extraction_receipt.json")}):
            raise FigureCoverageError("Source modified during visual audit")
        evidence={"status":"FIGURE_SOURCE_LABEL_AND_IMAGE_PROOF_REVIEW_REQUIRED",
                  **before,"mapped_figures":list(mapped.values()),
                  "mapped_count":len(mapped),"slide_figure_refs":references,
                  "figure_refs_count":len(references),
                  "source_labels_unmapped":missed,
                  "docling_crops_unassigned":unlabeled,
                  "figure_semantics_verified":False,
                  "figure_audio_alignment_verified":False,
                  "academic_approval":False,"publication_allowed":False,
                  "html_sha256":digest(out/"index.html"),
                  "csv_sha256":digest(out/"figure_source_mapping.csv")}
        atomic_json(out/"figure_coverage_receipt.json",evidence)
        return {"mapped":len(mapped),"references":len(references),
                "unassigned_crops":len(unlabeled),
                "source_labels_unmapped":len(missed),
                "publication_allowed":False}
    except Exception:
        shutil.rmtree(out)
        raise


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--stage",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    print(build_current_figure_coverage(a.stage,a.out))
