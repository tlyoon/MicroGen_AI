"""Offline corrected-audio boundary anomalies do not imply speaker identity."""
import csv
import json
import struct
import wave
from pathlib import Path
import pytest

from microgen_source_safe_orchestrator import digest,atomic_json
import microgen_corrected_boundary_screen as q
from test_microgen_corrected_exception_screen import _packet


def _source(tmp_path,monkeypatch):
    return _packet(tmp_path,monkeypatch)


def test_source_sha_bound_all_16_boundaries_and_no_voice_approval(tmp_path,monkeypatch):
    packet,pin=_source(tmp_path,monkeypatch)
    output=tmp_path/"new_boundary_report"
    r=q.scan_neighboring_clip_boundaries(packet,pin,output)
    assert r["slides"]==17 and r["boundaries"]==16
    assert r["publication_allowed"] is False
    receipt=json.loads((output/"boundary_screen_receipt.json").read_text())
    assert len(receipt["slide_audio"])==17
    assert receipt["boundary_count"]==16
    assert receipt["voice_identity_verified"] is False
    assert receipt["phonetic_correctness_verified"] is False
    assert q.verify_boundary_screen(output,digest(output/"boundary_screen_receipt.json"))[
        "publication_allowed"] is False
    with (output/"boundary_review.csv").open(encoding="utf8",newline="") as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==16
    assert all(x["review_verdict"]=="UNREVIEWED" for x in rows)


def test_16k_and_24k_pcm_are_measured_using_true_clock(tmp_path):
    for rate in (16000,24000):
        f=tmp_path/f"clip_{rate}.wav"
        with wave.open(str(f),"wb") as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate)
            w.writeframes(struct.pack("<h",1000)*rate)
        report=q.inspect_clip(f)
        assert report["samples"]==rate
        assert report["sample_rate_hz"]==rate
        assert report["seconds"]==1
        assert report["near_clip_windows"]==0


def test_edge_jump_and_voice_change_are_not_the_same_concept(tmp_path):
    # This is an objective waveform seam test, not a human speaker ID check.
    for id,v in enumerate((1000,28000)):
        f=tmp_path/f"test{id}.wav"
        with wave.open(str(f),"wb") as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
            w.writeframes(struct.pack("<h",v)*16000)
    a,b=(q.inspect_clip(tmp_path/f"test{i}.wav") for i in (0,1))
    assert abs(a["end_sample"]-b["start_sample"])/32768>.12
    assert "voice_identity_verified" not in a
    assert abs(a["median_voiced_dbfs"]-b["median_voiced_dbfs"])>7.5


@pytest.mark.parametrize("change",["wav","html","manifest","extra"])
def test_changed_source_packet_never_generates_boundary_report(tmp_path,monkeypatch,change):
    packet,pin=_source(tmp_path,monkeypatch)
    if change=="wav":
        (packet/"audio"/"slide05_CORRECTED_UNREVIEWED.wav").write_bytes(b"tampered")
    elif change=="html":
        (packet/"index.html").write_bytes(b"tampered")
    elif change=="manifest":
        meta=json.loads((packet/"semantic_review_receipt.json").read_text())
        meta["speaker_identity_approved"]=True
        atomic_json(packet/"semantic_review_receipt.json",meta)
    else:(packet/"malicious_extra.txt").write_text("changed")
    dest=tmp_path/"out"
    with pytest.raises((ValueError,OSError)):
        q.scan_neighboring_clip_boundaries(packet,pin,dest)
    assert not dest.exists()


@pytest.mark.parametrize("what",["csv","receipt","untracked"])
def test_output_sha_pin_and_unreviewed_status_defeat_forgery(tmp_path,monkeypatch,what):
    packet,pin=_source(tmp_path,monkeypatch)
    out=tmp_path/"boundary"
    q.scan_neighboring_clip_boundaries(packet,pin,out)
    trusted=digest(out/"boundary_screen_receipt.json")
    if what=="csv":
        with (out/"boundary_review.csv").open("a",encoding="utf8") as f:
            f.write("1->2,APPROVED,0,0,APPROVED,none")
    elif what=="receipt":
        meta=json.loads((out/"boundary_screen_receipt.json").read_text())
        meta["voice_identity_verified"]=True
        atomic_json(out/"boundary_screen_receipt.json",meta)
    else:(out/"untracked.txt").write_text("bad")
    with pytest.raises(q.BoundaryScreenError):
        q.verify_boundary_screen(out,trusted)


def test_occupied_or_inside_protected_review_packet_output_refused(tmp_path,monkeypatch):
    packet,pin=_source(tmp_path,monkeypatch)
    occupied=tmp_path/"prior";occupied.mkdir()
    with pytest.raises(q.BoundaryScreenError):
        q.scan_neighboring_clip_boundaries(packet,pin,occupied)
    with pytest.raises(q.BoundaryScreenError):
        q.scan_neighboring_clip_boundaries(packet,pin,packet/"out")
