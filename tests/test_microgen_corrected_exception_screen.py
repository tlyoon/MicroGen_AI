"""Exception prioritization never silently promotes acoustic or math review."""
import csv
import json
import math
import struct
import wave
from pathlib import Path

import pytest

from microgen_source_safe_orchestrator import digest,atomic_json
from microgen_corrected_exception_screen import (
    screen_corrected_exception_priority,lexical_screen,pcm_risk_screen,
    _source_text_match,ExceptionTriageError)
from test_microgen_corrected_release_gate_v2 import _case


def _packet(tmp_path,monkeypatch):
    inputs,*_= _case(tmp_path,monkeypatch)
    return inputs["semantic_review"],inputs["expected_semantic_receipt_sha256"]


def test_review_priority_reconciles_every_region_without_any_auto_approval(tmp_path,monkeypatch):
    packet,pin=_packet(tmp_path,monkeypatch)
    dest=tmp_path/"new_triage"
    result=screen_corrected_exception_priority(packet,pin,dest)
    receipt=json.loads((dest/"exception_screen_receipt.json").read_text())
    assert result["slides"]==17
    assert result["total"]==receipt["region_decisions_unreviewed"]
    assert result["review_first"]+result["pending"]==result["total"]
    assert receipt["source_semantic_receipt_sha256"]==pin
    assert receipt["publication_allowed"] is False
    assert receipt["no_region_auto_approved"] is True
    assert receipt["pronunciation_c_y_independently_verified"] is False
    assert set(x["slide"] for x in receipt["slides"])==set(range(1,18))
    for i in (5,6,10):
        assert "KNOWN_PRONUNCIATION_TRIAL_UNAPPROVED" in receipt["slides"][i-1]["risk_flags"]
    with (dest/"exception_priority.csv").open(encoding="utf8",newline="") as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==result["total"]
    assert all(r["review_verdict"]=="UNREVIEWED" for r in rows)


def test_lexical_screen_disagreement_is_anomaly_not_phonetic_certification():
    a=lexical_screen("We calculate the derivative at x",[
        {"word":w,"conf":.99} for w in
        ["we","calculate","the","derivative","at","x"]])
    b=lexical_screen("We calculate the derivative at x",[
        {"word":"purple","conf":.4},{"word":"sky","conf":.99}])
    assert a["word_sequence_similarity"]>b["word_sequence_similarity"]
    assert b["low_confidence_words"]==1
    assert _source_text_match("derivative of polynomial","derivative polynomial",[
        {"word":"derivative","start":1.0}])["textual_context_hint"]
    assert not _source_text_match("limit", "limit",[
        {"word":"limit"}])["textual_context_hint"]


def test_acoustic_screen_detects_clipping_and_silence_without_speaker_claim(tmp_path):
    f=tmp_path/"bad.wav"
    with wave.open(str(f),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(struct.pack("<h",32767)*8000+b"\0\0"*8000)
    screening=pcm_risk_screen(f)
    assert screening["near_clip_fraction"]==.5
    assert screening["quiet_sample_fraction"]==.5
    assert screening["samples"]==16000
    assert "speaker" not in screening


@pytest.mark.parametrize("tamper",["html","audio","receipt","extra"])
def test_input_integrity_failure_never_creates_untrusted_triage(tmp_path,monkeypatch,tamper):
    packet,pin=_packet(tmp_path,monkeypatch)
    if tamper=="html":
        (packet/"index.html").write_text("changed")
    elif tamper=="audio":
        (packet/"audio"/"slide05_CORRECTED_UNREVIEWED.wav").write_bytes(b"changed")
    elif tamper=="receipt":
        x=json.loads((packet/"semantic_review_receipt.json").read_text())
        x["publication_allowed"]=True
        atomic_json(packet/"semantic_review_receipt.json",x)
    else:(packet/"extra.txt").write_text("untrusted")
    out=tmp_path/"reject"
    with pytest.raises((ValueError,OSError)):
        screen_corrected_exception_priority(packet,pin,out)
    assert not out.exists()


def test_protected_or_occupied_output_never_overwritten(tmp_path,monkeypatch):
    packet,pin=_packet(tmp_path,monkeypatch)
    out=tmp_path/"occupied"
    out.mkdir()
    (out/"owner_file.txt").write_text("safe")
    with pytest.raises(ExceptionTriageError):
        screen_corrected_exception_priority(packet,pin,out)
    assert (out/"owner_file.txt").read_text()=="safe"
    with pytest.raises(ExceptionTriageError):
        screen_corrected_exception_priority(packet,pin,packet/"output")


def test_small_math_text_context_never_means_equation_correctness():
    matching=_source_text_match(
        "At x = 1: jump discontinuity, opposite approaches",
        "We see a jump discontinuity and opposite approaches",[
        {"word":"jump"},{"word":"opposite"}])
    assert matching["textual_context_hint"] is True
    assert "mathematically_correct" not in matching
    assert "phonetic_correct" not in matching


def test_corrected_trial_sample_rate_24k_is_supported_as_review_risk(tmp_path):
    f=tmp_path/"trial_24k.wav"
    with wave.open(str(f),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
        w.writeframes(struct.pack("<h",6000)*24000)
    result=pcm_risk_screen(f)
    assert result["sample_rate_hz"]==24000
    assert result["seconds"]==1.0
    assert result["near_clip_fraction"]==0


def test_title_asr_disagreement_not_graded_as_long_narration(tmp_path,monkeypatch):
    packet,pin=_packet(tmp_path,monkeypatch)
    out=tmp_path/"triage"
    screen_corrected_exception_priority(packet,pin,out)
    obj=json.loads((out/"exception_screen_receipt.json").read_text())
    title=obj["slides"][0]
    assert "SHORT_TITLE_NOT_ACOUSTICALLY_RATABLE" in title["risk_flags"]
    assert "ASR_SCRIPT_LOW_AGREEMENT" not in title["risk_flags"]
    assert "CHANGED_SAMPLE_RATE_AUDIO_CONTINUITY_REVIEW" not in title["risk_flags"]


@pytest.mark.parametrize("target",["index.html","exception_priority.csv","exception_screen_receipt.json"])
def test_exception_packet_output_tampering_is_detected(tmp_path,monkeypatch,target):
    from microgen_corrected_exception_screen import verify_exception_screen_packet
    packet,pin=_packet(tmp_path,monkeypatch)
    out=tmp_path/"triage"
    screen_corrected_exception_priority(packet,pin,out)
    original_digest=digest(out/"exception_screen_receipt.json")
    assert verify_exception_screen_packet(out,expected_sha256=original_digest)["publication_allowed"] is False
    p=out/target
    p.write_bytes(p.read_bytes()+b"forged APPROVED")
    with pytest.raises((ValueError,OSError)):
        verify_exception_screen_packet(out,expected_sha256=original_digest)
