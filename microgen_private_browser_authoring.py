"""ChatGPT/Gemini browser-response handoff for PRIVATE source-based lectures.

NO local model, inference dependency, paid API, network calls, browser profile
access or automatic upload. A user-authorized ChatGPT/Gemini browser conversation
can provide a bounded JSON response; this program validates it as untrusted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from microgen_portable_private_authoring_gate import (
    AuthoringGateError, _safe_output, build_authoring_packet,
    canonical_hash, write_validated_stage,
)


class BrowserAuthoringError(ValueError):
    pass


def browser_prompt(packet: dict) -> str:
    if packet.get("publication_allowed") is not False:
        raise BrowserAuthoringError("No publication-authorized source packets")
    return (
        "You are preparing NEW, independently worded physics lecture material "
        "from the PRIVATE source-evidence packet below. Do not reproduce "
        "textbook excerpts, images, or copyrighted figures in the response. "
        "Your output must be only ONE JSON object (no explanations), with "
        "schema_version=1, section_id and source_pdf_sha256 copied from the "
        "source packet, packet_sha256 set to the exact value below, "
        "publication_allowed=false, and topics (2 to 60). "
        "Each topic needs: topic_id (distinct lowercase slug), source_page "
        "(1-indexed), source_passage_ids (1-5 IDs on that page), "
        "source_anchor (8-160-character literal source substring), required_terms "
        "(1-4 exact technical terms, each present in the cited passage AND "
        "narration AND visible title/bullets), title (5-90 ASCII characters), "
        "bullets (2-5 original ASCII strings, each 5-88 characters), narration "
        "(60-250 original ASCII words). Order topics by source page. Avoid "
        "invented values, unverified equations, and speculative physical claims. "
        "Do not copy 12 consecutive source tokens or repeat scripts. "
        "Explain important assumptions within the teaching copy. "
        "This is an unpublished candidate; academic and rights checks remain. "
        "Do not request a locally installed model or paid API.\n\n"
        "SHA-LOCKED PACKET (do not alter source fields):\n"
        f"packet_sha256={canonical_hash(packet)}\n"
        + json.dumps(packet, ensure_ascii=True, indent=2)
    )


def parse_browser_response(raw: str) -> dict:
    """Only a whole JSON object or one isolated Markdown JSON fence is accepted."""
    if not isinstance(raw, str) or not 2 <= len(raw.encode("utf8")) <= 650_000:
        raise BrowserAuthoringError("Missing or oversized browser response")
    trimmed=raw.strip()
    fence=chr(96)*3
    if trimmed.startswith(fence):
        lines=trimmed.splitlines()
        if len(lines)<3 or lines[0] not in (fence, fence+"json") or lines[-1]!=fence:
            raise BrowserAuthoringError("Malformed fenced browser response")
        trimmed="\n".join(lines[1:-1]).strip()
    try:
        obj=json.loads(trimmed)
    except ValueError as exc:
        raise BrowserAuthoringError("Browser response must contain one JSON object") from exc
    if not isinstance(obj, dict) or obj.get("publication_allowed") is not False:
        raise BrowserAuthoringError("JSON response must explicitly deny publication")
    return obj


def prepare_private_prompt(source: Path, start_marker: str, next_marker: str | None,
                           section_id: str, dest: Path, *, end_of_pdf: bool = False):
    source,dest=Path(source),Path(dest)
    _safe_output(dest,source)
    packet=build_authoring_packet(source,start_marker,next_marker,
                                  end_of_pdf=end_of_pdf,section_id=section_id)
    # Source quotes stay in a PRIVATE local prompt. Never print them or upload.
    with dest.open("x",encoding="utf8") as output:
        output.write(browser_prompt(packet))
    return {"source_pdf_sha256":packet["source_pdf_sha256"],
            "packet_sha256":canonical_hash(packet),
            "source_passage_count":packet["source_passage_count"],
            "external_model_invocations":0,
            "publication_allowed":False}


def accept_browser_response(source:Path,start_marker:str,next_marker:str|None,
                            section_id:str,response:Path,new_stage:Path,
                            *,end_of_pdf:bool=False):
    source,response,new_stage=Path(source),Path(response),Path(new_stage)
    if response.is_symlink() or not response.is_file() or response.stat().st_size>650_000:
        raise BrowserAuthoringError("One bounded private response file is required")
    packet=build_authoring_packet(source,start_marker,next_marker,
                                  end_of_pdf=end_of_pdf,section_id=section_id)
    draft=parse_browser_response(response.read_text(encoding="utf8"))
    # Independent PR247 source-packet regeneration and academic-format checks
    # operate on the untrusted response, not the provider's claimed identity.
    qa=write_validated_stage(source,packet,draft,new_stage)
    return {"topic_count":qa["topic_count"],
            "source_passage_count":qa["passage_count"],
            "linked_passage_count":qa["passages_used_count"],
            "source_sha256":qa["source_pdf_sha256"],
            "provider_identity_independently_verified":False,
            "source_semantics_independently_proven":False,
            "publication_allowed":False}


def main(argv=None):
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source",type=Path,required=True)
    cli.add_argument("--start-marker",required=True)
    cli.add_argument("--next-marker")
    cli.add_argument("--end-of-pdf",action="store_true")
    cli.add_argument("--section-id",required=True)
    group=cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--new-private-prompt",type=Path)
    group.add_argument("--browser-response",type=Path)
    cli.add_argument("--new-private-stage",type=Path)
    args=cli.parse_args(argv)
    if args.new_private_prompt is not None:
        result=prepare_private_prompt(args.source,args.start_marker,
          args.next_marker,args.section_id,args.new_private_prompt,
          end_of_pdf=args.end_of_pdf)
    else:
        if args.new_private_stage is None:
            cli.error("--new-private-stage is required with --browser-response")
        result=accept_browser_response(args.source,args.start_marker,
          args.next_marker,args.section_id,args.browser_response,
          args.new_private_stage,end_of_pdf=args.end_of_pdf)
    print(json.dumps(result,ensure_ascii=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
