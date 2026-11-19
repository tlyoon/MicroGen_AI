"""Independent source/producer-bound PCM reuse, never old acoustic approval.

Regression of the paid 88-WAV re-synthesis loop when only Gemini ASR
normalization / reviewer implementation changes. All examples are synthetic;
the HP private real-source replay is verified separately outside this suite.
"""
import json
import os
from pathlib import Path
import wave

import pytest

import microgen_verified_tts_reuse as reuse


def _wav(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),"wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\x00\x00"*24000)


def _setup(tmp_path, monkeypatch):
    import fitz
    root=tmp_path/"MicroGen_AI_Checkpoints"
    root.mkdir()
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setattr(reuse.socket,"gethostname",lambda:"hp")
    oldwork=root/"OLD_SOURCE_G2"
    newwork=root/"NEW_REVIEWER_G2"
    old=oldwork/"2.5"
    new=newwork/"2.5"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    def pdf(path):
        with fitz.open() as doc:
            page=doc.new_page(width=650,height=400)
            page.insert_text((60,80),"Test source physics",fontsize=12)
            page.insert_text((570,365),"1 / 1",fontsize=10)
            doc.save(path)
    pdf(old/"slides.pdf")
    pdf(old/"source.pdf")
    for name in reuse.SOURCE[2:] + reuse.PRODUCER + (reuse.TIMED[0],):
        (old/name).write_bytes(("SYNTHETIC: "+name).encode())
    pdf(old/"slide1.pdf")
    for name in reuse.SOURCE+reuse.PRODUCER+(reuse.TIMED[0],):
        (new/name).write_bytes((old/name).read_bytes())
    (new/"slide1.pdf").write_bytes((old/"slide1.pdf").read_bytes())
    voice_env={"MICROGEN_TTS_VOICE":"Kore",
               "MICROGEN_FORMAL_TTS_PROVIDER":"gemini_flash_lite_tts",
               "MICROGEN_TIMED_CUES":"1",
               "MICROGEN_ACOUSTIC_MODEL_A":"gemini-3.5-flash",
               "MICROGEN_ACOUSTIC_MODEL_B":"gemini-3.8-flash"}
    def auth(work,revision,env=voice_env):
        scope={"code_revision":revision,"host":"hp",
               "work_root":str(work),
               "source_sha256":reuse._sha(new/"source.pdf"),
               "stop_after":"acceptance","provider_environment":env}
        (work/reuse.OWNER).write_text(json.dumps(
            {"schema_version":1,"publication_authorized":False,
             "scope":scope}),encoding="utf8")
    auth(oldwork,"OLD_REVISION")
    auth(newwork,"NEW_REVISION")
    (old/".microgen_checkpoint.json").write_text(json.dumps(
        {"package_commit":"OLD_REVISION",
         "completed":{"tts":"2026-11-13T01:00:00Z"}}))
    (old/".microgen_timed_highlights.json").write_text('{"source":"old"}')
    (old/".microgen_tts_provenance.json").write_text('{"slides":[1]}')
    _wav(old/"slide1.wav")
    _wav(old/"highlight_chunks"/"slide1_cue1.wav")
    cache=old/".microgen_tts_cache"
    cache.mkdir()
    (cache/("pronunciation-risk-"+"a"*24+".json")).write_text('{"risk":0}')
    cp={"package_commit":"NEW_REVISION","completed":{
        name:"verified" for name in (
        "figure_extraction","figure_mapping","figure_merge","slides",
        "narration","science_qa")}}
    def fake_verify(stage,count):
        assert count==1
        assert all((stage/name).exists() for name in
                   reuse.SOURCE+(reuse.TIMED[0],)+reuse.TIMED[1:])
        # An actual PDF-grounded math plan binds the source-math helper
        # policy SHA; candidate QA cannot run without those exact files.
        assert all((stage/name).is_file() for name in reuse.MATH_POLICY)
        assert (stage/"slide1.pdf").is_file()
        assert (stage/"slide1.wav").is_file()
        assert (stage/"highlight_chunks"/"slide1_cue1.wav").is_file()
    monkeypatch.setattr(reuse,"_verify",fake_verify)
    marked=[]
    def mark(*args):
        marked.append("tts")
        cp["completed"]["tts"]="reused"
    return old,new,newwork,cp,marked,mark,voice_env


