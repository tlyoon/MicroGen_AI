"""Real pixel-interval QA checks fail closed and do not certify word meaning."""
import json
import wave
from pathlib import Path
import pytest
import pymupdf as fitz
from microgen_source_safe_orchestrator import digest
from microgen_quality import check_video
from microgen_production_bridge import render_staged_highlight
from microgen_offline_highlight_pixel_qa import (
    verify_highlight_pixels,PixelEvidenceError
)

def _fixture(tmp_path):
    from imageio_ffmpeg import get_ffmpeg_exe
    source=tmp_path/"source.pdf"
    with fitz.open() as doc:
        page=doc.new_page(width=640,height=360)
        page.insert_text((45,60),"formal",fontsize=20)
        doc.save(source)
    with fitz.open(source) as doc:
        box=list(doc[0].get_text("words")[0][:4])
    audio=tmp_path/"audio.wav"
    with wave.open(str(audio),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
        w.writeframes(bytes(16000*2))
    stage=tmp_path/"stage";(stage/"inputs").mkdir(parents=True)
    (stage/"media").mkdir()
    page=stage/"inputs"/"page.pdf"
    page.write_bytes(source.read_bytes())
    video=stage/"media"/"candidate.mp4"
    cues=[{"box":box,"text":"formal","start_seconds":.25,"end_seconds":.75}]
    render_staged_highlight(page,audio,cues,video,ffmpeg_exe=get_ffmpeg_exe())
    (stage/"candidate_receipt.json").write_text(json.dumps({
        "slide":1,"publication_allowed":False,"cues":cues,
        "source_pdf_sha256":digest(source),"video_sha256":digest(video),
        "video_seconds":check_video(video)["seconds"]}),encoding="utf8")
    return stage,source,video,get_ffmpeg_exe()

def test_highlight_detected_at_measured_timestamp_not_publication(tmp_path):
    stage,source,video,ff=_fixture(tmp_path)
    output=stage/"pixel_verified.json"
    status=verify_highlight_pixels(stage,source,ff,output)
    assert status["verified_cues"]==1
    result=json.loads(output.read_text())
    assert result["checks"][0]["mean_rgb_difference"]>2.5
    assert not result["math_figure_semantics_certified"]
    assert not result["publication_allowed"]

def test_changed_video_is_rejected(tmp_path):
    stage,source,video,ff=_fixture(tmp_path)
    with video.open("ab") as stream:stream.write(b"changed")
    with pytest.raises(PixelEvidenceError):
        verify_highlight_pixels(stage,source,ff,stage/"out.json")

def test_pixel_receipt_overwrite_is_rejected(tmp_path):
    stage,source,video,ff=_fixture(tmp_path)
    output=stage/"out.json";output.write_text("previous")
    with pytest.raises(PixelEvidenceError):
        verify_highlight_pixels(stage,source,ff,output)
