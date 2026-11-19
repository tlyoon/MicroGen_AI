"""Offline regression for Gemini ASR failure recovery and truthful typed diagnosis.

Covers the actual 2026-11-17 no-transcript model/key exhaustion,
the November 13/15 independently successful reviewer fallback, and
new JSON-schema compatibility downgrade. Zero Gemini/API calls.
"""
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from google import genai
from microgen_tts_acoustic_qa import (
    gemini_audio_recognizer,
    AcousticQAError,
    _audio_json_schema_rejected,
    _parse_source_blind_transcriber_output,
)
from microgen_tts_service_recovery import (
    AudioRecognitionUnavailable, run_bounded_recognition,
    failure_kind, safe_http_status,
)


class ApiError(Exception):
    def __init__(self, code, message):
        self.code=code
        super().__init__(message)


@pytest.fixture
def wav(tmp_path):
    p=tmp_path/"slide1.wav"
    with wave.open(str(p),"wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00"*240)
    return p


def fake_backend(monkeypatch, responses):
    calls=[]
    replies=iter(responses)
    def generate_content(*, model, contents, config):
        calls.append((model,contents,config))
        item=next(replies)
        if isinstance(item,Exception):
            raise item
        if hasattr(item,"candidates"):
            return item
        return SimpleNamespace(text=item)
    client=SimpleNamespace(models=SimpleNamespace(
        generate_content=generate_content))
    monkeypatch.setattr(genai,"Client",lambda **kw:client)
    return calls


def test_real_schema_400_repaired_within_existing_two_of_three_requests(
        monkeypatch,wav):
    calls=fake_backend(monkeypatch,[
        ApiError(400,"Invalid JSON payload: unknown name 'responseJsonSchema'"),
        '{"transcript":"Velocity increases from zero to three metres per second."}',
    ])
    monkeypatch.setattr("microgen_tts_acoustic_qa.time.sleep",lambda _:None)
    transcribe=gemini_audio_recognizer("synthetic-key",model="gemini-3.8-flash")
    assert transcribe(wav).startswith("Velocity increases")
    assert len(calls)==2
    assert calls[0][2].response_json_schema is not None
    assert calls[1][2].response_json_schema is None
    assert calls[1][2].response_mime_type is None
    assert calls[1][0]==calls[0][0]=="gemini-3.8-flash"
    assert "zero" not in calls[0][1][1]  # source/script never sent


@pytest.mark.parametrize("exc,kind,http",[
    (ApiError(400,"400 INVALID_ARGUMENT. Invalid audio body"),"INVALID_REQUEST",400),
    (ApiError(401,"401 UNAUTHENTICATED"),"AUTHORIZATION",401),
    (ApiError(403,"403 PERMISSION_DENIED"),"AUTHORIZATION",403),
    (ApiError(404,"404 NOT_FOUND"),"MODEL_UNAVAILABLE",404),
    (ApiError(429,"429 RESOURCE_EXHAUSTED: quota Limit: 0"),"HARD_QUOTA",429),
])
def test_non_schema_errors_never_trigger_format_downgrade(
        monkeypatch,wav,exc,kind,http):
    calls=fake_backend(monkeypatch,[exc])
    with pytest.raises(AcousticQAError) as failure:
        gemini_audio_recognizer("synthetic-key")(wav)
    assert len(calls)==1
    assert f"kind={kind}" in str(failure.value)
    assert f"http_status={http}" in str(failure.value)


def test_503_still_retries_at_most_three_and_reports_code_without_secret(
        monkeypatch,wav):
    secret="PRIVATE-KEY-DO-NOT-LOG"
    calls=fake_backend(monkeypatch,[
        ApiError(503,"503 UNAVAILABLE "+secret) for _ in range(3)])
    monkeypatch.setattr("microgen_tts_acoustic_qa.time.sleep",lambda _:None)
    with pytest.raises(AcousticQAError) as failure:
        gemini_audio_recognizer(secret,model="gemini-3.5-flash")(wav)
    assert len(calls)==3
    msg=str(failure.value)
    assert "kind=TRANSIENT_PROVIDER" in msg
    assert "http_status=503" in msg
    assert secret not in msg


