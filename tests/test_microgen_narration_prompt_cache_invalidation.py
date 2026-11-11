"""Prevent old narration caches hiding changes in the active Gemini request.

Runs both the normal gen_script_v13 entrypoint and the shared batch helper.
Fixtures are source-free and do not contact a model or publish media.
"""
import json

import fitz
import pytest

from microgen_narration_batch import NarrationBatchError, generate_batched


def test_batch_cache_reused_only_for_exact_request_fingerprint(tmp_path):
    slides = [{"id": "slide_01", "title": "Source illustration"}]
    source = [{"id": "source1", "text": "Acceleration changes velocity"}]
    calls = []

    def fake_model(batch, _source):
        calls.append(len(calls) + 1)
        return {x["id"]: {"narration": f"Grounded narration revision {len(calls)}.",
                           "tts_text": f"Grounded narration revision {len(calls)}."}
                for x in batch}

    cache = tmp_path / "cache"
    a = generate_batched(slides, source, fake_model, cache_dir=cache,
                         model="stub", prompt_hash="template-unchanged",
                         prompt_fingerprint=lambda _: "full-request-A")
    b = generate_batched(slides, source, fake_model, cache_dir=cache,
                         model="stub", prompt_hash="template-unchanged",
                         prompt_fingerprint=lambda _: "full-request-A")
    c = generate_batched(slides, source, fake_model, cache_dir=cache,
                         model="stub", prompt_hash="template-unchanged",
                         prompt_fingerprint=lambda _: "full-request-B")
    d = generate_batched(slides, source, fake_model, cache_dir=cache,
                         model="stub", prompt_hash="template-unchanged",
                         prompt_fingerprint=lambda _: "full-request-B")
    assert len(calls) == 2
    assert a == b
    assert c == d
    assert a != c


def test_refuse_unverifiable_prompt_fingerprint_before_generator(tmp_path):
    calls = []

    with pytest.raises(NarrationBatchError, match="Empty narration request fingerprint"):
        generate_batched(
            [{"id": "slide_01"}], [{"text": "known original"}],
            lambda *_: calls.append(1), model="stub", cache_dir=tmp_path,
            prompt_fingerprint=lambda _: "",
        )
    assert not calls


def _make_one_page(path, sentence):
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), sentence, fontsize=12)
    pdf.save(path)
    pdf.close()


def test_normal_generator_reuses_same_prompt_but_regenerates_after_inline_change(
    tmp_path, monkeypatch,
):
    import gen_script_v13 as narrator

    monkeypatch.chdir(tmp_path)
    _make_one_page(tmp_path / "source.pdf",
                   "Acceleration is the time derivative of velocity.")
    _make_one_page(tmp_path / "slides.pdf",
                   "2.5 Acceleration: The velocity changes with time.")
    # Title slide narration is deliberately forced to match the PDF title;
    # assert cache behavior on a second, substantive generated slide.
    with fitz.open(str(tmp_path / "slides.pdf")) as deck:
        second = deck.new_page()
        second.insert_text((72, 72),
                           "Acceleration is the derivative of velocity.")
        deck.save(tmp_path / "slides_new.pdf")
    (tmp_path / "slides_new.pdf").replace(tmp_path / "slides.pdf")
    (tmp_path / "gen_script_prompt_v8_hybrid.md").write_text(
        "Unchanged externally stored template.", encoding="utf8")

    monkeypatch.setattr(narrator, "_load_runtime_environment", lambda: None)
    request_version = ["INITIAL_INLINE_SOURCE_GROUNDING"]
    monkeypatch.setattr(
        narrator, "_read_prompt", lambda name: request_version[0])
    calls = []

    def fake_generation(batch, source):
        calls.append((len(batch), len(source)))
        text = f"Acceleration describes velocity changes, revision {len(calls)}."
        return {slide["id"]: {"narration": text, "tts_text": text}
                for slide in batch}

    monkeypatch.setattr(narrator, "_generate_polished", fake_generation)

    narrator.main()
    first = json.loads((tmp_path / "script_tts.json").read_text(
        encoding="utf8"))
    first_cache = json.loads(
        (tmp_path / ".microgen_narration_batches" / "batch_0000.json")
        .read_text(encoding="utf8"))
    assert len(calls) == 1

    narrator.main()
    repeated_cache = json.loads(
        (tmp_path / ".microgen_narration_batches" / "batch_0000.json")
        .read_text(encoding="utf8"))
    assert len(calls) == 1
    assert repeated_cache["key"] == first_cache["key"]

    # The external prompt file and the original source are UNCHANGED.
    # A changed in-code instruction must nevertheless trigger a new model
    # batch in the active main(), not reuse the old cached words.
    request_version[0] = "UPDATED_INLINE_SOURCE_GROUNDING"
    narrator.main()
    third_cache = json.loads(
        (tmp_path / ".microgen_narration_batches" / "batch_0000.json")
        .read_text(encoding="utf8"))
    assert len(calls) == 2
    assert third_cache["key"] != first_cache["key"]
    third = json.loads((tmp_path / "script_tts.json").read_text(
        encoding="utf8"))
    assert first["slides"][1]["tts_text"] != third["slides"][1]["tts_text"]

    # Thinking-level changes also change an otherwise identical request.
    monkeypatch.setattr(narrator, "THINKING_LEVEL", "LOW")
    narrator.main()
    assert len(calls) == 3


def test_direct_request_digest_uses_the_real_source_and_visible_prompt(monkeypatch):
    import gen_script_v13 as narrator
    slides = [{"id": "slide_01", "title": "Acceleration",
               "onscreen": ["Acceleration is change in velocity"]}]
    source = [{"id": "p1", "page": 1,
               "text": "Acceleration is the derivative of velocity."}]
    monkeypatch.setattr(narrator, "_read_prompt",
                        lambda name: "Instruction one")
    a = narrator._narration_request_fingerprint(slides, source)
    monkeypatch.setattr(narrator, "_read_prompt",
                        lambda name: "Instruction two")
    b = narrator._narration_request_fingerprint(slides, source)
    assert a != b
    monkeypatch.setattr(narrator, "_read_prompt",
                        lambda name: "Instruction one")
    assert narrator._narration_request_fingerprint(slides, source) == a


def test_narration_checkpoint_fingerprint_tracks_shared_cache_helper(tmp_path):
    from microgen_quality import dependency_fingerprint
    required = (
        "source.pdf", "slides.pdf", "gen_script_v13.py",
        "gen_script_prompt_v8_hybrid.md", "microgen_narration_batch.py",
    )
    for name in required:
        (tmp_path / name).write_bytes(b"original-source-free-fixture")
    before = dependency_fingerprint(tmp_path, "narration")
    (tmp_path / "microgen_narration_batch.py").write_bytes(
        b"new source-bound cache identity")
    assert dependency_fingerprint(tmp_path, "narration") != before
