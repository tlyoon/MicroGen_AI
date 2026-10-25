"""Independent decoded word-overlay evidence never certifies spoken mathematics."""
import json
from pathlib import Path
import pytest
import pymupdf as fitz
from PIL import ImageDraw

import microgen_corrected_word_pixel_qa as qa
from test_microgen_corrected_word_video import _fixture
from microgen_source_safe_orchestrator import digest,atomic_json
from microgen_audio_cue_binding import _verified_audio_rows,bind_cues_to_current_audio


def _ready(tmp_path,monkeypatch):
    source,stage,selection,shadow,asr,ff=_fixture(tmp_path,monkeypatch)
    # Give the synthetic slide enough clock after its cue to check a
    # full-frame post-cue guard; real slide 5 has 310 ms.
    src,_,intervals=_verified_audio_rows(stage)
    with fitz.open(source/"slides.pdf") as pdf:
        box=list(pdf[4].get_text("words")[0][:4])
    start=intervals[4]["start_seconds"]
    cues=bind_cues_to_current_audio(stage,[{
        "slide":5,"text":"source","box":box,
        "local_start":.01,"local_end":.10,
        "start_seconds":start+.01,"end_seconds":start+.10}],
        derivation="CURRENT_STAGE_OFFLINE_ASR_NOT_PHONETIC_GROUND_TRUTH")
    atomic_json(stage/"cues.json",cues)
    folder=tmp_path/"current_overlay";folder.mkdir()
    film=folder/"section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4"
    film.write_bytes(b"synthetic movie")
    plan=qa._validated_inputs(stage,selection,shadow,asr)[0]
    receipt={"status":"ASR_WORD_HIGHLIGHT_TECHNICAL_CANDIDATE_NOT_APPROVED",
             "publication_allowed":False,
             "word_highlight_pixels_independently_verified":False,
             "video_sha256":digest(film),
             "source_pdf_sha256":digest(source/"slides.pdf"),
             "cue_manifest_sha256":digest(stage/"cues.json"),
             "recognition_report_sha256":digest(asr),
             "shadow_wav_sha256":digest(plan["shadow_wav"]),
             "corrected_pcm_sha256":plan["pcm"]["pcm_sha256"],
             "candidate_cues":1,"fps":8,"audio_pcm_identical":True}
    atomic_json(folder/"word_highlight_candidate_receipt.json",receipt)
    refs,transforms,_=qa._pdf_refs(source)
    cue=qa._validated_inputs(stage,selection,shadow,asr)[2][5][0]
    box=qa._bbox(cue,transforms[4])
    def sample(movie,ffmpeg,time,scratch):
        ref=refs[4].copy()
        if cue["start"]<=time<cue["end"]:
            draw=ImageDraw.Draw(ref)
            draw.rectangle(box,fill=(250,195,50),outline=(240,80,20),width=3)
        return ref
    monkeypatch.setattr(qa,"_capture",sample)
    return source,stage,selection,shadow,asr,folder,ff,refs,box


def test_positive_and_negative_cue_pixels_are_independently_detected(tmp_path,monkeypatch):
    src,stage,sel,shadow,asr,film,ff,refs,box=_ready(tmp_path,monkeypatch)
    out=tmp_path/"fresh_qa"
    result=qa.audit_current_word_highlights(stage,sel,shadow,asr,film,out,ffmpeg=ff)
    assert result["positive"]==1 and result["negative"]==1
    assert result["failed"]==0 and result["status"].endswith("TECHNICAL_PASS")
    report=json.loads((out/"word_pixel_audit_receipt.json").read_text())
    assert report["actual_overlay_pixels_verified"] is True
    assert report["phonetic_correctness_verified"] is False
    assert report["figure_math_semantics_verified"] is False
    assert report["publication_allowed"] is False
    assert len(report["samples"])==2


