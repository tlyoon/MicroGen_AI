"""G3 a_x acceleration voice clarity: no general homophone waiver.

Fixture-only tests do not call Gemini. Optional HP private Serway 2.7 proof
verifies the entire existing 21-slide PDF, raw narration, numerical evidence,
voice policy, semantic cue budget and original WAV immutability.
"""
import hashlib,json,os,shutil
from pathlib import Path

import pytest
from microgen_reviewed_math_voice import (
    reviewed_math_voice,voice_input_risk_status,preflight_voice_sidecar,
)
from text_to_speech_v25 import normalize_scientific_speech
from microgen_cue_semantic_mapping import numbers
from microgen_quality import check_narration
from microgen_timed_cue_planner import _require_budget_preflight


def example():
    return (
        "We examine average velocity for constant acceleration. Since "
        "velocity varies linearly, average velocity is the arithmetic mean "
        "of the initial and final velocities, vee sub ex average equals "
        "vee sub ex initial plus vee sub ex final divided by two, "
        "for constant ay sub ex. No additional force is assumed."
    )


def output(text):
    return normalize_scientific_speech(reviewed_math_voice(text))


def test_contextual_acceleration_math_phrase_is_not_the_letter_i():
    source=example()
    revised=output(source)
    assert "for constant acceleration along the ex axis" in revised
    assert "for constant ay sub ex" not in revised
    assert output(revised)==revised
    assert numbers(source)==numbers(revised)
    assert output(source.replace("ay sub ex","ay ex"))==revised


@pytest.mark.parametrize("input_text",[
    "For constant ay sub ex, use this formula.",
    "A harmonic mean is valid for constant ay sub ex.",
    "The arithmetic mean is valid only for constant ay sub why.",
    "The arithmetic mean is valid for constant vee sub ex.",
    "The arithmetic mean is valid for constant ay sub ex squared.",
    "The arithmetic mean is valid for constant ay sub ex plus other terms.",
    "The arithmetic mean is valid for constant ay sub ex minus a correction.",
    "The arithmetic mean is valid for constant ay sub ex divided by time.",
    "The arithmetic mean is valid for constant ay sub ex cubed.",
    "The arithmetic mean is valid for constant ay sub ex multiplied by tee.",
])
def test_no_global_substitution_or_equation_overreach(input_text):
    assert "for constant acceleration along the ex axis" not in output(input_text)


@pytest.mark.parametrize("different",[
    example().replace("for constant ay sub ex","for constant ay sub why"),
    example().replace("arithmetic mean","geometric mean"),
    example().replace("for constant ay sub ex","for constant vee sub ex"),
    example().replace("for constant ay sub ex","for negative ay sub ex"),
])
def test_changed_math_or_axis_cannot_trigger_voice_repair(different):
    assert "for constant acceleration along the ex axis" not in output(different)


def test_only_one_math_clause_changed_in_safe_synthetic_content():
    source=example()
    augmented=(
        source+" The position expression applies for constant ay sub ex. "
        "The combined kinematic equations hold for constant ay ex."
    )
    actual=output(augmented)
    assert actual.count("for constant acceleration along the ex axis")==1
    assert "The position expression applies for constant ay sub ex." in actual
    assert "for constant ay ex" in actual
    assert output(actual)==actual


def test_actual_hp_serway_21_slide_source_preflights_offline(tmp_path):
    value=os.environ.get("MICROGEN_HP_G3_COMPONENT_STAGE","")
    if not value:
        pytest.skip("Owner HP private stage fixture not mounted")
    stage=Path(value)
    data=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    orig_scripts=[dict(row) for row in data["slides"]]
    assert len(orig_scripts)==21
    before={row["slide"]:row["tts_text"] for row in orig_scripts}
    original_wav_hashes={
        f"slide{n}.wav":hashlib.sha256((stage/f"slide{n}.wav").read_bytes()).hexdigest()
        for n in range(1,22)
    }
    changed=[]
    for row in data["slides"]:
        old=row["tts_text"]
        revised=output(old)
        if revised!=old:changed.append(row["slide"])
        assert numbers(old)==numbers(revised)
        assert output(revised)==revised
        row["tts_text"]=revised
        row["tts_math_voice_preflight"]=voice_input_risk_status(
            revised,normalize_scientific_speech)
    assert changed==[6]
    assert data["slides"][5]["narration"]==orig_scripts[5]["narration"]
    assert "for constant acceleration along the ex axis" in (
        data["slides"][5]["tts_text"])
    tmp=tmp_path/"private_21_slide_shadow"
    tmp.mkdir()
    for name in ["source.pdf","slides.pdf","script.txt","slides.tex"]+[
            f"slide{n}.pdf" for n in range(1,22)]:
        shutil.copy2(stage/name,tmp/name)
    (tmp/"script_tts.json").write_text(
        json.dumps(data,indent=2,ensure_ascii=False),encoding="utf8")
    check_narration(tmp/"script.txt",tmp/"script_tts.json",21)
    preflight_voice_sidecar(tmp,require_policy_binding=True)
    _require_budget_preflight(tmp,semantic_limit=4,max_cues=120)
    assert hashlib.sha256((tmp/"source.pdf").read_bytes()).hexdigest()==(
        hashlib.sha256((stage/"source.pdf").read_bytes()).hexdigest())
    assert original_wav_hashes=={
        f"slide{n}.wav":hashlib.sha256((stage/f"slide{n}.wav").read_bytes()).hexdigest()
        for n in range(1,22)
    }
