"""Corrective narration timestamps must originate from exact replacement bytes."""
import json
import struct
import wave

import pymupdf as fitz
import pytest

from microgen_source_safe_orchestrator import digest
from microgen_corrected_shadow_alignment import (
    CorrectedAlignmentError, _check_recognized_track,
    conservative_unique_word_cues, build_corrected_shadow_cue_manifest,
)


def _word(word, start=.2, conf=.95):
    return {"word":word,"start":start,"end":start+.22,"conf":conf}


def test_only_unique_source_pdf_words_may_receive_corrected_asr_times():
    with fitz.open() as doc:
        page=doc.new_page(width=640,height=360)
        page.insert_text((35,65),"intermediate unique repeated repeated",fontsize=18)
        observed=[_word("intermediate",.2),_word("unique",.9),
                  _word("repeated",1.5),_word("repeated",2.0),
                  _word("unseen",2.4),_word("extraneous",2.8,.2)]
        cues=conservative_unique_word_cues(page,observed)
    assert [c["text"] for c in cues]==["intermediate","unique"]
    assert [c["local_start"] for c in cues]==[.2,.9]
    assert not any(c["math_figure_semantic_match_verified"] for c in cues)


def test_mutated_wav_cannot_reuse_old_model_timestamps(tmp_path):
    wav=tmp_path/"slide6.wav"
    with wave.open(str(wav),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(struct.pack("<h",100)*16000)
    report={"source_wav_sha256":digest(wav),"words":[_word("discontinuous",.1)]}
    assert len(_check_recognized_track(report,wav,1.0))==1
    with wave.open(str(wav),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(struct.pack("<h",140)*16000)
    with pytest.raises(CorrectedAlignmentError,match="different WAV"):
        _check_recognized_track(report,wav,1.0)


def test_audio_word_after_end_is_rejected(tmp_path):
    wav=tmp_path/"slide.wav"
    with wave.open(str(wav),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000)
        f.writeframes(struct.pack("<h",0)*16000)
    report={"source_wav_sha256":digest(wav),"words":[_word("limit",1.4)]}
    with pytest.raises((CorrectedAlignmentError,ValueError)):
        _check_recognized_track(report,wav,1.0)


def test_missing_full_source_evidence_fails_before_any_output(tmp_path):
    output=tmp_path/"new.json"
    with pytest.raises((FileNotFoundError,CorrectedAlignmentError)):
        build_corrected_shadow_cue_manifest(
            tmp_path/"recovery",tmp_path/"review",tmp_path/"selected",
            tmp_path/"shadow",tmp_path/"legacy_asr.json",
            tmp_path/"correction_asr.json",output)
    assert not output.exists()
