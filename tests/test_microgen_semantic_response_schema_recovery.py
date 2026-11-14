"""Schema-only recovery of equivalent Gemini semantic-mapping JSON replies.

Runs offline, including the real planner's normal path. Every recovered
row still passes the original PDF quote/numerical-evidence checks.
"""
import json
from types import SimpleNamespace
import pytest

from microgen_cue_semantic_mapping import (
    SemanticMappingError, _parse_semantic_model_response,
    normalize_model_proposal, validate_matches, propose_with_gemini,
)
from microgen_timed_cue_planner import write_verified_plan, PLAN_FILE
from microgen_timed_cue_tts import _verified_plan
from test_microgen_cue_semantic_mapping import paraphrase_fixture

MISSING = [(1, "Conservation is maintained across the process.")]
BLOCKS = [([10., 10., 220., 28.],
           "Conservation of momentum and energy",
           {"conservation", "momentum", "energy"})]
ROW = {"cue": 1, "block": 1, "quote": "Conservation of momentum"}


@pytest.mark.parametrize("response_json", [
    {"matches": [ROW]},
    [ROW],
    {"mappings": [ROW]},
    {"result": {"matches": [ROW]}},
    {"data": {"matches": [ROW]}},
    {"output": {"matches": [ROW]}},
    {"matches": [ROW], "reasoning": "selected literal source block"},
    {"matches": [ROW], "status": "ok"},
    {"matches": {"1": {"block": 1, "quote": "Conservation of momentum"}}},
    {"matches": [{"cue_id": "1", "block_id": "1",
                  "source_quote": "Conservation of momentum"}]},
    {"matches": [{"cue_number": 1, "block_index": 1,
                  "quote": "Conservation of momentum"}]},
])
def test_equivalent_json_shapes_recover_to_exact_source_evidence(response_json):
    matches = normalize_model_proposal(response_json, MISSING)
    assert matches == [ROW]
    assert validate_matches(matches, MISSING, BLOCKS)[1][0] == (0,)


def test_fenced_and_double_serialized_whole_json_only():
    payload = json.dumps({"matches": [ROW]})
    fence = chr(96) * 3
    for body in (payload, fence + "json\n" + payload + "\n" + fence,
                 json.dumps(payload)):
        got = _parse_semantic_model_response(SimpleNamespace(text=body), MISSING)
        assert got == [ROW]


def test_sdk_parsed_response_without_text_recovers():
    response = SimpleNamespace(text=None, parsed={"matches": [ROW]})
    assert _parse_semantic_model_response(response, MISSING) == [ROW]


@pytest.mark.parametrize("bad", [
    {"error": "Do not map the source"},
    {"matches": [ROW], "status": "failed"},
    {"matches": [ROW], "secret": "unknown field"},
    {"matches": [], "reason": "no matching evidence"},
    {"matches": [ROW, ROW]},
    {"matches": [{"cue": True, "block": 1,
                  "quote": "Conservation of momentum"}]},
    {"matches": [{"cue": 1, "block": False,
                  "quote": "Conservation of momentum"}]},
    {"matches": [{"cue": 1, "block": 1.0,
                  "quote": "Conservation of momentum"}]},
    {"matches": [{"cue": "00", "block": 1,
                  "quote": "Conservation of momentum"}]},
    {"matches": [{"cue": 1, "cue_id": 1, "block": 1,
                  "quote": "Conservation of momentum"}]},
    {"matches": [{"cue": 2, "block": 1,
                  "quote": "Conservation of momentum"}]},
])
def test_unsafe_or_incomplete_response_structure_rejected(bad):
    with pytest.raises(SemanticMappingError):
        normalize_model_proposal(bad, MISSING)


def test_reordered_multi_element_selection_rejected_by_original_pdf_validator():
    proposed = normalize_model_proposal(
        {"matches": [{"cue": 1, "blocks": [2, 1],
                      "quotes": ["Transport of radiation",
                                 "Conservation of momentum"]}]}, MISSING)
    with pytest.raises(SemanticMappingError):
        validate_matches(proposed, MISSING, [
            BLOCKS[0],
            ([10., 35., 220., 60.], "Transport of radiation and momentum", set()),
        ])


def test_nongrounded_quote_and_wrong_numeric_claim_fail_even_after_recovery():
    for missing, row in (
        (MISSING, {"cue": 1, "block": 1, "quote": "Fabricated scientific result"}),
        ([(1, "The final result is 999 joules")], ROW),
    ):
        output = normalize_model_proposal({"data": {"matches": [row]}}, missing)
        with pytest.raises(SemanticMappingError):
            validate_matches(output, missing, BLOCKS)


def test_error_shape_diagnostics_never_reprint_model_content():
    secret = "PRIVATE_SOURCE_SENTENCE_123456"
    with pytest.raises(SemanticMappingError) as exc:
        normalize_model_proposal({"unknown": secret}, MISSING)
    assert secret not in str(exc.value)
    assert "object_keys=unknown" in str(exc.value)


def test_prose_wrapped_json_is_not_silently_extracted():
    payload = json.dumps({"matches": [ROW]})
    with pytest.raises(SemanticMappingError, match="Invalid model JSON"):
        _parse_semantic_model_response(
            SimpleNamespace(text="I guess the correct answer is " + payload),
            MISSING,
        )


