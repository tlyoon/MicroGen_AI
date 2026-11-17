"""Regression: old HP checkpoints said 'unknown' while grants pinned real Git SHA.

Test both normal new-stage commit propagation and exact historical Git-blob
attestation before any old source/PCM can be reused. No paid/API requests.
"""
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import microgen_batch as batch
import microgen_verified_tts_reuse as reuse


SHA="a"*40


def test_normal_standing_private_checkpoint_pins_verified_git_head(monkeypatch,tmp_path):
    args=SimpleNamespace(
        repo=tmp_path,commit="unknown",standing_private_development=True)
    invoked=[]
    def checked(repo,*,expected_commit):
        invoked.append((repo,expected_commit))
        return SHA
    monkeypatch.setattr(batch,"inspect_local_checkout",checked)
    assert batch.pin_standing_private_revision(args)==SHA
    assert args.commit==SHA
    assert invoked==[(tmp_path,"unknown")]


@pytest.mark.parametrize("starting",["unknown",SHA])
def test_explicit_pinned_revision_revalidated_before_any_paid_stage(
        monkeypatch,tmp_path,starting):
    args=SimpleNamespace(repo=tmp_path,commit=starting,
                         standing_private_development=True)
    monkeypatch.setattr(batch,"inspect_local_checkout",
                        lambda repo,*,expected_commit:
                        SHA if expected_commit in ("unknown",SHA) else "invalid")
    assert batch.pin_standing_private_revision(args)==SHA


def test_nonstanding_scope_cannot_claim_private_checkpoint_pin(tmp_path):
    args=SimpleNamespace(repo=tmp_path,commit="unknown",
                         standing_private_development=False)
    with pytest.raises(RuntimeError,match="outside standing scope"):
        batch.pin_standing_private_revision(args)
    assert args.commit=="unknown"


def test_dirty_or_wrong_commit_never_repaired_into_a_grant(monkeypatch,tmp_path):
    args=SimpleNamespace(repo=tmp_path,commit="unknown",
                         standing_private_development=True)
    def unsafe(*a,**k):
        raise RuntimeError("checkout dirty")
    monkeypatch.setattr(batch,"inspect_local_checkout",unsafe)
    with pytest.raises(RuntimeError,match="dirty"):
        batch.pin_standing_private_revision(args)
    assert args.commit=="unknown"


def historical_fixture(tmp_path):
    old=tmp_path/"private"/"2.7"
    old.mkdir(parents=True)
    src=old/"source.pdf"
    src.write_bytes(b"synthetic-source")
    runner=old/"microgen_batch.py"
    runner.write_bytes(b"print('verified')\r\n")
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    grant={"scope":{"code_revision":SHA,"source_sha256":digest(src),
                    "work_root":str(old.parent),"host":"hp"}}
    checkpoint={"package_commit":"unknown",
                "inflight_provider_stage":{"stage":"acoustic_qa",
                "source_sha256":digest(src),
                "runner_sha256":digest(runner)},
                "completed":{"tts":"2026-11-17T12:00:00Z"}}
    return old,grant,checkpoint


def fake_git(monkeypatch,raw=b"print('verified')\n",code=0):
    commands=[]
    def run(args,**kwargs):
        commands.append((args,kwargs))
        return SimpleNamespace(returncode=code,stdout=raw)
    monkeypatch.setattr(reuse.subprocess,"run",run)
    return commands


def test_legacy_cp_unknown_can_be_verified_using_exact_git_blob(monkeypatch,tmp_path):
    old,grant,cp=historical_fixture(tmp_path)
    calls=fake_git(monkeypatch)
    assert reuse._legacy_checkpoint_commit_attested(old,grant,cp) is True
    assert len(calls)==1
    assert calls[0][0][-1]==SHA+":microgen_batch.py"
    assert calls[0][1]["timeout"]==20
    assert calls[0][1]["stdin"] is not None


@pytest.mark.parametrize("damage",[
    "source", "runner", "original_sha", "source_sha",
    "declared_git_sha", "wrong_stage", "unaccounted_send",
    "missing_marker", "unknown_stage_code", "symlinked_runner",
])
def test_old_ambiguous_or_modified_media_never_reused(
        monkeypatch,tmp_path,damage):
    old,grant,cp=historical_fixture(tmp_path)
    fake_git(monkeypatch)
    if damage=="source":
        (old/"source.pdf").write_bytes(b"changed")
    elif damage=="runner":
        (old/"microgen_batch.py").write_bytes(b"print('changed')")
    elif damage=="original_sha":
        cp["inflight_provider_stage"]["runner_sha256"]="f"*64
    elif damage=="source_sha":
        cp["inflight_provider_stage"]["source_sha256"]="f"*64
    elif damage=="declared_git_sha":
        grant["scope"]["code_revision"]="not-a-commit"
    elif damage=="wrong_stage":
        cp["inflight_provider_stage"]["stage"]="tts"
    elif damage=="unaccounted_send":
        cp["inflight_provider_stage"]["stage"]="unknown"
    elif damage=="missing_marker":
        cp["inflight_provider_stage"]=None
    elif damage=="unknown_stage_code":
        cp["package_commit"]="an-untrusted-value"
    elif damage=="symlinked_runner":
        runner=old/"microgen_batch.py"
        runner.unlink()
        target=old/"target.py"
        target.write_text("print('verified')")
        try: runner.symlink_to(target)
        except (OSError,NotImplementedError):
            pytest.skip("symlink permission unavailable")
    assert reuse._legacy_checkpoint_commit_attested(old,grant,cp) is False


@pytest.mark.parametrize("git_code,git_blob",[
    (1,b""), (0,b"print('unrelated')\n"), (0,b""),
])
def test_git_object_missing_or_mismatched_rejects_legacy_tts(
        monkeypatch,tmp_path,git_code,git_blob):
    old,grant,cp=historical_fixture(tmp_path)
    fake_git(monkeypatch,raw=git_blob,code=git_code)
    assert reuse._legacy_checkpoint_commit_attested(old,grant,cp) is False


def test_real_hp_source_bound_audio_reuse_is_verified_read_only():
    source=os.environ.get("MICROGEN_HP_PRIVATE_TTS_LEGACY_STAGE")
    if not source:
        pytest.skip("read-only real HP source must be selected explicitly")
    old=Path(source)
    grant=json.loads((old.parent/reuse.OWNER).read_text(encoding="utf8"))
    cp=json.loads((old/".microgen_checkpoint.json").read_text(encoding="utf8"))
    original={
      name:reuse._sha(old/name) for name in
      ("source.pdf","script_tts.json","microgen_batch.py")
    }
    assert cp["package_commit"]=="unknown"
    assert reuse._legacy_checkpoint_commit_attested(old,grant,cp) is True
    reuse._verify(old,21)
    _,manifest=reuse._inventory(old,21)
    assert len(manifest)>=100
    assert all(reuse._sha(old/name)==value for name,value in original.items())
