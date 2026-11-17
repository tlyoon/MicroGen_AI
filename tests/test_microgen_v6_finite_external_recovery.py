"""V6 Test C/H/I/J: finite external circuit and uncertain paid submission.

Only fake child workers and simulated circuit states; no credentials or API
requests. The normal production runner must preserve evidence and never
reissue an uncertain paid whole-stage request.
"""
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
import microgen_batch as batch


def failed_worker(folder, name="failed_stage.py", report="remote service 503"):
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / name
    script.write_text(
        "import sys\n"
        f"print({report!r}, file=sys.stderr)\n"
        "raise SystemExit(2)\n", encoding="utf8",
    )
    return script


def test_i_finite_circuit_wait_always_terminates(tmp_path,monkeypatch):
    clock=[0.]
    sleeps=[]
    def sleep(seconds):
        assert 0 < seconds <= 60.
        clock[0]+=seconds
        sleeps.append(seconds)
    fake_time=SimpleNamespace(
        monotonic=lambda:clock[0],
        time=lambda:1700000000.+clock[0],
        sleep=sleep,
    )
    monkeypatch.setattr(batch,"time",fake_time)
    monkeypatch.setattr(batch,"circuit_is_open",
                        lambda:(True,{"type":"rate_limit",
                                       "retry_after_epoch":1700030000.}))
    monkeypatch.setenv("MICROGEN_CIRCUIT_MAX_WAIT_SECONDS","60")
    with pytest.raises(RuntimeError,match="GEMINI_CIRCUIT_BOUNDED_PAUSE"):
        batch.wait_for_gemini_circuit()
    assert 60 <= clock[0] <= 120
    assert 1 <= len(sleeps) <= 3


@pytest.mark.parametrize("raw",["0","-1","inf","nan","foo","36000"])
def test_i_circuit_budget_rejects_unbounded_or_ambiguous_input(monkeypatch,raw):
    monkeypatch.setenv("MICROGEN_CIRCUIT_MAX_WAIT_SECONDS",raw)
    with pytest.raises(RuntimeError,match="INVALID_FINITE"):
        batch.wait_for_gemini_circuit()


def test_c_external_circuit_reopen_cycles_do_not_loop_forever(tmp_path,monkeypatch):
    stage=tmp_path/"stage"
    script=failed_worker(stage)
    calls=[]
    class FakeResult:
        returncode=2
    def run(command,**kwargs):
        calls.append(list(command))
        return FakeResult()
    monkeypatch.setattr(batch.subprocess,"run",run)
    monkeypatch.setattr(batch,"wait_for_gemini_circuit",lambda lease=None:None)
    monkeypatch.setattr(batch,"circuit_is_open",
                        lambda:(True,{"type":"rate_limit"}))
    with pytest.raises(RuntimeError,match="GEMINI_CIRCUIT_RECOVERY_EXHAUSTED"):
        batch.run_subprocess(
            sys.executable,script.name,stage,tmp_path/"circuit.log",
            "Gemini narration",gemini_stage=True,retries=100,
            stage_name="narration",
        )
    assert len(calls)==3
    assert (tmp_path/"circuit.log").read_text().count(":: attempt 1") == 3
    assert not (stage/".microgen_recovery_v6.json").exists()


@pytest.mark.parametrize("stage_name",["narration","science_qa","acoustic_qa","tts"])
def test_h_uncertain_paid_stage_will_never_whole_stage_retry(
        tmp_path,monkeypatch,stage_name):
    stage=tmp_path/"stage"
    script=failed_worker(stage)
    paid_calls=[]
    class FakeResult:
        returncode=2
    def run(command,**kwargs):
        paid_calls.append(command)
        return FakeResult()
    monkeypatch.setattr(batch.subprocess,"run",run)
    monkeypatch.setattr(batch,"wait_for_gemini_circuit",lambda lease=None:None)
    monkeypatch.setattr(batch,"circuit_is_open",lambda:(True,{"type":"rate_limit"}))
    with pytest.raises(RuntimeError,match="AMBIGUOUS_PROVIDER_STAGE_HOLD"):
        batch.run_subprocess(
            sys.executable,script.name,stage,tmp_path/"paid.log",
            "bounded private stage",gemini_stage=(stage_name!="tts"),
            retries=20,stage_name=stage_name,
            nonrepeatable_external_stage=True,
        )
    assert len(paid_calls)==1
    assert "attempt 2" not in (tmp_path/"paid.log").read_text()


def test_a_inexpensive_known_transient_recovers_then_next_stage_runs(tmp_path,monkeypatch):
    stage=tmp_path/"stage"
    stage.mkdir()
    worker=stage/"transient.py"
    worker.write_text(
        "from pathlib import Path\n"
        "p=Path('attempt.flag')\n"
        "if not p.exists():\n"
        "    p.write_text('one')\n"
        "    raise SystemExit(12)\n"
        "Path('accepted.flag').write_text('verified')\n",encoding="utf8")
    next_stage=stage/"next_stage.py"
    next_stage.write_text(
        "from pathlib import Path\n"
        "assert Path('accepted.flag').read_text()=='verified'\n"
        "Path('downstream.flag').write_text('advanced')\n",
        encoding="utf8")
    monkeypatch.setattr(batch.time,"sleep",lambda delay:None)
    batch.run_subprocess(
        sys.executable,worker.name,stage,tmp_path/"stage.log",
        "bounded temporary local failure",gemini_stage=False,retries=1,
        stage_name="figure_extraction",
    )
    # The next eligible stage is launched by the same stage-loop call path,
    # rather than requiring another ChatGPT "proceed" message.
    batch.run_subprocess(
        sys.executable,next_stage.name,stage,tmp_path/"stage.log",
        "next eligible verified stage",gemini_stage=False,retries=0,
        stage_name="figure_merge",
    )
    assert (stage/"downstream.flag").read_text()=="advanced"
    assert (tmp_path/"stage.log").read_text().count("attempt 2")==1
