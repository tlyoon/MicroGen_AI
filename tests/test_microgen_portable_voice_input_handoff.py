"""Provider-neutral voice export: source-bound, no local voice or paid services."""
import json
import tempfile
from pathlib import Path

import pytest

from test_microgen_portable_private_authoring_gate import construct
from microgen_portable_private_authoring_gate import write_validated_stage
from microgen_portable_slide_render import render_portable_slides
from microgen_portable_voice_input_handoff import (
    PortableVoiceHandoffError, prepare_portable_voice_input_handoff,
    save_portable_voice_input_handoff,
)
from microgen_pronunciation_closed_loop import sha_file


def setup_case(root: Path):
    source, packet, draft = construct(root)
    before = sha_file(source)
    stage = root / "stage"
    write_validated_stage(source, packet, draft, stage)
    slides = root / "slides"
    render_portable_slides(
        stage, stage / "narration.json", stage / "plan.json",
        stage / "contract.json", slides)
    return source, before, stage, slides


def test_verified_private_deck_exports_exact_provider_neutral_inputs():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source, before, stage, slides = setup_case(root)
        output = root / "voice_handoff.json"
        result = save_portable_voice_input_handoff(stage, slides, output)
        assert result["slide_count"] == 2
        assert len(result["requests"]) == 2
        assert result["provider_calls"] == 0
        assert result["local_model_invocations"] == 0
        assert result["formal_voice_provider"] is None
        assert result["formal_voice_name"] is None
        assert result["formal_voice_synthesis_authorized"] is False
        assert result["publication_allowed"] is False
        assert all(x["audio_filename"] is None for x in result["requests"])
        assert sha_file(source) == before
        assert json.loads(output.read_text()) == result
        assert not (stage / "voice_handoff.json").exists()


@pytest.mark.parametrize("target,field", [
    ("stage/narration.json", "narration"),
    ("stage/plan.json", "visual_plan"),
    ("stage/contract.json", "contract"),
    ("slides/slides_teaching_candidate.pdf", "rendered_pdf"),
    ("slides/teaching_slide_receipt.json", "slide_receipt"),
])
def test_tampered_protected_artifact_rejected_without_export(target, field):
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _, _, stage, slides = setup_case(root)
        path = root / target
        with path.open("ab") as f:
            f.write(b"\nTampered")
        output = root / "voice_handoff.json"
        with pytest.raises(PortableVoiceHandoffError):
            save_portable_voice_input_handoff(stage, slides, output)
        assert not output.exists()


def test_attempt_to_promote_voice_or_publication_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _, _, stage, slides = setup_case(root)
        receipt = slides / "teaching_slide_receipt.json"
        record = json.loads(receipt.read_text())
        record["formal_voice_authorized"] = True
        receipt.write_text(json.dumps(record))
        with pytest.raises(PortableVoiceHandoffError):
            prepare_portable_voice_input_handoff(stage, slides)


def test_source_grounded_handoff_cannot_be_overwritten():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _, _, stage, slides = setup_case(root)
        out = root / "voice_handoff.json"
        save_portable_voice_input_handoff(stage, slides, out)
        digest = sha_file(out)
        with pytest.raises(PortableVoiceHandoffError):
            save_portable_voice_input_handoff(stage, slides, out)
        assert sha_file(out) == digest


def test_output_under_source_tree_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _, _, stage, slides = setup_case(root)
        with pytest.raises(PortableVoiceHandoffError):
            save_portable_voice_input_handoff(stage, slides, stage / "voice_handoff.json")
