"""Offline fail-closed semantic cue matching, no Gemini API calls."""
import json

import pytest

from test_microgen_timed_cue_tts import input_stage
from microgen_cue_semantic_mapping import (
    SemanticMappingError, validate_matches,
)
from microgen_timed_cue_planner import (
    PLAN_FILE, CuePlanningError, propose_plan, write_verified_plan,
)
from microgen_timed_cue_tts import _verified_plan, CueTTSError


def paraphrase_fixture(tmp_path):
    stage = input_stage(tmp_path)
    (stage / PLAN_FILE).unlink()
    path = stage / "script_tts.json"
    data = json.loads(path.read_text(encoding="utf8"))
    for slide in data["slides"]:
        slide["tts_text"] = (
            "The total amount of motion stays the same. "
            "Transport of radiation and momentum."
        )
        slide["narration"] = slide["tts_text"]
    path.write_text(json.dumps(data), encoding="utf8")
    return stage


def safe_resolver(slide, missing, blocks):
    assert len(missing) == 1
    assert missing[0][0] == 1
    return [{"cue": 1, "block": 1, "quote": "Conservation of momentum"}]


def test_no_hidden_model_call_and_no_partial_plan(tmp_path, monkeypatch):
    monkeypatch.delenv("MICROGEN_TIMED_SEMANTIC_ASSIST", raising=False)
    stage = paraphrase_fixture(tmp_path)
    with pytest.raises(CuePlanningError, match="insufficient"):
        write_verified_plan(stage)
    assert not (stage / PLAN_FILE).exists()


def test_paraphrases_checked_against_real_pdf_and_original_script(tmp_path):
    stage = paraphrase_fixture(tmp_path)
    path = write_verified_plan(stage, semantic_resolver=safe_resolver)
    saved = json.loads(path.read_text(encoding="utf8"))
    assert saved["planning_method"] == "source_pdf_grounded_semantic_screen"
    assert saved["semantic_mapping_certified"] is False
    assert saved["semantic_assist_applied"] is True
    assert len(saved["slides"]) == 2
    assert saved["total_cues"] == 4
    assert saved["slides"][0]["cues"][0]["semantic_source_quote"] == "Conservation of momentum"
    assert "semantic_source_quote" not in saved["slides"][0]["cues"][1]
    verified, fragments = _verified_plan(stage)
    assert verified == saved
    assert len(fragments) == 4


def test_model_forged_quote_does_not_create_plan(tmp_path):
    stage = paraphrase_fixture(tmp_path)
    def bad(*args):
        return [{"cue": 1, "block": 1, "quote": "Completely invented mathematical claim"}]
    with pytest.raises(CuePlanningError, match="untrusted semantic proposal"):
        write_verified_plan(stage, semantic_resolver=bad)
    assert not (stage / PLAN_FILE).exists()


def test_numerical_hallucinations_rejected():
    blocks = [([10,10,100,25], "The conservation law is unchanged", {"conservation"})]
    with pytest.raises(SemanticMappingError, match="Numerical"):
        validate_matches(
            [{"cue": 2, "block": 1, "quote": "conservation law"}],
            [(2, "The result is 999 units")], blocks
        )


@pytest.mark.parametrize("rows", [
    [{"cue": True, "block": 1, "quote": "Conservation of momentum"}],
    [{"cue": 1, "block": 2, "quote": "Conservation of momentum"}],
    [{"cue": 1, "block": 1, "quote": "          "}],
    [{"cue": 1, "block": 1, "quote": "Conservation of momentum", "extra": True}],
    [],
])
def test_malformed_proposals_are_rejected(rows):
    with pytest.raises(SemanticMappingError):
        validate_matches(rows, [(1, "A different explanation")],
                         [([10,10,100,25], "Conservation of momentum and energy",
                           {"conservation", "momentum"})])


def test_budget_applies_across_slides(tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "1")
    stage = paraphrase_fixture(tmp_path)
    with pytest.raises(CuePlanningError, match="budget exceeded"):
        propose_plan(stage, semantic_resolver=safe_resolver)
    assert not (stage / PLAN_FILE).exists()


def test_semantic_provenance_cannot_be_forged_after_plan(tmp_path):
    stage = paraphrase_fixture(tmp_path)
    path = write_verified_plan(stage, semantic_resolver=safe_resolver)
    raw = json.loads(path.read_text(encoding="utf8"))
    raw["slides"][0]["cues"][0]["semantic_source_quote"] = "Not present in source"
    path.write_text(json.dumps(raw), encoding="utf8")
    with pytest.raises(CueTTSError, match="exact PDF evidence"):
        _verified_plan(stage)

