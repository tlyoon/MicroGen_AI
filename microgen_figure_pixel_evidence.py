"""Rasterize source-bound PDF figures into isolated pixel QA crops.

Checks non-blank pixel texture, not mathematical semantics, caption
truth, axis correctness, or narration-to-figure synchronization.
"""
from pathlib import Path
import pymupdf as fitz
from PIL import Image,ImageStat
from microgen_source_safe_orchestrator import read_json,digest,atomic_json,OrchestratorError

class FigurePixelError(OrchestratorError):
    pass

def render_source_figure_review_crops(pdf_file,geometry_receipt,directory):
    source=Path(pdf_file).resolve(strict=True)
    manifest=read_json(geometry_receipt)
    out=Path(directory).resolve(strict=False)
    if (source.is_symlink() or out.exists() or out.is_symlink() or
        out.is_relative_to(source.parent) or
        manifest.get("status")!="SOURCE_PDF_FIGURE_GEOMETRY_ONLY" or
        manifest.get("source_pdf_sha256")!=digest(source) or
        manifest.get("publication_allowed") is not False):
        raise FigurePixelError("Source PDF/geometry mismatch or unsafe output")
    out.mkdir(parents=True)
    rows=[];blank=0
    with fitz.open(source) as doc:
        if len(manifest["slides"])!=doc.page_count:
            raise FigurePixelError("Source page count differs")
        for i,page in enumerate(doc,1):
            entry=manifest["slides"][i-1]
            if entry["slide"]!=i:raise FigurePixelError("Slide identity mismatch")
            for j,fig in enumerate(entry["figure_geometry_candidates"],1):
                rect=fitz.Rect(fig["box"])
                if rect.is_empty or not page.rect.contains(rect):
                    raise FigurePixelError("Unsafe figure crop bounds")
                if j>60:raise FigurePixelError("Unbounded crop count")
                pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),clip=rect,
                                    colorspace=fitz.csRGB,alpha=False)
                if not 3<=pix.width<=4000 or not 3<=pix.height<=4000:
                    raise FigurePixelError("Corrupt source PDF figure dimensions")
                path=out/f"slide{i:02d}_region{j:02d}.png"
                pix.save(path)
                with Image.open(path) as im:
                    color_std=round(sum(ImageStat.Stat(im.convert("RGB")).stddev)/3,3)
                is_blank=color_std<3.0
                blank+=is_blank
                rows.append({"slide":i,"region":j,"kind":fig["kind"],
                     "box":fig["box"],"png_sha256":digest(path),
                     "png_name":path.name,"mean_rgb_stddev":color_std,
                     "potential_blank_region":is_blank,
                     "figure_academic_correctness_verified":False})
    if digest(source)!=manifest["source_pdf_sha256"]:
        raise FigurePixelError("Original PDF mutated")
    atomic_json(out/"pixel_review_manifest.json",{
       "schema_version":1,"status":"PDF_FIGURE_PIXELS_REQUIRE_ACADEMIC_REVIEW",
       "source_pdf_sha256":manifest["source_pdf_sha256"],
       "figure_region_count":len(rows),"blank_like_regions":blank,
       "regions":rows,"academic_figures_verified":False,
       "caption_spoken_semantics_verified":False,"publication_allowed":False})
    return {"crops":len(rows),"blank_like_regions":blank,
       "source_modified":False,"publication_allowed":False}
