"""Regression from real HP Thomas 2.5 2026-11-21 private source-only intake."""
from types import SimpleNamespace
from unittest import mock

import pytest

import microgen_batch as batch


def _args(tmp_path, *, source_only):
    return SimpleNamespace(
        source_root=tmp_path / "immutable_sources",
        work_root=tmp_path / "scratch",
        repo=tmp_path,
        source_wait=0,
        commit="pinned",
        figure_extraction_only=source_only,
        stop_after=None,
        rebuild_unverified=False,
        multipart=False,
        offline_figure_mapping=False,
        main_py="offline",
        docling_py="offline",
        stage_retries=0,
    )


@pytest.mark.parametrize("published_receipt_is_valid", [False, True])
def test_source_only_legacy_mp4_cannot_block_or_fake_completion(tmp_path, published_receipt_is_valid):
    args = _args(tmp_path, source_only=True)
    dest = args.source_root / "2" / "2.5"
    dest.mkdir(parents=True)
    old_mp4 = dest / "slides.mp4"
    original_bytes = b"untouched prior Thomas MP4"
    old_mp4.write_bytes(original_bytes)
    stage = tmp_path / "staged"
    stage.mkdir()
    report = []
    with mock.patch.object(batch, "prepare_stage", return_value=(
        stage, {"completed": {}, "dependency_fingerprints": {}}, stage / ".microgen_checkpoint.json"
    )), mock.patch.object(
        batch.quality, "published_manifest_valid", return_value=published_receipt_is_valid
    ) as published_check, mock.patch.object(
        batch, "run_subprocess"
    ) as run, mock.patch.object(
        batch, "stage_valid", return_value=True
    ), mock.patch.object(
        batch, "source_page_extraction_valid", return_value=True
    ), mock.patch.object(
        batch, "mark_complete"
    ), mock.patch.object(
        batch, "publish"
    ) as publish:
        batch.process_one(args, "2.5", report)
    assert len(report) == 1
    assert report[0]["status"] == "offline_figure_extraction_complete"
    assert report[0]["gemini_or_tts_invoked"] is False
    assert report[0]["published"] is False
    assert run.call_count == 1
    assert run.call_args.args[1] == "crop_figs_v3.py"
    assert publish.call_count == 0
    assert published_check.call_count == 0
    assert old_mp4.read_bytes() == original_bytes


def test_normal_unverified_legacy_mp4_remains_protected(tmp_path):
    args = _args(tmp_path, source_only=False)
    dest = args.source_root / "2" / "2.5"
    dest.mkdir(parents=True)
    old_mp4 = dest / "slides.mp4"
    original_bytes = b"untouched prior Thomas MP4"
    old_mp4.write_bytes(original_bytes)
    stage = tmp_path / "staged"
    stage.mkdir()
    with mock.patch.object(batch, "prepare_stage", return_value=(
        stage, {"completed": {}}, stage / ".microgen_checkpoint.json"
    )), mock.patch.object(
        batch.quality, "published_manifest_valid", return_value=False
    ), mock.patch.object(batch, "run_subprocess") as run:
        with pytest.raises(RuntimeError, match="existing MP4 has no current verified"):
            batch.process_one(args, "2.5", [])
    assert run.call_count == 0
    assert old_mp4.read_bytes() == original_bytes


def test_offline_legacy_media_recovery_registry_is_project_pinned():
    from pathlib import Path
    import microgen_recovery_registry as recovery
    registry = recovery.load_registry(Path(batch.__file__).resolve().parent)
    entry = next(r for r in registry["entries"]
                 if r["id"] == "MGA-20261121-THOMAS-SOURCEONLY-LEGACY-MP4")
    assert entry["handler"] == "microgen_batch.process_one"
    assert entry["publication_allowed"] is False
    assert entry["max_unmodified_retries"] == 0
