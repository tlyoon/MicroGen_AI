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
    (stage / "script_tts.json").write_text(json.dumps({
        "slides": [{"slide": 1, "tts_text":
                    "The system has an ordinary momentum lesson."}]
    }), encoding="utf8")
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
        required = {
            "figure_extraction": ("figure_extraction_receipt.json",),
            "figure_mapping": ("figure_composition_receipt.json",),
            "figure_merge": ("figure_composition_receipt.json",),
            "slides": ("slides.pdf",),
            "narration": ("slides.pdf", "script_tts.json", "script.txt"),
            "science_qa": ("script_tts.json", ".microgen_autonomous_science_qa.json"),
        }.get(name, ())
        return (stage / "source.pdf").is_file() and all(
            (stage / filename).is_file() for filename in required)
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


def test_recurring_math_source_risk_imports_only_figures_and_slides_for_new_voice(
    tmp_path,
):
    """Old source-bound slides reused; stale narration/science must rerun."""
    def old_risky_voice(base, campaign, stage, source):
        (stage / "script_tts.json").write_text(json.dumps({
            "slides": [{"slide": 1, "tts_text":
                        "The variable y approaches zero."}]
        }), encoding="utf8")
    result, work, old_stage = call_fixture(tmp_path, old_risky_voice)
    assert result["status"] == reuse.FOUR_STATUS
    assert result["stages"] == list(reuse.FOUR_UPSTREAM)
    current = work / "2.5"
    cp = json.loads((current / ".microgen_checkpoint.json").read_text())
    assert set(cp["completed"]) == set(reuse.FOUR_UPSTREAM)
    assert (current / "slides.pdf").is_file()
    assert (current / "figure_extraction_receipt.json").is_file()
    assert not (current / "script_tts.json").exists()
    assert not (current / "script.txt").exists()
    assert not (current / ".microgen_autonomous_science_qa.json").exists()
    assert not (current / ".microgen_narration_batches").exists()
    assert not (current / "slide1.wav").exists()
    assert (old_stage / "script_tts.json").is_file()
    summary = json.loads((current / reuse.RECEIPT).read_text())
    assert summary["status"] == reuse.FOUR_STATUS
    assert summary["stages"] == list(reuse.FOUR_UPSTREAM)
    assert not any(name in summary["copied_items"] for name in (
        "script.txt", "script_tts.json", ".microgen_narration_batches",
        ".microgen_autonomous_science_qa.json"))
    assert reuse.verify_import_receipt(current)["stages"] == list(reuse.FOUR_UPSTREAM)
    summary["status"] = reuse.SIX_STATUS
    (current / reuse.RECEIPT).write_text(json.dumps(summary))
    with pytest.raises(reuse.UpstreamReuseError, match="provenance drift"):
        reuse.verify_import_receipt(current)


def test_unreadable_prior_narration_never_silently_imports_science_proof(tmp_path):
    def malformed_voice(base, campaign, stage, source):
        (stage / "script_tts.json").write_text("not a JSON sidecar")
    # Malformed old narration is not reusable, but the independently checked
    # four source/slide stages need not be discarded or regenerated.
    result, work, _ = call_fixture(tmp_path, malformed_voice)
    assert result["status"] == reuse.FOUR_STATUS
    stage = work / "2.5"
    assert (stage / "slides.pdf").exists()
    assert not (stage / "script_tts.json").exists()
    assert not (stage / ".microgen_autonomous_science_qa.json").exists()


def test_private_source_bound_response_cache_copied_without_tts_or_provider(
    tmp_path,
):
    """A terminal old narration stage may donate verified returned responses,
    NEVER a completed narration receipt, WAV or provider authorization.
    """
    base,repo,sources,source,old_work,old_stage,_=fixture(tmp_path)
    target = base / "NEW_PRIVATE_CAMPAIGN" / "2.5"
    target.mkdir(parents=True)
    for name in reuse.FOUR_UPSTREAM:
        pass
    (target / "source.pdf").write_bytes(source.read_bytes())
    (target / "slides.pdf").write_bytes((old_stage / "slides.pdf").read_bytes())
    scripts = (
        "gen_script_v13.py", "microgen_narration_batch.py",
        "gen_script_prompt_v8_hybrid.md",
    )
    for name in scripts:
        (old_stage / name).write_bytes(b"same-authentic-generator-contents")
        (target / name).write_bytes(b"same-authentic-generator-contents")
    folder = old_stage / ".microgen_narration_batches"
    folder.mkdir()
    payload = {
        "key": "1" * 64,
        "narration": {"slide_01": {
            "narration": "Original source-confirmed mathematical explanation.",
            "tts_text": "Original source-confirmed mathematical explanation.",
        }},
    }
    (folder / "batch_0000.json").write_text(json.dumps(payload),encoding="utf8")
    imported = reuse._copy_verifiable_narration_response_cache(
        base,target,source_sha=sha(source.read_bytes()),
        slides_sha=sha((target/"slides.pdf").read_bytes()))
    assert imported["file_sha256"] == {
        "batch_0000.json": sha((folder/"batch_0000.json").read_bytes())
    }
    assert imported["requires_exact_prompt_key_revalidation"] is True
    assert (target/".microgen_narration_batches"/"batch_0000.json").read_bytes() == (
        folder/"batch_0000.json").read_bytes()
    assert not (target/"script_tts.json").exists()
    assert not (target/"slide1.wav").exists()
    assert not (target/".microgen_autonomous_science_qa.json").exists()


