"""Source-free normal-entrypoint regression for omitted textbook vector figures.

A PDF figure is automatically rendered only if its caption is unique,
distinctively styled, in a narrow column, and adjacent to complete vector
regions and labels. No external provider, OCR or human crop selection.
"""
import json

import pymupdf
import pytest

from microgen_missing_source_figure_candidates import (
    check_graphics_with_source_candidates,
)
from microgen_source_caption_vector_recovery import (
    CaptionVectorRecoveryError, recover_caption_anchored_vectors,
    validate_source_caption_vector_recovery,
)
from microgen_quality import dependency_fingerprint


def source_fixture(tmp_path, *, caption_color=(0.08, 0.40, 0.70),
                   caption_bold=True, figure=True, duplicate=False):
    pdf = pymupdf.open()
    for _ in range(2 if duplicate else 1):
        pdf.new_page(width=612, height=783)
    for index in range(len(pdf)):
        page = pdf[index]
        page.insert_text(
            (453, 700), "Figure 2.7  Acceleration and velocity-time graphs",
            fontsize=10, fontname="hebo" if caption_bold else "helv",
            color=caption_color,
        )
        page.insert_text((70, 655),
                         "Figure 2.7 illustrates how acceleration works.",
                         fontsize=10, fontname="helv", color=(0, 0, 0))
        if figure:
            page.draw_rect(pymupdf.Rect(457, 487, 555, 530),
                           color=(0.63, 0.15, 0.04))
            page.draw_rect(pymupdf.Rect(463, 560, 570, 609),
                           color=(0.63, 0.15, 0.04))
            page.draw_rect(pymupdf.Rect(448, 632, 570, 663),
                           color=(0.63, 0.15, 0.04))
            page.insert_text((457, 472), "Instantaneous acceleration", fontsize=9)
            page.insert_text((457, 547), "a", fontsize=9)
            page.insert_text((470, 595),
                             "Acceleration equals slope of velocity curve.",
                             fontsize=6)
            page.insert_text((457, 676), "b", fontsize=9)
    pdf.save(tmp_path / "source.pdf")
    pdf.close()
    (tmp_path / "slides.tex").write_text(
        "\\documentclass{beamer}\n"
        "\\begin{document}\n"
        "\\begin{frame}{Velocity}\n"
        "\\includegraphics[height=0.4\\textheight]{Figure 2.7.png}\n"
        "\\end{frame}\n\\end{document}\n",
        encoding="utf-8",
    )
    return tmp_path


def test_real_production_graphics_gate_autorecovers_unique_pdf_vector(tmp_path):
    stage = source_fixture(tmp_path)
    assert not (stage / "Figure 2.7.png").exists()
    verified = check_graphics_with_source_candidates(stage / "slides.tex")
    assert len(verified) == 1
    image = stage / "Figure 2.7.png"
    pix = pymupdf.Pixmap(str(image))
    assert pix.width >= 120 and pix.height >= 120
    receipt = json.loads(
        (stage / ".microgen_source_caption_vector_recovery.json")
        .read_text(encoding="utf-8"))
    assert receipt["status"] == "SOURCE_CAPTION_VECTOR_GEOMETRY_ATTESTED"
    assert receipt["source_image_identity"].startswith("unique styled caption")
    assert receipt["science_qa_required"] is True
    assert receipt["publication_allowed"] is False
    assert len(receipt["figures"]) == 1
    assert receipt["figures"][0]["source_page"] == 1
    assert receipt["figures"][0]["vector_regions"] >= 3
    assert receipt["figures"][0]["label_blocks"] >= 3
    assert validate_source_caption_vector_recovery(stage)["figures"] == [
        "Figure 2.7.png"]
    # Re-entry is idempotent; it does not silently replace the accepted PNG.
    before = image.read_bytes()
    assert len(check_graphics_with_source_candidates(stage / "slides.tex")) == 1
    assert image.read_bytes() == before