def _run(new,newwork,cp,mark):
    return reuse.maybe_reuse_verified_tts(
        new,work_root=newwork,source_sha=reuse._sha(new/"source.pdf"),
        mark_complete=mark,cp=cp,
        checkpoint_path=new/".microgen_checkpoint.json",
        stage_valid=lambda s,n,d:n=="tts" and (s/"slide1.wav").exists(),
        dest=Path("PRIVATE_NONPUBLIC"))


def test_reuses_identical_pcm_from_failed_acoustic_campaign_without_old_verdict(
    tmp_path, monkeypatch,
):
    old,new,work,cp,marked,mark,_=_setup(tmp_path,monkeypatch)
    (old/".microgen_acoustic_blocked_PRIVATE.json").write_text(
        '{"status":"INDEPENDENT_ACOUSTIC_SCREEN_BLOCKED"}')
    result=_run(new,work,cp,mark)
    assert result["status"]=="SOURCE_BOUND_PCM_REVERIFIED_ACOUSTIC_REVIEW_REQUIRED"
    assert marked==["tts"]
    assert result["new_model_requests"] is False
    assert result["old_acoustic_reused"] is False
    assert reuse._sha(new/"slide1.wav")==reuse._sha(old/"slide1.wav")
    assert reuse._sha(new/"highlight_chunks"/"slide1_cue1.wav")==reuse._sha(
        old/"highlight_chunks"/"slide1_cue1.wav")
    assert not list(new.glob(".microgen_acoustic*"))
    assert not (new/".microgen_autonomous_acoustic_qa.json").exists()
    receipt=json.loads((new/reuse.RECEIPT).read_text())
    assert receipt["original_acoustic_approval_reused"] is False
    assert receipt["publication_allowed"] is False
    assert receipt["file_sha256"]["slide1.wav"]==reuse._sha(new/"slide1.wav")


@pytest.mark.parametrize("drift",[
    "source","script","narration_code","voice_policy","cue_plan",
    "source_slide","environment_voice","missing_grant",
    "old_unverified_tts","extra_cache_file","source_provenance",
    "source_math_policy","worked_equation_policy"
])
def test_mismatched_or_unverified_prior_audio_is_not_imported(
    tmp_path, monkeypatch, drift,
):
    old,new,work,cp,marked,mark,voice_env=_setup(tmp_path,monkeypatch)
    if drift=="source":
        (new/"source.pdf").write_bytes(b"DRIFT")
    elif drift=="script":
        (new/"script_tts.json").write_bytes(b"DRIFT")
    elif drift=="narration_code":
        (new/"text_to_speech_v25.py").write_bytes(b"DRIFT")
    elif drift=="voice_policy":
        (new/"microgen_reviewed_math_voice.py").write_bytes(b"DRIFT")
    elif drift=="source_math_policy":
        (new/reuse.MATH_POLICY[0]).write_bytes(b"DRIFT")
    elif drift=="worked_equation_policy":
        (new/reuse.MATH_POLICY[1]).write_bytes(b"DRIFT")
    elif drift=="cue_plan":
        (new/reuse.TIMED[0]).write_bytes(b"DRIFT")
    elif drift=="source_slide":
        (new/"slide1.pdf").write_bytes(b"DRIFT")
    elif drift=="environment_voice":
        grant=json.loads((work/reuse.OWNER).read_text())
        grant["scope"]["provider_environment"]["MICROGEN_TTS_VOICE"]="DifferentVoice"
        (work/reuse.OWNER).write_text(json.dumps(grant))
    elif drift=="missing_grant":
        (work/reuse.OWNER).unlink()
    elif drift=="old_unverified_tts":
        checkpoint=old/".microgen_checkpoint.json"
        j=json.loads(checkpoint.read_text())
        j["completed"]={}
        checkpoint.write_text(json.dumps(j))
    elif drift=="extra_cache_file":
        (old/".microgen_tts_cache"/"UNTRUSTED_CREDENTIAL.txt").write_text(
            "NEVER_COPY")
    elif drift=="source_provenance":
        grant=json.loads((old.parent/reuse.OWNER).read_text())
        grant["scope"]["source_sha256"]="0"*64
        (old.parent/reuse.OWNER).write_text(json.dumps(grant))
    assert _run(new,work,cp,mark) is None
    assert marked==[]
    assert not (new/"slide1.wav").exists()
    assert not (new/reuse.RECEIPT).exists()


