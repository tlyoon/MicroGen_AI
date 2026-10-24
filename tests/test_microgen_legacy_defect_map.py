import pytest
from microgen_legacy_defect_map import map_legacy_pronunciation_defects,DefectEvidenceError

def test_no_workspace_cannot_produce_fake_qa(tmp_path):
    dest=tmp_path/"report.json"
    with pytest.raises((FileNotFoundError,DefectEvidenceError)):
        map_legacy_pronunciation_defects(tmp_path/"absent",tmp_path/"asr.json",dest)
    assert not dest.exists()

@pytest.mark.parametrize("floor",[-.1,.2,1.1])
def test_no_weak_or_invalid_confidence_floor(tmp_path,floor):
    with pytest.raises((FileNotFoundError,DefectEvidenceError)):
        map_legacy_pronunciation_defects(tmp_path/"absent",tmp_path/"asr.json",
                                         tmp_path/"out.json",minimum_confidence=floor)
