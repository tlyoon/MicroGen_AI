"""Original/trial side-by-side review is not a phonetic proof."""
import json
from pathlib import Path
import pytest
from microgen_source_safe_orchestrator import atomic_json,digest
import microgen_corrected_listening_packet as p
from test_microgen_corrected_slide_pixel_audit import _case

def _setup(tmp_path,monkeypatch):
    src,stage,sel,shadow,film,ff=_case(tmp_path,monkeypatch)
    recovery=tmp_path/"LEGACY_RECOVERY"
    pixel=tmp_path/"pixel_audit";pixel.mkdir()
    audit={"status":"CORRECTED_SLIDE_PIXEL_AUDIT_PASS_NOT_ACADEMIC",
           "publication_allowed":False,"slide_mapping_technically_verified":True,
           "sample_count":50,"passed_samples":50,
           "source_pdf_sha256":digest(src/"slides.pdf"),
           "source_shadow_wav_sha256":digest(shadow/"section25_corrected_shadow_UNAPPROVED.wav"),
           "video_sha256":digest(film/"corrected_slides_NO_WORD_HIGHLIGHTS_UNAPPROVED.mp4")}
    atomic_json(pixel/"pixel_audit_receipt.json",audit)
    return src,recovery,stage,sel,shadow,film,pixel

def test_real_source_bound_review_packet_uses_exact_script_and_unapproved_flags(tmp_path,monkeypatch):
    src,rec,stage,sel,shadow,film,pixel=_setup(tmp_path,monkeypatch)
    out=tmp_path/"review"
    result=p.prepare_corrected_pronunciation_packet(rec,stage,sel,shadow,film,pixel,out)
    assert result["audio_pairs"]==3 and result["manual_review_required"]
    assert result["publication_allowed"] is False
    assert len(list(out.glob("*.wav")))==6
    assert len(list(out.glob("*.png")))==3
    html=(out/"index.html").read_text(encoding="utf8")
    assert html.count("<audio controls")==6
    assert "Source slide number 5" in html
    assert "UNAPPROVED" in html and "c" in html
    manifest=json.loads((out/"listening_packet_receipt.json").read_text())
    assert manifest["phonetic_correctness_verified"] is False
    assert manifest["voice_consistency_verified"] is False
    assert manifest["publication_allowed"] is False
    assert digest(src/"slides.pdf")==manifest["source_pdf_sha256"]

@pytest.mark.parametrize("tamper",["video","pixel","approved","original","trial","script"])
def test_wrong_source_or_approval_cannot_build_review(tmp_path,monkeypatch,tamper):
    src,rec,stage,sel,shadow,film,pixel=_setup(tmp_path,monkeypatch)
    if tamper=="video":
        (film/"corrected_slides_NO_WORD_HIGHLIGHTS_UNAPPROVED.mp4").write_bytes(b"wrong")
    elif tamper=="pixel":
        path=pixel/"pixel_audit_receipt.json"
        obj=json.loads(path.read_text());obj["passed_samples"]=49
        atomic_json(path,obj)
    elif tamper=="approved":
        path=sel/"selection_receipt.json";obj=json.loads(path.read_text())
        obj["trials"][0]["phonetic_approved"]=True;atomic_json(path,obj)
    elif tamper=="original":
        (rec/"audio"/"slide5.wav").write_bytes(b"changed")
    elif tamper=="trial":
        (sel/"slide05_CDOT_UNAPPROVED.wav").write_bytes(b"changed")
    else:
        (src/"script_tts.json").write_text('{"wrong":true}')
    with pytest.raises((ValueError,OSError)):
        p.prepare_corrected_pronunciation_packet(rec,stage,sel,shadow,film,pixel,tmp_path/"review")
    assert not (tmp_path/"review").exists()

def test_protected_or_existing_review_path_rejected(tmp_path,monkeypatch):
    _src,rec,stage,sel,shadow,film,pixel=_setup(tmp_path,monkeypatch)
    out=tmp_path/"existing";out.mkdir()
    with pytest.raises(p.ListeningPacketError):
        p.prepare_corrected_pronunciation_packet(rec,stage,sel,shadow,film,pixel,out)
