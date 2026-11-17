"""V6 Acceptance B/D/E/F/G/H/J on the NORMAL original API MicroGen_AI path.

A/C/I are exercised in test_microgen_v6_finite_external_recovery.py.
No internet or paid Gemini calls. Fake stage receipts never grant real QA.
"""
from pathlib import Path
from types import SimpleNamespace
import json
import os
import shutil
import sys

import pytest
import microgen_batch as batch
from microgen_recovery_registry import (
    REGISTRY_NAME, DECISION_NAME, classify_log_attempt,
    persist_stage_decision, verified_stage_hold,
)


HERE=Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    stage=tmp_path/"2.7"
    stage.mkdir()
    (stage/"source.pdf").write_bytes(b"offline synthetic physics source")
    (stage/"microgen_batch.py").write_bytes(b"version pinned test runner")
    shutil.copy2(HERE/REGISTRY_NAME,stage/REGISTRY_NAME)
    return stage


def test_b_new_failure_becomes_registered_and_reused_by_normal_code(tmp_path):
    stage=fixture(tmp_path)
    raw=(
        "Traceback (most recent call last):\n"
        "CheckpointIntegrityError: AMBIGUOUS_CHECKPOINT_HOLD: corrupted JSON\n"
    ).encode()
    registry=stage/REGISTRY_NAME
    original=json.loads(registry.read_text())
    without=dict(original)
    without["entries"]=[
        item for item in original["entries"]
        if item["id"]!="MGA-CHECKPOINT-CORRUPTION"
    ]
    registry.write_text(json.dumps(without))
    assert classify_log_attempt("checkpoint",raw,
                                registry_folder=stage) is None
    registry.write_text(json.dumps(original))
    decision=classify_log_attempt("checkpoint",raw,
                                  registry_folder=stage)
    assert decision["failure_id"]=="MGA-CHECKPOINT-CORRUPTION"
    assert decision["handler"]=="microgen_batch.load_checkpoint"
    assert decision["disposition"]=="DETERMINISTIC_HOLD"
    # New known remedy is the normal loader, not an LLM instruction.
    (stage/".microgen_checkpoint.json").write_bytes(b'{broken')
    with pytest.raises(batch.CheckpointIntegrityError,
                       match="AMBIGUOUS_CHECKPOINT_HOLD"):
        batch.load_checkpoint(stage/".microgen_checkpoint.json")


def test_d_crash_after_durable_recovery_receipt_reconciles_on_new_process(
        tmp_path):
    stage=fixture(tmp_path)
    traceback=(
        "Traceback (most recent call last):\n"
        "AutonomousAcousticError: ASR_DISAGREEMENT_HOLD: "
        "unresolved independently detected number\n"
    ).encode()
    decision=classify_log_attempt("acoustic_qa",traceback,
                                  registry_folder=stage)
    assert decision["failure_id"]=="MGA-20261116-ACOUSTIC-ASR"
    old=persist_stage_decision(stage,decision,attempt_number=1)
    assert not (stage/".microgen_checkpoint.json").exists()
    # A new OS Python process, not just an in-memory reimport, verifies the
    # saved hold after the previous process is gone.
    code=(
        "from microgen_recovery_registry import verified_stage_hold;"
        "from pathlib import Path;"
        f"assert verified_stage_hold(Path({str(stage)!r}), 'acoustic_qa');"
        "print('V6_RESTART_HOLD_VERIFIED')"
    )
    import subprocess
    result=subprocess.run(
        [sys.executable,"-c",code],cwd=str(HERE),
        capture_output=True,text=True,timeout=25,
    )
    assert result.returncode==0,result.stderr
    assert "V6_RESTART_HOLD_VERIFIED" in result.stdout
    assert json.loads((stage/DECISION_NAME).read_text())==old


