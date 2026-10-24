"""Inspect original PDF image and large vector geometry as figure proposals.

PDF coordinates and image xrefs are evidence, but not narration semantics,
academic figure correctness, or acceptance of a particular textbook panel.
"""
from pathlib import Path
import pymupdf as fitz
from microgen_source_safe_orchestrator import digest,atomic_json,OrchestratorError

class FigureGeometryError(OrchestratorError):
    pass

def figure_region_inventory(pdf_file,output):
    source=Path(pdf_file).resolve(strict=True)
    dest=Path(output).resolve(strict=False)
    if (source.is_symlink() or not source.is_file() or dest.exists() or dest.is_symlink()
        or dest.is_relative_to(source.parent)):
        raise FigureGeometryError("Original source PDF is protected")
    original_sha=digest(source)
    slides=[];count=0
    with fitz.open(source) as doc:
        if not 1<=doc.page_count<=2000:raise FigureGeometryError("Unexpected PDF page count")
        for i,page in enumerate(doc,1):
            hits=[];seen=set()
            for image in page.get_images(full=True):
                xref=int(image[0])
                for rect in page.get_image_rects(xref):
                    if rect.is_empty or not page.rect.contains(rect):continue
                    key=tuple(round(v,2) for v in rect)
                    if key in seen:continue
                    seen.add(key)
                    if rect.width<20 or rect.height<20:continue
                    hits.append({"kind":"PDF_RASTER_IMAGE","xref":xref,
                        "box":list(map(float,rect)),
                        "source_image_pixels_not_QA_verified":True})
            # Large vector groups can be decorative frames: keep labelled as hypotheses.
            for drawing in page.get_drawings():
                rect=drawing.get("rect")
                if not rect or not page.rect.contains(rect):continue
                if rect.width<.18*page.rect.width or rect.height<.12*page.rect.height:
                    continue
                key=tuple(round(v,2) for v in rect)
                if key in seen:continue
                seen.add(key)
                hits.append({"kind":"LARGE_VECTOR_DRAWING_CANDIDATE",
                    "box":list(map(float,rect)),
                    "possibly_decorative":True})
            if len(hits)>60:raise FigureGeometryError("Ambiguous excessive drawing regions")
            slides.append({"slide":i,"figure_geometry_candidates":hits,
                "caption_to_panel_semantics_verified":False})
            count+=len(hits)
    if digest(source)!=original_sha:raise FigureGeometryError("Original PDF changed")
    atomic_json(dest,{"schema_version":1,
       "status":"SOURCE_PDF_FIGURE_GEOMETRY_ONLY",
       "source_pdf_sha256":original_sha,"slides":slides,
       "figure_candidates":count,
       "image_integrity_academic_QA_verified":False,
       "narration_to_figure_mapping_verified":False,
       "publication_allowed":False})
    return {"slides":len(slides),"figure_candidates":count,
        "publication_allowed":False}
