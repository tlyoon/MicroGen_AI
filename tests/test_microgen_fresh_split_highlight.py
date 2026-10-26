"""Fresh-source split renderer enforces every nonpublishing duration/evidence boundary."""
import wave
from pathlib import Path

import pymupdf
import pytest

from microgen_fresh_split_highlight import (
    PreviewError, _unique_slide_rects, safe_token, select_parts,
    source_evidence, wav_evidence
)


def test_real_audio_duration_plan_is_two_safe_parts():
    stage=Path(
        r"C:\Users\tlyoo\AppData\Local\MicroGen_AI_Checkpoints\20261026_HP_M1_SOURCE_ONLY\2.5")
    if not stage.is_dir():
        pytest.skip("real HP §2.5 pilot exists only on authorized HP")
    proof=source_evidence(stage)
    assert proof["slide_count"]==23
    durations=[v["seconds"] for v in proof["audio"]]
    plans=select_parts(durations)
    assert len(plans)==2
    assert plans[0][0]==1 and plans[-1][1]==23
    assert sum(p[2] for p in plans)==pytest.approx(sum(durations))
    assert all(p[2] < 600 for p in plans)


@pytest.mark.parametrize("durations", [
    [],[0],[-1,3],[599],[100, float("nan")],[650,5]])
def test_bad_duration_rejected(durations):
    with pytest.raises(PreviewError):
        select_parts(durations)


def test_no_slide_loss_or_duplication_under_budget():
    result=select_parts([58]*23,max_seconds=570)
    assert sum(len(range(a,b+1)) for a,b,_ in result)==23
    assert [i for a,b,_ in result for i in range(a,b+1)]==list(range(1,24))
    assert all(0 < dur < 570 for _,_,dur in result)


def test_unique_pdf_word_screen_is_not_semantic_approval():
    doc=pymupdf.open()
    p=doc.new_page()
    p.insert_text((42,120),"Derivative antiderivative antiderivative continuity")
    regions=_unique_slide_rects(p)
    assert "derivative" in regions
    assert "antiderivative" not in regions  # Ambiguous repeated text
    assert "continuity" in regions
    assert safe_token("continuity,")=="continuity"
    assert safe_token("x=1")==""
    doc.close()


def test_original_wave_cannot_be_accepted_with_wrong_format(tmp_path):
    f=tmp_path/"slide1.wav"
    with wave.open(str(f),"wb") as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(24000)
        wav.writeframes(b"\0"*24000)
    with pytest.raises(PreviewError):
        wav_evidence(f)


def test_source_evidence_rejects_mutated_or_missing_wavs(tmp_path):
    stage=tmp_path/"stage"
    stage.mkdir()
    doc=pymupdf.open();doc.new_page();doc.save(stage/"slides.pdf");doc.close()
    (stage/"source.pdf").write_bytes(b"source bytes")
    with pytest.raises(PreviewError):
        source_evidence(stage)


def test_part_boundary_preserves_exact_clock_under_600():
    durations=[2.6053333333333333,36.26533333333333]+[40.0]*21
    plan=select_parts(durations)
    assert all(0<part[2]<570 for part in plan)
    assert [i for a,b,_ in plan for i in range(a,b+1)]==list(range(1,24))
    assert sum(part[2] for part in plan)==pytest.approx(sum(durations))


def test_ambiguity_rejects_nonword_math_labels():
    for bad in ("x=1", "2.38", "f'(x)", "a/b", "x-2"):
        assert safe_token(bad)==""


def test_sha_binds_actual_original_bytes(tmp_path):
    from microgen_fresh_split_highlight import sha
    p=tmp_path/"source.pdf"
    p.write_bytes(b"protected")
    expected=sha(p)
    p.write_bytes(b"altered")
    assert sha(p)!=expected


def test_actual_video_pixel_score_prefers_highlighted_expected():
    from PIL import Image
    from microgen_fresh_split_pixel_qa import _mae
    a=Image.new("RGB",(40,40),"white")
    b=Image.new("RGB",(40,40),(255,192,50))
    assert _mae(b,b)==0
    assert _mae(b,a)>10