def test_e_accepted_receipt_after_crash_advances_real_stage_loop_automatically(
        tmp_path,monkeypatch):
    stage=fixture(tmp_path)
    cp_path=stage/".microgen_checkpoint.json"
    earlier=batch.STAGES[:batch.STAGES.index("science_qa")]
    cp={"completed":{name:"accepted" for name in earlier},
        "dependency_fingerprints":{name:"same" for name in earlier}}
    args=SimpleNamespace(
        repo=HERE,source_root=tmp_path,work_root=tmp_path,
        source_wait=0.,commit="f"*40,
        docling_py="no-provider",main_py="no-provider",
        figure_extraction_only=False,multipart=False,
        stage_retries=0,stop_after="tts",
        offline_figure_mapping=False,rebuild_unverified=False,
        bounded_provider_scope_verified=False,
        standing_private_development=False,
    )
    stages_called=[]
    monkeypatch.setattr(batch,"prepare_stage",
                        lambda *args:(stage,cp,cp_path))
    monkeypatch.setattr(batch,"_science_qa_update_upstream_fingerprints",
                        lambda *args:None)
    monkeypatch.setattr(batch.quality,"dependency_fingerprint",
                        lambda *args:"same")
    def valid(folder,name,dest):
        if name in earlier or name=="science_qa":
            return True  # verified source-bound QA receipt already exists
        return name=="tts" and (stage/"tts_verification.marker").exists()
    monkeypatch.setattr(batch,"stage_valid",valid)
    def fake_stage(exe,script,folder,log,label,**kwargs):
        assert kwargs["stage_name"]=="tts"
        stages_called.append(kwargs["stage_name"])
        (stage/"tts_verification.marker").write_text("synthetic accepted")
    monkeypatch.setattr(batch,"run_subprocess",fake_stage)
    report=[]
    batch.process_one(args,"2.7",report)
    assert stages_called==["tts"]
    assert cp["completed"].get("science_qa")
    assert cp["completed"].get("tts")
    assert batch.load_checkpoint(cp_path)["completed"]["tts"]
    assert report[0]["status"]=="bounded_stage_complete"
    assert report[0]["stop_after"]=="tts"
    # A second invocation after successfully advancing must NOT repeat paid
    # work or synthesize an additional audio review.
    batch.process_one(args,"2.7",report)
    assert stages_called==["tts"]
    assert len(report)==2


@pytest.mark.skipif(os.name!="nt",reason="Windows kernel byte-range lock test")
def test_f_two_workers_cannot_own_same_subchapter(tmp_path,monkeypatch):
    monkeypatch.setenv("MICROGEN_LOCAL_LOCK_WAIT_SECONDS","0")
    args=SimpleNamespace(work_root=tmp_path,multi_pc=False)
    with batch.subchapter_ownership(args,"2.7"):
        with pytest.raises(RuntimeError,match="another active local worker"):
            with batch.subchapter_ownership(args,"2.7"):
                pytest.fail("overlapping kernel locks must not both succeed")


def test_g_genuine_qa_failure_cannot_be_misclassified_as_transient(tmp_path):
    stage=fixture(tmp_path)
    code=stage/"fail_qa.py"
    code.write_text(
        "raise type('AutonomousAcousticError',(RuntimeError,),{})("
        "'ASR_DISAGREEMENT_HOLD: changed numerical value')\n"
    )
    with pytest.raises(RuntimeError,match="non-retryable AutonomousAcousticError"):
        batch.run_subprocess(
            sys.executable,code.name,stage,tmp_path/"qa.log",
            "independent acoustic QA",gemini_stage=False,retries=10,
            stage_name="acoustic_qa",
        )
    assert not (stage/"QA_ACCEPTED").exists()
    receipt=json.loads((stage/DECISION_NAME).read_text())
    assert receipt["decision"]["category"]=="scientific_qa"
    assert receipt["publication_allowed"] is False
    assert receipt["paid_retry_authorized"] is False


