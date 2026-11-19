"""Historical source-grounded science correction reused for spoken math names.

The real G2 narrator reads 'a x' as 'ay ex'; reviewer citations refer to
the original written source. Never require model quotes to be invented in
the TTS text, and never approve a non-original source correction.
"""
import copy
import json

import fitz
import pytest
from google.genai import types

import microgen_autonomous_science_qa as qa
from microgen_reviewed_math_voice import (
    reviewed_math_voice, voice_input_risk_status,
)
from text_to_speech_v25 import normalize_scientific_speech


WRONG = "The acceleration a x is five metres per second"
SOURCE = "The acceleration a x is ten metres per second"


def _make_stage(tmp_path):
    stage=tmp_path/"G2"
    stage.mkdir()
    with fitz.open() as pdf:
        page=pdf.new_page(width=600,height=250)
        page.insert_text((45,75),SOURCE+" in this example.",fontsize=11)
        pdf.save(stage/"source.pdf")
    with fitz.open() as pdf:
        for n in (1,2):
            page=pdf.new_page(width=600,height=250)
            page.insert_text((40,75),"Acceleration",fontsize=13)
            page.insert_text((40,120),f"{n} / 2",fontsize=10)
        pdf.save(stage/"slides.pdf")
    (stage/"slides.tex").write_text(r"\begin{document}\end{document}")
    right="The system has an ordinary time parameter."
    voiced=normalize_scientific_speech(reviewed_math_voice(WRONG))
    rows=[
        {"slide":1,"title":"Acceleration","narration":WRONG,"tts_text":voiced,
         "tts_math_voice_preflight":voice_input_risk_status(
             WRONG,normalize_scientific_speech)},
        {"slide":2,"title":"Time","narration":right,"tts_text":right},
    ]
    (stage/"script_tts.json").write_text(json.dumps({"slides":rows}),encoding="utf8")
    (stage/"script.txt").write_text(
        f"**Slide 1 [10 sec]:\n{WRONG}\n\n**Slide 2 [10 sec]:\n{right}\n",
        encoding="utf8")
    return stage


def _review_flag():
    return {"slide":1,"status":"error","issues":[{
        "field":"narration","observed_quote":WRONG,"source_quote":SOURCE,
        "suggested_replacement":SOURCE}]}


def _pass():
    return {"reviews":[
        {"slide":1,"status":"pass","issues":[]},
        {"slide":2,"status":"pass","issues":[]},
    ]}


def test_source_true_science_repair_updates_spoken_variable_and_rechecks(tmp_path):
    stage=_make_stage(tmp_path)
    original_source=(stage/"source.pdf").read_bytes()
    original_slides=(stage/"slides.pdf").read_bytes()
    calls=[]
    def reviewer(source,slides,items):
        calls.append(items[0]["narration"])
        if len(calls)==1:
            return {"reviews":[_review_flag(),_pass()["reviews"][1]]}
        assert items[0]["narration"]==SOURCE
        assert items[0]["tts_text"]==normalize_scientific_speech(
            reviewed_math_voice(SOURCE))
        return _pass()
    receipt=qa.audit_stage(stage,reviewer=reviewer)
    assert receipt["source_bound_narration_corrections"]==1
    assert receipt["unresolved_blocking_issues"]==0
    assert receipt["publication_allowed"] is False
    assert len(calls)==2
    assert qa.verify_receipt(stage)
    assert (stage/"source.pdf").read_bytes()==original_source
    assert (stage/"slides.pdf").read_bytes()==original_slides
    rows=json.loads((stage/"script_tts.json").read_text())["slides"]
    assert rows[0]["tts_math_voice_preflight"]["voice_input_sha256"]==__import__(
        "hashlib").sha256(rows[0]["tts_text"].encode()).hexdigest()
    assert rows[0]["tts_math_voice_preflight"]["phoneme_certified"] is False
    assert rows[0]["tts_math_voice_preflight"]["publication_allowed"] is False


def test_forged_math_voice_receipt_rejects_scientific_correction(tmp_path):
    stage=_make_stage(tmp_path)
    path=stage/"script_tts.json"
    data=json.loads(path.read_text())
    data["slides"][0]["tts_math_voice_preflight"]["voice_input_sha256"]="0"*64
    path.write_text(json.dumps(data))
    before=qa._inputs(stage)
    with pytest.raises(qa.ScienceQAError,match="Unbound mathematical voice"):
        qa.audit_stage(stage,reviewer=lambda *_:{"reviews":[_review_flag(),_pass()["reviews"][1]]})
    assert qa._inputs(stage)==before
    assert not (stage/qa.RECEIPT).exists()


def test_non_source_quotation_never_becomes_spoken_corrected_narration(tmp_path):
    stage=_make_stage(tmp_path)
    false=copy.deepcopy(_review_flag())
    false["issues"][0]["source_quote"]="The acceleration a x is ninety metres per second"
    false["issues"][0]["suggested_replacement"]=false["issues"][0]["source_quote"]
    before=qa._inputs(stage)
    with pytest.raises(qa.ScienceQAError,match="Unsupported or ungrounded"):
        qa.audit_stage(stage,reviewer=lambda *_:{"reviews":[false,_pass()["reviews"][1]]})
    assert qa._inputs(stage)==before


def test_native_gemini_science_response_schema_serializes_and_keeps_strict_validation():
    schema=qa.SCIENCE_REVIEW_RESPONSE_SCHEMA
    config=types.GenerateContentConfig(
        temperature=0, response_mime_type="application/json",
        response_json_schema=schema, max_output_tokens=8192)
    assert config.response_json_schema["required"]==["reviews"]
    row=config.response_json_schema["properties"]["reviews"]["items"]
    assert row["properties"]["status"]["enum"]==["pass","advisory","error"]
    assert row["properties"]["issues"]["items"]["properties"]["source_quote"]["type"]=="string"
    with pytest.raises(qa.ScienceQAError,match="skipped or duplicated"):
        qa._validate_review({"reviews":[_pass()["reviews"][0]]},2)
