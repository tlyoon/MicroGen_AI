"""Synthetic source-discovery tests; no copyrighted Serway material in repository."""
import hashlib
import json
import tempfile
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_pronunciation_closed_loop import sha_file
from microgen_source_passage_discovery import (
    SourceDiscoveryError, discover_passages, main)


START = "Section B.2: Modeling and Representation"
NEXT = "Section B.3: Later Physics"


def pdf_fixture(root, variant="normal"):
    original = root/"source.pdf"
    pdf=fitz.open()
    p=pdf.new_page()
    p.insert_text((45,35),"Chapter 5: Old context",fontsize=12)
    p.insert_textbox(fitz.Rect(45,80,510,165),
                     "An old section describes unrelated density and algebra. "*4,
                     fontsize=11)
    p.insert_text((45,201),START,fontsize=12)
    p.insert_textbox(fitz.Rect(45,220,510,340),
                     "A particle model simplifies motion by neglecting irrelevant internal processes. "*4,
                     fontsize=11)
    p.insert_textbox(fitz.Rect(45,348,510,430),
                     "A geometric model uses a right triangle to represent a height measurement. "*3,
                     fontsize=11)
    p.insert_text((40,785),"Copyright reserved earlier textbook section.")
    if variant == "one_page":
        p.insert_text((45,498),NEXT,fontsize=12)
        p.insert_textbox(fitz.Rect(45,516,510,605),
                         "Hidden neighboring section explains an unrelated hidden claim. "*3,
                         fontsize=11)
    else:
        p=pdf.new_page()
        p.insert_text((45,35),START)  # Running header, not a second true section.
        p.insert_textbox(fitz.Rect(45,87,510,183),
                         "A pictorial representation shows the scene before physics equations. "*4,
                         fontsize=11)
        p.insert_textbox(fitz.Rect(45,200,510,288),
                         "Figure 2.4 illustrates a pictorial representation of a ball. "*4,
                         fontsize=11)
        p.insert_textbox(fitz.Rect(45,307,510,400),
                         "A graph of position against time reveals the pattern of oscillation. "*4,
                         fontsize=11)
        p.insert_text((45,455),NEXT,fontsize=12)
        p.insert_textbox(fitz.Rect(45,472,510,566),
                         "Hidden neighboring section explains an unrelated hidden claim. "*3,
                         fontsize=11)
        p.insert_text((45,785),"Copyright reserved next textbook section.")
    pdf.save(original)
    pdf.close()
    return original


def test_passages_exclude_previous_and_next_section_and_discover_figure_labels():
    with tempfile.TemporaryDirectory() as td:
        src=pdf_fixture(Path(td))
        original=sha_file(src)
        result=discover_passages(src,START,NEXT)
        assert result["source_pdf_sha256"]==original
        assert result["source_page_count"]==2
        assert result["passage_count"]>=4
        assert [x["source_page"] for x in result["passages"]]==sorted(
            x["source_page"] for x in result["passages"])
        text=" ".join(x["text"] for x in result["passages"]).lower()
        assert "particle model" in text
        assert "geometric model" in text
        assert "pictorial representation" in text
        assert "unrelated density" not in text
        assert "hidden neighboring" not in text
        assert "copyright" not in text
        assert "Figure 2.4" in result["figure_label_mentions"]
        assert all(x["auto_narration_generated"] is False for x in result["candidate_topics"])
        assert not result["source_topic_completeness_proven"]
        assert not result["publication_allowed"]
        assert sha_file(src)==original


def test_single_page_section_boundaries():
    with tempfile.TemporaryDirectory() as td:
        src=pdf_fixture(Path(td),variant="one_page")
        result=discover_passages(src,START,NEXT)
        assert result["passage_count"]==2
        assert all(x["source_page"]==1 for x in result["passages"])
        assert "hidden neighboring" not in " ".join(x["text"] for x in result["passages"])


def test_explicit_end_of_pdf_and_missing_boundaries_fail_closed():
    with tempfile.TemporaryDirectory() as td:
        src=pdf_fixture(Path(td))
        assert discover_passages(src,START,end_of_pdf=True)["passage_count"]>=4
        with pytest.raises(SourceDiscoveryError):
            discover_passages(src,START,"Nonexistent next section")
        with pytest.raises(SourceDiscoveryError):
            discover_passages(src,"Unknown start",NEXT)
        with pytest.raises(SourceDiscoveryError):
            discover_passages(src,START)
        with pytest.raises(SourceDiscoveryError):
            discover_passages(src,START,NEXT,end_of_pdf=True)


def test_stale_contract_rejected_and_existing_report_never_overwritten():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        src=pdf_fixture(root)
        manifest=root/"contract.json"
        manifest.write_text(json.dumps({
            "source_pdf_sha256":sha_file(src),
            "start_marker":START,"next_section_marker":NEXT,
            "publication_allowed":False,
            "topics":[{
                "topic_id":"particle","source_page":1,
                "source_anchors":["particle model"]
            }]
        }))
        result=discover_passages(src,START,NEXT,contract=manifest)
        assert len(result["declared_topic_anchor_overlaps"])==1
        assert result["declared_topic_anchor_overlaps"][0][
            "source_passage_ids_with_anchor_overlap"]
        assert len(result["passages_without_declared_topic_anchor_overlap"])>=2
        out=root/"new_private.json"
        assert main(["--source",str(src),"--start-marker",START,
                     "--next-marker",NEXT,"--contract",str(manifest),
                     "--new-private-report",str(out)])==0
        previous=sha_file(out)
        with pytest.raises(SourceDiscoveryError):
            main(["--source",str(src),"--start-marker",START,
                  "--next-marker",NEXT,"--new-private-report",str(out)])
        assert sha_file(out)==previous
        obj=json.loads(manifest.read_text())
        obj["source_pdf_sha256"]="0"*64
        manifest.write_text(json.dumps(obj))
        with pytest.raises(SourceDiscoveryError):
            discover_passages(src,START,NEXT,contract=manifest)


def test_headings_reversed_on_single_page_cannot_fake_valid_section():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        src=root/"source.pdf"
        pdf=fitz.open()
        p=pdf.new_page()
        p.insert_text((45,90),NEXT)
        p.insert_text((45,220),START)
        p.insert_textbox(fitz.Rect(45,250,510,420),
                         "The model explains a physical system by choosing a representation. "*5,
                         fontsize=11)
        pdf.save(src)
        pdf.close()
        with pytest.raises(SourceDiscoveryError):
            discover_passages(src,START,NEXT)


def test_short_example_heading_and_last_page_content_before_footer_not_lost():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        src=root/"source.pdf"
        pdf=fitz.open()
        p=pdf.new_page()
        p.insert_text((45,105),START)
        p.insert_text((45,145),"Example 2.1 Height of a Tree")
        p.insert_textbox(fitz.Rect(45,178,510,285),
                         "A triangle models the geometric height using a measured angle. "*4,
                         fontsize=11)
        p.insert_textbox(fitz.Rect(45,690,510,747),
                         "Mathematical representation connects a quantity to a useful equation. "*3,
                         fontsize=11)
        p.insert_text((45,780),"Copyright protects the publisher's footer.")
        p=pdf.new_page()
        p.insert_text((45,120),NEXT)
        pdf.save(src)
        pdf.close()
        result=discover_passages(src,START,NEXT)
        content=" ".join(x["text"] for x in result["passages"])
        assert "Example 2.1 Height of a Tree" in content
        assert "Mathematical representation" in content
        assert "Copyright protects" not in content
        assert result["source_page_count"]==2
