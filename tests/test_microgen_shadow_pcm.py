import pytest
from microgen_shadow_pcm import make_corrected_shadow_pcm,ShadowAudioError

def test_absent_source_blocks_shadow(tmp_path):
    with pytest.raises((FileNotFoundError,ShadowAudioError)):
        make_corrected_shadow_pcm(tmp_path/"missing",tmp_path/"selected",
                                  tmp_path/"shadow",ffmpeg="ffmpeg")
    assert not (tmp_path/"shadow").exists()

def test_existing_output_never_overwritten(tmp_path):
    out=tmp_path/"shadow";out.mkdir();(out/"old").write_text("retain")
    with pytest.raises((FileNotFoundError,ShadowAudioError)):
        make_corrected_shadow_pcm(tmp_path/"missing",tmp_path/"selected",out,ffmpeg="ffmpeg")
    assert (out/"old").read_text()=="retain"
