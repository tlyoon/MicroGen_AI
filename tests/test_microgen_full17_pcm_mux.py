"""Tail-preserving full lecture remux shall fail closed without authentic receipts."""
import pytest
from microgen_full17_pcm_mux import remux_full_lecture_with_all_source_pcm,FullPCMError
from microgen_source_safe_orchestrator import OrchestratorError

def test_refuses_missing_workspace(tmp_path):
    with pytest.raises((FileNotFoundError,FullPCMError,OrchestratorError)):
        remux_full_lecture_with_all_source_pcm(tmp_path/"missing",ffmpeg="ffmpeg")

def test_refuses_fake_workspace_no_original_source(tmp_path):
    (tmp_path/"workspace_receipt.json").write_text('{"publication_permitted":true}')
    with pytest.raises((KeyError,FileNotFoundError,FullPCMError,OrchestratorError)):
        remux_full_lecture_with_all_source_pcm(tmp_path,ffmpeg="ffmpeg")

def test_never_infers_approved_video_from_existing_part(tmp_path):
    (tmp_path/"part01.mp4").write_bytes(b"not a source-bound video")
    with pytest.raises((KeyError,FileNotFoundError,FullPCMError,OrchestratorError)):
        remux_full_lecture_with_all_source_pcm(tmp_path,ffmpeg="ffmpeg")
