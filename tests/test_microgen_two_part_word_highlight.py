"""Tampering, ten-minute split and source-bound cue safety tests."""
import wave,json
from pathlib import Path
import pymupdf
import pytest
from microgen_source_safe_orchestrator import atomic_json
from microgen_fresh_source_cues import source_inventory
from microgen_two_part_word_highlight import validate,FreshHighlightError


def _fixture(tmp_path):
    p=pymupdf.open()
    for i in range(23):
        q=p.new_page()
        q.insert_text((20,40),f"Momentum slide {i+1}")
    p.save(tmp_path/"slides.pdf");p.close()
    for i in range(1,24):
        with wave.open(str(tmp_path/f"slide{i}.wav"),"wb") as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000)
            wav.writeframes(b"\x00\x00"*24000)
    _,src=source_inventory(tmp_path)
    rows=[{"slide":i,"wav_sha256":src["wav_inventory"][i-1]["wav_sha256"],
           "cues":[{"text":"momentum","start":.1,"end":.4,
                    "confidence":.95,"box":[20.,30.,100.,44.]}]}
          for i in range(1,24)]
    report={"schema_version":1,
            "status":"CURRENT_23_SLIDE_ASR_CANDIDATES_NOT_ACADEMIC_APPROVAL",
            "source":src,"slides":rows,"total_cues":23,
            "publication_allowed":False,"phonetic_correctness_verified":False,
            "figure_equation_alignment_verified":False}
    path=tmp_path.parent/"cues.json"
    atomic_json(path,report)
    return path


def test_current_audio_and_pdf_cues_validate(tmp_path):
    f=_fixture(tmp_path)
    assert validate(tmp_path,f)[2]["total_cues"]==23


@pytest.mark.parametrize("mutate",["wav_hash","pixel_box","audio_clock","false_approval","missing_slide"])
def test_forged_or_incompatible_asr_reports_rejected(tmp_path,mutate):
    f=_fixture(tmp_path)
    data=json.loads(f.read_text())
    if mutate=="wav_hash":data["slides"][3]["wav_sha256"]="wrong"
    elif mutate=="pixel_box":data["slides"][4]["cues"][0]["box"]=[0,0,9999,10000]
    elif mutate=="audio_clock":data["slides"][8]["cues"][0]["end"]=5.0
    elif mutate=="false_approval":data["publication_allowed"]=True
    else:data["slides"].pop()
    atomic_json(f,data)
    with pytest.raises(FreshHighlightError):
        validate(tmp_path,f)


def test_changed_original_wav_rejects_current_report(tmp_path):
    f=_fixture(tmp_path)
    with (tmp_path/"slide2.wav").open("ab") as wav:wav.write(b"X")
    with pytest.raises(FreshHighlightError):
        validate(tmp_path,f)
