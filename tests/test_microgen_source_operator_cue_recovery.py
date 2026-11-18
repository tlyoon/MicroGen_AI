"""Private 21-slide real-source operator repair, injected provider failures.

All provider callbacks in these tests are synthetic and do not establish
a real Gemini-reviewed WAV or private video acceptance.
"""
import json
import os
from pathlib import Path
import shutil
import wave

import pytest

from microgen_source_operator_cue_recovery import (
    _eligible,maybe_repair_rejected_operator,
    SourceOperatorCueRecoveryError,JOURNAL,
)
from microgen_autonomous_acoustic_gate import _normalized,verify_receipt
from microgen_verified_acoustic_replay import sha,OWNER
from microgen_one_sided_acoustic_replay import RECEIPT as RECHECK


@pytest.fixture
def full_real_source_campaign(tmp_path,monkeypatch):
    actual_root=Path(os.environ["LOCALAPPDATA"])/"MicroGen_AI_Checkpoints"
    historical=actual_root/"20261118_HP_G3_SERWAY27_TIMED_REPAIR_9B7_PRIVATE"/"2.7"
    rejected=actual_root/"20261118_HP_G3_SERWAY27_ONE_SIDED_2FE9_PRIVATE"/"2.7"
    if (not historical.is_dir() or not rejected.is_dir()):
        pytest.skip("Real HP private campaign evidence unavailable")
    root=tmp_path/"MicroGen_AI_Checkpoints"
    old=root/"original-private"/"2.7"
    newer=root/"new-private"/"2.7"
    previous=root/"prior-rejected"/"2.7"
    for path in (old,newer,previous):
        path.mkdir(parents=True)
    repo=Path(__file__).resolve().parents[1]
    names=[
        "source.pdf","slides.pdf","slides.tex","script_tts.json",
        "script.txt",".microgen_tts_provenance.json",
        ".microgen_timed_highlights.json",".microgen_timed_cue_plan.json",
    ]
    for stage in (old,newer):
        for name in names:
            os.link(historical/name,stage/name)
        for i in range(1,22):
            os.link(historical/f"slide{i}.wav",stage/f"slide{i}.wav")
            os.link(historical/f"slide{i}.pdf",stage/f"slide{i}.pdf")
        (stage/"highlight_chunks").mkdir()
        for source in (historical/"highlight_chunks").glob("*.wav"):
            os.link(source,stage/"highlight_chunks"/source.name)
        (stage/".microgen_tts_cache").mkdir()
        for entry in (historical/".microgen_tts_cache").glob("*.json"):
            os.link(entry,stage/".microgen_tts_cache"/entry.name)
    shutil.copy2(historical/"microgen_autonomous_acoustic_gate.py",
                 old/"microgen_autonomous_acoustic_gate.py")
    shutil.copy2(repo/"microgen_autonomous_acoustic_gate.py",
                 newer/"microgen_autonomous_acoustic_gate.py")
    shutil.copy2(repo/"microgen_source_operator_cue_recovery.py",
                 newer/"microgen_source_operator_cue_recovery.py")
    for pattern in (".microgen_acoustic_blocked_*.json",
                    ".microgen_private_acoustic_failed_*.json"):
        for source in historical.glob(pattern):
            shutil.copy2(source,old/source.name)
    for campaign,rev in ((old.parent,"9b7b31eea04300463442a12fdc046f2f1fdb5a84"),
                         (newer.parent,"9e031480fac776163a0c83b2f8cc253b7deb7f3b")):
        grant={"publication_authorized":False,
               "scope":{"host":"hp","work_root":str(campaign),
                        "source_sha256":sha(newer/"source.pdf"),
                        "stop_after":"acceptance","code_revision":rev}}
        (campaign/OWNER).write_text(json.dumps(grant),encoding="utf8")
        (campaign/"2.7"/".microgen_checkpoint.json").write_text(
            json.dumps({"package_commit":rev,"completed":{"tts":"2026-11-18"}}),
            encoding="utf8")
    before=json.loads((rejected/RECHECK).read_text(encoding="utf8"))
    before["source_binding"]["old_campaign"]=old.parent.name
    priorgrant={
        "publication_authorized":False,
        "scope":{"host":"hp","work_root":str(previous.parent),
                 "source_sha256":sha(newer/"source.pdf")}
    }
    (previous.parent/OWNER).write_text(json.dumps(priorgrant),encoding="utf8")
    (previous/RECHECK).write_text(json.dumps(before),encoding="utf8")
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    return old,newer,previous


def synthentic_new_cue(wav:Path,output:Path):
    """Real old WAV frames plus short silent pause, synthetic NON-speech proof."""
    with wave.open(str(wav),"rb") as inp:
        config=inp.getparams()
        raw=inp.readframes(inp.getnframes())
    frames=int(config.framerate*.12)
    silence=b"\x00"*(config.nchannels*config.sampwidth*frames)
    with wave.open(str(output),"wb") as out:
        out.setparams(config)
        out.writeframes(raw+silence)


def good_fake_recognizers(original,transcripts):
    def first(path):
        transcripts.append((0,path.name))
        return original
    def second(path):
        transcripts.append((1,path.name))
        return original
    return lambda:(first,second,("gemini-3.5-flash","gemini-3.8-flash"))


def test_real_authenticated_previous_rejection_selects_only_cue_5_2(
        full_real_source_campaign):
    old,new,prior=full_real_source_campaign
    found=_eligible(new,_normalized(new))
    assert found is not None
    assert found["selected"]=={5:[2]}
    assert found["found"]["retakes"]==[(5,1)]
    assert found["rejected"][1]==prior/RECHECK


