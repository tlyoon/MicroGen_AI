"""Historical live G2: one distinct Gemini reviewer unavailable after key rotation.

Production fallback must choose another independent Gemini audio reviewer
without regenerating source/WAV or resending the available model's transcripts.
It must NEVER switch models to circumvent a genuine pronunciation mismatch.
"""
import pytest

import microgen_autonomous_acoustic_gate as gate


def _review(indexes):
    return {
        "slide_count": 3,
        "unavailable_recognizer_passes": list(indexes),
        "review_required_slides": ([1,2,3] if indexes else []),
        "slides": [],
    }


def _fake_engine(model, *, broken=False, calls=None):
    def recognize(path):
        if calls is not None:
            calls.append((model,str(path)))
        if broken:
            raise gate.AutonomousAcousticError("Unavailable Gemini audio reviewer")
        return f"Verified independent transcript from {model}"
    return recognize


def test_recovers_unavailable_secondary_reviewer_with_fixed_distinct_model(
    monkeypatch,
):
    counts=[]
    originals=("gemini-3.5-flash","gemini-3.8-flash")
    engines=(_fake_engine(originals[0],calls=counts),
             _fake_engine(originals[1],broken=True,calls=counts))
    calls=[]
    def provider_factory(models):
        calls.append(models)
        model=models[1]
        return (_fake_engine(models[0],calls=counts),
                _fake_engine(model,broken=model=="gemini-2.5-flash",
                             calls=counts),models)
    def transcript_stage(stage,texts,engines,models,*,memo):
        unavailable=set()
        for i in range(3):
            for index in (0,1):
                key=(index,f"SHA{i}")
                if key in memo:
                    continue
                if index in unavailable:
                    continue
                try:
                    memo[key]=engines[index](f"slide{i+1}.wav")
                except Exception:
                    unavailable.add(index)
        return _review(sorted(unavailable))
    monkeypatch.setattr(gate,"_transcripts",transcript_stage)
    initial_memo={}
    initial=transcript_stage(None,["a","b","c"],engines,originals,
                              memo=initial_memo)
    assert initial["unavailable_recognizer_passes"]==[1]
    assert len([v for v in counts if v[0]==originals[0]])==3
    report,actual_engines,models,memo,trace=gate._recover_unavailable_reviewers(
        None,["a","b","c"],engines,originals,initial,initial_memo,
        provider_factory=provider_factory)
    assert report["unavailable_recognizer_passes"]==[]
    assert models==("gemini-3.5-flash","gemini-2.5-pro")
    assert trace["status"]=="UNAVAILABLE_GEMINI_MODEL_REPLACED_FOR_ASR_ONLY"
    assert trace["actual_models"]==list(models)
    assert trace["publication_allowed"] is False
    assert [item["model"] for item in trace["attempts"]]==[
        "gemini-2.5-flash","gemini-2.5-pro"]
    assert all(pair[0]!=pair[1] for pair in calls)
    # The untouched independent model is not billed again.
    assert len([v for v in counts if v[0]==originals[0]])==3
    assert len([v for v in counts if v[0]=="gemini-2.5-pro"])==3
    assert len([k for k in memo if k[0]==0])==3
    assert len([k for k in memo if k[0]==1])==3


def test_no_model_switch_for_real_audio_disagreement():
    originals=gate.DEFAULT_MODELS
    report={"unavailable_recognizer_passes":[],
            "review_required_slides":[5],
            "slides":[{"slide":5,
                       "assessment":"REVIEW_REQUIRED_PRONUNCIATION_RISK"}]}
    def forbidden(*args,**kwargs):
        raise AssertionError("Must not shop models for favorable phonetic QA")
    result=gate._recover_unavailable_reviewers(
        None,["x"],(forbidden,forbidden),originals,report,{},
        provider_factory=forbidden)
    assert result[0] is report
    assert result[2]==originals
    assert result[4]=={}


def test_all_fallbacks_unavailable_still_fail_closed(monkeypatch):
    original=gate.DEFAULT_MODELS
    counts=[]
    def factory(models):
        counts.append(models)
        return (_fake_engine(models[0]),
                _fake_engine(models[1],broken=True),models)
    def unavailable(*args,**kwargs):
        return _review([1])
    monkeypatch.setattr(gate,"_transcripts",unavailable)
    initial=_review([1])
    report,engines,models,memo,trace=gate._recover_unavailable_reviewers(
        None,["x"],(_fake_engine(original[0]),_fake_engine(original[1])),
        original,initial,{},provider_factory=factory)
    assert report["unavailable_recognizer_passes"]==[1]
    assert models==original
    assert trace["status"]=="FINITE_GEMINI_REVIEWER_FALLBACK_EXHAUSTED"
    assert len(counts)==len(gate.BOUNDED_AUDIO_REVIEWER_FALLBACK)==2
    assert trace["publication_allowed"] is False


@pytest.mark.parametrize("bad",[[-1],[2],[True],["1"]])
def test_rejects_malformed_unavailable_model_pass_index(bad):
    with pytest.raises(gate.AutonomousAcousticError,
                       match="Malformed independent ASR"):
        gate._recover_unavailable_reviewers(
            None,["x"],(lambda x:"",lambda x:""),gate.DEFAULT_MODELS,
            _review(bad),{},provider_factory=lambda x: None)


def test_fallback_cannot_forge_model_identity(monkeypatch):
    original=gate.DEFAULT_MODELS
    monkeypatch.setattr(gate,"_transcripts",lambda *args,**kw:_review([1]))
    def lie(models):
        return (_fake_engine(models[0]),
                _fake_engine(models[1]),original)
    report,engines,models,memo,trace=gate._recover_unavailable_reviewers(
        None,["x"],(_fake_engine(original[0]),_fake_engine(original[1])),
        original,_review([1]),{},provider_factory=lie)
    assert models==original
    assert report["unavailable_recognizer_passes"]==[1]
    assert len(trace["attempts"])==2


def test_source_code_preserves_strict_two_model_check_and_actual_receipt():
    from pathlib import Path
    source=Path(gate.__file__).read_text(encoding="utf8")
    assert 'models[0]==models[1]' in source
    assert 'if report.get("unavailable_recognizer_passes")' in source
    assert 'report["independent_model_failover"]=model_failover' in source
    assert '"recognition_models":list(models)' in source
    assert 'for candidate in BOUNDED_AUDIO_REVIEWER_FALLBACK:' in source
    assert 'report=_recheck_disagreements' in source
