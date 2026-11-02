"""Interior last-heading boundaries with additional trailing textbook pages."""
import tempfile
from pathlib import Path

import pymupdf as fitz
import pytest

from microgen_portable_private_authoring_gate import (
    build_authoring_packet,canonical_hash,write_validated_stage)
from microgen_portable_section_contract import audit_portable_contract
from microgen_pronunciation_closed_loop import sha_file
from microgen_source_passage_discovery import (
    SourceDiscoveryError,discover_passages)
from test_microgen_portable_private_authoring_gate import (
    START,NEXT,construct)


def add_extra_pages(original):
    doc=fitz.open(original)
    # A follow-on section occupies page 3 and repeats the earlier section
    # marker in the running header. Its original PDF must stay intact for
    # both independently reproduced authoring/contract boundary proofs.
    extra=doc.new_page()
    extra.insert_text((45,35),NEXT,fontsize=11)
    extra.insert_textbox(fitz.Rect(45,110,510,255),
        "Additional unrelated physics discussions about hidden topics "
        "must never become the previous section source evidence. "*3,
        fontsize=11)
    extra=doc.new_page()
    extra.insert_textbox(fitz.Rect(45,110,510,255),
        "Several more pages of next-chapter exercises and summaries "
        "are not allowed to enter prior section authoring drafts. "*4,
        fontsize=11)
    tmp=original.with_name("expanded.pdf")
    doc.save(tmp)
    doc.close()
    return tmp


def test_true_next_heading_before_final_page_excludes_all_later_pages():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        base,_,_=construct(root)
        source=add_extra_pages(base)
        before=sha_file(source)
        result=discover_passages(source,START,NEXT)
        assert result["source_page_count"]==4
        assert result["next_section_heading_source_page"]==2
        assert result["trailing_pdf_pages_outside_section"]==2
        assert result["passage_count"]>=2
        assert all(x["source_page"]<=2 for x in result["passages"])
        whole=" ".join(x["text"] for x in result["passages"])
        assert "Additional unrelated physics" not in whole
        assert "Several more pages" not in whole
        assert "Unrelated novel principle" not in whole
        assert sha_file(source)==before


def test_original_authoring_contract_passes_with_intermediate_next_heading():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        source,packet,draft=construct(root)
        expanded=add_extra_pages(source)
        packet=build_authoring_packet(expanded,START,NEXT,section_id="B.2")
        assert packet["source_page_count"]==4
        assert packet["source_passage_count"]>=2
        draft["source_pdf_sha256"]=sha_file(expanded)
        draft["packet_sha256"]=canonical_hash(packet)
        stage=root/"new-section-stage"
        qa=write_validated_stage(expanded,packet,draft,stage)
        assert qa["topic_count"]==2
        assert qa["existing_portable_section_contract_passed"]
        files=[stage/k for k in ("source.pdf","narration.json","plan.json","contract.json")]
        academic=audit_portable_contract(*files)
        assert academic["topic_count"]==2
        assert academic["source_pdf_sha256"]==sha_file(expanded)
        assert not qa["publication_allowed"]


def test_marker_missing_in_all_pages_still_rejected():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        source,_,_=construct(root)
        extra=add_extra_pages(source)
        with pytest.raises(SourceDiscoveryError,match="Required section boundary"):
            discover_passages(extra,START,"Impossible Future Heading")
