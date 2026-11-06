"""Bounded end-to-end offline source/PDF -> cue TTS -> visible encoded MP4 test.

Run only with MICROGEN_MEDIA_INTEGRATION_TEST=1 and a local H.264 FFmpeg.
No Gemini calls, no textbook files, no publication, no release certification.
"""
import io
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image
import pytest

from test_microgen_timed_cue_tts import input_stage, sample_wav
from microgen_timed_cue_tts import produce_measured_cue_audio
from microgen_timed_highlight_contract import inspect_timed_highlights
from microgen_quality import sha256,check_video
from gen_video_v22 import main as render_video


@pytest.mark.skipif(os.environ.get("MICROGEN_MEDIA_INTEGRATION_TEST")!="1",
                    reason="opt-in 2.4-second media integration only")
def test_source_to_measured_cues_to_encoded_mp4(tmp_path,monkeypatch):
    binary=os.environ.get("MICROVID_FFMPEG") or shutil.which("ffmpeg")
    if not binary or not Path(binary).is_file():
        pytest.skip("Local H.264 FFmpeg unavailable")
    monkeypatch.setenv("MICROVID_FFMPEG",binary)
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS","1")
    source=input_stage(tmp_path)
    source_pdf_hash=sha256(source/"slides.pdf")
    cues=produce_measured_cue_audio(source,speak=sample_wav)
    assert cues["cue_count"]==4
    assert inspect_timed_highlights(source)["slide_count"]==2
    monkeypatch.chdir(source)
    render_video()
    measured=check_video(source/"slides.mp4",expected_seconds=2.4)
    assert 0<measured["seconds"]<600
    assert sha256(source/"slides.pdf")==source_pdf_hash

    def pixel_at(seconds,point):
        result=subprocess.run([
            binary,"-nostdin","-hide_banner","-loglevel","error",
            "-ss",str(seconds),"-i",str(source/"slides.mp4"),
            "-frames:v","1","-f","image2pipe","-vcodec","png","pipe:1",
        ],capture_output=True,check=True,timeout=45)
        image=Image.open(io.BytesIO(result.stdout)).convert("RGB")
        return image.getpixel(point)
    a=pixel_at(0.3,(900,245))
    b=pixel_at(0.9,(900,245))
    c=pixel_at(0.3,(900,370))
    d=pixel_at(0.9,(900,370))
    assert a[2]<b[2]-20
    assert d[2]<c[2]-20
    # Synthetic integration passing never turns private QA into publication.
    assert not (source/".microgen_autonomous_acceptance.json").exists()
