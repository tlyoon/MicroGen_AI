"""ASR-candidate highlight frame bounds are SHA/current-PCM based, never release."""
import io
import json
from pathlib import Path

import pymupdf as fitz
import pytest

import microgen_corrected_word_video as unit
from microgen_audio_cue_binding import bind_cues_to_current_audio, _verified_audio_rows
from microgen_source_safe_orchestrator import atomic_json,digest
from test_microgen_corrected_slide_clock import _ready


def _fixture(tmp_path,monkeypatch):
    src,stage,selection,shadow=_ready(tmp_path)
    source,audios,intervals=_verified_audio_rows(stage)
    with fitz.open(src/"slides.pdf") as pdf:
        word=pdf[0].get_text("words")[0]
    box=list(word[:4])
    elements=[{"slide":1,"text":"source","box":box,
               "local_start":.01,"local_end":.16,
               "start_seconds":.01,"end_seconds":.16}]
    cues=bind_cues_to_current_audio(stage,elements,
                  derivation="CURRENT_STAGE_OFFLINE_ASR_NOT_PHONETIC_GROUND_TRUTH")
    atomic_json(stage/"cues.json",cues)
    (tmp_path/"asr_reports").mkdir()
    report=tmp_path/"asr_reports"/"real_candidate_observation.json"
    atomic_json(report,{
       "schema_version":1,"status":"CURRENT_STAGE_OFFLINE_ASR_NOT_GROUND_TRUTH",
       "publication_allowed":False,
       "phonetic_identity_verified":False,
       "semantic_alignment_verified":False,
       "source_pdf_sha256":source["source_pdf_sha256"],
       "narration_sha256":source["narration_sha256"],
       "stage_audio_bindings":audios,
       "results":[{"slide":i,"source_wav_sha256":audio["wav_sha256"],"words":[]}
                  for i,audio in enumerate(audios,1)]})
    ff=tmp_path/"ffmpeg.exe";ff.write_bytes(b"mocked FFmpeg")
    monkeypatch.setattr(unit,"WIDTH",320)
    monkeypatch.setattr(unit,"HEIGHT",180)
    return src,stage,selection,shadow,report,ff


def test_synthetic_current_cue_render_preserves_full_pcm_and_release_false(tmp_path,monkeypatch):
    src,stage,sel,shadow,asr,ff=_fixture(tmp_path,monkeypatch)
    plan=unit.build_slide_clock(stage,sel,shadow)
    byte_lengths=[]
    class FakeInput:
        def write(self,content):
            byte_lengths.append(len(content))
        def close(self):pass
    class FakeStderr:
        def read(self):return b""
        def close(self):pass
    class FakeProc:
        stdin=FakeInput()
        stderr=FakeStderr()
        def poll(self):return 0
        def wait(self,timeout=None):return 0
    def fake_launch(command,**kwargs):
        Path(command[-1]).write_bytes(b"fake technical output")
        return FakeProc()
    monkeypatch.setattr(unit.subprocess,"Popen",fake_launch)
    monkeypatch.setattr(unit,"check_video",
                        lambda *a,**kw:{"seconds":plan["audio_seconds"]})
    monkeypatch.setattr(unit,"_decoded_audio_hash",lambda *a:plan["pcm"])
    output=tmp_path/"new_overlay"
    result=unit.render_corrected_word_highlight_candidate(
        stage,sel,shadow,asr,output,ffmpeg=ff)
    assert result["pcm_verified"] is True
    assert result["frames_with_cues"]>=1
    receipt=json.loads((output/"word_highlight_candidate_receipt.json").read_text())
    assert receipt["candidate_cues"]==1
    assert receipt["frames_rendered"]==len(byte_lengths)
    assert set(byte_lengths)=={unit.WIDTH*unit.HEIGHT*3}
    assert receipt["word_highlight_pixels_independently_verified"] is False
    assert receipt["phonetic_correctness_verified"] is False
    assert receipt["publication_allowed"] is False
    assert (src/"slides.pdf").exists()


@pytest.mark.parametrize("tamper",["old_cue","approved","audio","asr","cuebox","old_asr"])
def test_refuse_stale_cues_or_changed_sources_before_render(tmp_path,monkeypatch,tamper):
    src,stage,sel,shadow,asr,ff=_fixture(tmp_path,monkeypatch)
    if tamper in ("old_cue","approved","cuebox"):
        p=stage/"cues.json"
        obj=json.loads(p.read_text())
        if tamper=="old_cue":obj["derivation"]="OLD_UNBOUND_CUES"
        if tamper=="approved":obj["publication_allowed"]=True
        if tamper=="cuebox":obj["elements"][0]["box"]=[-1,2,300,500]
        atomic_json(p,obj)
    if tamper=="audio":
        (stage/"audio"/"slide6.wav").write_bytes(b"mutated")
    if tamper in ("asr","old_asr"):
        p=asr;obj=json.loads(p.read_text())
        if tamper=="asr":obj["stage_audio_bindings"][0]["wav_sha256"]="0"*64
        else:obj["status"]="OLD_SOUND_OBSERVATION"
        atomic_json(p,obj)
    output=tmp_path/"new_overlay"
    with pytest.raises((ValueError,OSError)):
        unit.render_corrected_word_highlight_candidate(
            stage,sel,shadow,asr,output,ffmpeg=ff)
    assert not output.exists()


def test_highlight_box_changes_pixels_but_not_unrelated_area(tmp_path,monkeypatch):
    src,stage,sel,shadow,asr,ff=_fixture(tmp_path,monkeypatch)
    pdfsha,frames,transforms=unit._pdf_frames(src)
    target={"box":json.loads((stage/"cues.json").read_text())["elements"][0]["box"]}
    changed=unit._highlight(frames[0],transforms[0],[target])
    assert changed.tobytes()!=frames[0].tobytes()
    assert changed.getpixel((319,179))==frames[0].getpixel((319,179))
    assert digest(src/"slides.pdf")==pdfsha


def test_existing_highlight_output_never_replaced(tmp_path,monkeypatch):
    _,stage,sel,shadow,asr,ff=_fixture(tmp_path,monkeypatch)
    p=tmp_path/"occupied";p.mkdir()
    with pytest.raises(unit.CorrectedHighlightError,match="independent"):
        unit.render_corrected_word_highlight_candidate(
            stage,sel,shadow,asr,p,ffmpeg=ff)
