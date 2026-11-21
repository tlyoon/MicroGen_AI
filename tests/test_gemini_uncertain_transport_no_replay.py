"""Post-send Gemini transport failure cannot cause paid replay or key rotation."""
import os
from unittest.mock import patch

import pytest

from gemini_keys import (
    GeminiUncertainRequestOutcome, call_with_key_failover,
    call_with_client_failover,
)


class ReadTimeout(Exception):
    pass


class WriteTimeout(Exception):
    pass


class RemoteProtocolError(Exception):
    pass


@pytest.mark.parametrize("exc", [
    ReadTimeout("http://private.invalid/?secret=NO_LEAK"),
    WriteTimeout("unknown post-send outcome"),
    RemoteProtocolError("response disconnected after send"),
    TimeoutError("No response after server received request"),
])
@pytest.mark.parametrize("retries", [0, 4])
def test_possibly_consumed_transport_never_retries_or_rotates(exc, retries):
    calls=[]
    def operation(key):
        calls.append(key)
        raise exc
    with patch.dict(os.environ, {
            "GEMINI_API_KEY_1":"first",
            "GEMINI_API_KEY_2":"second",
            "MICROGEN_GEMINI_MAX_RETRIES":str(retries)}, clear=True), patch(
            "gemini_keys.time.sleep") as sleep:
        with pytest.raises(GeminiUncertainRequestOutcome,
                           match="GEMINI_UNCERTAIN_EXTERNAL_RESULT_HOLD") as caught:
            call_with_key_failover(operation, max_retries=retries)
    assert calls == ["first"]
    sleep.assert_not_called()
    assert "NO_LEAK" not in str(caught.value)


def test_client_closed_after_unsafe_provider_read_timeout():
    calls=[]
    class Client:
        def __init__(self,key):
            calls.append(("create",key))
        def close(self):
            calls.append(("close",None))
    def operation(client):
        calls.append(("send",None))
        raise ReadTimeout("uncertain")
    with patch.dict(os.environ,{"GEMINI_API_KEY_1":"first",
                                "GEMINI_API_KEY_2":"second"},clear=True):
        with pytest.raises(GeminiUncertainRequestOutcome):
            call_with_client_failover(Client,operation)
    assert calls == [("create","first"),("send",None),("close",None)]


def test_pre_send_connection_timeout_not_misclassified():
    from gemini_keys import _possibly_consumed_transport_failure
    class ConnectTimeout(Exception): pass
    class PoolTimeout(Exception): pass
    assert not _possibly_consumed_transport_failure(ConnectTimeout())
    assert not _possibly_consumed_transport_failure(PoolTimeout())


def test_explicit_pre_send_billing_denial_still_allows_safe_key_rotation():
    class CreditDenied(Exception):
        code=402
        def __str__(self):
            return "prepayment credits depleted"
    calls=[]
    def operation(key):
        calls.append(key)
        if key=="first":
            raise CreditDenied()
        return "accepted"
    with patch.dict(os.environ,{"GEMINI_API_KEY_1":"first",
                                "GEMINI_API_KEY_2":"second"},clear=True):
        assert call_with_key_failover(operation,max_retries=0)=="accepted"
    assert calls == ["first","second"]


def test_recovery_registry_detects_real_terminal_uncertain_request(tmp_path):
    import shutil
    from pathlib import Path
    from microgen_recovery_registry import (
        REGISTRY_NAME, classify_log_attempt, load_registry,
    )
    original = Path(__file__).resolve().parents[1] / REGISTRY_NAME
    shutil.copy2(original, tmp_path / REGISTRY_NAME)
    assert "MGA-20261122-GEMINI-POSTSEND-UNCERTAIN-RESULT" in {
        x["id"] for x in load_registry(tmp_path)["entries"]
    }
    terminal = (
        "Traceback (most recent call last):\n"
        '  File "worker.py", line 3, in <module>\n'
        "GeminiUncertainRequestOutcome: "
        "GEMINI_UNCERTAIN_EXTERNAL_RESULT_HOLD: response absent\n"
    )
    decision = classify_log_attempt(
        "narration", terminal.encode("utf-8"), registry_folder=tmp_path
    )
    assert decision["failure_id"] == "MGA-20261122-GEMINI-POSTSEND-UNCERTAIN-RESULT"
    assert decision["disposition"] == "PAUSED_EXTERNAL_DEPENDENCY"


def test_parent_runner_preserves_exactly_one_uncertain_paid_submission(tmp_path):
    import shutil
    import sys
    from pathlib import Path
    import microgen_batch
    from microgen_recovery_registry import REGISTRY_NAME, classify_runtime_error

    original = Path(__file__).resolve().parents[1] / REGISTRY_NAME
    stage = tmp_path / "private" / "2.5"
    stage.mkdir(parents=True)
    shutil.copy2(original, stage / REGISTRY_NAME)
    (stage / "source.pdf").write_bytes(b"source pinned")
    (stage / "microgen_batch.py").write_bytes(b"runner pinned")
    worker = stage / "uncertain.py"
    worker.write_text(
        "class GeminiUncertainRequestOutcome(RuntimeError): pass\n"
        "raise GeminiUncertainRequestOutcome("
        "'GEMINI_UNCERTAIN_EXTERNAL_RESULT_HOLD: "
        "possibly consumed external API request')\n",
        encoding="utf8",
    )
    log = tmp_path / "provider.log"
    with pytest.raises(RuntimeError,
                       match="VERIFIED_EXTERNAL_DEPENDENCY_HOLD") as got:
        microgen_batch.run_subprocess(
            sys.executable, worker.name, stage, log,
            "original source-bound narration",
            gemini_stage=False, retries=4, stage_name="narration",
            nonrepeatable_external_stage=True,
        )
    raw = log.read_bytes()
    assert raw.count(b":: attempt 1") == 1
    assert b":: attempt 2" not in raw
    verdict = classify_runtime_error(
        "narration", got.value, registry_folder=stage)
    assert verdict["disposition"] == "PAUSED_EXTERNAL_DEPENDENCY"
