import pytest
from microgen_acoustic_math_anchors import match_acoustic_math_anchors,MathAnchorError

def test_incomplete_source_asr_rejected(tmp_path):
    with pytest.raises((FileNotFoundError,MathAnchorError)):
        match_acoustic_math_anchors(tmp_path/"missingmath.json",
            tmp_path/"missingaudio.json",tmp_path/"new.json")
    assert not (tmp_path/"new.json").exists()
