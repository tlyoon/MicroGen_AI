"""Re-link an existing private author response across PDF passage segmentation changes.

Source PDF, narrated words, titles and bullets are never edited. Only an
unambiguous old source anchor can be re-cited to the new independently extracted
passage. Reuses original SHA/anti-copy/numeric/citation checks both before and
after rebinding. This is not semantic reinterpretation or an authoring model.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from microgen_portable_private_authoring_gate import (
    _safe_output, _validate_draft, build_authoring_packet, canonical_hash, clean,
)
from microgen_pronunciation_closed_loop import sha_file


class SourceCitationRelinkError(ValueError):
    pass


def relink_prior_source_packet(source: Path, old_packet: dict, old_draft: dict):
    source = Path(source)
    if source.is_symlink() or not source.is_file():
        raise SourceCitationRelinkError("Immutable original source PDF required")
    digest = sha_file(source)
    if (not isinstance(old_packet, dict) or not isinstance(old_draft, dict)
        or old_packet.get("source_pdf_sha256") != digest
        or old_draft.get("source_pdf_sha256") != digest
        or old_packet.get("section_id") != old_draft.get("section_id")
        or old_draft.get("packet_sha256") != canonical_hash(old_packet)
        or old_packet.get("publication_allowed") is not False
        or old_draft.get("publication_allowed") is not False):
        raise SourceCitationRelinkError("Old source/draft not SHA-locked to the original PDF")
    # The old packet still has to pass the historical original-source numeric
    # and anti-copy validator; old claims are never trusted merely by age.
    _validate_draft(old_packet, old_draft, source)
    try:
        fresh = build_authoring_packet(
            source, old_packet["start_marker"],
            old_packet.get("next_section_marker"),
            end_of_pdf=old_packet.get("end_of_pdf") is True,
            section_id=old_packet["section_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceCitationRelinkError("Fresh source passages cannot be reconstructed") from exc
    old_passages = {x["passage_id"]: x for x in old_packet["source_evidence"]}
    revised = copy.deepcopy(old_draft)
    moved = []
    for i, topic in enumerate(revised["topics"], 1):
        page = topic["source_page"]
        anchor = clean(topic["source_anchor"])
        if not anchor or len(anchor) < 12:
            raise SourceCitationRelinkError("Old authored source anchor is too short")
        old_ids = topic["source_passage_ids"]
        if (not isinstance(old_ids, list) or not 1 <= len(old_ids) <= 5
            or any(x not in old_passages or old_passages[x]["source_page"] != page
                   for x in old_ids)):
            raise SourceCitationRelinkError("Original source citations missing")
        original = " ".join(old_passages[x]["text"] for x in old_ids)
        if anchor not in clean(original):
            raise SourceCitationRelinkError("Original author anchor absent from cited source")
        candidates = [x for x in fresh["source_evidence"]
                      if x["source_page"] == page and
                      anchor in clean(x["text"])]
        if len(candidates) != 1:
            raise SourceCitationRelinkError(
                f"Slide {i}: source anchor not uniquely supported by current original PDF")
        new_ids = [candidates[0]["passage_id"]]
        if new_ids != old_ids:
            moved.append({"slide": i, "source_page": page,
                "previous_citations": len(old_ids),
                "current_citations": len(new_ids)})
        topic["source_passage_ids"] = new_ids
    revised["packet_sha256"] = canonical_hash(fresh)
    _validate_draft(fresh, revised, source)
    if sha_file(source) != digest:
        raise SourceCitationRelinkError("Original PDF changed during source citation migration")
    return fresh, revised, {
        "schema_version": 1,
        "status": "PRIVATE_SOURCE_CITATIONS_RELINKED_AND_ORIGINAL_DRAFT_REVALIDATED",
        "section_id": fresh["section_id"],
        "original_source_pdf_sha256": digest,
        "previous_packet_sha256": canonical_hash(old_packet),
        "current_packet_sha256": canonical_hash(fresh),
        "previous_draft_sha256": canonical_hash(old_draft),
        "current_draft_sha256": canonical_hash(revised),
        "passages_old": old_packet["source_passage_count"],
        "passages_current": fresh["source_passage_count"],
        "topics_preserved": len(revised["topics"]),
        "citations_relinked_count": len(moved),
        "citation_relink_records": moved,
        "authored_narration_titles_and_bullets_modified": False,
        "source_pdf_modified": False,
        "entire_scientific_semantics_proven": False,
        "local_model_invocations": 0,
        "provider_calls": 0,
        "publication_allowed": False,
    }


def save_private_source_relink(source: Path, old_packet_file: Path,
                               old_draft_file: Path, output: Path) -> dict:
    inputs = [Path(source), Path(old_packet_file), Path(old_draft_file)]
    for p in inputs:
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 15_000_000:
            raise SourceCitationRelinkError("Bounded private source or authoring artifact missing")
    dest = _safe_output(Path(output), Path(source))
    real = [p.resolve(strict=True) for p in inputs]
    if any(dest == p or dest in p.parents or p in dest.parents for p in real):
        raise SourceCitationRelinkError("Output cannot overlap original authoring source")
    before = {p: sha_file(p) for p in real}
    old = json.loads(inputs[1].read_text(encoding="utf8"))
    draft = json.loads(inputs[2].read_text(encoding="utf8"))
    packet, revised, evidence = relink_prior_source_packet(source, old, draft)
    if any(sha_file(p) != h for p, h in before.items()):
        raise SourceCitationRelinkError("Source input changed during citation migration")
    tmp = Path(tempfile.mkdtemp(prefix=".microgen-relink-private-", dir=dest.parent))
    try:
        for name, obj in (
            ("current_source_packet.json", packet),
            ("original_author_response_relinked.json", revised),
            ("private_source_relink_receipt.json", evidence)):
            (tmp/name).write_text(json.dumps(obj, indent=2), encoding="utf8")
        if dest.exists() or dest.is_symlink():
            raise SourceCitationRelinkError("Private output appeared before completion")
        os.rename(tmp, dest)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)
    return evidence


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-source-pdf", required=True, type=Path)
    parser.add_argument("--previous-private-packet", required=True, type=Path)
    parser.add_argument("--previous-private-draft", required=True, type=Path)
    parser.add_argument("--new-private-output", required=True, type=Path)
    opts = parser.parse_args(argv)
    result = save_private_source_relink(
        opts.original_source_pdf, opts.previous_private_packet,
        opts.previous_private_draft, opts.new_private_output)
    print(json.dumps({"status": result["status"],
        "topics": result["topics_preserved"],
        "source_citations_relinked": result["citations_relinked_count"],
        "provider_calls": 0, "publication_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
