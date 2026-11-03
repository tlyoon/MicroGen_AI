"""Complete private chapter inventory with atomic scientific and voice evidence."""
import json
import tempfile
from pathlib import Path

import pytest

from microgen_portable_private_authoring_gate import (
    canonical_hash, write_validated_stage,
)
from microgen_portable_slide_render import render_portable_slides
from microgen_private_chapter_voice_campaign import (
    PrivateChapterCampaignError, audit_private_chapter_handoff)
from microgen_pronunciation_closed_loop import sha_file
from test_microgen_portable_private_authoring_gate import construct


def make_chapter(root):
    cases = []
    for i in (1, 2):
        name = f"1.{i}"
        folder = root/name
        folder.mkdir()
        source, packet, draft = construct(folder)
        packet["section_id"] = name
        draft["section_id"] = name
        draft["packet_sha256"] = canonical_hash(packet)
        pf, df = folder/"packet.json", folder/"draft.json"
        pf.write_text(json.dumps(packet), encoding="utf8")
        df.write_text(json.dumps(draft), encoding="utf8")
        stage = folder/"stage"
        write_validated_stage(source,packet,draft,stage)
        slides = folder/"slides"
        render_portable_slides(stage, stage/"narration.json",
            stage/"plan.json",stage/"contract.json",slides)
        cases.append({"section_id":name,"source_pdf":str(source),
            "private_packet":str(pf),"private_draft":str(df),
            "stage":str(stage),"slides":str(slides)})
    return {"chapter_id":"1","expected_sections":["1.1","1.2"],"cases":cases}


def test_complete_chapter_source_science_voice_templates_atomic():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);chapter=make_chapter(root)
        prev=[sha_file(Path(x["source_pdf"])) for x in chapter["cases"]]
        out=root/"finished"
        r=audit_private_chapter_handoff(chapter,out)
        assert r["section_count"]==2
        assert r["total_teaching_slides"]==4
        assert r["total_voice_requests"]==4
        assert r["original_textbook_source_modified"] is False
        assert r["tts_audio_generated"] is False
        assert r["provider_calls"]==0
        assert r["publication_allowed"] is False
        assert not r["complete_academic_semantics_proven"]
        assert r["unapproved_voice_handoff_has_private_narration_text"]
        assert (out/"chapter_private_readiness_receipt.json").is_file()
        assert (out/"source_science"/"unified_private_campaign_receipt.json").is_file()
        assert r["combined_source_science_receipt_sha256"]==sha_file(
            out/"source_science"/"unified_private_campaign_receipt.json")
        for item in r["sections"]:
            voice=json.loads((out/item["voice_request_file"]).read_text())
            template=json.loads((out/item["empty_capture_template_file"]).read_text())
            assert voice["section_id"]==item["section_id"]
            assert len(voice["requests"])==item["authored_topics_and_slides_verified"]
            assert not voice["formal_voice_synthesis_authorized"]
            assert all(x["audio_filename"] is None for x in voice["requests"])
            assert all(x["wav_sha256"] is None for x in template["captured_wavs"])
            assert template["declared_provider"] is None
            assert item["voice_request_sha256"]==sha_file(out/item["voice_request_file"])
        metadata=(out/"chapter_private_readiness_receipt.json").read_text()
        assert "This learning segment" not in metadata
        assert "A model can simplify" not in metadata
        assert [sha_file(Path(x["source_pdf"])) for x in chapter["cases"]]==prev


@pytest.mark.parametrize("fault",[
    "missing_section", "duplicate", "reversed", "unexpected", "wrong_chapter",
    "missing_slides", "changed_rendered_pdf", "fake_voice_approval",
    "modified_private_response", "changed_source", "output_under_stage",
    "output_in_drive", "output_exists", "tampered_second_packet"
])
def test_fleet_rejects_failed_member_without_partial_source_or_voice_output(fault):
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);chapter=make_chapter(root)
        rows=chapter["cases"]
        output=root/"all_or_nothing"
        if fault=="missing_section":
            chapter["expected_sections"].pop()
        elif fault=="duplicate":
            rows[1]["section_id"]="1.1"
        elif fault=="reversed":
            rows.reverse()
        elif fault=="unexpected":
            chapter["expected_sections"]=["1.1","1.3"]
        elif fault=="wrong_chapter":
            chapter["chapter_id"]="2"
        elif fault=="missing_slides":
            rows[1]["slides"]=str(root/"missing")
        elif fault=="changed_rendered_pdf":
            pdf=Path(rows[1]["slides"])/"slides_teaching_candidate.pdf"
            with pdf.open("ab") as file:file.write(b"tamper")
        elif fault=="fake_voice_approval":
            file=Path(rows[1]["slides"])/"teaching_slide_receipt.json"
            record=json.loads(file.read_text())
            record["formal_voice_authorized"]=True
            file.write_text(json.dumps(record))
        elif fault=="modified_private_response":
            file=Path(rows[1]["private_draft"])
            record=json.loads(file.read_text())
            record["topics"][0]["title"]="An invented paper finding"
            file.write_text(json.dumps(record))
        elif fault=="changed_source":
            file=Path(rows[1]["source_pdf"])
            with file.open("ab") as out:out.write(b"changed")
        elif fault=="output_under_stage":
            output=Path(rows[1]["stage"])/"unsafe"
        elif fault=="output_in_drive":
            cloud=root/"My Drive";cloud.mkdir()
            output=cloud/"unsafe"
        elif fault=="output_exists":
            output.mkdir()
        elif fault=="tampered_second_packet":
            file=Path(rows[1]["private_packet"])
            record=json.loads(file.read_text())
            record["source_pdf_sha256"]="a"*64
            file.write_text(json.dumps(record))
        with pytest.raises((PrivateChapterCampaignError, ValueError, OSError)):
            audit_private_chapter_handoff(chapter,output)
        assert not (output/"chapter_private_readiness_receipt.json").exists()
        assert not (output/"source_science").exists()
        assert not (output/"voice_inputs").exists()


def test_no_successful_partial_chapter_without_explicit_inventory():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);chapter=make_chapter(root)
        chapter.pop("expected_sections")
        with pytest.raises(PrivateChapterCampaignError):
            audit_private_chapter_handoff(chapter,root/"bad")
