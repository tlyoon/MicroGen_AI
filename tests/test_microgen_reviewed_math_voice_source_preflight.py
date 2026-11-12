"""Regression: recurring source math pronunciation risks must be fixed before billable TTS.

No provider calls, no source mutation, no phonetic approval inferred.
"""
import json
from pathlib import Path

import pytest

from microgen_reviewed_math_voice import (
    reviewed_math_voice, voice_input_risk_status,
    preflight_voice_sidecar, VoiceRiskPreflightError,
)
from text_to_speech_v25 import normalize_scientific_speech
from microgen_tts_risk_register import find_pronunciation_risks


@pytest.mark.parametrize("raw, fragment", [
    ("The acceleration a x, is defined here.", "acceleration ay ex,"),
    ("The instantaneous acceleration a x as the limit appears.",
     "acceleration ay ex as the limit"),
    ("Later a x becomes negative.", "ay ex becomes negative."),
    ("The velocity and a x both vanish.", "ay ex both vanish."),
    ("A velocity increment delta v x equal to minus 10 t.",
     "delta vee ex equal to minus 10 t"),
    ("At time t C where the slope changes.", "time tee see where"),
    ("Velocity v x versus t.", "velocity vee ex versus tee."),
    ("Position d x over d t.", "position dee ex over d t."),
    ("Use d squared x over d t squared.", "dee squared ex over d t squared"),
    ("A v sub x is constant.", "vee sub ex is constant"),
    ("Later, a sub x equals zero.", "ay sub ex equals zero"),
    ("The point occurs at time t C.", "time tee see."),
    ("Position x of t is constant.", "ex of tee is constant"),
    ("Position b t cubed minus c t.", "minus see tee"),
    ("Use the x-axis for position.", "ex axis"),
])
def test_reviewed_variable_spoken_form_is_explicit_and_not_high_risk(raw, fragment):
    speech = normalize_scientific_speech(reviewed_math_voice(raw))
    assert fragment.casefold() in speech.casefold()
    assert not find_pronunciation_risks(speech, speech)
    assert normalize_scientific_speech(reviewed_math_voice(speech)) == speech


@pytest.mark.parametrize("ordinary", [
    "A xylitol tablet is sweet.",
    "The x-ray apparatus is ready.",
    "The painter made a x mark in the margin.",
    "Vitamin C is available here.",
    "The letter C. Smith signed the report.",
    "This discovery occurred c. 1900.",
    "We measured a wave with vector components.",
    "We use a y-shaped junction.",
])
def test_no_global_letter_rewrites_in_ordinary_prose(ordinary):
    assert reviewed_math_voice(ordinary) == ordinary


def test_old_unresolved_source_risk_blocks_before_spending(tmp_path):
    stage = tmp_path / "2.5"
    stage.mkdir()
    src = "The variable y approaches zero."
    (stage / "script_tts.json").write_text(
        json.dumps({"slides": [{"slide": 1, "tts_text": src}]}),
        encoding="utf8")
    with pytest.raises(VoiceRiskPreflightError, match="PREPAY_HOLD"):
        preflight_voice_sidecar(stage)


def test_reviewed_source_voice_can_proceed_but_no_audio_pass_is_claimed(tmp_path):
    stage = tmp_path / "2.5"
    stage.mkdir()
    raw = "The acceleration a x, changes as v sub x becomes constant."
    status = voice_input_risk_status(raw, normalize_scientific_speech)
    assert status["unresolved_source_risk_count"] == 0
    assert status["phoneme_certified"] is False
    speech = normalize_scientific_speech(reviewed_math_voice(raw))
    (stage / "script_tts.json").write_text(json.dumps({
        "slides": [{"slide": 1, "tts_text": speech,
                    "tts_math_voice_preflight": status}]
    }), encoding="utf8")
    ready = preflight_voice_sidecar(stage)
    assert ready["source_risk_count"] == 0
    assert ready["acoustic_qa_required"] is True
    assert ready["publication_allowed"] is False
    assert len(ready["script_tts_sha256"]) == 64


def test_forged_or_drifted_voice_evidence_never_accepted(tmp_path):
    stage = tmp_path / "2.5"
    stage.mkdir()
    speech = "Position ex of tee remains constant."
    status = voice_input_risk_status(speech, normalize_scientific_speech)
    bad = {**status, "phoneme_certified": True}
    path = stage / "script_tts.json"
    path.write_text(json.dumps({"slides": [
        {"slide": 1, "tts_text": speech, "tts_math_voice_preflight": bad}
    ]}))
    with pytest.raises(VoiceRiskPreflightError, match="receipt mismatch"):
        preflight_voice_sidecar(stage)
    bad = {**status, "voice_input_sha256": "0" * 64}
    path.write_text(json.dumps({"slides": [
        {"slide": 1, "tts_text": speech, "tts_math_voice_preflight": bad}
    ]}))
    with pytest.raises(VoiceRiskPreflightError, match="receipt mismatch"):
        preflight_voice_sidecar(stage)


