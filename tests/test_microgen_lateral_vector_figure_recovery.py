"""Offline and real-source tests for caption-adjacent vector graph recovery."""
from __future__ import annotations
import hashlib,json,os,shutil,tempfile
from pathlib import Path

import pymupdf
import pytest
from microgen_figure_composition import FigureCollector
from microgen_lateral_vector_figure_recovery import (
    LateralFigureError, _lateral_geometry, recover_lateral_figure,
    verify_lateral_figure_receipt,
)


def create_six_panel_source(path: Path, *, bad_labels=False):
    pdf=pymupdf.open()
    page=pdf.new_page(width=612,height=783)
    # Unique textbook-style, bold blue caption to the RIGHT of vector charts.
    page.insert_textbox(pymupdf.Rect(452,467,580,595),
        "Figure 2.12\nSix source vector graphs\nwith caption text\nand labeled axes"
        "\nThe panels each have a"
        "\nseparate axis label"
        "\nand a numbered key",
        fontname="hebo",fontsize=11,lineheight=1.2,
        color=(.07,.4,.7))
    for n in range(6):
        left=70+64*n
        page.draw_rect(pymupdf.Rect(left+2,497,left+36,530),
                       color=(.1,.1,.1),width=1)
        page.draw_line(pymupdf.Point(left+2,529),
                       pymupdf.Point(left+36,498),color=(.7,.22,.1),width=2)
        page.insert_text((left,495),"v" if n<3 else "a",
                         fontname="heit",fontsize=10)
        page.insert_text((left+40,534),"t",fontname="heit",fontsize=10)
        page.draw_rect(pymupdf.Rect(left+13,538,left+23,550),
                       color=(.65,.65,.6),fill=(.65,.65,.6))
        label=("q" if bad_labels and n==2 else chr(ord("a")+n))
        page.insert_text((left+14,548),label,fontname="helv",
                         fontsize=9,color=(1,1,1))
    pdf.save(path)
    pdf.close()


def test_synthetic_lateral_graph_recovery_and_stable_sha(tmp_path):
    stage=tmp_path/"stage"
    stage.mkdir()
    create_six_panel_source(stage/"source.pdf")
    page=stage/"pages"/"page_1"
    page.mkdir(parents=True)
    with pymupdf.open(stage/"source.pdf") as pdf:
        geometry=_lateral_geometry(pdf[0],"2.12")
    assert geometry["panel_labels"]=="abcdef"
    assert geometry["vector_panels"]==6
    assert geometry["axis_label_spans"]>=12
    collector=FigureCollector(stage/"pages")
    names=recover_lateral_figure(stage,page,"- **Figure 2.12**: synthetic captions",
                                 collector,only_labels={"2.12"})
    assert names==["Figure 2.12.png"]
    collector.finalize()
    proof=verify_lateral_figure_receipt(stage)
    assert proof["figures"]==names
    # Recheck after normal mapper moves composed files to stage root.
    shutil.move(str(stage/"pages"/names[0]),str(stage/names[0]))
    shutil.copy2(stage/"pages"/"figure_composition_receipt.json",
                 stage/"figure_composition_receipt.json")
    assert verify_lateral_figure_receipt(stage)==proof
    # The page crops are disposable; geometry is independently reconstructible.
    shutil.rmtree(stage/"pages")
    assert verify_lateral_figure_receipt(stage)==proof


def test_missing_one_panel_label_fails_without_partial_png(tmp_path):
    stage=tmp_path/"stage"
    stage.mkdir()
    create_six_panel_source(stage/"source.pdf",bad_labels=True)
    page=stage/"pages"/"page_1"
    page.mkdir(parents=True)
    with pytest.raises(LateralFigureError):
        recover_lateral_figure(stage,page,"Figure 2.12: synthetic",
                               FigureCollector(stage/"pages"),only_labels={"2.12"})
    assert not list(stage.rglob("source_lateral_*.png"))
    assert not (stage/".microgen_lateral_vector_figure_recovery.json").exists()


