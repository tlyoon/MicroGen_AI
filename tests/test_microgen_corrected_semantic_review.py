"""Academic/math/figure review packet must never fabricate spoken acceptance."""
import csv
import json
from pathlib import Path

import pytest

import microgen_corrected_semantic_review as qa
from microgen_source_safe_orchestrator import atomic_json,digest
from test_microgen_corrected_word_pixel_qa import _ready


def _setup(tmp_path,monkeypatch):
    source,stage,selection,shadow,asr,film,ff,refs,box=_ready(tmp_path,monkeypatch)
    # The old rendering fixture intentionally omitted acoustic-approval fields;
    # add explicit negative flags so review provenance is complete.
    asr_doc=json.loads(asr.read_text())
    for item in asr_doc["results"]:
        item["phonetic_identity_verified"]=False
        item["semantic_word_alignment_certified"]=False
    atomic_json(asr,asr_doc)
    movie_receipt=film/"word_highlight_candidate_receipt.json"
    item=json.loads(movie_receipt.read_text())
    item["recognition_report_sha256"]=digest(asr)
    atomic_json(movie_receipt,item)
    pixel_dir=tmp_path/"source_bound_pixel_qa"
    pixel_dir.mkdir()
    cues=json.loads((stage/"cues.json").read_text())
    atomic_json(pixel_dir/"word_pixel_audit_receipt.json",{
        "status":"CURRENT_ASR_OVERLAY_PIXEL_AUDIT_TECHNICAL_PASS",
        "actual_overlay_pixels_verified":True,
        "publication_allowed":False,
        "video_sha256":digest(film/"section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4"),
        "cues_sha256":digest(stage/"cues.json"),
        "asr_sha256":digest(asr),
        "corrected_pcm_sha256":json.loads((film/"word_highlight_candidate_receipt.json").read_text())["corrected_pcm_sha256"],
        "expected_cues":len(cues["elements"]),
        "positive_samples":len(cues["elements"]),
        "post_cue_control_samples":1,
        "failed_samples":0})
    return source,stage,selection,shadow,asr,film,pixel_dir


def test_complete_17_slide_review_packet_does_not_grant_academic_approval(tmp_path,monkeypatch):
    source,stage,selection,shadow,asr,film,pixel=_setup(tmp_path,monkeypatch)
    output=tmp_path/"new_math_figure_review"
    result=qa.build_corrected_semantic_review_packet(
        stage,selection,shadow,asr,film,pixel,output)
    assert result["slides"]==17
    assert result["publication_allowed"] is False
    assert len(list((output/"audio").glob("slide*.wav")))==17
    assert len(list((output/"slides").glob("slide*.png")))==17
    html=(output/"index.html").read_text(encoding="utf8")
    assert html.count("<audio controls")==17
    assert "NOT certified" in html
    receipt=json.loads((output/"semantic_review_receipt.json").read_text())
    assert receipt["slide_count"]==17
    assert receipt["source_pdf_sha256"]==digest(source/"slides.pdf")
    assert receipt["all_mathematical_semantics_verified"] is False
    assert receipt["all_figure_spoken_correspondence_verified"] is False
    assert receipt["pronunciation_approved"] is False
    assert receipt["publication_allowed"] is False
    with (output/"manual_semantic_review.csv").open(encoding="utf8",newline="") as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==receipt["unreviewed_region_decisions"]
    assert all(x["spoken_correspondence"]=="UNREVIEWED" for x in rows)
    assert all(x["academic_correctness"]=="UNREVIEWED" for x in rows)


@pytest.mark.parametrize("kind",["movie","asr","pixel","pixel_approval","pdf",
                                 "wav","cues","stale_cues","pixel_count"])
def test_stale_or_forged_evidence_fails_before_any_output(tmp_path,monkeypatch,kind):
    source,stage,selection,shadow,asr,film,pixel=_setup(tmp_path,monkeypatch)
    if kind=="movie":
        (film/"section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4").write_bytes(b"tampered")
    elif kind=="asr":
        data=json.loads(asr.read_text())
        data["narration_sha256"]="f"*64
        atomic_json(asr,data)
    elif kind=="pixel":
        data=json.loads((pixel/"word_pixel_audit_receipt.json").read_text())
        data["failed_samples"]=1
        atomic_json(pixel/"word_pixel_audit_receipt.json",data)
    elif kind=="pixel_approval":
        data=json.loads((pixel/"word_pixel_audit_receipt.json").read_text())
        data["publication_allowed"]=True
        atomic_json(pixel/"word_pixel_audit_receipt.json",data)
    elif kind=="pdf":
        (source/"slides.pdf").write_bytes(b"tampered")
    elif kind=="wav":
        (stage/"audio"/"slide5.wav").write_bytes(b"tampered")
    elif kind in ("cues","stale_cues"):
        data=json.loads((stage/"cues.json").read_text())
        if kind=="cues":data["publication_allowed"]=True
        else:data["derivation"]="HISTORICAL_AUDIO_UNVERIFIED"
        atomic_json(stage/"cues.json",data)
    elif kind=="pixel_count":
        data=json.loads((pixel/"word_pixel_audit_receipt.json").read_text())
        data["positive_samples"]=0
        atomic_json(pixel/"word_pixel_audit_receipt.json",data)
    dest=tmp_path/"review"
    with pytest.raises((ValueError,OSError)):
        qa.build_corrected_semantic_review_packet(
            stage,selection,shadow,asr,film,pixel,dest)
    assert not dest.exists()


def test_never_overwrites_unowned_or_protected_location(tmp_path,monkeypatch):
    source,stage,selection,shadow,asr,film,pixel=_setup(tmp_path,monkeypatch)
    forbidden=[tmp_path/"existing",source/"review",stage/"review",
               film/"review",pixel/"review",tmp_path]
    forbidden[0].mkdir()
    for dest in forbidden:
        with pytest.raises(qa.SemanticPacketError,match="new isolated"):
            qa.build_corrected_semantic_review_packet(
                stage,selection,shadow,asr,film,pixel,dest)


def test_context_only_heuristic_does_not_certify_spoken_equation():
    words=[
        {"word":"boundary","start":1.0,"end":1.3,"conf":.97},
        {"word":"integral","start":2.0,"end":2.2,"conf":.96},
        {"word":"boundary","start":3.0,"end":3.2,"conf":.97}]
    assert qa._context_only_anchors("Boundary integral = 0",words)==[]
    candidates=qa._context_only_anchors("Integral variable = 0",words)
    assert candidates==[]
    good=[{"word":"derivative","start":1,"end":1.3,"conf":.98},
          {"word":"integral","start":2,"end":2.3,"conf":.99}]
    x=qa._context_only_anchors("Derivative integral = 0",good)
    assert len(x)==1
    assert x[0]["NOT_semantic_alignment"] is True
