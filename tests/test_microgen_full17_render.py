"""Safe failure checks for the full recovered-audio movie stage."""
import pytest
from microgen_full17_render import (
    FullRenderError,create_full17_render_workspace,render_complete_full17
)

def test_missing_source_and_no_stage_writes(tmp_path):
    destination=tmp_path/"new_stage"
    with pytest.raises((FileNotFoundError,FullRenderError)):
        create_full17_render_workspace(tmp_path/"absent_manifest.json",destination)
    assert not destination.exists()

def test_invalid_manifest_status_abstains(tmp_path):
    from microgen_source_safe_orchestrator import atomic_json
    p=tmp_path/"manifest.json"
    atomic_json(p,{"status":"PUBLISH_APPROVED","publication_allowed":True,"slide_count":17})
    stage=tmp_path/"stage"
    with pytest.raises(FullRenderError):
        create_full17_render_workspace(p,stage)
    assert not stage.exists()

def test_missing_source_receipt_refuses_render(tmp_path):
    with pytest.raises((FileNotFoundError,FullRenderError)):
        render_complete_full17(tmp_path/"missing",ffmpeg="ffmpeg")