def test_h_authorization_hold_does_not_prevent_independent_offline_work(
        tmp_path,monkeypatch):
    stage=fixture(tmp_path)
    failed=stage/"uncertain_paid.py"
    failed.write_text("raise SystemExit(2)\n")
    independent=stage/"independent_offline.py"
    independent.write_text(
        "from pathlib import Path\n"
        "Path('independent_verified.flag').write_text('pass')\n"
    )
    with pytest.raises(RuntimeError,match="AMBIGUOUS_PROVIDER_STAGE_HOLD"):
        batch.run_subprocess(
            sys.executable,failed.name,stage,tmp_path/"paid.log",
            "paid attempted stage",gemini_stage=False,retries=20,
            stage_name="tts",nonrepeatable_external_stage=True,
        )
    # Normal executable stage path makes progress on an independent target
    # without asking the user for another "proceed", and without retrying.
    batch.run_subprocess(
        sys.executable,independent.name,stage,tmp_path/"offline.log",
        "independent eligible offline stage",gemini_stage=False,retries=0,
        stage_name="figure_extraction",
    )
    assert (stage/"independent_verified.flag").read_text()=="pass"
    assert "attempt 2" not in (tmp_path/"paid.log").read_text()


@pytest.mark.parametrize("stage_name,exception,marker,expected",[
    ("acoustic_qa","AutonomousAcousticError","ASR_DISAGREEMENT_HOLD",
     "MGA-20261116-ACOUSTIC-ASR"),
    ("tts","CuePlanningError","Unattested source math",
     "MGA-SOURCE-CUE-PLANNING"),
    ("tts","SemanticMappingError","Missing source quote",
     "MGA-SOURCE-SEMANTIC-MAPPING"),
    ("tts","PronunciationPreflightError","Invalid voiced equation",
     "MGA-MATH-VOICE-PREFLIGHT"),
    ("video","HighlightContractError","Unverified PDF rectangle",
     "MGA-PDF-HIGHLIGHT-CONTRACT"),
    ("checkpoint","CheckpointIntegrityError",
     "AMBIGUOUS_CHECKPOINT_HOLD: incomplete save",
     "MGA-CHECKPOINT-CORRUPTION"),
])
def test_j_multiple_historical_regressions_recognized_without_model_calls(
        tmp_path,stage_name,exception,marker,expected):
    stage=fixture(tmp_path)
    failed=(f"Traceback (most recent call last):\n"
            f"{exception}: {marker}\n").encode()
    result=classify_log_attempt(stage_name,failed,registry_folder=stage)
    assert result is not None
    assert result["failure_id"]==expected
    assert result["disposition"]=="DETERMINISTIC_HOLD"
    assert result["max_unmodified_retries"]==0


def test_h_normal_batch_continues_second_offline_target_after_qa_hold(
        tmp_path,monkeypatch):
    import contextlib
    source_root=tmp_path/"source"
    work_root=tmp_path/"scratch"
    args=[
        "microgen_batch.py",
        "--repo",str(HERE),
        "--source-root",str(source_root),
        "--work-root",str(work_root),
        "--targets","2.7,2.8",
        "--figure-extraction-only",
        "--source-wait","0",
    ]
    monkeypatch.setattr(sys,"argv",args)
    monkeypatch.setattr(batch.quality,"require_scratch_space",
                        lambda root:{"free_gb":100,"required_gb":1})
    monkeypatch.setattr(batch,"resolve_docling_python",lambda *a,**k:sys.executable)
    monkeypatch.setattr(batch,"preflight",lambda *a,**k:None)
    monkeypatch.setattr(batch,"subchapter_ownership",
                        lambda *a,**k:contextlib.nullcontext(None))
    executed=[]
    def stage(args,topic,report,lease=None):
        executed.append(topic)
        if topic=="2.7":
            raise RuntimeError("independent_acoustic_qa evidence hold")
        assert topic=="2.8"
        report.append({"subchapter":topic,
                       "status":"offline_figure_extraction_complete",
                       "publication_allowed":False})
    monkeypatch.setattr(batch,"process_one",stage)
    # A failed branch yields a nonzero summary return code but DOES NOT
    # prevent already authorized independent offline work from progressing.
    assert batch.main()==2
    assert executed==["2.7","2.8"]
    report=json.loads((work_root/"batch_report.json").read_text())
    assert [r["status"] for r in report]==[
        "failed","offline_figure_extraction_complete"
    ]
    assert not (work_root/"2.7"/"slide1.wav").exists()


