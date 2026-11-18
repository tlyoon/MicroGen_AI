"""Real owner-private source/PCM replay; no provider calls or stage mutation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

import pytest

from microgen_preacoustic_timed_pcm_reuse import (
    _original_pcm_candidate, _same_source_and_speech_producer,
    SPEECH_PRODUCER, maybe_reuse_preacoustic_timed_pcm,
)
from microgen_verified_tts_reuse import SOURCE, MATH_POLICY, TIMED, _verify
from microgen_timed_highlight_contract import inspect_timed_highlights


def _real_stage():
    root=Path(os.environ.get("LOCALAPPDATA","/unavailable"))/"MicroGen_AI_Checkpoints"
    old=root/"20261118_HP_G3_SERWAY27_KINEMATICS_C5C_PRIVATE"/"2.7"
    if not (old/".microgen_autonomous_acoustic_qa.json").is_file():
        pytest.skip("Original authorized HP private experiment unavailable")
    return old


def test_historical_verified_21_slide_timed_pcm_recovered_with_current_code(tmp_path):
    source=_real_stage()
    policy=Path(__file__).resolve().parents[1]
    new=tmp_path/"new-source"
    new.mkdir()
    for name in SOURCE:
        shutil.copy2(source/name,new/name)
    from microgen_preacoustic_timed_pcm_reuse import VERIFIER_ONLY_UPGRADES
    for name in set(MATH_POLICY+SPEECH_PRODUCER+tuple(VERIFIER_ONLY_UPGRADES)):
        shutil.copy2(policy/name,new/name)
    for n in range(1,22):
        shutil.copy2(source/f"slide{n}.pdf",new/f"slide{n}.pdf")
    candidate=tmp_path/"candidate"
    candidate.mkdir()
    inventory,changed,cues=_original_pcm_candidate(source,new,candidate,21)
    assert changed==[5,17]
    assert cues==10
    assert len(inventory)>100
    assert inspect_timed_highlights(candidate)["slide_count"]==21
    _verify(candidate,21)
    assert _same_source_and_speech_producer(source,new)
    assert not (candidate/".microgen_autonomous_acoustic_qa.json").exists()


def test_source_or_voice_policy_drift_prevents_reuse(tmp_path):
    source=_real_stage()
    new=tmp_path/"new-source"
    new.mkdir()
    from microgen_preacoustic_timed_pcm_reuse import VERIFIER_ONLY_UPGRADES
    for name in set(SOURCE+SPEECH_PRODUCER+tuple(VERIFIER_ONLY_UPGRADES)):
        shutil.copy2(source/name,new/name)
    assert _same_source_and_speech_producer(source,new)
    (new/"microgen_reviewed_math_voice.py").write_text(
        "UNTRUSTED_VOICE_RULE",encoding="utf8")
    assert not _same_source_and_speech_producer(source,new)
    shutil.copy2(source/"microgen_reviewed_math_voice.py",
                 new/"microgen_reviewed_math_voice.py")
    (new/"script_tts.json").write_bytes(b"UNTRUSTED_NARRATION")
    assert not _same_source_and_speech_producer(source,new)


def test_reuse_is_not_a_general_unbounded_tts_wav_override(tmp_path):
    # No specially authorized new HP private campaign => not reusable.
    source=_real_stage()
    cp={"package_commit":"a"*40,"completed":{}}
    assert maybe_reuse_preacoustic_timed_pcm(
        tmp_path,work_root=tmp_path,source_sha="0"*64,cp=cp,
        checkpoint_path=tmp_path/"checkpoint.json",mark_complete=lambda *x:None,
        stage_valid=lambda *x:True,dest=tmp_path
    ) is None
