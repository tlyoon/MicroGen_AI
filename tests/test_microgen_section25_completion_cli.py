"""CLI and release gate must abstain absent genuine source-bound QA evidence."""
import pytest
import microgen_section25_completion_cli as cli

def test_release_gate_requires_real_original_stage(tmp_path):
    with pytest.raises((FileNotFoundError,ValueError)):
        cli.collect_release_blockers(tmp_path/"missing",pixel_report=tmp_path/"missing.json")

def test_prepare_requires_explicit_manifest(tmp_path):
    with pytest.raises(SystemExit) as e:
        cli.main(["prepare","--stage",str(tmp_path/"stage")])
    assert e.value.code==2
    assert not (tmp_path/"stage").exists()

def test_release_audit_requires_independent_video_pixel_receipt(tmp_path):
    with pytest.raises(SystemExit) as e:
        cli.main(["audit","--stage",str(tmp_path/"stage")])
    assert e.value.code==2

def test_render_requires_explicit_ffmpeg(tmp_path):
    with pytest.raises(SystemExit) as e:
        cli.main(["render","--stage",str(tmp_path/"stage")])
    assert e.value.code==2
