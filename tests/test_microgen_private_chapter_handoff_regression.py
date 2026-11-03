"""Extra mid-flight checks not covered by the full synthetic chapter fixture.

No copyrighted source, live provider, generation or TTS dependency.
"""
import pytest
import microgen_private_chapter_voice_campaign as campaign
from microgen_pronunciation_closed_loop import sha_file


def _chapter(tmp_path):
    cases = []
    for section in ("1.1", "1.2"):
        source = tmp_path / f"source_{section}.pdf"
        source.write_bytes(f"synthetic PDF {section}".encode())
        stage = tmp_path / f"stage_{section}"
        slides = tmp_path / f"slides_{section}"
        stage.mkdir()
        slides.mkdir()
        (stage / "source.pdf").write_bytes(source.read_bytes())
        (stage / "contract.json").write_text('{"figures":[]}')
        (stage / "narration.json").write_text("{}")
        (stage / "plan.json").write_text("{}")
        (slides / "slides_teaching_candidate.pdf").write_bytes(b"synthetic deck")
        (slides / "teaching_slide_receipt.json").write_text("{}")
        packet = tmp_path / f"packet_{section}.json"
        draft = tmp_path / f"draft_{section}.json"
        packet.write_text("{}")
        draft.write_text("{}")
        cases.append(dict(section_id=section, source_pdf=str(source),
                          private_packet=str(packet), private_draft=str(draft),
                          stage=str(stage), slides=str(slides)))
    return {"chapter_id": "1", "expected_sections": ["1.1", "1.2"], "cases": cases}


def _stubs(monkeypatch, *, midflight_mutation=False, wrong_voice_section=False):
    def voice(stage, slides):
        section = stage.name.split("stage_", 1)[1]
        return {"section_id": "9.9" if wrong_voice_section else section,
                "source_pdf_sha256": sha_file(stage / "source.pdf"),
                "slide_count": 2,
                "rendered_pdf_sha256": sha_file(slides / "slides_teaching_candidate.pdf"),
                "narration_sha256": sha_file(stage / "narration.json"),
                "formal_voice_synthesis_authorized": False,
                "publication_allowed": False, "provider_calls": 0,
                "local_model_invocations": 0}

    def science(cases, output):
        output.mkdir()
        (output / "unified_private_campaign_receipt.json").write_text(
            '{"status":"synthetic"}')
        rows = [{"section_id": c["section_id"],
                 "original_source_sha256": sha_file(c["source_pdf"]),
                 "authored_topics_verified": 2,
                 "source_passages_discovered": 3,
                 "source_passages_linked": 2,
                 "high_interest_uncited_advisory": 0,
                 "original_source_draft_and_compiled_spoken_visual_text_identical": True,
                 "historical_authoring_sha_lineage_discrepancy_advisory": False} for c in cases]
        if midflight_mutation:
            from pathlib import Path
            (Path(cases[0]["stage"]) / "narration.json").write_text(
                '{"tampered":true}')
        return {"sections": rows}

    monkeypatch.setattr(campaign, "prepare_portable_voice_input_handoff", voice)
    monkeypatch.setattr(campaign, "audit_unified_private_campaign", science)
    monkeypatch.setattr(campaign, "make_audio_capture_template",
                        lambda _p: {"formal_production_authorized": False,
                                    "declared_provider": None, "declared_voice": None})


def test_change_to_protected_input_during_campaign_aborts_atomically(tmp_path, monkeypatch):
    chapter = _chapter(tmp_path)
    _stubs(monkeypatch, midflight_mutation=True)
    output = tmp_path / "no_partial_chapter"
    with pytest.raises(campaign.PrivateChapterCampaignError, match="changed"):
        campaign.audit_private_chapter_handoff(chapter, output)
    assert not output.exists()


def test_voice_section_identity_mismatch_aborts_before_output(tmp_path, monkeypatch):
    chapter = _chapter(tmp_path)
    _stubs(monkeypatch, wrong_voice_section=True)
    output = tmp_path / "no_partial_chapter"
    with pytest.raises(campaign.PrivateChapterCampaignError, match="identity"):
        campaign.audit_private_chapter_handoff(chapter, output)
    assert not output.exists()