def test_narration_adapter_writes_risk_free_sidecar_but_preserves_narration(
    tmp_path, monkeypatch,
):
    import gen_script_v13 as narration
    monkeypatch.chdir(tmp_path)
    (tmp_path / "gen_script_prompt_v8_hybrid.md").write_text("Synthetic prompt")
    monkeypatch.setattr(narration, "_load_runtime_environment", lambda: None)
    slides = [
        {"page": 1, "text": "Synthetic Lesson", "lines": ["Synthetic Lesson"]},
        {"page": 2, "text": "Example of acceleration", "lines": ["Acceleration"]},
    ]
    original = ("The instantaneous acceleration a x, is defined by "
                "d squared x over d t squared.")
    def fake_extract(path):
        if Path(path).name == "slides.pdf":
            return slides
        return [{"page": 1, "text": "Synthetic textbook evidence",
                 "lines": ["Synthetic textbook evidence"]}]
    def fake_generate(items, *_args, **_kwargs):
        return {
            items[0]["id"]: {"narration": "Synthetic Lesson",
                             "tts_text": "Synthetic Lesson"},
            items[1]["id"]: {"narration": original, "tts_text": original},
        }
    monkeypatch.setattr(narration, "_extract_pdf_pages", fake_extract)
    monkeypatch.setattr(narration, "generate_batched", fake_generate)
    monkeypatch.setattr(narration, "SCRIPT_FILE", tmp_path / "script.txt")
    monkeypatch.setattr(narration, "TTS_SIDECAR", tmp_path / "script_tts.json")
    narration.main()
    data = json.loads((tmp_path / "script_tts.json").read_text())
    assert data["slides"][1]["narration"] == original
    assert "ay ex" in data["slides"][1]["tts_text"]
    assert "dee squared ex" in data["slides"][1]["tts_text"]
    assert "a x" in (tmp_path / "script.txt").read_text()
    assert preflight_voice_sidecar(tmp_path)["source_risk_count"] == 0


def test_real_batch_route_rejects_ambiguous_voice_before_provider_send(
    tmp_path, monkeypatch,
):
    """Exercise production process_one, not just the new helper in isolation."""
    from types import SimpleNamespace
    import microgen_batch as batch

    repo = tmp_path / "repo"
    work = tmp_path / "work"
    stage = work / "2.5"
    stage.mkdir(parents=True)
    repo.mkdir()
    (stage / "script_tts.json").write_text(json.dumps({
        "slides": [{"slide": 1, "tts_text":
                    "The variable y approaches zero."}]
    }), encoding="utf8")
    initial = batch.STAGES[:batch.STAGES.index("tts")]
    cp = {
        "completed": {name: "2026-11-12T00:00:00Z" for name in initial},
        "dependency_fingerprints": {name: "already-verified" for name in initial},
        "last_error": None, "inflight_provider_stage": None,
    }
    args = SimpleNamespace(
        standing_private_development=False,
        bounded_provider_scope_verified=False,
        stop_after="acceptance",
        source_root=tmp_path / "source",
        work_root=work,
        repo=repo,
        commit="f" * 40,
        source_wait=0,
        main_py="python",
        docling_py="python",
        figure_extraction_only=False,
        multipart=False,
        rebuild_unverified=False,
        stage_retries=0,
    )
    monkeypatch.setattr(batch, "prepare_stage", lambda *a:
                        (stage, cp, stage / ".microgen_checkpoint.json"))
    monkeypatch.setattr(batch, "destination_for", lambda *_:
                        tmp_path / "source" / "2" / "2.5")
    monkeypatch.setattr(batch, "stage_valid", lambda *a: True)
    monkeypatch.setattr(batch.quality, "dependency_fingerprint",
                        lambda *_: "already-verified")
    monkeypatch.setattr(batch, "save_checkpoint", lambda *a: None)
    monkeypatch.setattr(batch, "preflight_private_timed_acceptance",
                        lambda *_: {"mode": "source_lexical_admitted", "pages": 1})
    sent = []
    monkeypatch.setattr(batch, "run_subprocess",
                        lambda *a, **k: sent.append("paid") or
                        pytest.fail("The known doomed source risk must never be billed"))
    with pytest.raises(Exception, match="PREDICTABLE_MATH_VOICE_RISK_PREPAY_HOLD"):
        batch.process_one(args, "2.5", [])
    assert sent == []