def test_dedicated_transcriber_is_source_blind_and_can_return_plain_text(
        monkeypatch,wav):
    calls=fake_backend(monkeypatch,[
        "The acceleration is in the positive x direction and equals five."
    ])
    transcript=gemini_audio_recognizer(
        "synthetic-key",model="gemini-3.5-transcribe")(wav)
    assert transcript.startswith("The acceleration")
    assert len(calls)==1
    assert calls[0][0]=="gemini-3.5-transcribe"
    assert calls[0][2].response_json_schema is None
    assert calls[0][2].response_mime_type is None
    assert "transcribe" in calls[0][1][1].lower()


@pytest.mark.parametrize("raw",[
    "", "short", "Transcript: The acceleration is five",
    "Here is the transcription: acceleration is five",
    "### Transcription\nAcceleration is five",
    "```\nacceleration is five\n```",
    '{"transcript":"I have checked; this is the likely correct value."}',
])
def test_dedicated_transcriber_rejects_preamble_meta_or_short_text(raw):
    with pytest.raises(AcousticQAError):
        _parse_source_blind_transcriber_output(raw)


def test_valid_dedicated_json_and_plain_both_require_real_words():
    phrase="Velocity stays constant at four metres per second."
    assert _parse_source_blind_transcriber_output(phrase)==phrase
    assert _parse_source_blind_transcriber_output(
        '{"transcript":"'+phrase+'"}')==phrase


def test_schema_downgrade_admits_only_explicit_schema_400():
    assert _audio_json_schema_rejected(ApiError(
        400,"Unsupported response_json_schema")) is True
    for exc in (
        ApiError(401,"response_json_schema"),
        ApiError(403,"responseJsonSchema"),
        ApiError(503,"responseJsonSchema"),
        ApiError(400,"Audio codec unsupported"),
        ApiError(400,"Forbidden model"),
    ):
        assert _audio_json_schema_rejected(exc) is False


def _native_audio_response(*transcripts):
    from google.genai import types
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(parts=[
            types.Part(audio_transcription={"text":words})
            for words in transcripts
        ]))]
    )


def test_real_gemini_specialist_native_audio_transcription_part_is_recovered(
        monkeypatch,wav):
    # Actual HP 912 campaign returned non-text ['audio_transcription']
    # with an empty response.text; legacy code discarded the valid part.
    spoken="The x component of acceleration equals five metres per second squared."
    response=_native_audio_response(spoken)
    assert response.candidates[0].content.parts[0].audio_transcription.text==spoken
    calls=fake_backend(monkeypatch,[response])
    reviewer=gemini_audio_recognizer(
        "synthetic-key",model="gemini-3.5-transcribe")
    assert reviewer(wav)==spoken
    assert len(calls)==1
    assert calls[0][0]=="gemini-3.5-transcribe"
    assert calls[0][2].response_json_schema is None


@pytest.mark.parametrize("transcripts",[
    ("",),
    ("Only two",),
    ("The x component is five metres per second squared.",
     "The y component is five metres per second squared."),
])
def test_native_transcription_empty_short_or_ambiguous_never_accepted(
        monkeypatch,wav,transcripts):
    calls=fake_backend(monkeypatch,[_native_audio_response(*transcripts)])
    with pytest.raises(AcousticQAError):
        gemini_audio_recognizer(
            "synthetic-key",model="gemini-3.5-transcribe")(wav)
    assert len(calls)==1


def test_native_transcription_mixed_text_and_audio_fails_closed(monkeypatch,wav):
    from google.genai import types
    response=types.GenerateContentResponse(candidates=[
        types.Candidate(content=types.Content(parts=[
            types.Part(audio_transcription={"text":
                "The acceleration is five metres per second squared."}),
            types.Part(text="A conflicting explanatory caption"),
        ]))
    ])
    calls=fake_backend(monkeypatch,[response])
    with pytest.raises(AcousticQAError):
        gemini_audio_recognizer(
            "synthetic-key",model="gemini-3.5-transcribe")(wav)
    assert len(calls)==1


def test_typed_provider_error_diagnostic_is_non_leaky():
    exc=ApiError(503,"503 UNAVAILABLE secret=PRIVATEKEY")
    assert failure_kind(exc)=="TRANSIENT_PROVIDER"
    assert safe_http_status(exc)==503
    with pytest.raises(AudioRecognitionUnavailable) as result:
        run_bounded_recognition(lambda:(_ for _ in ()).throw(exc),
                                lambda _:None,max_attempts=1)
    assert result.value.failure_kind=="TRANSIENT_PROVIDER"
    assert result.value.http_status==503
    assert "PRIVATEKEY" not in str(result.value)
