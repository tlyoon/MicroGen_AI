"""Optional Windows FFmpeg integration: actually decode time-gated highlight frames.

Enable with MICROGEN_MEDIA_INTEGRATION_TEST=1. No network, cloud provider,
source PDF mutation, external publication, or downloaded model is involved.
"""
import io
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image
import pytest

from test_microgen_timed_highlight_contract import stage
from microgen_timed_highlight_contract import (
    inspect_timed_highlights, ffmpeg_highlight_filter,
)
from gen_video_v22 import _make_segment


@pytest.mark.skipif(os.environ.get("MICROGEN_MEDIA_INTEGRATION_TEST") != "1",
                    reason="Opt-in local H.264 video integration test")
def test_encoded_video_switches_highlight_on_measured_pcm_cues(
        tmp_path: Path, monkeypatch) -> None:
    ffmpeg_path = os.environ.get("MICROVID_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg_path or not Path(ffmpeg_path).is_file():
        pytest.skip("Local H.264-capable ffmpeg executable unavailable")
    monkeypatch.setenv("MICROVID_FFMPEG", ffmpeg_path)
    work = stage(tmp_path)
    original = (work / "slide1.wav").read_bytes()
    inspected = inspect_timed_highlights(work)
    filt = ffmpeg_highlight_filter(inspected, 1)
    target = work / "highlighted.mp4"
    _make_segment(work / "slide1.pdf", work / "slide1.wav", target,
                  highlight_filter=filt)

    def decoded_frame(seconds: float):
        cmd = [
            ffmpeg_path, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-ss", str(seconds), "-i", str(target), "-frames:v", "1",
            "-f", "image2pipe", "-vcodec", "png", "pipe:1",
        ]
        pixels = subprocess.run(cmd, capture_output=True,
                                check=True, timeout=45).stdout
        return Image.open(io.BytesIO(pixels)).convert("RGB")

    first = decoded_frame(0.3)
    second = decoded_frame(1.0)
    # Chosen inside the original PDF text rectangles but away from glyphs.
    first_region = (900, 245)
    second_region = (900, 370)
    assert first.getpixel(first_region)[2] < second.getpixel(first_region)[2] - 20
    assert second.getpixel(second_region)[2] < first.getpixel(second_region)[2] - 20
    assert (work / "slide1.wav").read_bytes() == original
    assert inspected["visual_highlight_rendering_verified"] is False
    # A synthetic pixel-transition probe never issues a release receipt.
    assert not (work / ".microgen_autonomous_acceptance.json").exists()
