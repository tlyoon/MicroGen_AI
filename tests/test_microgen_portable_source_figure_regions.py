"""Lossless source PDF crop and neighboring caption provenance, synthetic-only."""
import hashlib
import json
import tempfile
from pathlib import Path

import pymupdf as fitz
from PIL import Image
import pytest

from microgen_portable_slide_render import render_portable_slides
from microgen_portable_source_figure_regions import SourceFigureRegionError
from microgen_pronunciation_closed_loop import sha_file
from test_microgen_portable_16_slide_source_figures import sixteen_topic_source


def geometric_fixture(root):
    stage,narr,plan,contract=sixteen_topic_source(root)
    src=stage/"source.pdf"
    clip=fitz.Rect(340,410,445,462)
    with fitz.open(src) as pdf:
        page=pdf[0]
        page.draw_rect(fitz.Rect(352,420,425,450),
                       fill=(.21,.65,.83),color=(.08,.25,.4))
        page.insert_text((349,482),"Figure 8.2 synthetic geometry",fontsize=12)
        pdf.saveIncr()
    with fitz.open(src) as pdf:
        pix=pdf[0].get_pixmap(matrix=fitz.Matrix(3,3),clip=clip,
                             colorspace=fitz.csRGB,alpha=False)
    m=json.loads(contract.read_text())
    spec=next(s for s in m["figures"] if s["slide"]==6)
    img=stage/spec["filename"]
    Image.frombytes("RGB",(pix.width,pix.height),pix.samples).save(img)
    spec["sha256"]=sha_file(img)
    spec.update({
        "source_figure_page":1,
        "source_figure_bbox":[float(n) for n in clip],
        "source_figure_label":"Figure 8.2",
        "source_pixel_sha256":hashlib.sha256(pix.samples).hexdigest(),
    })
    m["source_pdf_sha256"]=sha_file(src)
    contract.write_text(json.dumps(m))
    return stage,narr,plan,contract


def test_exact_original_pdf_crop_pixels_and_adjacent_caption_accepted():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        files=geometric_fixture(root)
        source_sha=sha_file(files[0]/"source.pdf")
        result=render_portable_slides(*files,root/"candidate")
        assert result["slide_count"]==16
        assert result["source_pdf_figures_with_geometric_provenance"]==1
        assert not result["all_figures_original_pdf_raster_and_nearby_caption_verified"]
        source=result["slides"][5]["source_pdf_figure_evidence"]
        assert source["source_figure_label"]=="Figure 8.2"
        assert source["source_caption_label_nearby_verified"]
        assert source["original_pdf_raster_pixels_identical"]
        assert not source["figure_caption_semantics_fully_proven"]
        assert sha_file(files[0]/"source.pdf")==source_sha
        assert not result["publication_allowed"]


@pytest.mark.parametrize("tamper",[
    "caption","pixel","bbox","source_page","partial","pixel_sha"
])
def test_source_pdf_figure_provenance_fails_closed(tamper):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        stage,narr,plan,contract=geometric_fixture(root)
        m=json.loads(contract.read_text())
        spec=next(s for s in m["figures"] if s["slide"]==6)
        if tamper=="caption":
            spec["source_figure_label"]="Figure 8.9"
        elif tamper=="pixel":
            path=stage/spec["filename"]
            with Image.open(path) as img:
                rgb=img.convert("RGB")
            rgb.putpixel((0,0),(0,0,0) if rgb.getpixel((0,0))!=(0,0,0) else (200,200,200))
            rgb.save(path)
            spec["sha256"]=sha_file(path)
        elif tamper=="bbox":
            spec["source_figure_bbox"][0]+=9
        elif tamper=="source_page":
            spec["source_figure_page"]=2
        elif tamper=="partial":
            del spec["source_figure_label"]
        elif tamper=="pixel_sha":
            spec["source_pixel_sha256"]="0"*64
        contract.write_text(json.dumps(m))
        with pytest.raises(SourceFigureRegionError):
            render_portable_slides(stage,narr,plan,contract,root/"not_written")
        assert not (root/"not_written").exists()


def test_reject_unsafe_image_size_though_sha_is_self_consistent():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        stage,narr,plan,contract=geometric_fixture(root)
        m=json.loads(contract.read_text())
        spec=next(s for s in m["figures"] if s["slide"]==6)
        path=stage/spec["filename"]
        Image.new("RGB",(40,250),(1,2,3)).save(path)
        spec["sha256"]=sha_file(path)
        contract.write_text(json.dumps(m))
        with pytest.raises(SourceFigureRegionError):
            render_portable_slides(stage,narr,plan,contract,root/"fail")
