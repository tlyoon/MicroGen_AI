"""Deterministic original-source citation migration without regenerating drafts."""
import copy
import json
import tempfile
from pathlib import Path

import pytest

from microgen_private_source_citation_relink import (
    SourceCitationRelinkError, relink_prior_source_packet,
    save_private_source_relink,
)
from microgen_portable_private_authoring_gate import canonical_hash
from microgen_pronunciation_closed_loop import sha_file
from test_microgen_portable_private_authoring_gate import construct


def old_version(source, packet, draft):
    packet = copy.deepcopy(packet)
    draft = copy.deepcopy(draft)
    mapping = {}
    for passage in packet["source_evidence"]:
        old = passage["passage_id"]
        new = "previous_segment_" + old
        mapping[old] = new
        passage["passage_id"] = new
    for topic in draft["topics"]:
        topic["source_passage_ids"] = [
            mapping[identifier] for identifier in topic["source_passage_ids"]]
    draft["packet_sha256"] = canonical_hash(packet)
    return packet, draft


def test_original_source_draft_is_preserved_while_unique_old_passage_ids_rebased():
    with tempfile.TemporaryDirectory() as td:
        source, packet, draft = construct(Path(td))
        before = sha_file(source)
        old, prior = old_version(source, packet, draft)
        fresh, moved, receipt = relink_prior_source_packet(source, old, prior)
        assert canonical_hash(fresh) == canonical_hash(packet)
        assert moved["packet_sha256"] == canonical_hash(fresh)
        assert receipt["citations_relinked_count"] == len(draft["topics"])
        assert receipt["topics_preserved"] == len(draft["topics"])
        assert not receipt["authored_narration_titles_and_bullets_modified"]
        assert not receipt["source_pdf_modified"]
        assert not receipt["publication_allowed"]
        for old_topic, new_topic in zip(prior["topics"], moved["topics"]):
            for field in ("title", "bullets", "narration", "source_anchor",
                          "required_terms", "topic_id", "source_page"):
                assert old_topic[field] == new_topic[field]
        assert sha_file(source) == before


def test_relink_can_save_atomic_private_packet_and_new_author_response():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source, packet, draft = construct(root)
        old, prior = old_version(source, packet, draft)
        packet_file = root/"previous_packet.json"
        draft_file = root/"previous_draft.json"
        packet_file.write_text(json.dumps(old), encoding="utf8")
        draft_file.write_text(json.dumps(prior), encoding="utf8")
        output = root/"relinked"
        result = save_private_source_relink(
            source, packet_file, draft_file, output)
        assert result["topics_preserved"] == 2
        assert (output/"current_source_packet.json").is_file()
        assert (output/"original_author_response_relinked.json").is_file()
        assert (output/"private_source_relink_receipt.json").is_file()
        record = (output/"private_source_relink_receipt.json").read_text()
        assert "This learning segment" not in record
        assert "A model can simplify" not in record
        with pytest.raises((SourceCitationRelinkError,ValueError)):
            save_private_source_relink(source, packet_file, draft_file, output)


@pytest.mark.parametrize("fault",[
    "source_changed", "forged_draft_hash", "missing_source_page",
    "fabricated_anchor", "unsupported_source_id", "publication_true",
])
def test_fabricated_source_evidence_never_silently_rebased(fault):
    with tempfile.TemporaryDirectory() as td:
        source, packet, draft = construct(Path(td))
        old, prior = old_version(source, packet, draft)
        if fault == "source_changed":
            source.write_bytes(source.read_bytes()+b"changed")
        elif fault == "forged_draft_hash":
            prior["packet_sha256"] = "f"*64
        elif fault == "missing_source_page":
            prior["topics"][0]["source_page"] = 5
        elif fault == "fabricated_anchor":
            prior["topics"][0]["source_anchor"] = (
                "An invented original physical source anchor is here")
        elif fault == "unsupported_source_id":
            prior["topics"][0]["source_passage_ids"] = ["not_present"]
        elif fault == "publication_true":
            prior["publication_allowed"] = True
        with pytest.raises((SourceCitationRelinkError,ValueError,KeyError)):
            relink_prior_source_packet(source, old, prior)


def test_exactly_matching_packet_preserves_all_original_topic_text():
    with tempfile.TemporaryDirectory() as td:
        source, packet, draft = construct(Path(td))
        fresh, same, result = relink_prior_source_packet(source, packet, draft)
        assert canonical_hash(fresh) == canonical_hash(packet)
        assert same == draft
        assert result["citations_relinked_count"] == 0
