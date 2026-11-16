"""V6 no-duplicate-paid-work checkpoint loader and crash-write regressions.

Checks real batch checkpoint load/save code: a missing checkpoint means a new
stage; a damaged or half-written checkpoint means execution is uncertain,
never 'completed={}' and never permission to rerun a paid model.
"""
import json
from pathlib import Path

import pytest
import microgen_batch as batch


@pytest.mark.parametrize("raw",[
    "{", '{"completed":',
    "null", "[]", '"not-an-object"',
    '{"completed":null}', '{"completed":[]}',
    '{"completed":42}', '{"completed":{"tts":false}}',
    '{"completed":{"tts":null}}',
    '{"last_error":"acoustic review failed"}',
    '{"inflight_provider_stage":"tts"}',
    '{"dependency_fingerprints":[]}',
])
def test_invalid_existing_checkpoint_cannot_reset_payment_history(tmp_path,raw):
    path=tmp_path/".microgen_checkpoint.json"
    path.write_text(raw,encoding="utf8")
    original=path.read_bytes()
    with pytest.raises(batch.CheckpointIntegrityError,match="AMBIGUOUS_CHECKPOINT_HOLD"):
        batch.load_checkpoint(path)
    assert path.read_bytes()==original
    assert not path.with_suffix(".tmp").exists()


def test_new_stage_missing_checkpoint_may_initialize_once(tmp_path):
    path=tmp_path/".microgen_checkpoint.json"
    assert batch.load_checkpoint(path)=={"completed":{}}
    assert not path.exists()
    cp={"completed":{},"package_commit":"f"*40}
    batch.save_checkpoint(path,cp)
    assert batch.load_checkpoint(path)==cp


@pytest.mark.parametrize("has_committed", [False,True])
def test_crash_during_atomic_checkpoint_write_fails_closed(tmp_path,has_committed):
    path=tmp_path/".microgen_checkpoint.json"
    original={"completed":{"tts":"2026-11-16T01:00:00+00:00"},
              "inflight_provider_stage":{"stage":"acoustic_qa"}}
    if has_committed:
        batch.save_checkpoint(path,original)
    tmp=path.with_suffix(".tmp")
    tmp.write_bytes(b'{"completed":{"acoustic_qa":')
    first=path.read_bytes() if has_committed else None
    with pytest.raises(batch.CheckpointIntegrityError,match="AMBIGUOUS_CHECKPOINT_HOLD"):
        batch.load_checkpoint(path)
    with pytest.raises(batch.CheckpointIntegrityError,match="AMBIGUOUS_CHECKPOINT_HOLD"):
        batch.save_checkpoint(path,{"completed":{}})
    assert tmp.is_file()
    if has_committed: assert path.read_bytes()==first
    else: assert not path.exists()


def test_invalid_existing_json_does_not_disappear_when_save_requested(tmp_path):
    path=tmp_path/".microgen_checkpoint.json"
    path.write_bytes(b'{broken')
    with pytest.raises(batch.CheckpointIntegrityError):
        batch.load_checkpoint(path)
    assert path.read_bytes()==b'{broken'


@pytest.mark.parametrize("content",[
    {"completed":{"science_qa":"2026-11-16T02:00:00Z"},
     "inflight_provider_stage":{"stage":"acoustic_qa"},
     "last_error":{"stage":"tts","recovery_disposition":"DETERMINISTIC_HOLD"}},
    {"completed":{"figure_extraction":"done","figure_mapping":"done",
                  "tts":"done","acoustic_qa":"done"},
     "dependency_fingerprints":{"acoustic_qa":"f"*64}},
    {"last_error":{"stage":"acoustic_qa"}},  # legacy/minimal checkpoint
])
def test_valid_historical_and_minimal_checkpoint_preserved(tmp_path,content):
    path=tmp_path/".microgen_checkpoint.json"
    batch.save_checkpoint(path,content)
    assert batch.load_checkpoint(path)=={**content,
                                        "completed":content.get("completed",{})}
    assert not path.with_suffix(".tmp").exists()


def test_repeated_successful_checkpoint_updates_do_not_require_manual_proceed(tmp_path):
    path=tmp_path/".microgen_checkpoint.json"
    batch.save_checkpoint(path,{"completed":{"narration":"done"}})
    cp=batch.load_checkpoint(path)
    cp["completed"]["science_qa"]="accepted"
    batch.save_checkpoint(path,cp)
    cp=batch.load_checkpoint(path)
    cp["completed"]["tts"]="accepted"
    batch.save_checkpoint(path,cp)
    assert list(batch.load_checkpoint(path)["completed"])==[
        "narration","science_qa","tts"
    ]
    assert not path.with_suffix(".tmp").exists()


def test_unknown_untrusted_checkpoint_state_blocks_before_provider(tmp_path):
    path=tmp_path/".microgen_checkpoint.json"
    path.write_bytes(b'{"completed":[]}')
    fake_paid_calls=[]
    def should_not_run():
        fake_paid_calls.append(1)
    with pytest.raises(batch.CheckpointIntegrityError):
        batch.load_checkpoint(path)
        should_not_run()
    assert fake_paid_calls==[]


def test_invalid_writer_data_does_not_publish_a_checkpoint(tmp_path):
    path=tmp_path/".microgen_checkpoint.json"
    with pytest.raises(batch.CheckpointIntegrityError):
        batch.save_checkpoint(path,{"completed":["tts"]})
    assert not path.exists()


def test_symlink_checkpoint_denied_where_supported(tmp_path):
    source=tmp_path/"hidden.json"
    source.write_text('{"completed":{}}')
    link=tmp_path/".microgen_checkpoint.json"
    try:
        link.symlink_to(source)
    except (OSError,NotImplementedError):
        pytest.skip("symlink privilege unavailable on Windows host")
    with pytest.raises(batch.CheckpointIntegrityError):
        batch.load_checkpoint(link)


def test_fail_on_checkpoint_directory_instead_of_reset(tmp_path):
    path=tmp_path/".microgen_checkpoint.json"
    path.mkdir()
    with pytest.raises(batch.CheckpointIntegrityError,match="not a file"):
        batch.load_checkpoint(path)


def test_existing_corrupted_workdir_is_blocked_before_stage_copy_or_paid_call(
        tmp_path,monkeypatch):
    src=tmp_path/"sources"
    (src/"2"/"2.7").mkdir(parents=True)
    (src/"2"/"2.7"/"source.pdf").write_bytes(b"genuine_source_fixture")
    work=tmp_path/"runs"
    stage=work/"2.7"
    stage.mkdir(parents=True)
    cp=stage/".microgen_checkpoint.json"
    cp.write_bytes(b'{"completed":{"tts":')
    calls=[]
    monkeypatch.setattr(batch,"copy_repo_into_stage",
                        lambda *args:calls.append("copied"))
    with pytest.raises(batch.CheckpointIntegrityError,match="AMBIGUOUS_CHECKPOINT_HOLD"):
        batch.prepare_stage(tmp_path,src,work,"2.7",0,"f"*40)
    assert calls==[]
    assert not (stage/"source.pdf").exists()
    assert cp.read_bytes()==b'{"completed":{"tts":'
