"""Synthetic multi-PDF source-backed campaign tests; no protected materials."""
import copy
import json
import tempfile
from pathlib import Path
import pytest

from microgen_private_cross_section_coverage import (
    MultiSectionEvidenceError,audit_private_section_campaign)
from microgen_portable_private_authoring_gate import canonical_hash
from test_microgen_portable_private_authoring_gate import construct


def cases(root):
    rows=[]
    for label in ("B.2","C.4"):
        directory=root/label
        directory.mkdir()
        source,packet,draft=construct(directory)
        if label!="B.2":
            packet["section_id"]=label
            draft["section_id"]=label
            draft["packet_sha256"]=canonical_hash(packet)
        packet_path=directory/"private_packet.json"
        draft_path=directory/"private_draft.json"
        packet_path.write_text(json.dumps(packet),encoding="utf8")
        draft_path.write_text(json.dumps(draft),encoding="utf8")
        rows.append({"section_id":label,"source_pdf":str(source),
                     "private_packet":str(packet_path),
                     "private_draft":str(draft_path)})
    return rows


def test_two_original_immutable_pdf_cases_verified_no_text_or_api():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);items=cases(root);dest=root/"private-report"
        result=audit_private_section_campaign(items,dest)
        assert result["section_count"]==2
        assert result["source_passages_discovered_total"]>=4
        assert result["source_passages_cited_total"]>=4
        assert result["provider_or_local_language_model_invoked"] is False
        assert result["no_source_or_authored_text_in_receipt"] is True
        assert not result["publication_allowed"]
        assert dest.is_dir()
        receipt=(dest/"multisection_private_coverage_receipt.json").read_text()
        assert "A model can simplify" not in receipt
        assert "This segment introduces a graph" not in receipt
        assert "This learning segment" not in receipt
        assert len(json.loads(receipt)["section_records"])==2
        for item in items:
            assert Path(item["source_pdf"]).is_file()


@pytest.mark.parametrize("fault",[
    "wrong_pdf_sha","wrong_packet_sha","fake_source_packet","duplicate_section",
    "missing_source","bad_cases","private_draft_modified","wrong_original_id",
    "preexisting_dest","my_drive_dest","wrong_source_section",
])
def test_any_one_bad_case_fails_whole_campaign_without_output(fault):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        entries=cases(root)
        dest=root/"new-private-receipt"
        bad=entries[1]
        packet_path=Path(bad["private_packet"])
        draft_path=Path(bad["private_draft"])
        if fault=="wrong_pdf_sha":
            src=Path(bad["source_pdf"]);src.write_bytes(src.read_bytes()+b" ")
        elif fault=="wrong_packet_sha":
            draft=json.loads(draft_path.read_text())
            draft["packet_sha256"]="0"*64
            draft_path.write_text(json.dumps(draft))
        elif fault=="fake_source_packet":
            packet=json.loads(packet_path.read_text())
            packet["source_evidence"][0]["text"]="Invented citation"
            packet_path.write_text(json.dumps(packet))
            draft=json.loads(draft_path.read_text())
            draft["packet_sha256"]=canonical_hash(packet)
            draft_path.write_text(json.dumps(draft))
        elif fault=="duplicate_section":bad["section_id"]=entries[0]["section_id"]
        elif fault=="missing_source":bad["source_pdf"]=str(root/"absent.pdf")
        elif fault=="bad_cases":bad.pop("private_packet")
        elif fault=="private_draft_modified":
            draft=json.loads(draft_path.read_text())
            draft["topics"][0]["narration"]+=" 9999."
            draft_path.write_text(json.dumps(draft))
        elif fault=="wrong_original_id":bad["section_id"]="C.900"
        elif fault=="preexisting_dest":dest.mkdir()
        elif fault=="my_drive_dest":
            folder=root/"My Drive"
            folder.mkdir()
            dest=folder/"private-receipt"
        elif fault=="wrong_source_section":
            packet=json.loads(packet_path.read_text())
            packet["next_section_marker"]="No genuine boundary"
            packet_path.write_text(json.dumps(packet))
        with pytest.raises((MultiSectionEvidenceError,ValueError,FileNotFoundError)):
            audit_private_section_campaign(entries,dest)
        assert not (dest/"multisection_private_coverage_receipt.json").exists()


def test_one_case_is_allowed_but_zero_or_too_many_are_not():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);rows=cases(root)
        assert audit_private_section_campaign(rows[:1],root/"one")["section_count"]==1
        with pytest.raises(MultiSectionEvidenceError):
            audit_private_section_campaign([],root/"zero")
        with pytest.raises(MultiSectionEvidenceError):
            audit_private_section_campaign(rows*7,root/"too-many")
