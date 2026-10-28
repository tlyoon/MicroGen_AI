"""A source-grounded technical pass must NEVER become release approval."""
import json
import pytest
from microgen_source_safe_orchestrator import atomic_json
import microgen_corrected_release_gate as g
import microgen_corrected_listening_packet as lp
from test_microgen_corrected_listening_packet import _setup

def _case(tmp_path,monkeypatch):
    source,recovery,stage,selection,shadow,film,pixel=_setup(tmp_path,monkeypatch)
    check=pixel/"pixel_audit_receipt.json"
    obj=json.loads(check.read_text())
    obj["samples"]=[{"correct_pdf_match":True} for _ in range(50)]
    atomic_json(check,obj)
    from microgen_corrected_slide_clock import build_slide_clock
    video_receipt=film/"corrected_slide_clock_receipt.json"
    video_meta=json.loads(video_receipt.read_text())
    video_meta["pcm_sha256_verified"]=build_slide_clock(stage,selection,shadow)["pcm"]["pcm_sha256"]
    atomic_json(video_receipt,video_meta)
    review=tmp_path/"a_b_review"
    lp.prepare_corrected_pronunciation_packet(
        recovery,stage,selection,shadow,film,pixel,review)
    return source,recovery,stage,selection,shadow,film,pixel,review

def test_verified_corrected_evidence_still_blocks_all_release(tmp_path,monkeypatch):
    _,recovery,stage,sel,shadow,film,pixel,review=_case(tmp_path,monkeypatch)
    report=tmp_path/"acceptance.json"
    result=g.audit_corrected_section25(
        recovery=recovery,corrected_stage=stage,selection=sel,
        shadow=shadow,slide_video=film,pixel_audit=pixel,
        listening_packet=review,output=report)
    assert result["slide_pixels"]==50
    assert result["publication_allowed"] is False
    assert result["release_blockers"]>=7
    data=json.loads(report.read_text())
    assert data["slide_level_visual_mapping_verified"] is True
    assert data["human_listening_verdict_provided"] is False
    assert data["ready_to_publish"] is False
    assert "FRESH_SHA_BOUND_17_SLIDE_ASR_CUES_NOT_GENERATED" in data["release_blockers"]
    assert data["phonetic_correctness_verified"] is False

@pytest.mark.parametrize("tamper",["video","pixel","one_pixel","approved","pair","slide","shadow"])
def test_no_tampered_inputs_can_produce_a_technical_acceptance(tmp_path,monkeypatch,tamper):
    _,recovery,stage,sel,shadow,film,pixel,review=_case(tmp_path,monkeypatch)
    if tamper=="video":
        (film/"corrected_slides_NO_WORD_HIGHLIGHTS_UNAPPROVED.mp4").write_bytes(b"altered")
    if tamper in ("pixel","one_pixel"):
        p=pixel/"pixel_audit_receipt.json";o=json.loads(p.read_text())
        if tamper=="pixel":o["passed_samples"]=49
        else:o["samples"][0]["correct_pdf_match"]=False
        atomic_json(p,o)
    if tamper=="approved":
        p=review/"listening_packet_receipt.json";o=json.loads(p.read_text())
        o["phonetic_correctness_verified"]=True;atomic_json(p,o)
    if tamper=="pair":
        (review/"slide05_trial_UNREVIEWED.wav").write_bytes(b"altered")
    if tamper=="slide":
        (stage/"audio"/"slide7.wav").write_bytes(b"altered")
    if tamper=="shadow":
        (shadow/"section25_corrected_shadow_UNAPPROVED.wav").write_bytes(b"altered")
    out=tmp_path/"blocked.json"
    with pytest.raises((ValueError,OSError)):
        g.audit_corrected_section25(
            recovery=recovery,corrected_stage=stage,selection=sel,
            shadow=shadow,slide_video=film,pixel_audit=pixel,
            listening_packet=review,output=out)
    assert not out.exists()

def test_release_dossier_never_overwritten(tmp_path,monkeypatch):
    _,rec,stage,sel,shadow,film,pixel,review=_case(tmp_path,monkeypatch)
    out=tmp_path/"existing.json";out.write_text("original")
    with pytest.raises(g.CorrectedReleaseGateError):
        g.audit_corrected_section25(recovery=rec,corrected_stage=stage,
            selection=sel,shadow=shadow,slide_video=film,
            pixel_audit=pixel,listening_packet=review,output=out)
    assert out.read_text()=="original"
