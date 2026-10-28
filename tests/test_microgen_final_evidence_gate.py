import pytest
from microgen_final_evidence_gate import audit_complete_section25,FinalEvidenceError

def test_cannot_invent_technical_release_evidence(tmp_path):
    with pytest.raises((FileNotFoundError,FinalEvidenceError)):
        audit_complete_section25(
          original_recovery=tmp_path/"absent",
          full_video_stage=tmp_path/"stage",
          phonetic_risks=tmp_path/"phonetic.json",
          shadow_audio=tmp_path/"shadow",shadow_seams=tmp_path/"seam.json",
          math_regions=tmp_path/"math.json",figure_regions=tmp_path/"figure.json",
          math_anchors=tmp_path/"anchor.json",figure_crops=tmp_path/"crop",
          independent_packet=tmp_path/"review",full_video_pixels=tmp_path/"pixels.json",
          output=tmp_path/"report.json")
    assert not (tmp_path/"report.json").exists()
