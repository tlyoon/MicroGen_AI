"""Reproduce normalizer-drift on real SHA-bound same-voice WAV manifests.

Read-only diagnostics on the normal acoustic entrypoint: no Gemini calls,
no mutations, and no false phonetic acceptance.
"""
import json
import wave

import pytest

from microgen_autonomous_acoustic_gate import audit_stage, AutonomousAcousticError
from microgen_tts_provenance import (
    inspect_normalized_input_drift, make_record, write_manifest,
    TTSProvenanceError, digest_file,
)


def _old_batch(folder):
    folder.mkdir(exist_ok=True)
    (folder / "script_tts.json").write_text(json.dumps({
        "slides": [
            {"slide": 1, "tts_text": "Position x of t changes."},
            {"slide": 2, "tts_text": "Conservation of energy matters."},
        ]
    }), encoding="utf8")
    old_texts = ["Position x of t changes.", "Conservation of energy matters."]
    records = []
    for slide, text in enumerate(old_texts, 1):
        file = folder / f"slide{slide}.wav"
        with wave.open(str(file), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(bytes([slide, 0]) * 24000)
        records.append(make_record(
            slide=slide, path=file, text=text,
            provider="gemini_flash_lite_tts", key=f"key{slide}",
            voice_name="Kore", language_code="en-US",
            speaking_rate=1.0, location="global",
        ))
    write_manifest(folder, records, old_texts)
    return old_texts


def test_normal_path_diagnoses_changed_spoken_input_before_model_request(tmp_path):
    old = _old_batch(tmp_path / "stage")
    stage = tmp_path / "stage"
    before = {name: digest_file(stage / name) for name in
              ["slide1.wav", "slide2.wav", ".microgen_tts_provenance.json"]}
    current = ["Position ex of tee changes.", old[1]]
    inv = inspect_normalized_input_drift(stage, current)
    assert inv["changed_input_slides"] == [1]
    assert inv["unchanged_input_slides"] == [2]
    assert not inv["independent_acoustic_review_passed"]
    calls = []
    def forbidden(_path):
        calls.append("paid")
        raise AssertionError("Recognition must never start")
    with pytest.raises(AutonomousAcousticError, match="SOURCE_NORMALIZER_DRIFT_HOLD.*\\[1\\]"):
        audit_stage(stage, engines=(forbidden, forbidden),
                    models=("gemini-3.5-flash", "gemini-3.8-flash"))
    assert calls == []
    assert before == {name: digest_file(stage / name) for name in before}


def test_no_drift_can_be_distinguished_from_new_speech_without_acceptance(tmp_path):
    old = _old_batch(tmp_path / "stage")
    inventory = inspect_normalized_input_drift(tmp_path / "stage", old)
    assert inventory["changed_input_slides"] == []
    assert inventory["source_text_current"]
    assert not inventory["independent_acoustic_review_passed"]


def test_corrupt_original_wav_never_reclassified_as_safe_target(tmp_path):
    _old_batch(tmp_path / "stage")
    stage = tmp_path / "stage"
    with (stage / "slide2.wav").open("ab") as f:
        f.write(b"untrusted")
    with pytest.raises(TTSProvenanceError, match="content changed"):
        inspect_normalized_input_drift(
            stage, ["Position ex of tee changes.", "Conservation of energy matters."])
    with pytest.raises(AutonomousAcousticError, match="UNVERIFIED_AUDIO_PROVENANCE_HOLD"):
        audit_stage(stage, engines=(lambda _: None, lambda _: None),
                    models=("gemini-3.5-flash", "gemini-3.8-flash"))


def test_voice_identity_cannot_be_forged_in_drift_inventory(tmp_path):
    _old_batch(tmp_path / "stage")
    stage = tmp_path / "stage"
    manifest_path = stage / ".microgen_tts_provenance.json"
    document = json.loads(manifest_path.read_text(encoding="utf8"))
    document["slides"][1]["voice_name"] = "Changed Voice"
    manifest_path.write_text(json.dumps(document), encoding="utf8")
    with pytest.raises(TTSProvenanceError, match="Mixed or forged"):
        inspect_normalized_input_drift(
            stage, ["Position ex of tee changes.", "Conservation of energy matters."])


def test_new_provenance_logic_participates_in_normal_stage_fingerprints(tmp_path):
    from microgen_quality import dependency_fingerprint
    required = (
        "script_tts.json", "text_to_speech_v25.py",
        ".microgen_tts_provenance.json",
        "microgen_autonomous_acoustic_gate.py",
        "microgen_tts_acoustic_qa.py",
        "microgen_tts_evidence.py",
        "microgen_tts_provenance.py",
    )
    for name in required:
        (tmp_path / name).write_bytes(b"source-free")
    old_tts = dependency_fingerprint(tmp_path, "tts")
    old_acoustic = dependency_fingerprint(tmp_path, "acoustic_qa")
    (tmp_path / "microgen_tts_provenance.py").write_bytes(b"changed logic")
    assert dependency_fingerprint(tmp_path, "tts") != old_tts
    assert dependency_fingerprint(tmp_path, "acoustic_qa") != old_acoustic
