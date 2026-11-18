"""Context-bound a_x voice clarity: no global math substitutions or QA bypass."""
import hashlib,json,os,shutil
from pathlib import Path
import pytest
from microgen_reviewed_math_voice import reviewed_math_voice,voice_input_risk_status,preflight_voice_sidecar
from microgen_cue_semantic_mapping import numbers
from text_to_speech_v25 import normalize_scientific_speech
from microgen_quality import check_narration
from microgen_timed_cue_planner import _require_budget_preflight


def speak(value):
    return normalize_scientific_speech(reviewed_math_voice(value))


def test_complete_kinematics_equations_and_zero_acceleration_axis():
    original=("Here we assemble the complete set of kinematic equations for constant ay ex, "
              "describing position and velocity. Consider the special case where ay ex equals zero. "
              "Then v ex final equals v ex initial.")
    revised=speak(original)
    assert "constant acceleration along the ex axis" in revised
    assert "where the acceleration along the ex axis equals zero" in revised
    assert "ay ex" not in revised
    assert numbers(original)==numbers(revised)
    assert speak(revised)==revised


def test_a_x_in_time_solution_denominator_and_comparative_trend():
    original=("All terms on the right-hand side of the time solution have a x in the denominator. "
              "Therefore, increasing a x decreases the overtake time t.")
    revised=speak(original)
    assert "have the ex component of acceleration in the denominator" in revised
    assert "increasing the ex component of acceleration decreases" in revised
    assert numbers(original)==numbers(revised)
    assert speak(revised)==revised


@pytest.mark.parametrize("phrase",[
    "An arbitrary letter a times x does not identify acceleration.",
    "The complete set of kinematic equations for constant ay why is different.",
    "The complete set of kinematic equations for constant vee ex is different.",
    "For constant ay ex, the arithmetic mean is not stated here.",
    "The special case where ay why equals zero is different.",
    "Some terms have a x in the denominator, but this is not a time solution.",
    "The time solution includes a times x in a numerator.",
    "Increasing a y decreases an unrelated observation.",
])
def test_no_unsupported_math_substitution(phrase):
    assert speak(phrase)==normalize_scientific_speech(phrase)


def test_real_hp_21_slide_no_paid_fresh_acceptance_preflight(tmp_path):
    configured=os.environ.get("MICROGEN_HP_G3_FRESH_STAGE")
    if not configured:
        pytest.skip("Only enabled against authorized private HP real stage")
    stage=Path(configured);data=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    original={row["slide"]:dict(row) for row in data["slides"]}
    before={i:hashlib.sha256((stage/f"slide{i}.wav").read_bytes()).hexdigest() for i in range(1,22)}
    changed=[]
    for row in data["slides"]:
        old=row["tts_text"];new=speak(old)
        assert numbers(old)==numbers(new)
        assert speak(new)==new
        if new!=old:changed.append(row["slide"])
        row["tts_text"]=new
        row["tts_math_voice_preflight"]=voice_input_risk_status(new,normalize_scientific_speech)
        assert row["narration"]==original[row["slide"]]["narration"]
    assert changed==[11,19]
    tmp=tmp_path/"real_21_slide_shadow";tmp.mkdir()
    for name in ["source.pdf","slides.pdf","script.txt","slides.tex"]+[f"slide{i}.pdf" for i in range(1,22)]:
        shutil.copy2(stage/name,tmp/name)
    (tmp/"script_tts.json").write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf8")
    check_narration(tmp/"script.txt",tmp/"script_tts.json",21)
    preflight_voice_sidecar(tmp,require_policy_binding=True)
    _require_budget_preflight(tmp,semantic_limit=4,max_cues=120)
    assert hashlib.sha256((stage/"source.pdf").read_bytes()).digest()==hashlib.sha256((tmp/"source.pdf").read_bytes()).digest()
    assert before=={i:hashlib.sha256((stage/f"slide{i}.wav").read_bytes()).hexdigest() for i in range(1,22)}

@pytest.mark.parametrize("malformed",[
    "Here is the complete set of kinematic equations for constant ay why, not x.",
    "Here is the complete set of kinematic equations for constant ay ex squared.",
    "Here is the complete set of kinematic equations for constant ay ex plus a term.",
    "In the special case where ay why equals zero, motion is different.",
    "The acceleration is where ay ex equals one, not zero.",
    "Some unrelated terms have a x in the denominator.",
    "All terms on the left-hand side of the time solution have a x in the denominator.",
    "All terms on the right-hand side of a different formula have a x in the denominator.",
    "Increasing a x increases the overtake time.",
    "Increasing a y decreases the overtake time.",
])
def test_fault_injected_wrong_axis_operator_or_equation_role_is_not_revoiced(malformed):
    assert speak(malformed)==normalize_scientific_speech(malformed)


def test_real_failed_acoustic_registry_disposition_and_adapter_binding():
    configured=os.environ.get("MICROGEN_HP_G3_FRESH_STAGE")
    if not configured:
        pytest.skip("Real private stage required")
    from microgen_recovery_registry import classify_log_attempt
    stage=Path(configured)
    registry=Path(__file__).resolve().parents[1]
    failure=(stage.parent/"2.7.log").read_bytes()
    decision=classify_log_attempt("acoustic_qa",failure,registry_folder=registry)
    assert decision["failure_id"]=="MGA-ACOUSTIC-REPAIR-BUDGET-HOLD"
    assert decision["handler"]=="microgen_reviewed_math_voice.reviewed_math_voice"
    assert decision["max_unmodified_retries"]==0
    assert decision["disposition"]=="DETERMINISTIC_HOLD"
    assert classify_log_attempt("tts",failure,registry_folder=registry) is None


def test_fault_injected_voice_policy_receipt_drift_is_fail_closed(tmp_path):
    configured=os.environ.get("MICROGEN_HP_G3_FRESH_STAGE")
    if not configured:
        pytest.skip("Real private stage required")
    from microgen_reviewed_math_voice import VoiceRiskPreflightError
    stage=Path(configured)
    data=json.loads((stage/"script_tts.json").read_text(encoding="utf8"))
    for row in data["slides"]:
        new=speak(row["tts_text"])
        row["tts_text"]=new
        row["tts_math_voice_preflight"]=voice_input_risk_status(new,normalize_scientific_speech)
    sidecar=tmp_path/"script_tts.json"
    sidecar.write_text(json.dumps(data,ensure_ascii=False),encoding="utf8")
    assert preflight_voice_sidecar(tmp_path,require_policy_binding=True)["source_risk_count"]==0
    data["slides"][10]["tts_math_voice_preflight"]["voice_adapter_code_sha256"]="0"*64
    sidecar.write_text(json.dumps(data,ensure_ascii=False),encoding="utf8")
    with pytest.raises(VoiceRiskPreflightError,match="code changed"):
        preflight_voice_sidecar(tmp_path,require_policy_binding=True)
