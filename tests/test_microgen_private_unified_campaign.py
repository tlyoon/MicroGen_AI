"""Unified private campaign transaction and source-identity regression tests."""
import json
import tempfile
from pathlib import Path

import pytest

from microgen_private_unified_campaign import (
    UnifiedPrivateCampaignError,audit_unified_private_campaign)
from microgen_portable_private_authoring_gate import (
    canonical_hash,write_validated_stage)
from microgen_pronunciation_closed_loop import sha_file
from test_microgen_portable_private_authoring_gate import construct


def cases(root):
    rows=[]
    for section in ("B.2","C.4"):
        sub=root/section
        sub.mkdir()
        source,packet,draft=construct(sub)
        if section!="B.2":
            packet["section_id"]=section
            draft["section_id"]=section
            draft["packet_sha256"]=canonical_hash(packet)
        pp=sub/"private_packet.json"
        dp=sub/"private_draft.json"
        pp.write_text(json.dumps(packet),encoding="utf8")
        dp.write_text(json.dumps(draft),encoding="utf8")
        stage=sub/"stage"
        write_validated_stage(source,packet,draft,stage)
        rows.append({"section_id":section,"source_pdf":str(source),
            "private_packet":str(pp),"private_draft":str(dp),
            "stage":str(stage)})
    return rows


def test_atomic_complete_two_section_receipt_contains_no_source_prose():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        rows=cases(root)
        before={x["source_pdf"]:sha_file(Path(x["source_pdf"])) for x in rows}
        dest=root/"combined"
        result=audit_unified_private_campaign(rows,dest)
        assert result["section_count"]==2
        assert result["status"].startswith("UNIFIED_PRIVATE_")
        assert result["original_sources_unchanged"]
        assert result["locally_installed_language_model_invoked"] is False
        assert result["paid_provider_api_calls"]==0
        assert not result["publication_allowed"]
        names=("unified_private_campaign_receipt.json",
               "coverage/multisection_private_coverage_receipt.json",
               "science/multisection_private_science_receipt.json")
        assert all((dest/name).is_file() for name in names)
        assert result["coverage_receipt_sha256"]==sha_file(dest/names[1])
        assert result["science_receipt_sha256"]==sha_file(dest/names[2])
        all_receipts=" ".join((dest/name).read_text() for name in names)
        assert "A model can simplify" not in all_receipts
        assert "This learning segment" not in all_receipts
        assert len(result["sections"])==2
        assert {x["section_id"] for x in result["sections"]}=={"B.2","C.4"}
        assert before=={x["source_pdf"]:sha_file(Path(x["source_pdf"])) for x in rows}


@pytest.mark.parametrize("fault",[
    "source_changed","stage_source_changed","bad_draft",
    "bad_packet","missing_stage","swapped_stages","duplicate_section",
    "missing_field","output_exists","source_in_drive",
    "false_spoken_equality"
])
def test_one_bad_case_fails_whole_unified_transaction_without_any_partial_receipt(fault):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);rows=cases(root)
        last=rows[-1]
        dest=root/"fresh"
        if fault=="source_changed":
            src=Path(last["source_pdf"])
            src.write_bytes(src.read_bytes()+b"!")
        elif fault=="stage_source_changed":
            stage=Path(last["stage"])/"source.pdf"
            stage.write_bytes(stage.read_bytes()+b"!")
        elif fault=="bad_draft":
            path=Path(last["private_draft"])
            data=json.loads(path.read_text())
            data["packet_sha256"]="0"*64
            path.write_text(json.dumps(data))
        elif fault=="bad_packet":
            path=Path(last["private_packet"])
            data=json.loads(path.read_text())
            data["source_evidence"][0]["text"]="Invented physics source"
            path.write_text(json.dumps(data))
        elif fault=="missing_stage":
            last["stage"]=str(root/"missing")
        elif fault=="swapped_stages":
            last["stage"]=rows[0]["stage"]
        elif fault=="duplicate_section":
            last["section_id"]=rows[0]["section_id"]
        elif fault=="missing_field":
            del last["private_packet"]
        elif fault=="output_exists":
            dest.mkdir()
        elif fault=="source_in_drive":
            folder=root/"My Drive"
            folder.mkdir()
            dest=folder/"fresh"
        elif fault=="false_spoken_equality":
            path=Path(last["stage"])/"narration.json"
            data=json.loads(path.read_text())
            # Not source validated but should be caught by the scientific
            # narration equivalence check after the source line gate.
            data["slides"][0]["narration"]+=" One mile equals 2 km."
            path.write_text(json.dumps(data))
        with pytest.raises((ValueError,FileNotFoundError,KeyError)):
            audit_unified_private_campaign(rows,dest)
        assert not (dest/"unified_private_campaign_receipt.json").exists()
        assert not (dest/"coverage").exists()
        assert not (dest/"science").exists()


def test_campaign_size_and_unsafe_output_protected():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);rows=cases(root)
        with pytest.raises(UnifiedPrivateCampaignError):
            audit_unified_private_campaign([],root/"zero")
        with pytest.raises(UnifiedPrivateCampaignError):
            audit_unified_private_campaign(rows*7,root/"many")
        with pytest.raises((ValueError,KeyError)):
            audit_unified_private_campaign(rows,Path(rows[0]["stage"])/"within-stage")