@pytest.mark.parametrize("stage_name,message,expected_disposition,rule_id",[
    ("narration","GEMINI_CIRCUIT_BOUNDED_PAUSE: 15-minute finite pause",
     "PAUSED_EXTERNAL_DEPENDENCY","MGA-GEMINI-CIRCUIT-PAUSED"),
    ("acoustic_qa","GEMINI_CIRCUIT_RECOVERY_EXHAUSTED: third outage",
     "PAUSED_EXTERNAL_DEPENDENCY","MGA-GEMINI-CIRCUIT-OSCILLATION"),
    ("tts","AMBIGUOUS_PROVIDER_STAGE_HOLD: failed paid request",
     "UNRESOLVED_EXTERNAL_EFFECT_HOLD","MGA-UNCERTAIN-PAID-WHOLE-STAGE"),
])
def test_c_h_i_parent_side_runtime_disposition_is_registered(
        tmp_path,stage_name,message,expected_disposition,rule_id):
    from microgen_recovery_registry import classify_runtime_error
    stage=fixture(tmp_path)
    row=classify_runtime_error(stage_name,RuntimeError(message),
                               registry_folder=stage)
    assert row["disposition"]==expected_disposition
    assert row["failure_id"]==rule_id
    assert row["max_unmodified_retries"]==0
    assert classify_runtime_error("figure_extraction",RuntimeError(message),
                                  registry_folder=stage) is None
    assert classify_runtime_error(stage_name,ValueError(message),
                                  registry_folder=stage) is None


def test_h_uncertain_paid_failure_is_saved_by_normal_process_one_and_blocks_restart(
        tmp_path,monkeypatch):
    stage=fixture(tmp_path)
    cp_path=stage/".microgen_checkpoint.json"
    earlier=batch.STAGES[:batch.STAGES.index("tts")]
    cp={"completed":{name:"accepted" for name in earlier},
        "dependency_fingerprints":{name:"same" for name in earlier}}
    args=SimpleNamespace(
        repo=HERE,source_root=tmp_path,work_root=tmp_path,
        source_wait=0.,commit="f"*40,docling_py="local",
        main_py="local",figure_extraction_only=False,multipart=False,
        stop_after="tts",rebuild_unverified=False,offline_figure_mapping=False,
        stage_retries=100,bounded_provider_scope_verified=True,
        standing_private_development=False,
    )
    monkeypatch.setattr(batch,"prepare_stage",
                        lambda *unused:(stage,cp,cp_path))
    monkeypatch.setattr(batch.quality,"dependency_fingerprint",
                        lambda *unused:"same")
    monkeypatch.setattr(batch,"stage_valid",
                        lambda stage,name,dest: name in earlier)
    calls=[]
    def fake_failure(*unused,**kwargs):
        calls.append(kwargs.get("stage_name"))
        assert kwargs["nonrepeatable_external_stage"] is True
        raise RuntimeError(
            "AMBIGUOUS_PROVIDER_STAGE_HOLD: provider result unknown"
        )
    monkeypatch.setattr(batch,"run_subprocess",fake_failure)
    with pytest.raises(RuntimeError,match="AMBIGUOUS_PROVIDER_STAGE_HOLD"):
        batch.process_one(args,"2.7",[])
    saved=batch.load_checkpoint(cp_path)
    assert calls==["tts"]
    assert saved["inflight_provider_stage"]["stage"]=="tts"
    assert saved["last_error"]["recovery_id"]=="MGA-UNCERTAIN-PAID-WHOLE-STAGE"
    assert saved["last_error"]["recovery_disposition"]==(
        "UNRESOLVED_EXTERNAL_EFFECT_HOLD")
    assert saved["last_error"]["paid_retry_authorized"] is False
    with pytest.raises(RuntimeError,match="AMBIGUOUS_PROVIDER_STAGE_HOLD"):
        batch.process_one(args,"2.7",[])
    assert calls==["tts"]  # zero duplicate paid whole-stage requests