def test_false_or_unrelated_caption_never_creates_graph(tmp_path):
    stage=tmp_path/"stage"
    stage.mkdir()
    create_six_panel_source(stage/"source.pdf")
    page=stage/"pages"/"page_1"
    page.mkdir(parents=True)
    for text,needed in (("Figure 2.13: wrong number",{"2.13"}),
                        ("Unlabeled motion picture",{"2.12"})):
        with pytest.raises(LateralFigureError):
            recover_lateral_figure(stage,page,text,FigureCollector(stage/"pages"),
                                   only_labels=needed)
    assert not list(stage.rglob("source_lateral_*.png"))


def test_source_or_crop_tampering_fails_attested_reverification(tmp_path):
    stage=tmp_path/"stage"
    stage.mkdir()
    create_six_panel_source(stage/"source.pdf")
    page=stage/"pages"/"page_1"
    page.mkdir(parents=True)
    collector=FigureCollector(stage/"pages")
    recover_lateral_figure(stage,page,"Figure 2.12 source graphs",collector,
                           only_labels={"2.12"})
    collector.finalize()
    proof=verify_lateral_figure_receipt(stage)
    receipt=stage/".microgen_lateral_vector_figure_recovery.json"
    contents=receipt.read_bytes()
    modified=json.loads(contents)
    modified["figures"][0]["panel_labels"]="abcde"
    receipt.write_text(json.dumps(modified),encoding="utf8")
    with pytest.raises(LateralFigureError,match="geometry changed"):
        verify_lateral_figure_receipt(stage)
    receipt.write_bytes(contents)
    assert verify_lateral_figure_receipt(stage)==proof
    crop=page/"source_lateral_2_12.png"
    crop.write_bytes(crop.read_bytes()+b"tamper")
    with pytest.raises(LateralFigureError,match="source crop changed"):
        verify_lateral_figure_receipt(stage)


@pytest.mark.skipif(not os.getenv("MICROGEN_REAL_G3_SECTION27_STAGE"),
                    reason="Opt-in genuine source/cached Gemini figure mapping on HP")
def test_authentic_source_pdf_and_failed_gemini_mapping_replayed_without_api(
        tmp_path,monkeypatch):
    import map_and_rename_v5 as mapper
    old=Path(os.environ["MICROGEN_REAL_G3_SECTION27_STAGE"])
    sha="03676ed9dc5ded9e07874902c5e2d3689d4293cdc086b9819003770310293102"
    assert hashlib.sha256((old/"source.pdf").read_bytes()).hexdigest()==sha
    stage=tmp_path/"real_stage"
    stage.mkdir()
    shutil.copy2(old/"source.pdf",stage/"source.pdf")
    page=stage/"pages"/"page_3"
    page.mkdir(parents=True)
    shutil.copy2(old/"pages"/"page_3"/"page_3.png",page/"page_3.png")
    shutil.copy2(old/"pages"/"page_3"/"fig_7.png",page/"fig_7.png")
    original_captions=(old/"pages"/"page_3"/"page_3_captions.txt").read_text("utf8")
    original_mapping=json.loads(
        (old/".microgen_mapping_cache"/"page_3_mapping_0000.json").read_text("utf8")
    )["response"]
    assert "UNLABELED" in original_mapping
    def original_cached_response(name,*args):
        return original_captions if name.endswith("_captions.json") else original_mapping
    monkeypatch.setattr(mapper,"_cached_figure_request",original_cached_response)
    monkeypatch.chdir(stage)
    mapper.mapping()
    proof=verify_lateral_figure_receipt(stage)
    assert proof["figures"]==["Figure 2.12.png"]
    assert (stage/"Figure 2.12.png").is_file()
    assert (stage/".microgen_lateral_vector_figure_recovery.json").is_file()