@pytest.mark.parametrize("variant", ("wrapped", "alias", "direct"))
def test_full_planner_recovers_safe_equivalent_model_response_without_network(
    tmp_path, monkeypatch, variant,
):
    import gemini_keys
    import microgen_flash_tts

    stage = paraphrase_fixture(tmp_path)
    calls = []

    monkeypatch.setenv("MICROGEN_TIMED_SEMANTIC_MAX_SLIDES", "2")
    monkeypatch.setattr(
        microgen_flash_tts, "_load_gemini_keys_from_microvid", lambda: None,
    )

    def model_call(factory, operation, **kwargs):
        assert kwargs["max_retries"] == 0
        calls.append(kwargs["label"])
        if variant == "wrapped":
            raw = {"result": {"matches": [ROW]}}
        elif variant == "alias":
            raw = {"matches": [
                {"cue_id": "1", "block_id": "1",
                 "source_quote": "Conservation of momentum"}
            ]}
        else:
            raw = [ROW]
        return operation(SimpleNamespace(
            models=SimpleNamespace(generate_content=lambda **options:
                SimpleNamespace(text=json.dumps(raw)))
        ))

    monkeypatch.setattr(
        gemini_keys, "call_with_client_failover", model_call,
    )
    output = write_verified_plan(stage, semantic_resolver=propose_with_gemini)
    assert output.name == PLAN_FILE
    assert len(calls) == 2
    verified, spoken = _verified_plan(stage)
    assert verified["planning_method"] == "source_pdf_grounded_semantic_screen"
    assert verified["semantic_mapping_certified"] is False
    assert verified["publication_allowed"] is False
    assert len(spoken) == 4



def test_provider_native_schema_declares_both_exact_row_shapes():
    from google.genai import types
    from microgen_cue_semantic_mapping import SEMANTIC_RESPONSE_JSON_SCHEMA

    source = SEMANTIC_RESPONSE_JSON_SCHEMA
    assert source["type"] == "object"
    assert source["required"] == ["matches"]
    assert source["additionalProperties"] is False
    matches = source["properties"]["matches"]
    assert matches["type"] == "array"
    # Zero matches must remain valid for grounded abstention.
    assert matches.get("minItems", 0) == 0
    variants = matches["items"]["anyOf"]
    assert len(variants) == 2
    for row in variants:
        assert row["type"] == "object"
        assert row["additionalProperties"] is False
        assert set(row["properties"]) == set(row["required"])
    assert set(variants[0]["required"]) == {"cue", "block", "quote"}
    assert set(variants[1]["required"]) == {"cue", "blocks", "quotes"}
    assert variants[1]["properties"]["blocks"]["maxItems"] == 5
    assert variants[1]["properties"]["quotes"]["minItems"] == 2
    # SDK schema serialization must work on HP without a billable request.
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0,
        response_json_schema=source,
    )
    assert config.response_json_schema["required"] == ["matches"]


def test_normal_semantic_provider_request_uses_constrained_schema_and_one_send(
    monkeypatch,
):
    import gemini_keys
    import microgen_flash_tts
    from microgen_cue_semantic_mapping import source_quote_constrained_schema

    monkeypatch.setattr(
        microgen_flash_tts, "_load_gemini_keys_from_microvid",
        lambda: None,
    )
    sent = []

    def fake_provider(factory, operation, **kwargs):
        assert kwargs["max_retries"] == 0
        def fake_generate(**options):
            sent.append(options)
            config = options["config"]
            assert config["temperature"] == 0
            assert config["response_mime_type"] == "application/json"
            assert config["response_json_schema"] == source_quote_constrained_schema(BLOCKS)
            source_quotes = config["response_json_schema"]["properties"]["matches"]["items"]["anyOf"][0]["properties"]["quote"]["enum"]
            assert source_quotes == [BLOCKS[0][1]]
            # Avoid duplicating schema examples in the narrated task.
            prompt = json.loads(options["contents"])
            assert "output_contract" not in prompt
            assert "unresolved_cues" in prompt
            assert "source_blocks" in prompt
            return SimpleNamespace(
                text=json.dumps({"matches": [ROW]})
            )
        client = SimpleNamespace(
            models=SimpleNamespace(generate_content=fake_generate)
        )
        return operation(client)

    monkeypatch.setattr(
        gemini_keys, "call_with_client_failover", fake_provider,
    )
    mapping = propose_with_gemini(7, MISSING, BLOCKS)
    assert mapping == [ROW]
    assert len(sent) == 1
    assert validate_matches(mapping, MISSING, BLOCKS)[1][0] == (0,)


def test_schema_mode_does_not_force_false_semantic_success(monkeypatch):
    import gemini_keys
    import microgen_flash_tts

    monkeypatch.setattr(
        microgen_flash_tts, "_load_gemini_keys_from_microvid",
        lambda: None,
    )
    sends = []
    def fake_provider(factory, operation, **kwargs):
        def fake_generate(**options):
            sends.append(options)
            return SimpleNamespace(text='{"matches":[]}')
        client = SimpleNamespace(
            models=SimpleNamespace(generate_content=fake_generate)
        )
        return operation(client)
    monkeypatch.setattr(
        gemini_keys, "call_with_client_failover", fake_provider,
    )
    with pytest.raises(SemanticMappingError, match="incomplete proposal"):
        propose_with_gemini(7, MISSING, BLOCKS)
    assert len(sends) == 1
    # A structured but empty response is an explicit fail-closed abstention,
    # never a success or permission to invent a cue-to-PDF mapping.
