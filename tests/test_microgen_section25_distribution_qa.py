"""A delivery-format candidate must not imply lecture release or source mutation."""
import pytest
from microgen_section25_distribution_qa import (
    DeliveryCandidateError,make_standard_aac_candidate
)

def test_absent_lossless_receipt_blocks_mp4_conversion(tmp_path):
    with pytest.raises((FileNotFoundError,DeliveryCandidateError)):
        make_standard_aac_candidate(tmp_path/"missing",ffmpeg="ffmpeg")

def test_unverified_stage_refuses_delivery_candidate(tmp_path):
    from pathlib import Path
    stage=tmp_path/"fake"
    stage.mkdir()
    (stage/"workspace_receipt.json").write_text('{"publication_permitted":true}')
    with pytest.raises((FileNotFoundError,DeliveryCandidateError,ValueError)):
        make_standard_aac_candidate(stage,ffmpeg="ffmpeg")
    assert not (stage/"standard_h264_aac_candidate").exists()