@pytest.mark.parametrize("kwargs", [
    {"caption_bold": False},
    {"caption_color": (0, 0, 0)},
    {"figure": False},
    {"duplicate": True},
])
def test_ambiguous_or_unattested_figures_fail_closed(tmp_path, kwargs):
    stage = source_fixture(tmp_path, **kwargs)
    with pytest.raises(CaptionVectorRecoveryError):
        recover_caption_anchored_vectors(stage)
    assert not (stage / "Figure 2.7.png").exists()
    assert not (stage / ".microgen_source_caption_vector_recovery.json").exists()


def test_untrusted_figure_reference_cannot_escape_stage(tmp_path):
    stage = source_fixture(tmp_path)
    text = (stage / "slides.tex").read_text(encoding="utf8")
    (stage / "slides.tex").write_text(
        text.replace("Figure 2.7.png", "../Figure 2.7.png"), encoding="utf8")
    with pytest.raises(CaptionVectorRecoveryError):
        recover_caption_anchored_vectors(stage)


def test_recovery_receipt_detects_tampered_figure_or_source(tmp_path):
    stage = source_fixture(tmp_path)
    recover_caption_anchored_vectors(stage)
    figure = stage / "Figure 2.7.png"
    figure.write_bytes(figure.read_bytes() + b"tampered")
    with pytest.raises(CaptionVectorRecoveryError):
        validate_source_caption_vector_recovery(stage)


def test_recovery_receipt_detects_bbox_drift(tmp_path):
    stage = source_fixture(tmp_path)
    recover_caption_anchored_vectors(stage)
    path = stage / ".microgen_source_caption_vector_recovery.json"
    receipt = json.loads(path.read_text(encoding="utf8"))
    receipt["figures"][0]["crop_bbox"][0] += 20
    path.write_text(json.dumps(receipt), encoding="utf8")
    with pytest.raises(CaptionVectorRecoveryError):
        validate_source_caption_vector_recovery(stage)


def test_correctly_existing_figure_never_overwritten(tmp_path):
    stage = source_fixture(tmp_path)
    original = b"untouched-external-image"
    (stage / "Figure 2.7.png").write_bytes(original)
    with pytest.raises(CaptionVectorRecoveryError):
        recover_caption_anchored_vectors(stage)
    assert (stage / "Figure 2.7.png").read_bytes() == original


def test_slide_stage_fingerprint_tracks_shared_missing_figure_remedy(tmp_path):
    for name in (
        "source.pdf", "gen_slides_v20.py", "gen_slides_prompt_v20_hybrid.txt",
        "microgen_slide_reflow.py", "microgen_layout_retry_guard.py",
        "microgen_missing_source_figure_candidates.py",
        "microgen_source_caption_vector_recovery.py",
    ):
        (tmp_path / name).write_bytes(b"frozen-original")
    old = dependency_fingerprint(tmp_path, "slides")
    (tmp_path / "microgen_source_caption_vector_recovery.py").write_bytes(
        b"new general source-figure recovery mechanism")
    assert dependency_fingerprint(tmp_path, "slides") != old


def test_receipt_input_change_invalidates_slide_stage_fingerprint(tmp_path):
    stage = source_fixture(tmp_path)
    for name in ("gen_slides_v20.py", "gen_slides_prompt_v20_hybrid.txt",
                 "microgen_slide_reflow.py",
                 "microgen_layout_retry_guard.py"):
        (stage / name).write_bytes(b"original-code")
    baseline = dependency_fingerprint(stage, "slides")
    recover_caption_anchored_vectors(stage)
    assert baseline != dependency_fingerprint(stage, "slides")



def test_genuine_source_receipt_survives_harmless_tex_reflow(tmp_path):
    stage = source_fixture(tmp_path)
    recover_caption_anchored_vectors(stage)
    before = validate_source_caption_vector_recovery(stage)
    tex = stage / "slides.tex"
    tex.write_text(tex.read_text(encoding="utf8").replace(
        r"height=0.4\textheight", r"height=0.4\textheight,width=\linewidth"),
        encoding="utf8")
    assert validate_source_caption_vector_recovery(stage) == before


