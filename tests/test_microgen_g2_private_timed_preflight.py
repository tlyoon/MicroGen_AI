"""Mandatory G2 timed-source admission on normal, bounded batch flow.

No Gemini, TTS, media upload or private textbook bytes. These tests replay
an offline source-free fixture against the real PDF-block matcher and runner.
"""
from contextlib import nullcontext
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

import pytest

import microgen_batch as batch
from microgen_timed_cue_planner import PLAN_FILE, CuePlanningError, sha
from test_microgen_timed_cue_tts import input_stage


def test_existing_exact_verified_plan_admitted_without_provider(tmp_path,monkeypatch):
    stage=input_stage(tmp_path)
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST","0")
    before=sha(stage/"slides.pdf")
    admitted=batch.preflight_private_timed_acceptance(stage)
    assert admitted=={"mode":"existing_verified_plan","pages":2,"cues":4}
    assert sha(stage/"slides.pdf")==before


def test_offline_lexical_plan_admitted_without_writing_or_model(tmp_path,monkeypatch):
    stage=input_stage(tmp_path)
    (stage/PLAN_FILE).unlink()
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST","0")
    before=sha(stage/"slides.pdf")
    admitted=batch.preflight_private_timed_acceptance(stage)
    assert admitted=={"mode":"offline_lexical_grounding","pages":2,"cues":4}
    assert not (stage/PLAN_FILE).exists()
    assert sha(stage/"slides.pdf")==before


def test_unsupported_lexical_cues_rejected_without_fabrication(tmp_path,monkeypatch):
    stage=input_stage(tmp_path)
    (stage/PLAN_FILE).unlink()
    side=stage/"script_tts.json"
    raw=json.loads(side.read_text(encoding="utf8"))
    raw["slides"][0]["tts_text"]="A poem about a distant village and its ancient towers."
    side.write_text(json.dumps(raw),encoding="utf8")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST","0")
    with pytest.raises(CuePlanningError,match="insufficient|no anchored"):
        batch.preflight_private_timed_acceptance(stage)
    assert not (stage/PLAN_FILE).exists()


def test_unaffordable_full_deck_semantic_proposal_rejected_offline(tmp_path,monkeypatch):
    stage=input_stage(tmp_path)
    (stage/PLAN_FILE).unlink()
    side=stage/"script_tts.json"
    raw=json.loads(side.read_text(encoding="utf8"))
    for slide in raw["slides"]:
        slide["tts_text"]="Poetry about winter villages and the distant hills."
    side.write_text(json.dumps(raw),encoding="utf8")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST","1")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES","1")
    with pytest.raises(CuePlanningError,match="required=2 allowed=1"):
        batch.preflight_private_timed_acceptance(stage)
    assert not (stage/PLAN_FILE).exists()


@pytest.mark.parametrize("invalid",["none","-1","41","not-numeric"])
def test_invalid_semantic_budget_never_runs_provider(tmp_path,monkeypatch,invalid):
    stage=input_stage(tmp_path)
    (stage/PLAN_FILE).unlink()
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST","1")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES",invalid)
    with pytest.raises(CuePlanningError,match="Invalid bounded"):
        batch.preflight_private_timed_acceptance(stage)


def test_real_batch_entrypoint_fails_before_paid_science_on_bad_timing(tmp_path,monkeypatch):
    stage=input_stage(tmp_path)
    (stage/PLAN_FILE).unlink()
    raw=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    for item in raw["slides"]:
        item["tts_text"]="Poetry about ancient castles and distant winter."
    (stage/"script_tts.json").write_text(json.dumps(raw),encoding="utf8")
    cp_path=stage/".microgen_checkpoint.json"
    earlier=["figure_extraction","figure_mapping","figure_merge",
             "slides","narration"]
    cp={
        "completed":{n:"verified" for n in earlier},
        "dependency_fingerprints":{n:"same" for n in earlier},
    }
    args=SimpleNamespace(
        repo=tmp_path,source_root=tmp_path,work_root=tmp_path,
        source_wait=0,commit="a"*40,multipart=False,
        stop_after="acceptance",rebuild_unverified=False,
        figure_extraction_only=False,stage_retries=0,
        main_py=sys.executable,docling_py=sys.executable,
        bounded_provider_scope_verified=True,
        offline_figure_mapping=False,
    )
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST","1")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES","1")
    with patch.object(batch,"prepare_stage",return_value=(stage,cp,cp_path)), \
         patch.object(batch,"destination_for",return_value=tmp_path), \
         patch.object(batch,"stage_valid",
                      side_effect=lambda _stage,name,_dest:
                          name!="science_qa"), \
         patch.object(batch.quality,"dependency_fingerprint",
                      return_value="same"), \
         patch.object(batch,"run_subprocess") as provider:
        with pytest.raises(CuePlanningError,match="required=2 allowed=1"):
            batch.process_one(args,"2.5",[])
        provider.assert_not_called()
    persisted=json.loads(cp_path.read_text(encoding="utf8"))
    assert persisted["last_error"]["stage"]=="science_qa"
    assert "inflight_provider_stage" not in persisted


def test_bounded_acceptance_enables_timed_mode_before_provider_scope(tmp_path,monkeypatch):
    repo=tmp_path/"repo"
    repo.mkdir()
    source_root=tmp_path/"source"
    dest=source_root/"2"/"2.5"
    dest.mkdir(parents=True)
    (dest/"source.pdf").write_bytes(b"fixture PDF")
    work=tmp_path/"work"
    monkeypatch.setenv("MICROGEN_TIMED_CUES","0")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST","0")
    seen=[]

    def save_scope(**kwargs):
        seen.append(("scope",os.environ.get("MICROGEN_TIMED_CUES")))
        return {"status":"FROZEN_ONE_TIME_PROVIDER_SCOPE"}

    def fake_dispatch(*args,**kwargs):
        seen.append(("stage",os.environ.get("MICROGEN_TIMED_CUES")))
    args=[
        "microgen_batch.py","--repo",str(repo),
        "--source-root",str(source_root),"--work-root",str(work),
        "--targets","2.5","--stop-after","acceptance",
        "--stage-retries","0","--authorize-provider-usage",
    ]
    with patch.object(sys,"argv",args), \
         patch("microgen_campaign_authorization.authorize_or_resume",
               side_effect=save_scope), \
         patch.object(batch.quality,"require_scratch_space",
                      return_value={"free_gb":20,"required_gb":8}), \
         patch.object(batch,"destination_for",return_value=dest), \
         patch.object(batch,"resolve_docling_python",
                      return_value=sys.executable), \
         patch.object(batch,"preflight"), \
         patch.object(batch,"subchapter_ownership",
                      return_value=nullcontext(None)), \
         patch.object(batch,"process_one",side_effect=fake_dispatch):
        assert batch.main()==0
    assert seen==[("scope","1"),("stage","1")]
