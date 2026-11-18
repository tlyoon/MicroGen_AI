"""Offline crash, rollback, tamper, and normal private acoustic integration tests."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from unittest import mock

import pytest
from microgen_timed_acoustic_transaction import (
    JOURNAL, TimedAcousticTransactionError,
    install_timed_acoustic, recover_interrupted_timed_acoustic,
)
from test_microgen_timed_highlight_contract import stage as make_stage


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def simple_inputs(tmp_path):
    root=tmp_path/"private"
    root.mkdir()
    for filename in ("source.pdf","slides.pdf","script_tts.json","slide1.wav",
                     "highlight_chunks/slide1_cue1.wav"):
        target=root/filename
        target.parent.mkdir(exist_ok=True,parents=True)
        target.write_bytes(("ORIGINAL_"+filename).encode())
    replacements={}
    for filename in ("slide1.wav","highlight_chunks/slide1_cue1.wav"):
        target=tmp_path/("candidate_"+filename.replace("/","_"))
        target.write_bytes(("CANDIDATE_"+filename).encode())
        replacements[filename]=target
    before={p:sha(root/p) for p in replacements}
    return root,replacements,before


def test_replacement_validated_and_committed_with_no_journal(tmp_path):
    stage,replacements,before=simple_inputs(tmp_path)
    result=install_timed_acoustic(stage,replacements,lambda:True)
    assert result["assets"]==2
    assert result["publication_allowed"] is False
    assert not (stage/JOURNAL).exists()
    assert all(sha(stage/k)==sha(v) for k,v in replacements.items())
    assert all(sha(stage/k)!=before[k] for k in before)
    assert recover_interrupted_timed_acoustic(stage)=="NO_TIMED_ACOUSTIC_TRANSACTION"


def test_validation_failure_rolls_back_every_asset(tmp_path):
    stage,replacements,before=simple_inputs(tmp_path)
    with pytest.raises(RuntimeError,match="source fault"):
        install_timed_acoustic(stage,replacements,
            lambda: (_ for _ in ()).throw(RuntimeError("source fault")))
    assert all(sha(stage/k)==old for k,old in before.items())
    assert not (stage/JOURNAL).exists()


def test_simulated_process_kill_and_no_provider_recovery(tmp_path):
    stage,replacements,before=simple_inputs(tmp_path)
    from microgen_timed_acoustic_transaction import _atomic_write_bytes
    calls=0
    def killed(dest,src):
        nonlocal calls
        _atomic_write_bytes(dest,src)
        calls+=1
        if calls==1:
            raise SystemExit("simulated process kill after first complete file")
    with mock.patch(
        "microgen_timed_acoustic_transaction._atomic_write_bytes",
        side_effect=killed):
        with pytest.raises(SystemExit,match="simulated process kill"):
            install_timed_acoustic(stage,replacements,lambda:True)
    assert (stage/JOURNAL/"plan.json").is_file()
    assert any(sha(stage/k)!=old for k,old in before.items())
    assert recover_interrupted_timed_acoustic(stage)==(
        "INTERRUPTED_TIMED_AUDIO_ROLLED_BACK_OFFLINE")
    assert all(sha(stage/k)==old for k,old in before.items())
    assert not (stage/JOURNAL).exists()


def test_unrecognized_external_asset_blocks_automatic_rollback(tmp_path):
    stage,replacements,before=simple_inputs(tmp_path)
    from microgen_timed_acoustic_transaction import _atomic_write_bytes
    def killed(dest,src):
        _atomic_write_bytes(dest,src)
        raise SystemExit("process loss")
    with mock.patch(
        "microgen_timed_acoustic_transaction._atomic_write_bytes",
        side_effect=killed):
        with pytest.raises(SystemExit):
            install_timed_acoustic(stage,replacements,lambda:True)
    (stage/"slide1.wav").write_bytes(b"UNKNOWN_OWNER_EDIT")
    with pytest.raises(TimedAcousticTransactionError,
                       match="UNRECOGNIZED_ACOUSTIC_ASSET_HOLD"):
        recover_interrupted_timed_acoustic(stage)
    assert (stage/JOURNAL).is_dir()


def test_original_source_alteration_blocks_transaction_recovery(tmp_path):
    stage,replacements,before=simple_inputs(tmp_path)
    from microgen_timed_acoustic_transaction import _atomic_write_bytes
    def killed(dest,src):
        _atomic_write_bytes(dest,src)
        raise SystemExit("process loss")
    with mock.patch(
        "microgen_timed_acoustic_transaction._atomic_write_bytes",
        side_effect=killed):
        with pytest.raises(SystemExit):
            install_timed_acoustic(stage,replacements,lambda:True)
    (stage/"source.pdf").write_bytes(b"UNEXPECTED_SOURCE")
    with pytest.raises(TimedAcousticTransactionError,
                       match="Source or journal identity changed"):
        recover_interrupted_timed_acoustic(stage)
    assert (stage/JOURNAL).exists()


def test_same_provider_measured_audio_repair_integrates_normal_gate(tmp_path):
    from microgen_autonomous_acoustic_gate import (
        _repair, _normalized,
        _input_snapshot,
    )
    from microgen_autonomous_acoustic_gate import REPAIRABLE
    from microgen_tts_provenance import (
        make_record, write_manifest, verify_manifest,
    )
    from microgen_timed_highlight_contract import inspect_timed_highlights
    from test_microgen_timed_acoustic_repair import synthesize

    stage=make_stage(tmp_path)
    shutil.copy2(stage/"slides.pdf",stage/"source.pdf")
    texts=_normalized(stage)
    records=[]
    for n in (1,2):
        record=make_record(
            slide=n,path=stage/f"slide{n}.wav",text=texts[n-1],
            provider="gemini_flash_lite_tts",key=f"synthetic-key-{n}",
            voice_name="Kore",language_code="en-US",
            speaking_rate=1.0,location="global")
        records.append(record)
        cache=stage/".microgen_tts_cache"
        cache.mkdir(exist_ok=True)
        (cache/f"slide{n}.json").write_text(json.dumps(record),encoding="utf8")
    write_manifest(stage,records,texts)
    verify_manifest(stage,texts)
    report={
        "review_required_slides":[1],
        "unavailable_recognizer_passes":[],
        "slides":[{"slide":1,"assessment":REPAIRABLE,
                   "source_pronunciation_risks":[]},
                  {"slide":2,"assessment":"ASR_SCREEN_PASS_LISTENING_REQUIRED",
                   "source_pronunciation_risks":[]}],
        "input_snapshot_sha256":_input_snapshot(stage,len(texts)),
    }
    old_wav=sha(stage/"slide1.wav")
    def recognized(path):
        return texts[0]
    corrected=_repair(stage,report,texts,(recognized,recognized),
                      synthesize=synthesize)
    assert corrected==1
    assert sha(stage/"slide1.wav")!=old_wav
    assert verify_manifest(stage,texts)
    assert inspect_timed_highlights(stage)["slide_count"]==2
    assert not (stage/JOURNAL).exists()
    assert not (stage/"slides.mp4").exists()


def test_real_previous_video_failure_is_registered_with_no_unchanged_retry():
    import os
    from microgen_recovery_registry import classify_log_attempt
    repo=Path(__file__).resolve().parents[1]
    root=Path(os.environ["LOCALAPPDATA"])/"MicroGen_AI_Checkpoints"
    observed=root/"20261118_HP_G3_SERWAY27_KINEMATICS_C5C_PRIVATE"/"2.7.log"
    if not observed.is_file():
        pytest.skip("Original private HP video traceback unavailable")
    decision=classify_log_attempt("video",observed.read_bytes(),registry_folder=repo)
    assert decision["failure_id"]=="MGA-20261118-TIMED-PCM-ACOUSTIC-REPAIR"
    assert decision["handler"]=="microgen_timed_acoustic_repair.prepare_timed_repair"
    assert decision["max_unmodified_retries"]==0
    from microgen_recovery_registry import load_registry
    rule=next(item for item in load_registry(repo)["entries"]
              if item["id"]==decision["failure_id"])
    assert rule["publication_allowed"] is False
    assert classify_log_attempt("tts",observed.read_bytes(),registry_folder=repo) is None


def test_exact_printed_math_glyph_reconstruction_is_narrow_and_fail_closed():
    from microgen_pdf_glyph_normalization import (
        correct_attested_glyphs, exact_source_glyph_equal,
    )
    original="x \u2212 y = \u221a5; \u0394x \u2192 t"
    wrong=original.replace("\u2212", "+")
    encoded=original.replace("\u2212", "\u00e2\u02c6\u2019").replace(
        "\u221a","\u00e2\u02c6\u0161").replace(
        "\u2192","\u00e2\u2020\u2019").replace(
        "\u0394", "\u0394")
    assert correct_attested_glyphs(encoded)==original
    assert exact_source_glyph_equal(encoded,original)
    assert not exact_source_glyph_equal(wrong,original)
    assert not exact_source_glyph_equal("x - y = 5",original)
    assert not exact_source_glyph_equal(["x", "y"],["x","y","z"])
