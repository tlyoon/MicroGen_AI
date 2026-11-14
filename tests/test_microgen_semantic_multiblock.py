"""Offline regression: one narrated cue may illuminate several real PDF blocks.

No Gemini call, third-party source text, Whisper, or public distribution.
"""
import json

import pytest

from test_microgen_timed_cue_tts import input_stage, sample_wav
from microgen_cue_semantic_mapping import SemanticMappingError, validate_matches
from microgen_timed_cue_planner import PLAN_FILE, write_verified_plan
from microgen_timed_cue_tts import CueTTSError, _verified_plan, produce_measured_cue_audio
from microgen_timed_highlight_contract import (
    HighlightContractError, MANIFEST, inspect_timed_highlights,
    ffmpeg_highlight_filter,
)


def _group_stage(tmp_path):
    stage = input_stage(tmp_path)
    path = stage / "script_tts.json"
    data = json.loads(path.read_text(encoding="utf8"))
    data["slides"][0]["tts_text"] = "These two related principles are connected."
    data["slides"][0]["narration"] = data["slides"][0]["tts_text"]
    path.write_text(json.dumps(data), encoding="utf8")
    (stage / PLAN_FILE).unlink()

    def source_bound_group(slide, missing, blocks):
        assert slide == 1
        assert [x[0] for x in missing] == [1]
        assert len(blocks) == 2
        return [{
            "cue": 1,
            "blocks": [1, 2],
            "quotes": ["Conservation of momentum", "Transport of radiation"],
        }]

    write_verified_plan(stage, semantic_resolver=source_bound_group)
    return stage


def test_group_proposal_anchored_and_legacy_single_unchanged():
    blocks = [
        ([40, 50, 260, 72], "Conservation of momentum and energy", set()),
        ([40, 80, 280, 102], "Transport of radiation and momentum", set()),
    ]
    got = validate_matches(
        [{"cue": 1, "blocks": [1, 2],
          "quotes": ["Conservation of momentum", "Transport of radiation"]}],
        [(1, "These two related principles are connected.")], blocks)
    assert got[1] == ((0, 1), ("Conservation of momentum", "Transport of radiation"))
    single = validate_matches(
        [{"cue": 1, "block": 1, "quote": "Conservation of momentum"}],
        [(1, "The relationship remains unchanged.")], blocks)
    assert single[1] == ((0,), ("Conservation of momentum",))


@pytest.mark.parametrize("proposal", [
    {"cue": 1, "blocks": [2, 1], "quotes": ["Transport of radiation", "Conservation of momentum"]},
    {"cue": 1, "blocks": [1, 1], "quotes": ["Conservation of momentum", "Conservation of momentum"]},
    {"cue": 1, "blocks": [1, 2], "quotes": ["Conservation of momentum", "Fabricated conclusion"]},
    {"cue": 1, "blocks": [1, 2], "quotes": ["Conservation of momentum"]},
    {"cue": 1, "blocks": [1, 2], "quotes": ["Conservation of momentum", "Transport of radiation"], "extra": True},
])
def test_unsafe_multiblock_group_fails_closed(proposal):
    blocks = [
        ([40, 50, 260, 72], "Conservation of momentum and energy", set()),
        ([40, 80, 280, 102], "Transport of radiation and momentum", set()),
    ]
    with pytest.raises(SemanticMappingError):
        validate_matches([proposal], [(1, "These two related principles are connected.")], blocks)


def test_grouped_numerical_claim_cannot_be_invented():
    blocks = [
        ([40, 50, 260, 72], "Momentum equals 12 kilograms", set()),
        ([40, 80, 280, 102], "Radiation energy equals 20 joules", set()),
    ]
    with pytest.raises(SemanticMappingError, match="Numerical"):
        validate_matches(
            [{"cue": 1, "blocks": [1, 2], "quotes":
              ["Momentum equals 12", "Radiation energy equals 20"]}],
            [(1, "The result is 999 joules.")], blocks)


