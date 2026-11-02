"""Simulated loopback model generation; no paid provider, network or source assets."""
import copy
import json
import tempfile
from pathlib import Path

import pytest

from microgen_private_local_authoring import (
    LocalAuthoringError,run_local_authoring,_check_endpoint,_content)
from test_microgen_portable_private_authoring_gate import construct


def envelope(draft):
    return {"message":{"content":json.dumps(draft)},"done":True}


def test_local_model_json_is_accepted_and_renderable_after_source_check():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        src,packet,draft=construct(root)
        observed=[]
        def model_call(url,payload,timeout):
            observed.append((url,payload,timeout))
            assert payload["stream"] is False
            assert payload["format"]=="json"
            assert payload["model"]=="offline-test"
            assert "source_evidence" in payload["messages"][1]["content"]
            assert payload["options"]["num_predict"]>1000
            return envelope(draft)
        stage=root/"new-private-stage"
        result=run_local_authoring(src,packet["start_marker"],
           packet["next_section_marker"],packet["section_id"],stage,
           model="offline-test",request_fn=model_call)
        assert result["attempts_used"]==1
        assert result["topic_count"]==2
        assert result["local_endpoint_verified"]
        assert not result["publication_allowed"]
        assert (stage/"narration.json").is_file()
        assert (stage/"contract.json").is_file()
        assert (stage/"authoring_private_qa.json").is_file()
        assert len(observed)==1


def test_wrong_local_draft_gets_single_bounded_retry():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);src,packet,draft=construct(root)
        counter=[]
        def fake(url,payload,timeout):
            counter.append(payload)
            if len(counter)==1:
                wrong=copy.deepcopy(draft)
                wrong["topics"][0]["narration"]+=" The unverified number is 45678."
                return envelope(wrong)
            return envelope(draft)
        stage=root/"accepted"
        result=run_local_authoring(src,packet["start_marker"],
           packet["next_section_marker"],packet["section_id"],stage,
           model="local-science",request_fn=fake,max_attempts=2)
        assert result["attempts_used"]==2
        assert "numerical data absent" in counter[1]["messages"][1]["content"]
        assert (stage/"contract.json").is_file()


def test_wrong_draft_exhausted_and_does_not_create_output():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);src,packet,draft=construct(root)
        wrong=copy.deepcopy(draft)
        wrong["source_pdf_sha256"]="f"*64
        calls=[]
        def fake(url,payload,timeout):
            calls.append(1)
            return envelope(wrong)
        with pytest.raises(LocalAuthoringError,match="after 2 attempt"):
            run_local_authoring(src,packet["start_marker"],
               packet["next_section_marker"],packet["section_id"],
               root/"should_not_exist",model="local-science",request_fn=fake)
        assert calls==[1,1]
        assert not (root/"should_not_exist").exists()


@pytest.mark.parametrize("url",[
 "https://127.0.0.1:11434/api/chat",
 "http://example.org:11434/api/chat",
 "http://localhost:11434/api/chat",
 "http://127.0.0.2:11434/api/chat",
 "http://[::1]:11434/api/chat",
 "http://127.0.0.1:11434/api/chat?proxy=1",
 "http://127.0.0.1:11434/api/generate",
 "http://127.0.0.1:11434@evil.example/api/chat",
 "http://127.0.0.1:11434/api/chat#fragment",
])
def test_nonapproved_network_locations_rejected_before_any_model_request(url):
    with pytest.raises(LocalAuthoringError):
        _check_endpoint(url)


@pytest.mark.parametrize("result",[
 {},
 {"message":{"content":None}},
 {"message":{"content":"not JSON"}},
 {"message":{"content":"[1,2,3]"}},
 {"message":{"content":"a"*650001}},
])
def test_malformed_local_model_responses_rejected(result):
    with pytest.raises(LocalAuthoringError):
        _content(result)


def test_missing_local_service_fails_closed_without_any_stage():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);src,packet,draft=construct(root)
        def offline(url,payload,timeout):
            raise LocalAuthoringError("No local model is running")
        with pytest.raises(LocalAuthoringError,match="after 1 attempt"):
            run_local_authoring(src,packet["start_marker"],
                packet["next_section_marker"],packet["section_id"],
                root/"should_not_exist",model="unavailable",
                request_fn=offline,max_attempts=3)
        assert not (root/"should_not_exist").exists()


def test_existing_stage_and_bad_retry_budgets_rejected():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);src,packet,draft=construct(root)
        (root/"existing").mkdir()
        with pytest.raises(LocalAuthoringError):
            run_local_authoring(src,packet["start_marker"],
                packet["next_section_marker"],packet["section_id"],
                root/"existing",model="offline-model",request_fn=lambda *_:envelope(draft))
        with pytest.raises(LocalAuthoringError):
            run_local_authoring(src,packet["start_marker"],
                packet["next_section_marker"],packet["section_id"],
                root/"new",model="offline-model",max_attempts=100,
                request_fn=lambda *_:envelope(draft))
