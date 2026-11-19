"""Offline measured-cue acoustic repair: real PDF/PCM binding and fault injection."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import wave
from pathlib import Path

import pytest
from microgen_timed_acoustic_repair import (
    TimedAcousticRepairError, prepare_timed_repair,
)
from microgen_timed_highlight_contract import (
    inspect_timed_highlights, HighlightContractError,
)
from test_microgen_timed_highlight_contract import stage as make_stage
from microgen_flash_tts import _merge_wavs


def synthesize(text, target, record):
    assert record["sample_rate_hz"] == 8000
    target = Path(target)
    with wave.open(str(target), "wb") as out:
        out.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        count = 4800 if "Conservation" in text else 6400
        out.writeframes(b"".join(
            struct.pack("<h", 9000 if i % 16 < 8 else -9000)
            for i in range(count)))


def test_source_bound_timed_candidate_and_full_deck_pcm(tmp_path):
    stage = make_stage(tmp_path)
    shutil.copy2(stage / "slides.pdf", stage / "source.pdf")
    old = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
           for p in stage.glob("slide*.wav")}
    verified = []
    (tmp_path / "fail").mkdir()
    with pytest.raises(TimedAcousticRepairError, match="reviewers rejected"):
        prepare_timed_repair(
            stage, [1], ["Conservation of energy. Energy transfers."] * 2,
            [{"sample_rate_hz": 8000}] * 2, tmp_path / "fail",
            synthesize, lambda wav, text: False)
    assert old == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in stage.glob("slide*.wav")}

    scratch = tmp_path / "success"
    scratch.mkdir()
    result = prepare_timed_repair(
        stage, [1], ["Conservation of energy. Energy transfers."] * 2,
        [{"sample_rate_hz": 8000}] * 2, scratch,
        synthesize, lambda wav, text: verified.append(wav.name) or True)
    assert result["changed_slides"] == [1]
    assert result["cue_count"] == 2
    assert verified == ["slide1.wav"]
    accepted = inspect_timed_highlights(result["prepared"])
    assert accepted["slide_count"] == 2
    assert accepted["status"] == "SOURCE_AND_PCM_TIMING_STRUCTURALLY_VERIFIED"
    assert old == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in stage.glob("slide*.wav")}
    for name, corrected in result["chunks"].items():
        assert name.startswith("highlight_chunks/slide1_cue")
        assert corrected.is_file()


@pytest.mark.parametrize("slides", [[1, 1], [2, 1], [0], [3], [1, 2, 2]])
def test_duplicate_out_of_order_or_missing_slide_rejected_before_synthesis(tmp_path,slides):
    stage = make_stage(tmp_path)
    shutil.copy2(stage / "slides.pdf", stage / "source.pdf")
    def forbidden(*args):
        raise AssertionError("Paid synthesis should never start")
    with pytest.raises(TimedAcousticRepairError, match="selection"):
        prepare_timed_repair(stage,slides,["narration"]*2,
                             [{"sample_rate_hz":8000}]*2,
                             tmp_path/"scratch", forbidden, forbidden)


def test_tampered_pcm_is_rejected_before_any_paid_synthesis(tmp_path):
    stage = make_stage(tmp_path)
    shutil.copy2(stage / "slides.pdf", stage / "source.pdf")
    with (stage/"highlight_chunks"/"slide1_cue1.wav").open("ab") as out:
        out.write(b"CORRUPTED")
    def forbidden(*args):
        raise AssertionError("Do not spend for tampered source")
    with pytest.raises(HighlightContractError):
        prepare_timed_repair(stage,[1],["narration"]*2,
                             [{"sample_rate_hz":8000}]*2,
                             tmp_path/"scratch",forbidden,forbidden)


def test_real_hp_21_slide_reconstructed_timing_and_offline_repair(tmp_path):
    env = os.environ.get("MICROGEN_HP_G3_TIMED_STAGE")
    if not env:
        pytest.skip("Authorized HP real PCM fixture absent")
    source = Path(env)
    dest = tmp_path/"restored_original_pcm"
    dest.mkdir()
    manifest=json.loads((source/".microgen_timed_highlights.json").read_text())
    for name in ["source.pdf","slides.pdf","script_tts.json"]:
        shutil.copy2(source/name,dest/name)
    for n in range(1,22):
        shutil.copy2(source/f"slide{n}.pdf",dest/f"slide{n}.pdf")
        shutil.copy2(source/f"slide{n}.wav",dest/f"slide{n}.wav")
    (dest/"highlight_chunks").mkdir()
    for row in manifest["slides"]:
        for cue in row["cues"]:
            path=cue["audio_chunk"]
            shutil.copy2(source/path,dest/path)
        if row["slide"] in (5,17):
            old_pcm=_merge_wavs([(dest/c["audio_chunk"]).read_bytes() for c in row["cues"]])
            (dest/f"slide{row['slide']}.wav").write_bytes(old_pcm)
    (dest/".microgen_timed_highlights.json").write_text(
        json.dumps(manifest),encoding="utf8")
    assert inspect_timed_highlights(dest)["slide_count"]==21
    original_pcm_sha={
        f"slide{i}.wav":hashlib.sha256((source/f"slide{i}.wav").read_bytes()).hexdigest()
        for i in range(1,22)}
    voice=json.loads((source/"script_tts.json").read_text())["slides"]
    texts=[r.get("tts_text") or r["narration"] for r in voice]
    # This is a non-provider *real source and actual cue* stress test;
    # synthesize uses the old source-grounded fragments for a reproducible
    # offline candidate. No fake acoustic acceptance is saved.
    def reuse_original_cue(text,target,record):
        nonlocal next_chunk
        shutil.copy2(dest/next_chunk.pop(0),target)
    next_chunk=[c["audio_chunk"] for n in (5,17)
                for c in manifest["slides"][n-1]["cues"]]
    recs=[{"sample_rate_hz":24000} for _ in texts]
    scratch=tmp_path/"real_shadow_candidate"
    scratch.mkdir()
    candidate=prepare_timed_repair(
        dest,[5,17],texts,recs,scratch,reuse_original_cue,
        lambda wav,text: True)
    assert candidate["cue_count"]==10
    assert inspect_timed_highlights(candidate["prepared"])["slide_count"]==21
    assert original_pcm_sha == {
        f"slide{i}.wav":hashlib.sha256((source/f"slide{i}.wav").read_bytes()).hexdigest()
        for i in range(1,22)}
