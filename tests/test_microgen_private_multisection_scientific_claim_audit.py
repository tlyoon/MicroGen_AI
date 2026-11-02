"""Synthetic private multi-section science receipt tests (never textbook data)."""
import copy
import json
import tempfile
from pathlib import Path
import pytest

from microgen_private_multisection_scientific_claim_audit import (
    MultiSectionScientificEvidenceError,audit_private_science_campaign)
from microgen_portable_private_authoring_gate import write_validated_stage
from microgen_pronunciation_closed_loop import sha_file
from test_microgen_portable_private_authoring_gate import construct


def cases(root):
    out=[]
    for label in ("B.2","C.4"):
        sub=root/label;sub.mkdir()
        src,packet,draft=construct(sub)
        if label!="B.2":
            from microgen_portable_private_authoring_gate import canonical_hash
            packet["section_id"]=label
            draft["section_id"]=label
            draft["packet_sha256"]=canonical_hash(packet)
        stage=sub/"stage"
        write_validated_stage(src,packet,draft,stage)
        out.append({"section_id":label,"original_pdf":str(src),"stage":str(stage)})
    return out


def test_two_real_synthetic_pdf_stage_drafts_revalidated_immutable_and_private():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);entries=cases(root)
        orig=[sha_file(Path(c["original_pdf"])) for c in entries]
        output=root/"fresh-report"
        report=audit_private_science_campaign(entries,output)
        assert report["section_count"]==2
        assert report["typed_dimensional_equalities_checked"]==0
        assert report["typed_si_unit_relations_checked"]==0
        assert report["source_confirmed_spoken_speed_limit_conclusions_checked"]==0
        assert report["source_or_narration_excerpts_in_report"] is False
        assert report["provider_or_local_language_model_invoked"] is False
        assert report["publication_allowed"] is False
        text=(output/"multisection_private_science_receipt.json").read_text()
        assert "A model can simplify" not in text
        assert "This segment introduces a graph" not in text
        assert "This learning segment" not in text
        assert [sha_file(Path(c["original_pdf"])) for c in entries]==orig


@pytest.mark.parametrize("fault",[
    "pdf_changed","stage_pdf_changed","stage_narration_changed",
    "stage_contract_changed","case_duplicate","section_mismatch",
    "missing_stage","missing_source","too_many","existing_output",
    "unsafe_drive_output","missing_case_field",
])
def test_single_source_or_stage_fault_rejects_whole_batch_without_receipt(fault):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);rows=cases(root);last=rows[-1]
        output=root/"report-fresh"
        if fault=="pdf_changed":
            src=Path(last["original_pdf"]);src.write_bytes(src.read_bytes()+b"!")
        elif fault=="stage_pdf_changed":
            src=Path(last["stage"])/"source.pdf";src.write_bytes(src.read_bytes()+b"!")
        elif fault=="stage_narration_changed":
            src=Path(last["stage"])/"narration.json"
            x=json.loads(src.read_text());x["slides"][0]["narration"]+=" Modified"
            src.write_text(json.dumps(x))
        elif fault=="stage_contract_changed":
            src=Path(last["stage"])/"contract.json"
            x=json.loads(src.read_text());x["section_id"]="Fake.9"
            src.write_text(json.dumps(x))
        elif fault=="case_duplicate":last["section_id"]=rows[0]["section_id"]
        elif fault=="section_mismatch":last["section_id"]="R.900"
        elif fault=="missing_stage":last["stage"]=str(root/"unknown-stage")
        elif fault=="missing_source":last["original_pdf"]=str(root/"missing.pdf")
        elif fault=="too_many":rows=rows*7
        elif fault=="existing_output":output.mkdir()
        elif fault=="unsafe_drive_output":
            cloud=root/"My Drive";cloud.mkdir();output=cloud/"report"
        elif fault=="missing_case_field":last.pop("original_pdf")
        with pytest.raises((MultiSectionScientificEvidenceError,ValueError,FileNotFoundError,KeyError)):
            audit_private_science_campaign(rows,output)
        assert not (output/"multisection_private_science_receipt.json").exists()


def test_only_bounded_cases_allowed():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);rows=cases(root)
        assert audit_private_science_campaign(rows[:1],root/"one")["section_count"]==1
        for count in (0,13):
            with pytest.raises(MultiSectionScientificEvidenceError):
                audit_private_science_campaign(rows[:1]*count,root/"never")


def test_explicit_wrong_spoken_unit_claim_rejected_before_reporting():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);rows=cases(root);stage=Path(rows[0]["stage"])
        p=stage/"narration.json";n=json.loads(p.read_text())
        n["slides"][0]["narration"]+=" One mile equals 2 km."
        from hashlib import sha256
        script=n["slides"][0]["narration"]
        n["slides"][0]["spoken_text_sha256"]=sha256(script.encode("utf8")).hexdigest()
        p.write_text(json.dumps(n))
        contract=stage/"contract.json";m=json.loads(contract.read_text())
        m["narration_sha256"]=sha_file(p)
        contract.write_text(json.dumps(m))
        with pytest.raises(ValueError):
            audit_private_science_campaign(rows,root/"no-invalid-narration")
        assert not (root/"no-invalid-narration").exists()