def test_missing_highlight_yields_explicit_failure_report(tmp_path,monkeypatch):
    src,stage,sel,shadow,asr,film,ff,refs,box=_ready(tmp_path,monkeypatch)
    monkeypatch.setattr(qa,"_capture",lambda *args:refs[4])
    out=tmp_path/"audit"
    result=qa.audit_current_word_highlights(stage,sel,shadow,asr,film,out,ffmpeg=ff)
    assert result["failed"]>0
    assert result["status"]=="CURRENT_ASR_OVERLAY_PIXEL_AUDIT_NEEDS_REVIEW"
    assert json.loads((out/"word_pixel_audit_receipt.json").read_text())[
        "actual_overlay_pixels_verified"] is False


@pytest.mark.parametrize("mutation",["movie","source","cue","asr","forge","weakpcm"])
def test_unbound_input_rejected_before_any_pixel_stage(tmp_path,monkeypatch,mutation):
    src,stage,sel,shadow,asr,film,ff,refs,box=_ready(tmp_path,monkeypatch)
    if mutation=="movie":
        (film/"section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4").write_bytes(b"change")
    if mutation=="source":
        (src/"slides.pdf").write_bytes(b"change")
    if mutation=="cue":
        p=stage/"cues.json";r=json.loads(p.read_text())
        r["derivation"]="OLD_TIMING";atomic_json(p,r)
    if mutation=="asr":
        p=asr;r=json.loads(p.read_text())
        r["stage_audio_bindings"][0]["wav_sha256"]="0"*64;atomic_json(p,r)
    if mutation in ("forge","weakpcm"):
        p=film/"word_highlight_candidate_receipt.json";r=json.loads(p.read_text())
        if mutation=="forge":r["word_highlight_pixels_independently_verified"]=True
        else:r["corrected_pcm_sha256"]="f"*64
        atomic_json(p,r)
    out=tmp_path/"audit"
    with pytest.raises((ValueError,OSError)):
        qa.audit_current_word_highlights(stage,sel,shadow,asr,film,out,ffmpeg=ff)
    assert not out.exists()


def test_existing_audit_path_preserved_without_writes(tmp_path,monkeypatch):
    src,stage,sel,shadow,asr,film,ff,refs,box=_ready(tmp_path,monkeypatch)
    out=tmp_path/"exists";out.mkdir()
    with pytest.raises(qa.HighlightPixelQAError):
        qa.audit_current_word_highlights(stage,sel,shadow,asr,film,out,ffmpeg=ff)


def test_missing_8fps_frame_center_is_inconclusive_not_accepted(tmp_path,monkeypatch):
    src,stage,sel,shadow,asr,film,ff,refs,box=_ready(tmp_path,monkeypatch)
    from microgen_audio_cue_binding import bind_cues_to_current_audio,_verified_audio_rows
    _,_,intervals=_verified_audio_rows(stage)
    start=intervals[4]["start_seconds"]
    cue=json.loads((stage/"cues.json").read_text())["elements"][0]
    new={**cue,
         "local_start":.001,"local_end":.011,
         "start_seconds":start+.001,"end_seconds":start+.011}
    bound=bind_cues_to_current_audio(stage,[new],
          derivation="CURRENT_STAGE_OFFLINE_ASR_NOT_PHONETIC_GROUND_TRUTH")
    atomic_json(stage/"cues.json",bound)
    rp=film/"word_highlight_candidate_receipt.json"
    receipt=json.loads(rp.read_text())
    receipt["cue_manifest_sha256"]=digest(stage/"cues.json")
    atomic_json(rp,receipt)
    result=qa.audit_current_word_highlights(stage,sel,shadow,asr,film,
                                            tmp_path/"pixel_out",ffmpeg=ff)
    assert result["missing_frames"]==1
    assert result["status"]=="CURRENT_ASR_OVERLAY_PIXEL_AUDIT_NEEDS_REVIEW"
    assert json.loads((tmp_path/"pixel_out"/"word_pixel_audit_receipt.json").read_text())[
        "actual_overlay_pixels_verified"] is False
