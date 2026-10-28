"""Whole §2.5 combined-video visual proof is never semantic publication approval."""
import pytest
from microgen_full17_pixel_acceptance import (
    WholeVideoPixelError,check_all_full17_highlights
)

def test_refuses_missing_stage(tmp_path):
    with pytest.raises((FileNotFoundError,WholeVideoPixelError)):
        check_all_full17_highlights(tmp_path/"missing",tmp_path/"report.json",ffmpeg="ffmpeg")
    assert not (tmp_path/"report.json").exists()

@pytest.mark.parametrize("threshold",[0,-2,101,float("nan")])
def test_rejects_unbounded_pixel_floor(tmp_path,threshold):
    with pytest.raises((FileNotFoundError,WholeVideoPixelError)):
        check_all_full17_highlights(tmp_path/"missing",tmp_path/"report.json",
                                      ffmpeg="ffmpeg",threshold=threshold)

def test_never_overwrites_existing_evidence(tmp_path):
    out=tmp_path/"report.json";out.write_text("old approved")
    with pytest.raises((FileNotFoundError,WholeVideoPixelError)):
        check_all_full17_highlights(tmp_path/"missing",out,ffmpeg="ffmpeg")
    assert out.read_text()=="old approved"