def test_audio_reuse_does_not_cross_new_acoustic_models_or_require_same_review(
    tmp_path,monkeypatch,
):
    old,new,work,cp,marked,mark,_=_setup(tmp_path,monkeypatch)
    grant=json.loads((work/reuse.OWNER).read_text())
    grant["scope"]["provider_environment"]["MICROGEN_ACOUSTIC_MODEL_B"] = (
        "gemini-4-flash")
    (work/reuse.OWNER).write_text(json.dumps(grant))
    result=_run(new,work,cp,mark)
    assert result and result["wav_count"]==1
    assert not (new/".microgen_autonomous_acoustic_qa.json").exists()


def test_missing_preflight_plan_is_source_verified_and_imported_before_tts(
    tmp_path, monkeypatch,
):
    old,new,work,cp,marked,mark,_=_setup(tmp_path,monkeypatch)
    (new/reuse.TIMED[0]).unlink()
    result=_run(new,work,cp,mark)
    assert result and result["wav_count"]==1
    assert reuse._sha(new/reuse.TIMED[0])==reuse._sha(old/reuse.TIMED[0])
    assert marked==["tts"]
    assert reuse.verify_reuse_receipt(new)


@pytest.mark.parametrize("mutation",["wav","cue","policy","receipt","source"])
def test_reused_provenance_is_reverified_on_later_checkpoint(
    tmp_path, monkeypatch, mutation,
):
    old,new,work,cp,marked,mark,_=_setup(tmp_path,monkeypatch)
    assert _run(new,work,cp,mark)
    assert reuse.verify_reuse_receipt(new)
    file={"wav":"slide1.wav",
          "cue":reuse.TIMED[0],
          "policy":"microgen_reviewed_math_voice.py",
          "receipt":reuse.RECEIPT,
          "source":"source.pdf"}[mutation]
    if mutation=="receipt":
        row=json.loads((new/file).read_text())
        row["publication_allowed"]=True
        (new/file).write_text(json.dumps(row))
    else:
        (new/file).write_bytes(b"FALSIFIED")
    with pytest.raises((reuse.VerifiedTTSReuseError,OSError)):
        reuse.verify_reuse_receipt(new)


def test_wrong_code_bound_owner_grant_cannot_import_tts(
    tmp_path,monkeypatch,
):
    old,new,work,cp,marked,mark,_=_setup(tmp_path,monkeypatch)
    cp["package_commit"]="DIFFERENT_REVISION"
    assert _run(new,work,cp,mark) is None
    assert not (new/"slide1.wav").exists()


def test_original_math_policy_hashes_are_source_producer_dependencies():
    # All candidate copies must carry the exact same two policies that the
    # independent cue plan uses for PDF numerical and geometry grounding.
    import microgen_timed_cue_tts as timed
    assert len(reuse.MATH_POLICY)==2
    assert set(reuse.MATH_POLICY).issubset(set(reuse.PRODUCER))
    import inspect
    verifier=inspect.getsource(timed._verified_plan)
    for policy in reuse.MATH_POLICY:
        assert policy in verifier
    candidate_source=inspect.getsource(reuse.maybe_reuse_verified_tts)
    assert "for name in SOURCE + MATH_POLICY:" in candidate_source
    assert "shutil.copy2(stage/name,candidate/name)" in candidate_source


def test_newly_fixed_real_math_candidate_error_has_persistent_v6_history():
    from microgen_recovery_registry import load_registry, classify_log_attempt
    root=Path(__file__).resolve().parents[1]
    rules=load_registry(root)["entries"]
    matching=[x for x in rules
              if x["id"]=="MGA-TTS-REUSE-CUE-PLAN-PROVENANCE"]
    assert len(matching)==1
    row=matching[0]
    assert row["handler"]=="microgen_verified_tts_reuse.maybe_reuse_verified_tts"
    assert row["max_unmodified_retries"]==0
    assert row["publication_allowed"] is False
    # The source-only historical signature can be recognized during any
    # later child-process traceback. It must not authorize paying for or
    # accepting an audio result when the proof is absent.
    traceback=(
        "Traceback (most recent call last):\\n"
        "CueTTSError: Unreadable source-bound cue plan\\n"
    ).replace("\\n","\n").encode("utf8")
    found=classify_log_attempt("tts",traceback,registry_folder=root)
    assert found and found["failure_id"]==row["id"]
    assert found["disposition"]=="DETERMINISTIC_HOLD"