def test_semantic_mode_and_resolver_code_change_invalidate_tts_cache(tmp_path, monkeypatch):
    from microgen_quality import dependency_fingerprint

    stage = input_stage(tmp_path)
    for filename in (
        "text_to_speech_v25.py", "microgen_flash_tts.py",
        "microgen_timed_cue_tts.py", "microgen_timed_cue_planner.py",
        "microgen_cue_semantic_mapping.py",
    ):
        (stage / filename).write_text("code version 1", encoding="utf8")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "0")
    baseline = dependency_fingerprint(stage, "tts")
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_ASSIST", "1")
    enabled = dependency_fingerprint(stage, "tts")
    assert enabled != baseline
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "2")
    bounded = dependency_fingerprint(stage, "tts")
    assert bounded != enabled
    (stage / "microgen_cue_semantic_mapping.py").write_text(
        "code version 2", encoding="utf8"
    )
    assert dependency_fingerprint(stage, "tts") != bounded


def test_semantic_empty_quote_rejected_even_if_space_length_is_eight():
    with pytest.raises(SemanticMappingError):
        validate_matches(
            [{"cue": 1, "block": 1, "quote": "           "}],
            [(1, "This paraphrase refers to conservation.")],
            [([10, 10, 100, 25], "Conservation of momentum and energy", set())],
        )

def test_gemini_semantic_adapter_is_single_bounded_json_operation(monkeypatch):
    import types
    import gemini_keys
    import microgen_flash_tts
    from microgen_cue_semantic_mapping import propose_with_gemini

    seen = []
    monkeypatch.setattr(
        microgen_flash_tts, "_load_gemini_keys_from_microvid", lambda: None
    )
    def fake_failover(factory, operation, **kwargs):
        assert kwargs["max_retries"] == 0
        assert "semantic cue screen" in kwargs["label"]
        def request(**options):
            seen.append(options)
            return types.SimpleNamespace(text=json.dumps({
                "matches": [{"cue": 1, "block": 1,
                             "quote": "Conservation of momentum"}]
            }))
        return operation(types.SimpleNamespace(
            models=types.SimpleNamespace(generate_content=request)
        ))
    monkeypatch.setattr(gemini_keys, "call_with_client_failover", fake_failover)
    matches = propose_with_gemini(
        3, [(1, "This total amount remains unchanged")],
        [([10,10,100,25], "Conservation of momentum and energy", set())],
    )
    assert len(matches) == 1
    assert seen[0]["model"] == "gemini-3.8-flash"
    sent = json.loads(seen[0]["contents"])
    assert sent["slide"] == 3
    assert sent["source_blocks"][0]["text"] == "Conservation of momentum and energy"
    assert seen[0]["config"]["response_mime_type"] == "application/json"

def test_service_failure_classified_not_misreported_as_bad_pdf(tmp_path):
    stage = paraphrase_fixture(tmp_path)
    def unavailable(*_):
        raise RuntimeError("service unavailable")
    with pytest.raises(CuePlanningError, match="semantic service unavailable"):
        write_verified_plan(stage, semantic_resolver=unavailable)
    assert not (stage / PLAN_FILE).exists()

def test_budget_preflight_checks_whole_deck_before_any_semantic_request(tmp_path, monkeypatch):
    """A doomed paid campaign must not consume even its first semantic call."""
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "1")
    stage = paraphrase_fixture(tmp_path)
    calls = []
    def model(*args):
        calls.append(args)
        raise AssertionError("A preknown over-budget lecture must never call Gemini")
    with pytest.raises(
        CuePlanningError,
        match=r"budget exceeded in offline preflight: required=2 allowed=1",
    ):
        propose_plan(stage, semantic_resolver=model)
    assert calls == []
    assert not (stage / PLAN_FILE).exists()


def test_sufficiently_budgeted_semantic_preflight_does_not_change_narration(
        tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "2")
    stage = paraphrase_fixture(tmp_path)
    original = (stage / "script_tts.json").read_bytes()
    called = []
    def resolver(slide, missing, blocks):
        called.append(slide)
        return safe_resolver(slide, missing, blocks)
    plan = write_verified_plan(stage, semantic_resolver=resolver)
    data = json.loads(plan.read_text(encoding="utf8"))
    assert called == [1, 2]
    assert data["total_cues"] == 4
    assert (stage / "script_tts.json").read_bytes() == original
    assert data["publication_allowed"] is False
