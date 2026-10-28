import pytest
from microgen_independent_review_packet import prepare_full_lecture_review_packet,IndependentPacketError

def test_missing_evidence_blocks_release_packet(tmp_path):
    out=tmp_path/"review"
    with pytest.raises((FileNotFoundError,IndependentPacketError)):
        prepare_full_lecture_review_packet(
            tmp_path/"no_recovery",tmp_path/"math.json",tmp_path/"figure.json",
            tmp_path/"crops",tmp_path/"defect.json",tmp_path/"cue.json",
            tmp_path/"shadow",out)
    assert not out.exists()
