import pytest
from microgen_correction_selection import select_source_bound_trials,TrialSelectionError

def test_missing_recovery_source_blocks_trial_selection(tmp_path):
    out=tmp_path/"selected"
    with pytest.raises((FileNotFoundError,TrialSelectionError)):
        select_source_bound_trials(tmp_path/"missing",tmp_path/"review",out)
    assert not out.exists()

def test_existing_output_not_replaced(tmp_path):
    out=tmp_path/"selected";out.mkdir()
    (out/"keep").write_text("old")
    with pytest.raises((FileNotFoundError,TrialSelectionError)):
        select_source_bound_trials(tmp_path/"missing",tmp_path/"review",out)
    assert (out/"keep").read_text()=="old"
