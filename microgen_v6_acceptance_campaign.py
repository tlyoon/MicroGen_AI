"""Read-only V6 A-J code/restart acceptance + historical live-G3 evidence replay.

Not a paid QA request. No Gemini SDK calls, model prompts, media generation,
source redistribution, or publication. Running this after a commit produces
an immutable, source/revision-bound local report for a later ChatGPT session.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone


EXPECTED_ORIGINAL_SOURCE = (
    "03676ed9dc5ded9e07874902c5e2d3689d4293cdc086b9819003770310293102"
)
A_J = {
    "A": "test_a_inexpensive_known_transient_recovers_then_next_stage_runs",
    "B": "test_b_new_failure_becomes_registered_and_reused_by_normal_code",
    "C": "test_c_external_circuit_reopen_cycles_do_not_loop_forever",
    "D": "test_d_crash_after_durable_recovery_receipt_reconciles_on_new_process",
    "E": "test_e_accepted_receipt_after_crash_advances_real_stage_loop_automatically",
    "F": "test_f_two_workers_cannot_own_same_subchapter",
    "G": "test_g_genuine_qa_failure_cannot_be_misclassified_as_transient",
    "H": "test_h_authorization_hold_does_not_prevent_independent_offline_work",
    "I": "test_i_finite_circuit_wait_always_terminates",
    "J": "test_j_multiple_historical_regressions_recognized_without_model_calls",
}
TEST_FILES = [
    "tests/test_microgen_v6_aj_acceptance.py",
    "tests/test_microgen_v6_finite_external_recovery.py",
    "tests/test_microgen_recovery_registry_v6.py",
    "tests/test_microgen_v6_checkpoint_integrity.py",
    "tests/test_microgen_g3_bounded_decimal_witness.py",
]


def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git(repo: Path, *argv: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *argv],
        capture_output=True, text=True, errors="replace", timeout=40,
    )
    if result.returncode:
        raise RuntimeError("Cannot verify exact source revision")
    return result.stdout.strip()


def historical_replay(stage: Path) -> dict:
    # Read the exact private original campaign, never the live Google model.
    from microgen_autonomous_acoustic_gate import _normalized
    from microgen_tts_acoustic_qa import audit_with_recognizer

    source=stage/"source.pdf"
    if not source.is_file() or digest(source)!=EXPECTED_ORIGINAL_SOURCE:
        raise RuntimeError("G3 source SHA mismatch; private replay denied")
    checkpoint=json.loads((stage/".microgen_checkpoint.json").read_text(
        encoding="utf8"))
    required=["figure_extraction","figure_mapping","figure_merge",
              "slides","narration","science_qa","tts"]
    done=checkpoint.get("completed",{})
    if (not all(done.get(x) for x in required)
            or done.get("acoustic_qa") or done.get("video")
            or checkpoint.get("package_commit") !=
               "0f8ba4117add27c29437c9b141dec13d7e17e11b"):
        raise RuntimeError("Original G3 checkpoint drift; refusing fake acceptance")
    traces=list(stage.glob(".microgen_private_acoustic_failed_*.json"))
    if len(traces)!=1:
        raise RuntimeError("Ambiguous original Gemini acoustic transcript")
    evidence=json.loads(traces[0].read_text(encoding="utf8"))
    texts=_normalized(stage)
    if len(texts)!=21 or len(evidence.get("slides",[]))!=21:
        raise RuntimeError("Missing original full 21-slide evidence")
    original_files=list(stage.glob("slide*.wav"))
    if len(original_files)!=21:
        raise RuntimeError("Missing original lecture WAVs")
    originals={p.name:digest(p) for p in original_files}

    def saved_asr(model_index):
        def recognize(wav):
            idx=int(wav.stem.removeprefix("slide"))
            return evidence["slides"][idx-1]["original_blind_transcripts"][
                model_index]
        return recognize
    report=audit_with_recognizer(
        stage,texts,saved_asr(0),lambda s:s,
        independent_recognizer=saved_asr(1),
        recognition_models=tuple(evidence["models"]),
    )
    if (evidence.get("review_required_slides") !=
            [4,7,8,9,10,11,14,15,16,17,18,19,20,21]):
        raise RuntimeError("Original failed independent QA history drift")
    unresolved=report.get("review_required_slides")
    if not unresolved:
        raise RuntimeError("Unexpected all-pass reclassification: require live QA")
    after={p.name:digest(p) for p in stage.glob("slide*.wav")}
    if originals!=after:
        raise RuntimeError("Private original WAVs modified during read-only audit")
    return {
        "original_campaign_commit":checkpoint["package_commit"],
        "original_source_sha256":digest(source),
        "original_private_transcript_sha256":digest(traces[0]),
        "all_21_original_wavs_unchanged":True,
        "original_completed_stages":required,
        "original_failed_review_slide_count":14,
        "source_blind_offline_remaining_slides":unresolved,
        "third_gemini_called":False,
        "new_paid_provider_calls":0,
        "independent_live_acoustic_accepted":False,
        "video_or_g3_closed":False,
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",required=True,type=Path)
    parser.add_argument("--historical-stage",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    repo=args.repo.resolve()
    if repo!=Path(__file__).resolve().parent:
        raise RuntimeError("Runner must audit its own exact checkout")
    sha=git(repo,"rev-parse","HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}",sha):
        raise RuntimeError("Unpinned source code")
    if git(repo,"status","--porcelain"):
        raise RuntimeError("Dirty checkout; commit before acceptance evidence")
    for path in TEST_FILES:
        if not (repo/path).is_file():
            raise RuntimeError("Incomplete v6 acceptance test campaign")
    stage=args.historical_stage.resolve()
    replay=historical_replay(stage)
    cmd=[sys.executable,"-m","pytest","-q",*TEST_FILES]
    test_run=subprocess.run(
        cmd,cwd=str(repo),capture_output=True,
        text=True,errors="replace",timeout=240,
    )
    combined=(test_run.stdout+"\n"+test_run.stderr)
    # We never store raw private lecture content or credentials in the
    # stable report: only counted/summarized code evidence.
    match=re.search(r"(\d+) passed(?:, (\d+) skipped)?",combined)
    passed=int(match[1]) if match else 0
    skipped=int(match[2] or 0) if match else 0
    if test_run.returncode!=0 or passed<50:
        raise RuntimeError("V6 acceptance code test campaign failed")
    record={
        "schema_version":6,
        "project":"MicroGen_AI_ORIGINAL_API",
        "code_sha":sha,
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "acceptance_mode":"OFFLINE_REAL_HISTORY_NO_PROVIDER_CALLS",
        "test_scenarios":{
            name:{"test":test,"status":"AUTOMATED_OFFLINE_PASS"}
            for name,test in A_J.items()
        },
        "pytest":{"passed":passed,"skipped":skipped,
                  "returncode":test_run.returncode,
                  "test_files":TEST_FILES},
        "historical_g3":replay,
        "overall_status":"V6_OFFLINE_AJ_PASS_G3_LIVE_ACOUSTIC_HOLD",
        "live_provider_recovery_verified":False,
        "full_v6_end_to_end_production_closed":False,
        "publication_allowed":False,
    }
    out=args.output
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists() or out.is_symlink():
        raise RuntimeError("Immutable prior acceptance record exists")
    tmp=out.with_suffix(out.suffix+".tmp")
    if tmp.exists():
        raise RuntimeError("Ambiguous prior acceptance report write")
    with tmp.open("x",encoding="utf8") as fd:
        json.dump(record,fd,indent=2,sort_keys=True)
        fd.flush()
        os.fsync(fd.fileno())
    os.replace(tmp,out)
    print("V6_CODE_ACCEPTANCE_A_TO_J_OFFLINE_PASSED",passed,"skipped",skipped)
    print("G3_HISTORICAL_REPLAY_UNRESOLVED",replay["source_blind_offline_remaining_slides"])
    print("NO_PAID_CALLS",replay["new_paid_provider_calls"])
    print("ACOUSTIC_G3_LIVE_PASS",False)
    print("IMMUTABLE_REPORT_SHA256",digest(out))
    return 0


if __name__=="__main__":
    sys.exit(main())
