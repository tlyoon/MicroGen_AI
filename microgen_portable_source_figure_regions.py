"""Verify mapped figure PNG pixels against source PDF crop and nearby caption.

A nearby source caption is evidence of proximity, NOT complete semantic matching.
Optional geometry fields preserve compatibility with historical image-only manifests.
"""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
import re

import pymupdf as fitz
from PIL import Image, ImageChops


class SourceFigureRegionError(ValueError):
    pass


FIELDS = ("source_figure_page", "source_figure_bbox",
          "source_figure_label", "source_pixel_sha256")


def checked_source_figure_regions(pdf: fitz.Document, specs: list,
                                  figure_files: dict) -> dict:
    """Prove exact source PDF raster origin plus caption-label proximity.

    One stable source pixel digest uses the RGB bytes, not PNG metadata.  The
    source pixel dimensions are inferred from the provided PNG's own size.
    Explicitly supplied geometry may not be partial or unverifiable.
    """
    verified={}
    if not isinstance(specs,list):
        raise SourceFigureRegionError("Expected original source figure specifications")
    for spec in specs:
        if not isinstance(spec,dict):
            raise SourceFigureRegionError("Malformed source figure row")
        slide=spec.get("slide")
        present=[key in spec for key in FIELDS]
        if not any(present):
            continue
        if not all(present) or slide not in figure_files:
            raise SourceFigureRegionError("Incomplete figure source PDF provenance")
        pageno=spec["source_figure_page"]
        coords=spec["source_figure_bbox"]
        label=spec["source_figure_label"]
        digest=spec["source_pixel_sha256"]
        if (type(pageno) is not int or not 1<=pageno<=len(pdf)
            or not isinstance(coords,list) or len(coords)!=4
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in coords)
            or not isinstance(label,str)
            or not re.fullmatch(r"Figure \d+(?:\.\d+)+",label)
            or not isinstance(digest,str)
            or not re.fullmatch("[a-f0-9]{64}",digest)):
            raise SourceFigureRegionError("Invalid figure page, bbox, label or pixel identity")
        rect=fitz.Rect(coords)
        page=pdf[pageno-1]
        if (not rect.is_valid or rect.is_empty or rect.width<10 or rect.height<10
            or not page.rect.contains(rect)):
            raise SourceFigureRegionError("Figure region not contained in original PDF page")
        source_path,sha,_=figure_files[slide]
        if Path(source_path).suffix.lower()!=".png":
            raise SourceFigureRegionError("Source-pixel evidence requires lossless PNG")
        with Image.open(source_path) as original:
            rgb=original.convert("RGB")
        w,h=rgb.size
        if (w<40 or h<40 or w>4000 or h>4000
            or abs(w/rect.width-h/rect.height)>0.055*max(w/rect.width,h/rect.height)):
            raise SourceFigureRegionError("Figure crop size cannot be reconstructed from bbox")
        # Actual source pixels, independently rasterized at the known image scale.
        pix=page.get_pixmap(matrix=fitz.Matrix(w/rect.width,h/rect.height),
                            clip=rect,colorspace=fitz.csRGB,alpha=False)
        if (pix.width,pix.height)!=(w,h):
            raise SourceFigureRegionError("Source crop dimensions differ from submitted pixels")
        computed=hashlib.sha256(pix.samples).hexdigest()
        if (computed!=digest or
            ImageChops.difference(rgb,Image.frombytes("RGB",(w,h),pix.samples)).getbbox()):
            raise SourceFigureRegionError("Submitted figure differs from original PDF pixels")
        captions=[area for area in page.search_for(label)
                  if rect.x0-32<=area.x0<=rect.x1+32
                  and rect.y1-20<=area.y0<=rect.y1+110]
        if not captions:
            raise SourceFigureRegionError("No nearby exact figure-caption label in source")
        closest=min(captions,key=lambda x:abs(x.y0-rect.y1))
        verified[slide]={
            "source_page":pageno,
            "source_bbox":[round(float(x),3) for x in rect],
            "source_pixel_sha256":computed,
            "source_figure_label":label,
            "source_caption_label_nearby_verified":True,
            "source_caption_label_bbox":[round(float(x),3) for x in closest],
            "original_pdf_raster_pixels_identical":True,
            "figure_caption_semantics_fully_proven":False,
            "figure_rights_to_distribute_proven":False,
        }
    return verified
