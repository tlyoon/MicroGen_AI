"""Private loopback-only local Ollama authoring backend.

Calls no cloud API. A local model must already be installed and active.
All output is treated as untrusted and passed through the PR247 authoring gate.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import urllib.request
import urllib.error
from urllib.parse import urlsplit

from microgen_portable_private_authoring_gate import (
    build_authoring_packet, write_validated_stage, canonical_hash,
    AuthoringGateError)


class LocalAuthoringError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _check_endpoint(endpoint):
    """No off-device destinations, DNS lookups or redirects."""
    try:
        url=urlsplit(endpoint)
        valid=(url.scheme=="http" and url.hostname=="127.0.0.1"
               and url.port is not None and 1<=url.port<=65535
               and url.path=="/api/chat" and not url.query and not url.fragment
               and url.username is None and url.password is None)
    except (ValueError,AttributeError):
        valid=False
    if not valid:
        raise LocalAuthoringError("Only http://127.0.0.1:<port>/api/chat allowed")
    return endpoint


def _post(endpoint,payload,timeout):
    data=json.dumps(payload,ensure_ascii=True).encode("utf8")
    if len(data)>600_000:
        raise LocalAuthoringError("Source packet too large for bounded local model request")
    request=urllib.request.Request(endpoint,data=data,
                                  headers={"Content-Type":"application/json"},
                                  method="POST")
    opener=urllib.request.build_opener(_NoRedirect,urllib.request.ProxyHandler({}))
    try:
        with opener.open(request,timeout=timeout) as response:
            raw=response.read(750_001)
            if len(raw)>750_000:
                raise LocalAuthoringError("Oversized local model response")
            return json.loads(raw.decode("utf8"))
    except (urllib.error.URLError,ConnectionError,TimeoutError,ValueError) as error:
        raise LocalAuthoringError(
            f"Local model unavailable or invalid response: {type(error).__name__}") from error


def _content(obj):
    if not isinstance(obj,dict):
        raise LocalAuthoringError("Malformed local model envelope")
    message=obj.get("message")
    data=message.get("content") if isinstance(message,dict) else None
    if not isinstance(data,str) or len(data)>650_000:
        raise LocalAuthoringError("Local model response lacks bounded JSON text")
    text=data.strip()
    fence=chr(96)*3
    if text.startswith(fence+"json") and text.endswith(fence):
        text=text[7:-3].strip()
    try:
        draft=json.loads(text)
    except ValueError as error:
        raise LocalAuthoringError("Local model did not return valid JSON") from error
    if not isinstance(draft,dict):
        raise LocalAuthoringError("Local model JSON must be an object")
    return draft


def run_local_authoring(source:Path,start_marker:str,next_marker:str|None,
                        section_id:str,new_private_stage:Path,
                        *,end_of_pdf=False,model:str,endpoint:str=
                        "http://127.0.0.1:11434/api/chat",
                        max_attempts=2,timeout=90,request_fn=None):
    """Start a local model call, bounded retry and source-grounded acceptance."""
    endpoint=_check_endpoint(endpoint)
    if (not isinstance(model,str) or not re.fullmatch(r"[a-zA-Z0-9._:/-]{1,90}",model)
        or type(max_attempts) is not int or not 1<=max_attempts<=3
        or type(timeout) is not int or not 5<=timeout<=300):
        raise LocalAuthoringError("Explicit local model and bounded retry timeout required")
    source=Path(source)
    stage=Path(new_private_stage)
    if stage.exists() or stage.is_symlink():
        raise LocalAuthoringError("Fresh private stage required")
    packet=build_authoring_packet(source,start_marker,next_marker,
                                  end_of_pdf=end_of_pdf,section_id=section_id)
    sender=request_fn if request_fn is not None else _post
    last_error=""
    last_type=None
    for attempt in range(1,max_attempts+1):
        payload={
          "model":model,"stream":False,"format":"json","keep_alive":"0s",
          "options":{"temperature":0.2,"num_predict":7000},
          "messages":[
            {"role":"system","content":(
                "You are a careful educational author. Create ORIGINAL short "
                "lecture content, never copy 12 consecutive words from source. "
                "Use ONLY the provided source packet. Output a JSON object "
                "with schema_version=1, section_id, source_pdf_sha256, "
                "packet_sha256, publication_allowed=false and topics. Each "
                "topic needs topic_id, source_page, source_passage_ids, "
                "source_anchor (exact substring from cited passage), "
                "required_terms, title, 2-5 bullets and 60-250 ASCII words "
                "of independently worded narration. Use 2-60 topics, ordered "
                "by source page, distinct and faithful. Do not make up facts, "
                "numerical values, or unrelated content. Academic quality "
                "is not fully certified by this format validation."
            )},
            {"role":"user","content":json.dumps({
               "task":"Produce original source-grounded teaching draft.",
               "packet_sha256":canonical_hash(packet),"packet":packet,
               "previous_validation_error":last_error
            },ensure_ascii=True)}
          ]}
        try:
            response=sender(endpoint,payload,timeout)
            draft=_content(response)
            qa=write_validated_stage(source,packet,draft,stage)
            return {
                "status":"LOCAL_AUTHORING_VERIFIED_CANDIDATE_NOT_PUBLISHED",
                "attempts_used":attempt,"topic_count":qa["topic_count"],
                "source_pdf_sha256":qa["source_pdf_sha256"],
                "source_passages_referenced":qa["passages_used_count"],
                "model_name":model,"local_endpoint_verified":True,
                "independent_scientific_certification":False,
                "formal_voice_authorized":False,"publication_allowed":False,
            }
        except (LocalAuthoringError,AuthoringGateError,KeyError,TypeError,
                ValueError) as exc:
            last_type=type(exc).__name__
            last_error=(str(exc) or last_type)[:220]
            if isinstance(exc,LocalAuthoringError):
                break
    raise LocalAuthoringError(
        f"No accepted authoring draft after {attempt} attempt(s); "
        f"last category {last_type}; {last_error}") from None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--start-marker",required=True)
    parser.add_argument("--next-marker")
    parser.add_argument("--end-of-pdf",action="store_true")
    parser.add_argument("--section-id",required=True)
    parser.add_argument("--model",required=True)
    parser.add_argument("--local-ollama-url",default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--attempts",type=int,default=2)
    parser.add_argument("--timeout",type=int,default=90)
    parser.add_argument("--new-private-stage",type=Path,required=True)
    args=parser.parse_args(argv)
    status=run_local_authoring(args.source,args.start_marker,args.next_marker,
       args.section_id,args.new_private_stage,end_of_pdf=args.end_of_pdf,
       model=args.model,endpoint=args.local_ollama_url,
       max_attempts=args.attempts,timeout=args.timeout)
    print(json.dumps(status))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