def test_full_real_21_slide_transaction_with_fake_gemini_and_immutable_source(
        full_real_source_campaign):
    old,new,prior=full_real_source_campaign
    source=_normalized(new)
    before={name:sha(new/name) for name in (
        "source.pdf","script_tts.json","slide6.wav","slide5.wav",
        "highlight_chunks/slide5_cue1.wav",
        "highlight_chunks/slide5_cue3.wav",
        "highlight_chunks/slide5_cue4.wav")}
    called=[]
    def fake_tts(text,wav,record):
        called.append(("TTS",wav.name))
        assert "divided by" in text.casefold()
        synthentic_new_cue(new/"highlight_chunks/slide5_cue2.wav",wav)
    reviewers=good_fake_recognizers(source[4],called)
    receipt=maybe_repair_rejected_operator(
        new,source,synthesize=fake_tts,recognizer_factory=reviewers)
    assert receipt["status"]=="AUTONOMOUS_INDEPENDENT_ASR_SCREEN_PASSED"
    assert receipt["repaired_audio_slides"]==1
    assert len(called)==3
    assert called[0][0]=="TTS"
    assert {x[0] for x in called[1:]}=={0,1}
    for name,value in before.items():
        if name=="slide5.wav":
            assert sha(new/name)!=value
        else:
            assert sha(new/name)==value
    assert verify_receipt(new)["slide_count"]==21
    assert sha(old/"slide5.wav")==before["slide5.wav"]
    assert sha(new/"highlight_chunks/slide5_cue2.wav")!=sha(
        old/"highlight_chunks/slide5_cue2.wav")
    state=json.loads((new/JOURNAL).read_text())
    assert state["status"]=="INDEPENDENT_ACOUSTIC_QA_PASSED"
    with pytest.raises(SourceOperatorCueRecoveryError):
        maybe_repair_rejected_operator(
            new,source,synthesize=lambda *_:pytest.fail("Billed twice"))


def test_paid_provider_crash_stops_duplicate_charge_before_audio_mutation(
        full_real_source_campaign):
    old,new,prior=full_real_source_campaign
    source=_normalized(new)
    original=sha(new/"slide5.wav")
    attempts=[]
    class SimulatedUncertainProvider(BaseException):pass
    def fails(*args):
        attempts.append("TTS")
        raise SimulatedUncertainProvider("crash after provider request reserved")
    with pytest.raises(SimulatedUncertainProvider):
        maybe_repair_rejected_operator(
            new,source,synthesize=fails,
            recognizer_factory=lambda:pytest.fail("No ASR before TTS"))
    assert attempts==["TTS"]
    assert sha(new/"slide5.wav")==original
    assert json.loads((new/JOURNAL).read_text())["status"]=="TTS_RESERVED"
    with pytest.raises(SourceOperatorCueRecoveryError,
                       match="PRIOR_SOURCE_OPERATOR_TTS_RESERVATION_HOLD"):
        maybe_repair_rejected_operator(
            new,source,synthesize=lambda *_:pytest.fail("Duplicate billing"))
    assert sha(new/"slide5.wav")==original


def test_new_pcm_rejected_by_realistic_contrary_mock_does_not_install(
        full_real_source_campaign):
    old,new,prior=full_real_source_campaign
    text=_normalized(new)[4]
    original=sha(new/"slide5.wav")
    def fake_tts(t,d,r):
        synthentic_new_cue(new/"highlight_chunks/slide5_cue2.wav",d)
    def reviewers():
        return (lambda _:text,
                lambda _:text.replace("divided by",""),
                ("gemini-3.5-flash","gemini-3.8-flash"))
    from microgen_timed_acoustic_repair import TimedAcousticRepairError
    with pytest.raises(TimedAcousticRepairError,match="reviewers rejected"):
        maybe_repair_rejected_operator(
            new,_normalized(new),synthesize=fake_tts,
            recognizer_factory=reviewers)
    assert sha(new/"slide5.wav")==original
    assert json.loads((new/JOURNAL).read_text())["status"]=="ASR_REJECTED"


def test_no_new_pcm_no_paid_asr_and_no_source_mutation(full_real_source_campaign):
    old,new,prior=full_real_source_campaign
    before=sha(new/"slide5.wav")
    from microgen_source_operator_cue_recovery import (
        SourceOperatorCueRecoveryError,
    )
    with pytest.raises(SourceOperatorCueRecoveryError,
                       match="UNCHANGED_CUE_PCM_HOLD"):
        maybe_repair_rejected_operator(
            new,_normalized(new),
            synthesize=lambda text,d,record:shutil.copy2(
                new/"highlight_chunks/slide5_cue2.wav",d),
            recognizer_factory=lambda:pytest.fail(
                "Never review a reissued identical PCM"))
    assert sha(new/"slide5.wav")==before


def test_executable_registry_handles_uncertain_paid_single_cue_send():
    from microgen_recovery_registry import classify_log_attempt
    repo=Path(__file__).resolve().parents[1]
    decision=classify_log_attempt(
        "acoustic_qa",
        b"Traceback (most recent call last):\n"
        b"AutonomousAcousticError: SOURCE_OPERATOR_CUE_RESERVATION_HOLD "
        b"after uncertain provider send\n",
        registry_folder=repo)
    assert decision is not None
    assert decision["failure_id"]==(
        "MGA-20261118-SINGLE-OPERATOR-CUE-REPAIR-RESERVATION")
    assert decision["max_unmodified_retries"]==0
    assert decision["disposition"]=="UNRESOLVED_EXTERNAL_EFFECT_HOLD"
