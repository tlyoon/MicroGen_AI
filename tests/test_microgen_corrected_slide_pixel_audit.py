"""Verified source-page frame sampling; fake frames cannot imply academic QA."""
import json
from pathlib import Path
from types import SimpleNamespace
import pymupdf as fitz
import pytest
from microgen_source_safe_orchestrator import atomic_json,digest
import microgen_corrected_slide_pixel_audit as a
from microgen_corrected_slide_clock import build_slide_clock
from test_microgen_corrected_slide_clock import _ready

def _case(tmp_path,monkeypatch):
    src,stage,selection,shadow=_ready(tmp_path)
    film=tmp_path/"candidate";film.mkdir()
    movie=film/"corrected_slides_NO_WORD_HIGHLIGHTS_UNAPPROVED.mp4"
    movie.write_bytes(b"technical movie")
    plan=build_slide_clock(stage,selection,shadow)
    atomic_json(film/"corrected_slide_clock_receipt.json",{
        "status":"CORRECTED_SLIDE_CLOCK_NOT_SEMANTICALLY_APPROVED",
        "publication_allowed":False,"word_highlights_present":False,
        "video_sha256":digest(movie),
        "source_pdf_sha256":digest(src/"slides.pdf"),
        "shadow_wav_sha256":digest(plan["shadow_wav"]),
        "slides":plan["segments"],"audio_seconds":plan["audio_seconds"]})
    ff=tmp_path/"ffmpeg.exe";ff.write_bytes(b"fake")
    def fake_capture(argv,**kwargs):
        name=Path(argv[-1]).stem
        if name.startswith("interior_"):index=int(name.split("_")[-1])
        elif name.startswith("before_"):index=int(name.split("_")[1])
        elif name.startswith("after_"):index=int(name.split("_")[-1])
        else:index=17
        with fitz.open(src/"slides.pdf") as pdf:
            a._reference(pdf[index-1]).save(argv[-1])
        return SimpleNamespace(returncode=0,stderr=b"")
    monkeypatch.setattr(a.subprocess,"run",fake_capture)
    return src,stage,selection,shadow,film,ff

def test_all_50_independently_sampled_synthetic_frames_match(tmp_path,monkeypatch):
    src,stage,sel,shadow,film,ff=_case(tmp_path,monkeypatch)
    result=a.audit_corrected_slide_pixels(stage,sel,shadow,film,
           tmp_path/"audit",ffmpeg=ff)
    assert result["samples"]==50
    assert result["correct"]==50 and result["slide_pixel_pass"] is True
    receipt=json.loads((tmp_path/"audit"/"pixel_audit_receipt.json").read_text())
    assert receipt["word_highlights_verified"] is False
    assert receipt["mathematical_figure_semantics_verified"] is False
    assert receipt["publication_allowed"] is False

def test_wrong_slide_pixels_are_rejected_not_approved(tmp_path,monkeypatch):
    src,stage,sel,shadow,film,ff=_case(tmp_path,monkeypatch)
    def wrong(argv,**kwargs):
        with fitz.open(src/"slides.pdf") as pdf:
            a._reference(pdf[16]).save(argv[-1])
        return SimpleNamespace(returncode=0,stderr=b"")
    monkeypatch.setattr(a.subprocess,"run",wrong)
    result=a.audit_corrected_slide_pixels(stage,sel,shadow,film,
           tmp_path/"audit",ffmpeg=ff)
    assert not result["slide_pixel_pass"] and result["correct"]<17
    assert (tmp_path/"audit"/"pixel_audit_receipt.json").is_file()

@pytest.mark.parametrize("tamper",["video","pdf","receipt","selected"])
def test_unbound_input_refused_before_pixel_io(tmp_path,monkeypatch,tamper):
    src,stage,sel,shadow,film,ff=_case(tmp_path,monkeypatch)
    if tamper=="video":
        (film/"corrected_slides_NO_WORD_HIGHLIGHTS_UNAPPROVED.mp4").write_bytes(b"tamper")
    elif tamper=="pdf": (src/"slides.pdf").write_bytes(b"tamper")
    elif tamper=="receipt":
        p=film/"corrected_slide_clock_receipt.json"
        val=json.loads(p.read_text());val["publication_allowed"]=True;atomic_json(p,val)
    else:
        p=sel/"selection_receipt.json";val=json.loads(p.read_text())
        val["modified"]="late";atomic_json(p,val)
    with pytest.raises((ValueError,OSError)):
        a.audit_corrected_slide_pixels(stage,sel,shadow,film,tmp_path/"audit",ffmpeg=ff)
    assert not (tmp_path/"audit").exists()

def test_audit_never_reuses_a_previous_destination(tmp_path,monkeypatch):
    _,stage,sel,shadow,film,ff=_case(tmp_path,monkeypatch)
    out=tmp_path/"existing";out.mkdir()
    with pytest.raises(a.SlidePixelAuditError):
        a.audit_corrected_slide_pixels(stage,sel,shadow,film,out,ffmpeg=ff)
