import pytest
from microgen_shadow_audio_diagnostics import inspect_shadow_seams,ShadowSeamError

@pytest.mark.parametrize("window",[0,-1,2])
def test_no_unbounded_analysis_window(tmp_path,window):
    with pytest.raises((FileNotFoundError,ShadowSeamError)):
        inspect_shadow_seams(tmp_path/"absent",tmp_path/"report.json",window_seconds=window)
    assert not (tmp_path/"report.json").exists()