def test_group_verified_before_audio_and_all_regions_rendered(tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS", "1")
    stage = _group_stage(tmp_path)
    saved = json.loads((stage / PLAN_FILE).read_text(encoding="utf8"))
    group = saved["slides"][0]["cues"][0]
    assert len(group["pdf_bboxes"]) == 2
    assert len(group["semantic_source_quotes"]) == 2
    assert saved["total_cues"] == 3
    assert saved["semantic_mapping_certified"] is False
    verified, fragments = _verified_plan(stage)
    assert verified == saved
    assert len(fragments) == 3

    report = produce_measured_cue_audio(stage, speak=sample_wav)
    assert report["cue_count"] == 3
    bound = inspect_timed_highlights(stage)
    assert bound["slides"][0]["elements"][0]["pdf_bboxes"] == group["pdf_bboxes"]
    assert bound["visual_highlight_rendering_verified"] is False
    assert bound["publication_allowed"] is False
    drawing = ffmpeg_highlight_filter(bound, 1)
    # Two independent visible regions, each with both fill and border.
    assert drawing.count("drawbox=") == 4
    assert not (stage / ".microgen_autonomous_acceptance.json").exists()


def test_forged_second_block_fails_before_paid_speech(tmp_path):
    stage = _group_stage(tmp_path)
    path = stage / PLAN_FILE
    saved = json.loads(path.read_text(encoding="utf8"))
    saved["slides"][0]["cues"][0]["semantic_source_quotes"][1] = "Never present in PDF"
    path.write_text(json.dumps(saved), encoding="utf8")
    with pytest.raises(CueTTSError, match="not PDF grounded"):
        _verified_plan(stage)


def test_forged_group_manifest_fails_independent_audio_validator(tmp_path, monkeypatch):
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS", "1")
    stage = _group_stage(tmp_path)
    produce_measured_cue_audio(stage, speak=sample_wav)
    manifest = stage / MANIFEST
    raw = json.loads(manifest.read_text(encoding="utf8"))
    raw["slides"][0]["cues"][0]["pdf_bboxes"][1] = [10, 10, 40, 15]
    manifest.write_text(json.dumps(raw), encoding="utf8")
    with pytest.raises(HighlightContractError):
        inspect_timed_highlights(stage)


@pytest.mark.skipif(
    __import__("os").environ.get("MICROGEN_MEDIA_INTEGRATION_TEST") != "1",
    reason="Explicit opt-in for offline H.264 decoded multi-region media verification",
)
def test_actual_encoded_group_shows_every_selected_pdf_region(tmp_path, monkeypatch):
    import shutil
    from pathlib import Path
    import fitz
    from gen_video_v22 import _make_segment
    from microgen_measured_highlight_video_qa import _frame, _pdf_reference, _pixel_box
    from microgen_single_figure_frame_diff_qa import (
        frame_difference_metrics, figure_change_visible,
    )

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("No Windows FFmpeg")
    monkeypatch.setenv("MICROGEN_TTS_QUEUE_ROUNDS", "1")
    monkeypatch.setenv("MICROVID_FFMPEG", ffmpeg)
    stage = _group_stage(tmp_path)
    produce_measured_cue_audio(stage, speak=sample_wav)
    checked = inspect_timed_highlights(stage)
    source_regions = checked["slides"][0]["elements"][0]["pdf_bboxes"]
    assert len(source_regions) == 2
    filtergraph = ffmpeg_highlight_filter(checked, 1)
    video = stage / "local_group_render.mp4"
    _make_segment(
        stage / "slide1.pdf", stage / "slide1.wav", video,
        highlight_filter=filtergraph,
    )
    assert video.is_file() and video.stat().st_size > 0
    with fitz.open(stage / "slide1.pdf") as doc:
        page = doc[0]
        original = _pdf_reference(page)
        decoded = _frame(Path(ffmpeg), video, 0.3)
        for region in source_regions:
            roi = _pixel_box(page, {"pdf_bbox": region})
            localized, full = frame_difference_metrics(original, decoded, roi)
            assert figure_change_visible(localized, full)
    assert checked["publication_allowed"] is False
    assert not (stage / ".microgen_autonomous_acceptance.json").exists()