def test_normal_pcm_reuse_imports_historically_unknown_checkpoint_only_after_git_proof(
        tmp_path,monkeypatch):
    # Real earlier HP private runs recorded 'unknown' in the stage checkpoint
    # while the single-use grant was already pinned to full Git HEAD.
    # Test the NORMAL reuse function, not merely the legacy helper.
    from types import SimpleNamespace
    old,new,work,cp,marked,mark,_=_setup(tmp_path,monkeypatch)
    runner=old/"microgen_batch.py"
    runner.write_bytes(b"print('historic runner')\r\n")
    old_grant=json.loads((old.parent/reuse.OWNER).read_text())
    old_grant["scope"]["code_revision"]="a"*40
    (old.parent/reuse.OWNER).write_text(json.dumps(old_grant))
    old_cp=json.loads((old/".microgen_checkpoint.json").read_text())
    old_cp["package_commit"]="unknown"
    old_cp["inflight_provider_stage"]={
        "stage":"acoustic_qa",
        "source_sha256":reuse._sha(old/"source.pdf"),
        "runner_sha256":reuse._sha(runner),
    }
    (old/".microgen_checkpoint.json").write_text(json.dumps(old_cp))
    seen=[]
    def exact_git(args,**kwargs):
        seen.append(args[-1])
        return SimpleNamespace(returncode=0,stdout=b"print('historic runner')\n")
    monkeypatch.setattr(reuse.subprocess,"run",exact_git)
    result=_run(new,work,cp,mark)
    assert result["status"]=="SOURCE_BOUND_PCM_REVERIFIED_ACOUSTIC_REVIEW_REQUIRED"
    assert result["new_model_requests"] is False
    assert result["old_acoustic_reused"] is False
    assert seen==["a"*40+":microgen_batch.py"]
    assert marked==["tts"]
    assert reuse._sha(new/"slide1.wav")==reuse._sha(old/"slide1.wav")
    assert not (new/".microgen_autonomous_acoustic_qa.json").exists()


def test_historical_unknown_commit_without_exact_git_object_is_not_imported(
        tmp_path,monkeypatch):
    from types import SimpleNamespace
    old,new,work,cp,marked,mark,_=_setup(tmp_path,monkeypatch)
    runner=old/"microgen_batch.py"
    runner.write_bytes(b"print('historic runner')\r\n")
    grant=json.loads((old.parent/reuse.OWNER).read_text())
    grant["scope"]["code_revision"]="a"*40
    (old.parent/reuse.OWNER).write_text(json.dumps(grant))
    saved=json.loads((old/".microgen_checkpoint.json").read_text())
    saved["package_commit"]="unknown"
    saved["inflight_provider_stage"]={
        "stage":"acoustic_qa",
        "source_sha256":reuse._sha(old/"source.pdf"),
        "runner_sha256":reuse._sha(runner)}
    (old/".microgen_checkpoint.json").write_text(json.dumps(saved))
    monkeypatch.setattr(reuse.subprocess,"run",lambda *a,**k:
                        SimpleNamespace(returncode=0,stdout=b"wrong git blob"))
    assert _run(new,work,cp,mark) is None
    assert marked==[]
    assert not (new/"slide1.wav").exists()


def test_copied_tts_grant_to_different_private_root_never_authorizes_pcm(
        tmp_path,monkeypatch):
    import shutil
    old,new,work,cp,marked,mark,_=_setup(tmp_path,monkeypatch)
    copied=old.parent.parent/"UNAUTHORIZED_AUDIO_GRANT_COPY"
    shutil.copytree(old.parent,copied)
    shutil.rmtree(old.parent)
    assert _run(new,work,cp,mark) is None
    assert marked==[]
    assert not (new/"slide1.wav").exists()
    assert not (new/reuse.RECEIPT).exists()
