"""Private ChatGPT/Gemini source-based handoff tests: synthetic only."""
import json
import tempfile
from pathlib import Path
import pytest
from microgen_private_browser_authoring import (
    BrowserAuthoringError, accept_browser_response, parse_browser_response,
    prepare_private_prompt,
)
from test_microgen_portable_private_authoring_gate import construct


def test_prompt_and_accept_original_chatgpt_draft_without_provider_call():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        source,packet,draft=construct(root)
        prompt=root/"private-browser-prompt.txt"
        meta=prepare_private_prompt(source,packet["start_marker"],
             packet["next_section_marker"],packet["section_id"],prompt)
        assert "source_evidence" in prompt.read_text()
        assert meta["source_passage_count"]>=2
        assert meta["external_model_invocations"]==0
        response=root/"chatgpt-private-response.txt"
        fence=chr(96)*3
        response.write_text(fence+"json\n"+json.dumps(draft)+"\n"+fence+"\n")
        stage=root/"validated-browser-draft"
        result=accept_browser_response(source,packet["start_marker"],
                  packet["next_section_marker"],packet["section_id"],response,stage)
        assert result["topic_count"]==2
        assert result["provider_identity_independently_verified"] is False
        assert not result["publication_allowed"]
        assert (stage/"contract.json").is_file()
        assert (stage/"authoring_private_qa.json").is_file()


@pytest.mark.parametrize("response",[
    "not JSON","hello\n{\"publication_allowed\":false}",
    '{"publication_allowed":true}',
    '[{"publication_allowed":false}]',
    (chr(96)*3)+"\n{}\n"+(chr(96)*3)+"\nextra",
    (chr(96)*4)+"json\n{\"publication_allowed\":false}\n"+(chr(96)*4),
])
def test_invalid_or_ambiguous_browser_response_rejected(response):
    with pytest.raises(BrowserAuthoringError):
        parse_browser_response(response)


def test_modified_source_and_forged_packet_do_not_create_stage():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        source,packet,draft=construct(root)
        response=root/"gemini-response.txt"
        response.write_text(json.dumps(draft))
        source.write_bytes(source.read_bytes()+b"\n")
        with pytest.raises(ValueError):
            accept_browser_response(source,packet["start_marker"],
                  packet["next_section_marker"],packet["section_id"],
                  response,root/"no-stage")
        assert not (root/"no-stage").exists()


def test_cannot_overwrite_prompt_or_stage():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);source,packet,draft=construct(root)
        prompt=root/"existing.txt";prompt.write_text("do not overwrite")
        with pytest.raises(ValueError):
            prepare_private_prompt(source,packet["start_marker"],
                   packet["next_section_marker"],packet["section_id"],prompt)
        assert prompt.read_text()=="do not overwrite"
        response=root/"draft.txt";response.write_text(json.dumps(draft))
        stage=root/"exists";stage.mkdir()
        with pytest.raises(ValueError):
            accept_browser_response(source,packet["start_marker"],
                  packet["next_section_marker"],packet["section_id"],response,stage)
