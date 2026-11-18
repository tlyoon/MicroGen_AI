"""Offline no-overwrite preacoustic import crash and adversarial tests."""
from __future__ import annotations

from pathlib import Path
from unittest import mock
import os

import pytest
from microgen_exclusive_audio_import import (
    JOURNAL,ExclusiveAudioImportError,sha,
    import_verified_audio_assets,recover_interrupted_audio_import,
)


def stage(tmp_path):
    work=tmp_path/"private"
    work.mkdir()
    for name in ("source.pdf","slides.pdf","script_tts.json"):
        (work/name).write_bytes(("ORIGINAL "+name).encode())
    candidates={}
    for name in ("slide1.wav","highlight_chunks/slide1_cue1.wav"):
        p=tmp_path/("candidate_"+name.replace("/","_"))
        p.write_bytes(("VERIFIED SOUND "+name).encode())
        candidates[name]=p
    return work,candidates


def test_private_original_pcm_import_checkpoints_once(tmp_path):
    root,candidates=stage(tmp_path)
    called=[]
    report=import_verified_audio_assets(root,candidates,
                                        lambda:called.append("verified"))
    assert called==["verified"]
    assert report["status"]=="ORIGINAL_PCM_IMPORTED_AND_TTS_CHECKPOINTED"
    assert report["publication_allowed"] is False
    assert not (root/JOURNAL).exists()
    assert all(sha(root/k)==sha(v) for k,v in candidates.items())


def test_validation_failure_removes_only_imported_audio(tmp_path):
    root,candidates=stage(tmp_path)
    def failed():
        raise ValueError("bad source binding")
    with pytest.raises(ValueError,match="bad source"):
        import_verified_audio_assets(root,candidates,failed)
    assert not (root/JOURNAL).exists()
    assert not any((root/name).exists() for name in candidates)
    assert (root/"source.pdf").read_bytes()==b"ORIGINAL source.pdf"


def test_terminated_after_first_link_recovers_without_provider(tmp_path):
    root,candidates=stage(tmp_path)
    original=os.link
    called=0
    def interrupted(source,destination):
        nonlocal called
        original(source,destination)
        called+=1
        if called==1:
            raise SystemExit("injected process kill after atomic link")
    with mock.patch("microgen_exclusive_audio_import.os.link",side_effect=interrupted):
        with pytest.raises(SystemExit,match="injected process kill"):
            import_verified_audio_assets(root,candidates,lambda:None)
    assert (root/JOURNAL/"plan.json").is_file()
    assert recover_interrupted_audio_import(root)==(
        "INTERRUPTED_ORIGINAL_CUES_REMOVED_OFFLINE")
    assert not any((root/name).exists() for name in candidates)
    assert not (root/JOURNAL).exists()


def test_unrecognized_modified_asset_is_never_deleted(tmp_path):
    root,candidates=stage(tmp_path)
    original=os.link
    def interrupted(source,destination):
        original(source,destination)
        raise SystemExit("injected kill")
    with mock.patch("microgen_exclusive_audio_import.os.link",side_effect=interrupted):
        with pytest.raises(SystemExit):
            import_verified_audio_assets(root,candidates,lambda:None)
    (root/"slide1.wav").write_bytes(b"UNRELATED USER AUDIO")
    with pytest.raises(ExclusiveAudioImportError,
                       match="UNRECOGNIZED_IMPORTED_AUDIO_HOLD"):
        recover_interrupted_audio_import(root)
    assert (root/"slide1.wav").read_bytes()==b"UNRELATED USER AUDIO"
    assert (root/JOURNAL).exists()


def test_source_change_holds_before_deletion(tmp_path):
    root,candidates=stage(tmp_path)
    original=os.link
    def interrupted(source,destination):
        original(source,destination)
        raise SystemExit("injected kill")
    with mock.patch("microgen_exclusive_audio_import.os.link",side_effect=interrupted):
        with pytest.raises(SystemExit):
            import_verified_audio_assets(root,candidates,lambda:None)
    (root/"source.pdf").write_bytes(b"DIFFERENT SOURCE")
    with pytest.raises(ExclusiveAudioImportError,match="Source or import plan changed"):
        recover_interrupted_audio_import(root)
    assert (root/JOURNAL).exists()


def test_existing_audio_cannot_be_overwritten(tmp_path):
    root,candidates=stage(tmp_path)
    (root/"slide1.wav").write_bytes(b"OLD ACCEPTED MEDIA")
    with pytest.raises(ExclusiveAudioImportError,match="Refuse overwrite"):
        import_verified_audio_assets(root,candidates,lambda:None)
    assert (root/"slide1.wav").read_bytes()==b"OLD ACCEPTED MEDIA"


@pytest.mark.parametrize("stage,exception,message,rule",[
    ("tts","ExclusiveAudioImportError","UNRECOGNIZED_IMPORTED_AUDIO_HOLD",
     "MGA-20261118-PREACOUSTIC-IMPORT-RECOVERY"),
    ("tts","PreAcousticReuseError","Source math policy drift",
     "MGA-20261118-PREACOUSTIC-SOURCE-POLICY-HOLD"),
    ("acoustic_qa","TimedAcousticTransactionError","Unrecognized WAV asset",
     "MGA-20261118-TIMED-ACOUSTIC-TXN-RECOVERY"),
    ("acoustic_qa","TimedAcousticRepairError","Cue text does not reconstruct source",
     "MGA-20261118-TIMED-ACOUSTIC-CUE-HOLD"),
])
def test_executable_registry_classifies_finite_recovery_without_provider(
        stage,exception,message,rule):
    from microgen_recovery_registry import classify_log_attempt
    repo=Path(__file__).resolve().parents[1]
    traceback=("Traceback (most recent call last):\n"
               '  File "microgen_batch.py", line 1\n'
               f"{exception}: {message}\n").encode()
    result=classify_log_attempt(stage,traceback,registry_folder=repo)
    assert result is not None
    assert result["failure_id"]==rule
    assert result["max_unmodified_retries"]==0
    assert result["disposition"]=="DETERMINISTIC_HOLD"
