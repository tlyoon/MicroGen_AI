"""Current §2.5 acceptance: technical pass must NOT imply human release."""
import json
from pathlib import Path

import pytest

import microgen_corrected_release_gate_v2 as gate
from microgen_corrected_semantic_review import build_corrected_semantic_review_packet
from microgen_corrected_slide_clock import build_slide_clock
from microgen_source_safe_orchestrator import atomic_json,digest
from test_microgen_corrected_semantic_review import _setup


def _case(tmp_path,monkeypatch):
    source,stage,selection,shadow,asr,film,pixel=_setup(tmp_path,monkeypatch)
    # The lower-level synthetic fixture does not simulate real FFmpeg
    # duration output; make this field explicit for the release gate.
    movie_receipt=film/"word_highlight_candidate_receipt.json"
    m=json.loads(movie_receipt.read_text())
    m["duration_seconds"]=build_slide_clock(stage,selection,shadow)["audio_seconds"]
    atomic_json(movie_receipt,m)
    semantic=tmp_path/"source_bound_semantic_packet"
    build_corrected_semantic_review_packet(
        stage,selection,shadow,asr,film,pixel,semantic)
    expected=digest(semantic/"semantic_review_receipt.json")
    recovery=tmp_path/"LEGACY_RECOVERY"
    old_video=tmp_path/"verified_pre_word_video";old_video.mkdir()
    old_pixel=tmp_path/"verified_pre_word_pixel";old_pixel.mkdir()
    comparison=tmp_path/"original_trial_AB";comparison.mkdir()
    def legacy(*,output,**kw):
        plan=build_slide_clock(stage,selection,shadow)
        atomic_json(output,{
            "publication_allowed":False,"ready_to_publish":False,
            "full_corrected_pcm_sample_integrity_verified":True,
            "slide_level_visual_mapping_verified":True,
            "corrected_pcm_sha256":plan["pcm"]["pcm_sha256"],
            "original_pdf_sha256":digest(source/"slides.pdf"),
            "pixel_matches":50})
        return {"publication_allowed":False}
    monkeypatch.setattr(gate,"audit_corrected_section25",legacy)
    inputs={"recovery":recovery,"stage":stage,"selection":selection,
            "shadow":shadow,"old_video":old_video,
            "old_pixel_audit":old_pixel,"pronunciation_packet":comparison,
            "asr":asr,"highlight_video":film,"word_pixel_audit":pixel,
            "semantic_review":semantic,
            "expected_semantic_receipt_sha256":expected}
    return inputs,source,stage,film,pixel,semantic


def test_real_structural_evidence_leaves_every_domain_gate_blocked(tmp_path,monkeypatch):
    data,source,stage,film,pixel,semantic=_case(tmp_path,monkeypatch)
    out=tmp_path/"release_report"
    result=gate.reconcile_corrected_lecture_release_evidence(**data,output=out)
    assert result["technical_pass"] is True
    assert result["publication_allowed"] is False
    assert result["release_blockers"]>=6
    assert result["pending_review"]==0  # synthetic test PDF has no math candidates
    detail=json.loads((out/"corrected_release_status_v2.json").read_text())
    assert detail["technical_evidence"]["actual_current_word_pixels_passed"]==1
    assert detail["technical_evidence"]["semantic_packet_files_sha_checked"]>=20
    assert detail["domain_approval"]["academic_and_listening_review_complete"] is False
    assert detail["ready_to_publish"] is False
    assert detail["publication_allowed"] is False
    assert "OFFLINE_ASR_PYTHON_PACKAGE_OR_EXPLICIT_MODEL_UNAVAILABLE" not in detail["release_blockers"]


@pytest.mark.parametrize("tamper",["crop_html","cue","film","pixel",
                                 "semantic_receipt","untrusted_receipt","fake_prior"])
def test_release_rejects_corruption_and_never_writes_success(tmp_path,monkeypatch,tamper):
    data,source,stage,film,pixel,semantic=_case(tmp_path,monkeypatch)
    if tamper=="crop_html":
        (semantic/"index.html").write_text("tampered")
    elif tamper=="cue":
        (stage/"cues.json").write_bytes(b"bad")
    elif tamper=="film":
        (film/"section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4").write_bytes(b"changed")
    elif tamper=="pixel":
        p=pixel/"word_pixel_audit_receipt.json";v=json.loads(p.read_text())
        v["failed_samples"]=1;atomic_json(p,v)
    elif tamper=="semantic_receipt":
        p=semantic/"semantic_review_receipt.json";v=json.loads(p.read_text())
        v["publication_allowed"]=True;atomic_json(p,v)
    elif tamper=="untrusted_receipt":
        data["expected_semantic_receipt_sha256"]="0"*64
    else:
        def legacy_false_approve(*,output,**kw):
            atomic_json(output,{"publication_allowed":True})
            return {"publication_allowed":True}
        monkeypatch.setattr(gate,"audit_corrected_section25",legacy_false_approve)
    out=tmp_path/"release_report"
    with pytest.raises((ValueError,OSError,KeyError)):
        gate.reconcile_corrected_lecture_release_evidence(**data,output=out)
    assert not out.exists()


def test_output_in_protected_or_existing_location_is_refused(tmp_path,monkeypatch):
    data,source,stage,film,pixel,semantic=_case(tmp_path,monkeypatch)
    present=tmp_path/"existing";present.mkdir()
    for dest in (present,source/"release",stage/"release",semantic/"release",
                 film/"release",tmp_path):
        with pytest.raises(gate.CorrectedCurrentGateError,match="isolated"):
            gate.reconcile_corrected_lecture_release_evidence(**data,output=dest)