def test_source_receipt_rejects_replaced_figure_reference(tmp_path):
    stage = source_fixture(tmp_path)
    recover_caption_anchored_vectors(stage)
    tex = stage / "slides.tex"
    tex.write_text(tex.read_text(encoding="utf8").replace(
        "Figure 2.7.png", "Figure 2.8.png"), encoding="utf8")
    with pytest.raises(CaptionVectorRecoveryError):
        validate_source_caption_vector_recovery(stage)


def test_validated_source_caption_receipt_tamper_does_not_escape_normal_path(tmp_path):
    stage = source_fixture(tmp_path)
    check_graphics_with_source_candidates(stage / "slides.tex")
    image = stage / "Figure 2.7.png"
    image.write_bytes(image.read_bytes() + b"corrupted")
    with pytest.raises(CaptionVectorRecoveryError):
        check_graphics_with_source_candidates(stage / "slides.tex")



def test_private_manifest_binds_caption_vector_provenance(tmp_path, monkeypatch):
    from microgen_quality import manifest_for
    stage = source_fixture(tmp_path)
    check_graphics_with_source_candidates(stage / "slides.tex")
    monkeypatch.setattr(
        "microgen_quality.check_slide_pdf",
        lambda *args, **kwargs: {"pages": 1, "sha256": "synthetic-pdf-hash"})
    monkeypatch.setattr("microgen_quality.figure_display_warnings",
                        lambda *args, **kwargs: [])
    monkeypatch.setattr("microgen_quality.check_narration",
                        lambda *args, **kwargs: {
                            "script_sha256": "narration",
                            "sidecar_sha256": "sidecar"})
    monkeypatch.setattr("microgen_quality.check_wavs",
                        lambda *args, **kwargs: {
                            "sha256": ["synthetic-wav"], "total_seconds": 4.0})
    monkeypatch.setattr("microgen_quality.check_video",
                        lambda *args, **kwargs: {
                            "sha256": "synthetic-video", "seconds": 4.0})
    result = manifest_for(stage)
    assert result["source_caption_vector_figures"] == ["Figure 2.7.png"]
    assert result["source_caption_vector_recovery_receipt_sha256"] == (
        validate_source_caption_vector_recovery(stage)["receipt_sha256"])


def test_published_manifest_rejects_tampered_source_graphics(tmp_path):
    from microgen_quality import published_manifest_valid, sha256

    stage = source_fixture(tmp_path)
    check_graphics_with_source_candidates(stage / "slides.tex")
    for name in ("slides.pdf", "script.txt", "script_tts.json",
                 "slide1.wav", "slides.mp4"):
        (stage / name).write_bytes(b"positive-synthetic-test-artifact")
    info = {
        "schema_version": 1,
        "slides_pdf_sha256": sha256(stage / "slides.pdf"),
        "slides_tex_sha256": sha256(stage / "slides.tex"),
        "source_sha256": sha256(stage / "source.pdf"),
        "script_sha256": sha256(stage / "script.txt"),
        "sidecar_sha256": sha256(stage / "script_tts.json"),
        "mp4_sha256": sha256(stage / "slides.mp4"),
        "wav_sha256": [sha256(stage / "slide1.wav")],
        "figure_sha256": {"Figure 2.7.png": sha256(stage / "Figure 2.7.png")},
        "source_caption_vector_recovery_receipt_sha256": sha256(
            stage / ".microgen_source_caption_vector_recovery.json"),
        "source_caption_vector_figures": ["Figure 2.7.png"],
    }
    (stage / ".microgen_verified_completion.json").write_text(
        json.dumps(info), encoding="utf8")
    assert published_manifest_valid(stage)
    # Changing the source graphic without updating receipt is prohibited.
    with (stage / "Figure 2.7.png").open("ab") as stream:
        stream.write(b"tampering")
    assert not published_manifest_valid(stage)
