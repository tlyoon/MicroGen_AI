"""Adversarial source recovery: historical records are not a release gate."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import microgen_section25_real_recovery as r
from microgen_source_safe_orchestrator import digest


def _inputs(tmp_path, monkeypatch):
    archive=tmp_path/"protected_historical"
    clone=tmp_path/"cloned"/"source.pdf"
    clone.parent.mkdir()
    archive.mkdir()
    clone.write_bytes(b"source-original-pdf")
    sha={}
    for filename,content in (
        ("slides.pdf",b"compiled-slide-pdf"),
        ("slides.mp4",b"historical-mp4"),
        ("script_tts.json",b'{"slides": []}'),
        ("source.pdf",clone.read_bytes()),
    ):
        sha[filename]=__import__("hashlib").sha256(content).hexdigest()
        (archive/filename).write_bytes(content)
    for item in r.EXTRAS:
        f=archive/item
        f.parent.mkdir(parents=True,exist_ok=True)
        f.write_bytes(("source-bound:"+item).encode())
    monkeypatch.setattr(r,"EXPECTED",sha)
    return clone, archive


def test_mirror_only_whitelisted_files_and_preserves_inputs(tmp_path,monkeypatch):
    clone,archive=_inputs(tmp_path,monkeypatch)
    fingerprints={str(p.relative_to(archive)):digest(p)
                  for p in archive.rglob("*") if p.is_file()}
    out=tmp_path/"unused_snapshot"
    result=r.mirror_known_lecture(clone,archive,out)
    assert result["mirrored"]==13
    assert result["publication_allowed"] is False
    for item in r.EXTRAS:
        assert digest(out/item)==digest(archive/item)
    assert json.loads((out/"recovery_mirror_manifest.json").read_text())[
        "publication_allowed"] is False
    assert {str(p.relative_to(archive)):digest(p)
            for p in archive.rglob("*") if p.is_file()} == fingerprints
    with pytest.raises(r.Section25RecoveryError,match="Unsafe or existing"):
        r.mirror_known_lecture(clone,archive,out)


def test_clone_mismatch_fails_before_any_write(tmp_path,monkeypatch):
    clone,archive=_inputs(tmp_path,monkeypatch)
    clone.write_bytes(b"tampered")
    target=tmp_path/"new"
    with pytest.raises(r.Section25RecoveryError,match="agreed"):
        r.mirror_known_lecture(clone,archive,target)
    assert not target.exists()


def test_archived_mp4_wrong_fails_before_write(tmp_path,monkeypatch):
    clone,archive=_inputs(tmp_path,monkeypatch)
    (archive/"slides.mp4").write_bytes(b"changed")
    target=tmp_path/"new"
    with pytest.raises(r.Section25RecoveryError,match="independent receipt"):
        r.mirror_known_lecture(clone,archive,target)
    assert not target.exists()


def test_missing_unapproved_wav_is_not_synthesized(tmp_path,monkeypatch):
    clone,archive=_inputs(tmp_path,monkeypatch)
    (archive/"QA_tts_cdot_20261019"/"slide6_corrected.wav").unlink()
    target=tmp_path/"new"
    with pytest.raises(r.Section25RecoveryError,match="missing"):
        r.mirror_known_lecture(clone,archive,target)
    assert not target.exists()


def test_linked_trial_and_missing_expected_receipt_are_rejected(tmp_path,monkeypatch):
    clone,archive=_inputs(tmp_path,monkeypatch)
    copied=archive/"QA_tts_y_20261019"/"slide10_corrected_y.wav"
    copied.unlink()
    try:
        copied.symlink_to(clone)
    except (OSError,NotImplementedError):
        pytest.skip("Local symbolic-link permissions absent")
    target=tmp_path/"new"
    with pytest.raises(r.Section25RecoveryError,match="linked"):
        r.mirror_known_lecture(clone,archive,target)
    assert not target.exists()


def test_late_file_drift_cleans_own_snapshot_only(tmp_path,monkeypatch):
    clone,archive=_inputs(tmp_path,monkeypatch)
    copy_impl=r.shutil.copyfile
    changed=[False]
    def drift_copy(src,dst):
        copy_impl(src,dst)
        if not changed[0]:
            changed[0]=True
            (archive/"script_tts.json").write_bytes(b"changed during copy")
    monkeypatch.setattr(r.shutil,"copyfile",drift_copy)
    target=tmp_path/"failed"
    with pytest.raises(r.Section25RecoveryError,match="changed"):
        r.mirror_known_lecture(clone,archive,target)
    assert not target.exists()
    assert (archive/"script_tts.json").is_file()


def test_filter_preflight_rejects_unsupported_ffmpeg_without_stage(tmp_path,monkeypatch):
    tool=tmp_path/"ffmpeg.exe"
    tool.write_bytes(b"binary placeholder")
    monkeypatch.setattr(r.subprocess,"run",lambda *a,**k:
        SimpleNamespace(returncode=0,stdout=" ... crop V->V\n",stderr=""))
    with pytest.raises(r.Section25RecoveryError,match="lacks tpad"):
        r.require_tail_ffmpeg_capabilities(tool)
    monkeypatch.setattr(r.subprocess,"run",lambda *a,**k:
        SimpleNamespace(returncode=0,stdout=" ... tpad V->V\n",stderr=""))
    assert r.require_tail_ffmpeg_capabilities(tool)==tool


def test_no_dest_inside_protected_trees(tmp_path,monkeypatch):
    clone,archive=_inputs(tmp_path,monkeypatch)
    with pytest.raises(r.Section25RecoveryError):
        r.mirror_known_lecture(clone,archive,archive/"newstage")
    with pytest.raises(r.Section25RecoveryError):
        r.mirror_known_lecture(clone,archive,clone.parent/"newstage")