@pytest.mark.parametrize("mutation", ("source","slides","generator","key","link"))
def test_mismatched_or_incomplete_cached_model_output_is_not_adopted(
    tmp_path, mutation,
):
    base,repo,sources,source,old_work,old_stage,_=fixture(tmp_path)
    target=base/"NEW_PRIVATE_CAMPAIGN"/"2.5"
    target.mkdir(parents=True)
    for name in ("source.pdf","slides.pdf"):
        (target/name).write_bytes((old_stage/name).read_bytes())
    for name in ("gen_script_v13.py","microgen_narration_batch.py",
                 "gen_script_prompt_v8_hybrid.md"):
        (old_stage/name).write_text("identical verified provider code")
        (target/name).write_text("identical verified provider code")
    old_cache=old_stage/".microgen_narration_batches"
    old_cache.mkdir()
    f=old_cache/"batch_0000.json"
    f.write_text(json.dumps({"key":"1"*64,"narration":{
        "slide_01":{"narration":"The verified original model narration"}}}))
    if mutation=="source": (old_stage/"source.pdf").write_bytes(b"source drift")
    if mutation=="slides": (old_stage/"slides.pdf").write_bytes(b"slide drift")
    if mutation=="generator": (old_stage/"gen_script_v13.py").write_bytes(b"unsafe generator")
    if mutation=="key": f.write_text(json.dumps({"key":"NOT_VALID","narration":{}}))
    if mutation=="link":
        f.unlink()
        try:
            f.symlink_to(old_stage/"source.pdf")
        except (OSError,NotImplementedError):
            pytest.skip("Symlinks unavailable on this Windows host")
    result=reuse._copy_verifiable_narration_response_cache(
        base,target,source_sha=sha(source.read_bytes()),
        slides_sha=sha((target/"slides.pdf").read_bytes()))
    assert result is None
    assert not (target/".microgen_narration_batches").exists()


def test_private_cached_response_digest_is_bound_to_import_receipt(tmp_path):
    def risky(base,old_work,old_stage,source):
        (old_stage/"script_tts.json").write_text(json.dumps({
            "slides":[{"slide":1,"tts_text":"The variable y approaches zero."}]
        }))
    result,work,_=call_fixture(tmp_path,risky)
    assert result and result["status"]==reuse.FOUR_STATUS
    stage=work/"2.5"
    cache=stage/".microgen_narration_batches"
    cache.mkdir()
    name="batch_0000.json"
    payload=b'{"key":"112233","narration":{}}'
    (cache/name).write_bytes(payload)
    manifest=json.loads((stage/reuse.RECEIPT).read_text())
    manifest["source_bound_narration_response_cache"]={
        "requires_exact_prompt_key_revalidation":True,
        "original_response_not_academic_qa":True,
        "file_sha256":{name:sha(payload)},
    }
    (stage/reuse.RECEIPT).write_text(json.dumps(manifest))
    assert reuse.verify_import_receipt(stage)
    (cache/name).write_bytes(payload+b"drift")
    with pytest.raises(reuse.UpstreamReuseError,match="Narration cache digest mismatch"):
        reuse.verify_import_receipt(stage)


