"""No-provider regression for genuine HP 2026-11-18 science QA 504 + 402.

A 504 on key #1 followed by 402 depleted prepayment on key #2
is a known external dependency, not proof the source is defective,
not proof BOTH keys are out of credit, and not authorization to replay.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

import pytest
import gemini_keys
import microgen_batch as batch
from gemini_lane import GeminiBillingError
from microgen_recovery_registry import (
    REGISTRY_NAME, DECISION_NAME, load_registry,
    classify_log_attempt, classify_runtime_error,
)

REPO=Path(__file__).resolve().parents[1]


class FakeGeminiError(Exception):
    def __init__(self,code,reason):
        self.code=code
        super().__init__(reason)


def fake_pool_case(first,second):
    seen=[]
    def operation(key):
        seen.append(key)
        error=first if key=="first" else second
        if isinstance(error,Exception):
            raise error
        return error
    settings={
        "GEMINI_API_KEY_1":"first",
        "GEMINI_API_KEY_2":"second",
        "MICROGEN_GEMINI_MAX_RETRIES":"0",
        "MICROGEN_GEMINI_TRANSIENT_RETRIES_PER_KEY":"1",
    }
    return seen, operation, settings


def test_real_504_then_402_has_typed_nonsecret_no_replay_hold(tmp_path):
    url="https://private.invalid/token=DO_NOT_LEAK"
    first=FakeGeminiError(504,"504 DEADLINE_EXCEEDED; "+url)
    second=FakeGeminiError(402,"402 Your prepayment credits are depleted; "+url)
    calls,operation,env=fake_pool_case(first,second)
    env["MICROGEN_GEMINI_LANE_DIR"]=str(tmp_path)
    with patch.dict(os.environ,env,clear=True),patch(
            "gemini_keys.time.sleep") as sleep:
        with pytest.raises(gemini_keys.GeminiProviderPoolUnavailable,
                           match="GEMINI_MIXED_TRANSIENT_BILLING_EXHAUSTED") as got:
            gemini_keys.call_with_key_failover(
                operation,label="source-bound independent science QA",
                max_retries=0)
    assert calls==["first","second"]
    assert sleep.call_count==0
    assert "DO_NOT_LEAK" not in str(got.value)
    assert "all configured" not in str(got.value).lower()
    # One key transient => do NOT open a circuit claiming all keys' credits
    # depleted; the paid stage still stops once with an explicit typed hold.
    assert not (tmp_path/"circuit_breaker.json").exists()


@pytest.mark.parametrize("first,second,expect_typed",[
    (FakeGeminiError(503,"503 UNAVAILABLE"),"valid transcript",False),
    ("valid transcript",FakeGeminiError(402,"402 prepayment credits"),False),
    (FakeGeminiError(401,"401 Unauthorized"),"valid transcript",False),
    (FakeGeminiError(504,"504 DEADLINE_EXCEEDED"),
     FakeGeminiError(402,"402 RESOURCE_EXHAUSTED prepayment credits"),True),
])
def test_no_false_mixed_holds_for_success(first,second,expect_typed,tmp_path):
    calls,operation,env=fake_pool_case(first,second)
    env["MICROGEN_GEMINI_LANE_DIR"]=str(tmp_path)
    with patch.dict(os.environ,env,clear=True):
        if expect_typed:
            with pytest.raises(gemini_keys.GeminiProviderPoolUnavailable):
                gemini_keys.call_with_key_failover(operation,max_retries=0)
        else:
            assert gemini_keys.call_with_key_failover(
                operation,max_retries=0)=="valid transcript"
    assert len(calls)<=2


def sandbox(tmp_path):
    stage=tmp_path/"2.7"
    stage.mkdir(parents=True)
    shutil.copy2(REPO/REGISTRY_NAME,stage/REGISTRY_NAME)
    (stage/"source.pdf").write_bytes(b"source-bound PDF")
    (stage/"microgen_batch.py").write_bytes(b"exact runner")
    return stage


def test_known_mixed_402_and_504_is_executable_history_entry(tmp_path):
    stage=sandbox(tmp_path)
    registry=load_registry(stage)
    ids={item["id"] for item in registry["entries"]}
    assert "MGA-GEMINI-MIXED-TRANSIENT-BILLING-POOL" in ids
    assert "MGA-GEMINI-LEGACY-SCIENCE-402-HOLD" in ids
    log=(
        "Traceback (most recent call last):\n"
        '  File "gemini_keys.py", line 260, in call_with_key_failover\n'
        "gemini_keys.GeminiProviderPoolUnavailable: "
        "GEMINI_MIXED_TRANSIENT_BILLING_EXHAUSTED: no further paid send\n"
    ).encode()
    for stage_name in ("science_qa","narration","acoustic_qa","tts"):
        decision=classify_log_attempt(stage_name,log,registry_folder=stage)
        assert decision["failure_id"]=="MGA-GEMINI-MIXED-TRANSIENT-BILLING-POOL"
        assert decision["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"


@pytest.mark.parametrize("trial",range(8))
def test_runner_never_retries_known_mixed_billing_provider_stage(tmp_path,trial):
    stage=sandbox(tmp_path/str(trial))
    worker=stage/"fail_science.py"
    worker.write_text(
        "import sys\n"
        "sys.stderr.write('Traceback (most recent call last):\\n"
        "gemini_keys.GeminiProviderPoolUnavailable: "
        "GEMINI_MIXED_TRANSIENT_BILLING_EXHAUSTED: stop\\n')\n"
        "sys.exit(1)\n",encoding="utf8")
    log=tmp_path/f"realistic-{trial}.log"
    with pytest.raises(RuntimeError,match=(
        "VERIFIED_EXTERNAL_DEPENDENCY_HOLD:.*"
        "recovery_id=MGA-GEMINI-MIXED-TRANSIENT-BILLING-POOL"
    )) as result:
        batch.run_subprocess(
            sys.executable,worker.name,stage,log,
            "source-grounded independent scientific QA",
            gemini_stage=False,retries=4,stage_name="science_qa",
            nonrepeatable_external_stage=True)
    raw=log.read_bytes()
    assert raw.count(b":: attempt 1")==1
    assert b":: attempt 2" not in raw
    assert not (stage/DECISION_NAME).exists()
    parent=classify_runtime_error(
        "science_qa",result.value,registry_folder=stage)
    assert parent["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"
    assert parent["failure_id"]=="MGA-CHILD-EXTERNAL-DEPENDENCY-HOLD"


def test_not_claimed_from_quoted_or_nonterminal_or_wrong_exception(tmp_path):
    stage=sandbox(tmp_path)
    marker="GEMINI_MIXED_TRANSIENT_BILLING_EXHAUSTED"
    examples=[
        "Narration says "+marker,
        "Traceback (most recent call last):\n"
        '  File "worker.py", line 4, in main\n'
        "RuntimeError: "+marker,
        "Traceback (most recent call last):\n"
        "GeminiProviderPoolUnavailable: "+marker+"\n"
        "Traceback (most recent call last):\n"
        "ValueError: final unrelated failure\n",
        "Traceback (most recent call last):\n"
        "  GeminiProviderPoolUnavailable: "+marker,
    ]
    for payload in examples:
        assert classify_log_attempt(
            "science_qa",payload.encode(),registry_folder=stage) is None


def test_historical_hp_18_nov_credit_log_matches_with_no_mutations():
    source=os.environ.get("MICROGEN_HP_PRIVATE_SCIENCE_402_STAGE","")
    if not source:
        pytest.skip("historical real HP 402 stage only under explicit local fixture")
    stage=Path(source)
    log=stage.parent/"2.7.log"
    assert stage.is_dir() and log.is_file()
    cp=stage/".microgen_checkpoint.json"
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (cp,log,stage/"source.pdf")}
    raw=log.read_bytes()
    assert b"504 DEADLINE_EXCEEDED" in raw
    assert b"402 RESOURCE_EXHAUSTED" in raw
    verdict=classify_log_attempt(
        "science_qa",raw,registry_folder=REPO)
    assert verdict["failure_id"]=="MGA-GEMINI-LEGACY-SCIENCE-402-HOLD"
    assert verdict["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"
    record=json.loads(cp.read_text(encoding="utf8"))
    assert record["inflight_provider_stage"]["stage"]=="science_qa"
    assert record["last_error"]["paid_retry_authorized"] is False
    assert "science_qa" not in record["completed"]
    assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (cp,log,stage/"source.pdf")}==before



def test_reverse_order_credit_then_timeout_is_same_typed_external_hold(tmp_path):
    calls,operation,env=fake_pool_case(
        FakeGeminiError(402,"402 RESOURCE_EXHAUSTED prepayment credits"),
        FakeGeminiError(504,"504 DEADLINE_EXCEEDED"))
    env["MICROGEN_GEMINI_LANE_DIR"]=str(tmp_path)
    with patch.dict(os.environ,env,clear=True):
        with pytest.raises(gemini_keys.GeminiProviderPoolUnavailable,
                           match="GEMINI_MIXED_TRANSIENT_BILLING_EXHAUSTED"):
            gemini_keys.call_with_key_failover(operation,max_retries=0)
    assert calls==["first","second"]
    assert not (tmp_path/"circuit_breaker.json").exists()


def test_all_keys_credit_depleted_opens_only_correct_billing_circuit(tmp_path):
    calls,operation,env=fake_pool_case(
        FakeGeminiError(402,"402 RESOURCE_EXHAUSTED prepayment credits"),
        FakeGeminiError(402,"402 RESOURCE_EXHAUSTED prepayment credits"))
    env["MICROGEN_GEMINI_LANE_DIR"]=str(tmp_path)
    with patch.dict(os.environ,env,clear=True):
        with pytest.raises(GeminiBillingError,
                           match="every configured Gemini key reported"):
            gemini_keys.call_with_key_failover(operation,max_retries=0)
    assert calls==["first","second"]
    assert (tmp_path/"circuit_breaker.json").is_file()
    stage=sandbox(tmp_path)
    raw=(
        "Traceback (most recent call last):\n"
        "gemini_lane.GeminiBillingError: source-bound independent science QA "
        "stopped because every configured Gemini key reported "
        "billing/prepayment failure: 402 RESOURCE_EXHAUSTED\n"
    ).encode()
    found=classify_log_attempt("science_qa",raw,registry_folder=stage)
    assert found["failure_id"]=="MGA-GEMINI-ALL-KEY-BILLING-HOLD"
    assert found["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"
    assert classify_log_attempt(
        "published",raw,registry_folder=stage) is None


@pytest.mark.parametrize("trial",range(4))
def test_all_keys_billing_stops_parent_driver_at_one_stage_attempt(tmp_path,trial):
    stage=sandbox(tmp_path/str(trial))
    worker=stage/"all_billing.py"
    worker.write_text(
        "import sys\n"
        "sys.stderr.write('Traceback (most recent call last):\\n"
        "gemini_lane.GeminiBillingError: science QA stopped because every "
        "configured Gemini key reported billing/prepayment failure: 402\\n')\n"
        "sys.exit(1)\n",encoding="utf8")
    log=stage.parent/"all-billing.log"
    with pytest.raises(RuntimeError,match=(
            "VERIFIED_EXTERNAL_DEPENDENCY_HOLD:.*"
            "recovery_id=MGA-GEMINI-ALL-KEY-BILLING-HOLD")) as raised:
        batch.run_subprocess(
            sys.executable,worker.name,stage,log,
            "source-grounded independent scientific QA",
            gemini_stage=False,retries=5,stage_name="science_qa",
            nonrepeatable_external_stage=True)
    assert log.read_bytes().count(b":: attempt 1")==1
    assert not (stage/DECISION_NAME).exists()
    assert classify_runtime_error(
        "science_qa",raised.value,registry_folder=stage
    )["disposition"]=="PAUSED_EXTERNAL_DEPENDENCY"
