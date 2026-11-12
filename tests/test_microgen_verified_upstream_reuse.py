"""No-network source-verification and reuse in the normal G2 batch path."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import microgen_batch as batch
import microgen_verified_upstream_reuse as reuse


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture(tmp_path):
    base = tmp_path / "MicroGen_AI_Checkpoints"
    base.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "placeholder.py").write_text("source code", encoding="utf8")
    sources = tmp_path / "sources"
    source = sources / "2" / "2.5" / "source.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"%PDF-1.4\nTEST CONTENT ONLY")
    prior = base / "OWNER_SIGNED_PREVIOUS_CAMPAIGN"
    prior.mkdir()
    stage = prior / "2.5"
    stage.mkdir()
    (stage / "source.pdf").write_bytes(source.read_bytes())
    for name in (
        "slides.pdf", "slides.tex", "script.txt", "script_tts.json",
        ".microgen_autonomous_science_qa.json",
        "figure_extraction_receipt.json", "figure_composition_receipt.json",
    ):
        (stage / name).write_bytes(b"previously-verified-" + name.encode())
    (stage / "slide1.wav").write_bytes(b"DO-NOT-REUSE-FAILED-TTS")
    (stage / ".microgen_source_caption_vector_recovery.json").write_bytes(
        b"SOURCE-BOUND-VECTOR-RECOVERY-PROOF")
    pages = stage / "pages" / "page_1"
    pages.mkdir(parents=True)
    (pages / "page_1.png").write_bytes(b"source-bound-figure")
    scope = {
        "source_sha256": sha(source.read_bytes()),
        "code_revision": "a" * 40, "host": "hp",
        "stop_after": "acceptance",
    }
    (prior / reuse.OWNER_RECEIPT).write_text(json.dumps({
        "schema_version": 1,
        "publication_authorized": False,
        "scope": scope,
    }), encoding="utf8")
    fake = SimpleNamespace(
        dependency_fingerprint=lambda stage,name: "test-fingerprint-" + name
    )
    old_cp = {
        "completed": {name: "2026-11-12T10:00:00+00:00"
                      for name in reuse.UPSTREAM},
        "dependency_fingerprints": {
            name: fake.dependency_fingerprint(stage,name)
            for name in reuse.UPSTREAM
        },
        "package_commit": "a" * 40,
        "last_error": {"stage": "tts", "type": "RuntimeError"},
    }
    (stage / ".microgen_checkpoint.json").write_text(
        json.dumps(old_cp), encoding="utf8")
    return base,repo,sources,source,prior,stage,fake


def fake_prepare(repo,source_root,root,subchapter,wait,commit):
    stage=root/subchapter
    stage.mkdir()
    source=Path(source_root)/"2"/subchapter/"source.pdf"
    (stage/"source.pdf").write_bytes(source.read_bytes())
    cp={"completed":{},"dependency_fingerprints":{},"package_commit":commit,
        "last_error":None}
    path=stage/".microgen_checkpoint.json"
    path.write_text(json.dumps(cp), encoding="utf8")
    return stage,cp,path


def fake_mark(cp,path,name,stage):
    cp["completed"][name]="2026-11-12T11:00:00+00:00"
    cp["dependency_fingerprints"][name]="test-fingerprint-"+name
    path.write_text(json.dumps(cp), encoding="utf8")


def call_fixture(tmp_path,make_changes=None):
    base,repo,sources,source,old_work,old_stage,quality=fixture(tmp_path)
    if make_changes:
        make_changes(base, old_work, old_stage, source)
    work=base/"NEW_PRIVATE_CAMPAIGN"
    work.mkdir()
    def valid(stage,name,dest):
        return (stage/"source.pdf").is_file() and all(
            (stage/file).is_file()
            for file in ("slides.pdf","script_tts.json",
                         "figure_extraction_receipt.json",
                         ".microgen_autonomous_science_qa.json"))
    result=reuse.maybe_import_verified_upstream(
        repo=repo,source_root=sources,work_root=work,
        subchapter="2.5",source_file=source,dest=source.parent,
        commit="b"*40,source_wait=0,
        prepare_stage=fake_prepare,stage_valid=valid,
        mark_complete=fake_mark,quality=quality)
    return result,work,old_stage


def test_normal_import_reverifies_six_stages_and_never_imports_failed_audio(tmp_path):
    result,work,old_stage=call_fixture(tmp_path)
    assert result["status"]=="SIX_UPSTREAM_SOURCE_BOUND_STAGES_REVERIFIED"
    assert result["stages"]==list(reuse.UPSTREAM)
    saved=work/"2.5"
    cp=json.loads((saved/".microgen_checkpoint.json").read_text())
    assert set(cp["completed"])==set(reuse.UPSTREAM)
    assert cp["last_error"] is None
    assert not (saved/"slide1.wav").exists()
    assert not (saved/".microgen_autonomous_acoustic_qa.json").exists()
    assert (saved/"pages"/"page_1"/"page_1.png").read_bytes()==b"source-bound-figure"
    assert (old_stage/"slide1.wav").read_bytes()==b"DO-NOT-REUSE-FAILED-TTS"
    vector = saved / ".microgen_source_caption_vector_recovery.json"
    assert vector.read_bytes() == b"SOURCE-BOUND-VECTOR-RECOVERY-PROOF"
    attested=json.loads((saved/reuse.RECEIPT).read_text())
    assert attested["source_pdf_sha256"]==sha((saved/"source.pdf").read_bytes())
    assert attested["new_audio_reused"] is False
    assert attested["publication_allowed"] is False
    assert attested["source_caption_vector_recovery_receipt_sha256"] == sha(
        vector.read_bytes())
    checked=reuse.verify_import_receipt(saved)
    assert checked["stages"]==list(reuse.UPSTREAM)
    assert len(checked["receipt_sha256"])==64
    assert not list(work.glob(".microgen-verified-upstream-*"))


@pytest.mark.parametrize("mutation", [
    lambda base,work,stage,source:
        (stage/".microgen_checkpoint.json").write_text('{"completed": {}}'),
    lambda base,work,stage,source:
        (stage/"source.pdf").write_bytes(b"modified source"),
    lambda base,work,stage,source:
        (work/reuse.OWNER_RECEIPT).write_text('{"publication_authorized": true}'),
])
def test_forged_incomplete_or_drifted_prior_campaign_cannot_be_imported(
    tmp_path, mutation,
):
    result,work,_=call_fixture(tmp_path,mutation)
    assert result is None
    assert not (work/"2.5").exists()


def test_duplicate_equally_recent_science_evidence_fails_closed(tmp_path):
    def duplicate(base,old_work,stage,source):
        import shutil
        shutil.copytree(old_work,base/"OTHER_IDENTICAL_CAMPAIGN")
    with pytest.raises(reuse.UpstreamReuseError,match="Ambiguous"):
        call_fixture(tmp_path,duplicate)


def test_standing_normal_process_dispatches_reuse_before_prepare(tmp_path):
    args=SimpleNamespace(
        standing_private_development=True,
        bounded_provider_scope_verified=True,
        stop_after="acceptance",
        work_root=tmp_path/"private",
        repo=tmp_path/"repo",
        source_root=tmp_path/"sources",
        commit="b"*40,
        source_wait=0,
    )
    calls=[]
    def seed(**kwargs):
        calls.append(kwargs["subchapter"])
        return None
    with patch.object(reuse,"maybe_import_verified_upstream",side_effect=seed), \
         patch.object(batch,"source_for",return_value=tmp_path/"source.pdf"), \
         patch.object(batch,"destination_for",return_value=tmp_path/"dest"), \
         patch.object(batch,"prepare_stage",side_effect=RuntimeError("stop after dispatch")):
        with pytest.raises(RuntimeError,match="stop after dispatch"):
            batch.process_one(args,"2.5",[])
    assert calls==["2.5"]



def test_import_receipt_tamper_or_source_drift_fails_revalidation(tmp_path):
    result,work,_=call_fixture(tmp_path)
    assert result
    stage=work/"2.5"
    receipt=stage/reuse.RECEIPT
    original=receipt.read_bytes()
    row=json.loads(receipt.read_text())
    row["publication_allowed"]=True
    receipt.write_text(json.dumps(row))
    with pytest.raises(reuse.UpstreamReuseError,match="provenance drift"):
        reuse.verify_import_receipt(stage)
    receipt.write_bytes(original)
    vector = stage / ".microgen_source_caption_vector_recovery.json"
    vector.write_bytes(b"TAMPERED-CAPTION-PROVENANCE")
    with pytest.raises(reuse.UpstreamReuseError, match="source-caption provenance"):
        reuse.verify_import_receipt(stage)
    vector.write_bytes(b"SOURCE-BOUND-VECTOR-RECOVERY-PROOF")
    with (stage/"source.pdf").open("ab") as f:
        f.write(b"changed")
    with pytest.raises(reuse.UpstreamReuseError,match="provenance drift"):
        reuse.verify_import_receipt(stage)


def test_imported_old_script_does_not_authorize_new_tts_by_itself(tmp_path):
    result,work,_=call_fixture(tmp_path)
    assert result
    stage=work/"2.5"
    assert not (stage/".microgen_timed_cue_plan.json").exists()
    assert not (stage/".microgen_tts_provenance.json").exists()
    assert not (stage/".microgen_autonomous_acoustic_qa.json").exists()
    assert not (stage/".microgen_autonomous_acceptance.json").exists()
    assert not (stage/"slides.mp4").exists()