def test_published_manifest_can_verify_cache_provenance_without_exporting_model_text(
    tmp_path,
):
    """Published bundle carries SHA proof but never private cached replies."""
    def risky(base,old_work,old_stage,source):
        (old_stage/"script_tts.json").write_text(json.dumps({
            "slides":[{"slide":1,"tts_text":"The variable y approaches zero."}]
        }))
    result,work,_=call_fixture(tmp_path,risky)
    assert result and result["status"]==reuse.FOUR_STATUS
    stage=work/"2.5"
    cache=stage/".microgen_narration_batches"
    cache.mkdir()
    payload=b'{"key":"1","narration":{}}'
    (cache/"batch_0000.json").write_bytes(payload)
    receipt=json.loads((stage/reuse.RECEIPT).read_text())
    receipt["source_bound_narration_response_cache"]={
        "requires_exact_prompt_key_revalidation":True,
        "original_response_not_academic_qa":True,
        "file_sha256":{"batch_0000.json":sha(payload)}
    }
    (stage/reuse.RECEIPT).write_text(json.dumps(receipt))
    assert reuse.verify_import_receipt(stage,require_cache=True)
    published=tmp_path/"PUBLISHED_PROVENANCE_ONLY"
    published.mkdir()
    import shutil
    for name in ("source.pdf","slides.pdf",reuse.RECEIPT,
                 ".microgen_source_caption_vector_recovery.json"):
        shutil.copy2(stage/name,published/name)
    assert not (published/".microgen_narration_batches").exists()
    assert reuse.verify_import_receipt(published,require_cache=False)
    with pytest.raises(reuse.UpstreamReuseError,match="cache missing"):
        reuse.verify_import_receipt(published,require_cache=True)


def test_science_reviewer_code_drift_reuses_only_four_trusted_source_stages(
    tmp_path,
):
    """Reproduce Nov 12 G2 blocker: upgraded science QA invalidates old QA
    receipt, but source PDFs/figures/slides retain independent validation.
    """
    base,repo,sources,source,old_work,old_stage,quality=fixture(tmp_path)
    work=base/"NEW_PRIVATE_CAMPAIGN"
    work.mkdir()
    def current_validator(stage,name,dest):
        if name=="science_qa":
            return False  # Updated independent reviewer must run again.
        required={
            "figure_extraction":("figure_extraction_receipt.json",),
            "figure_mapping":("figure_composition_receipt.json",),
            "figure_merge":("figure_composition_receipt.json",),
            "slides":("slides.pdf",),
        }.get(name,())
        return (stage/"source.pdf").is_file() and all(
            (stage/f).is_file() for f in required)
    result=reuse.maybe_import_verified_upstream(
        repo=repo,source_root=sources,work_root=work,subchapter="2.5",
        source_file=source,dest=source.parent,commit="b"*40,
        source_wait=0,prepare_stage=fake_prepare,
        stage_valid=current_validator,mark_complete=fake_mark,
        quality=quality,
    )
    assert result and result["status"]==reuse.FOUR_STATUS
    stage=work/"2.5"
    cp=json.loads((stage/".microgen_checkpoint.json").read_text())
    assert set(cp["completed"])==set(reuse.FOUR_UPSTREAM)
    assert (stage/"slides.pdf").is_file()
    assert not (stage/"script_tts.json").exists()
    assert not (stage/".microgen_autonomous_science_qa.json").exists()
    assert not (stage/"slide1.wav").exists()
    provenance=json.loads((stage/reuse.RECEIPT).read_text())
    assert provenance["full_previous_science_verification_current_code"] is False
    assert provenance["new_model_requests"] is False
    assert reuse.verify_import_receipt(stage)["stages"]==list(reuse.FOUR_UPSTREAM)


def test_prior_six_stage_math_voice_is_downgraded_to_four_on_new_policy(
    tmp_path,
):
    """An old *valid* science receipt cannot authorize stale spoken notation."""
    def stale_voice(_base, _campaign, stage, _source):
        old="We define instantaneous acceleration ay ex as the limit of motion."
        (stage/"script_tts.json").write_text(json.dumps({
            "slides":[{"slide":1,"tts_text":old,"narration":old}]
        }),encoding="utf8")
    result,work,old=call_fixture(tmp_path,stale_voice)
    assert result and result["status"]==reuse.FOUR_STATUS
    assert result["stages"]==list(reuse.FOUR_UPSTREAM)
    stage=work/"2.5"
    cp=json.loads((stage/".microgen_checkpoint.json").read_text())
    assert set(cp["completed"])==set(reuse.FOUR_UPSTREAM)
    assert (stage/"slides.pdf").is_file()
    assert not (stage/"script_tts.json").exists()
    assert not (stage/".microgen_autonomous_science_qa.json").exists()
    assert not (stage/"slide1.wav").exists()
    receipt=json.loads((stage/reuse.RECEIPT).read_text())
    assert receipt["full_previous_science_verification_current_code"] is False
    assert receipt["new_audio_reused"] is False
    assert receipt["publication_allowed"] is False
    assert reuse.verify_import_receipt(stage)["stages"]==list(reuse.FOUR_UPSTREAM)
