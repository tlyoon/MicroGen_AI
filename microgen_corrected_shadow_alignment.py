"""Regenerate source-bound audio/PDF word clocks for isolated corrective trials.

Only slides with identical original WAV hashes may reuse old recognition.
Changed slides MUST use independently captured recognizer output for the
exact correction WAV, with its original report hash. Recognition is
neither phonetic ground truth nor math/figure semantic approval.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import math

import pymupdf as fitz

from microgen_source_safe_orchestrator import (
    OrchestratorError, verify_workspace, digest, read_json, atomic_json
)
from microgen_offline_vosk_capture import validate_vosk_words
from microgen_offline_pronunciation_contrast import _validated_transcripts
from microgen_offline_asr_pdf_highlight import _word, _BLOCKED
from microgen_audio_cue_binding import _duration


class CorrectedAlignmentError(OrchestratorError):
    pass


def conservative_unique_word_cues(page, spoken, *, threshold=.9):
    """Use actual ASR clocks and uniquely extracted source-PDF coordinates."""
    if type(threshold) not in (int,float) or not math.isfinite(threshold) or not .75<=threshold<=1:
        raise CorrectedAlignmentError("Cue confidence must be bounded")
    pdf_words = page.get_text("words")
    geometry = {}
    for w in pdf_words:
        term = _word(w[4])
        if term:
            geometry.setdefault(term, []).append(list(map(float,w[:4])))
    counts = Counter(_word(r["word"]) for r in spoken)
    suggestions = []
    for row in spoken:
        term = _word(row["word"])
        if (not term or term in _BLOCKED or len(geometry.get(term,[]))!=1
            or counts[term]!=1 or row["conf"]<threshold):
            continue
        start,end=row["start"],row["end"]
        if end-start<.09 or not 0<=start<end:
            continue
        box = geometry[term][0]
        if not all(math.isfinite(n) for n in box) or not page.rect.contains(fitz.Rect(box)):
            raise CorrectedAlignmentError("PDF word coordinates out of bounds")
        suggestions.append({
            "text":term,"box":box,
            "local_start":round(start,5),"local_end":round(end,5),
            "asr_confidence":row["conf"],
            "acoustic_word_identity_independently_verified":False,
            "math_figure_semantic_match_verified":False
        })
    suggestions.sort(key=lambda r:r["local_start"])
    if len(suggestions)>64:
        raise CorrectedAlignmentError("Unbounded corrected-slide highlight proposals")
    return suggestions


def _check_recognized_track(asr_row, wav, duration):
    if asr_row.get("source_wav_sha256")!=digest(wav):
        raise CorrectedAlignmentError("Recognizer result belongs to a different WAV")
    words=validate_vosk_words(asr_row.get("words"),limit_seconds=duration+.03)
    if any(w["end"]>duration+.03 for w in words):
        raise CorrectedAlignmentError("Recognizer emitted word after actual WAV")
    return words


def build_corrected_shadow_cue_manifest(
    recovery_stage, review_bundle, selection_folder, shadow_folder,
    legacy_asr_json, corrected_asr_json, destination
):
    old=Path(recovery_stage).resolve(strict=True)
    receipt=verify_workspace(old)
    source=Path(receipt["source_root"]).resolve(strict=True)
    review=Path(review_bundle).resolve(strict=True)
    selected=Path(selection_folder).resolve(strict=True)
    shadow=Path(shadow_folder).resolve(strict=True)
    output=Path(destination).resolve(strict=False)
    if (output.exists() or output.is_symlink()
        or any(output==path or output.is_relative_to(path) for path in
               (old,source,review,selected,shadow))):
        raise CorrectedAlignmentError("Refuse protected source or existing output")
    shadow_receipt=read_json(shadow/"shadow_receipt.json")
    selection_receipt=read_json(selected/"selection_receipt.json")
    source_media=read_json(old/"legacy_mp4_audio_receipt.json")
    prior=read_json(legacy_asr_json)
    contrast_doc=read_json(corrected_asr_json)
    review_manifest, corrected=_validated_transcripts(review,contrast_doc)
    if (shadow_receipt.get("status")!="COMPLETE_UNAPPROVED_CORRECTION_SHADOW_PCM"
        or shadow_receipt.get("publication_allowed") is not False
        or shadow_receipt.get("voice_consistency_verified") is not False
        or shadow_receipt.get("all_preexisting_ASR_cue_timing_invalidated") is not True
        or selection_receipt.get("status")!="SHADOW_ONLY_TRIAL_SELECTION"
        or selection_receipt.get("publication_allowed") is not False
        or selection_receipt.get("source_pdf_sha256")!=receipt["source_pdf_sha256"]
        or selection_receipt.get("source_narration_sha256")!=receipt["narration_sha256"]
        or prior.get("status")!="SOURCE_BOUND_OFFLINE_17_SLIDE_ASR"
        or prior.get("publication_allowed") is not False
        or prior.get("source_pdf_sha256")!=receipt["source_pdf_sha256"]
        or prior.get("narration_sha256")!=receipt["narration_sha256"]
        or prior.get("source_mp4_sha256")!=digest(source/"slides.mp4")
        or review_manifest.get("source_slide_pdf_sha256")!=receipt["source_pdf_sha256"]
        or review_manifest.get("narration_sha256")!=receipt["narration_sha256"]
        or review_manifest.get("source_mp4_sha256")!=prior["source_mp4_sha256"]):
        raise CorrectedAlignmentError("Corrected and historical source lineage differs")
    clips=shadow_receipt.get("audio_segments")
    old_results=prior.get("results")
    corrections=selection_receipt.get("trials")
    if (not isinstance(clips,list) or len(clips)!=17
        or not isinstance(old_results,list) or len(old_results)!=17
        or not isinstance(corrections,list) or len(corrections)!=3
        or {x.get("slide") for x in corrections}!={5,6,10}):
        raise CorrectedAlignmentError("Incomplete corrected shadow and old ASR inputs")
    trials={x["slide"]:x for x in corrections}
    shadow_audio=Path(shadow_receipt["shadow_wav"]).resolve(strict=True)
    if shadow_audio.is_symlink() or digest(shadow_audio)!=shadow_receipt["shadow_sha256"]:
        raise CorrectedAlignmentError("Entire corrected shadow PCM changed")
    slides=[];cues=[];elapsed=0.
    with fitz.open(source/"slides.pdf") as pdf:
        if pdf.page_count!=17:
            raise CorrectedAlignmentError("Original slide deck changed")
        for index in range(1,18):
            clip=clips[index-1]
            baseline=old_results[index-1]
            if clip.get("slide")!=index or baseline.get("slide")!=index:
                raise CorrectedAlignmentError("Slide provenance order invalid")
            if index in trials:
                trial=trials[index]
                wav=Path(trial["trial_path"]).resolve(strict=True)
                if (wav.is_symlink() or not wav.is_file()
                    or digest(wav)!=trial["wav_sha256"]
                    or clip["source"]!="UNAPPROVED_TRIAL"
                    or clip["new_word_timing_required"] is not True
                    or clip["original_sha256"]!=trial["wav_sha256"]):
                    raise CorrectedAlignmentError("Shadow correction WAL/selection mismatch")
                # Matching corrected ASR must be freshly bound to the
                # exact current trial WAV; original timestamps are excluded.
                # Selected trial is deliberately renamed for safe shadow QA;
                # bind by immutable bytes, never by trial filename or a guess.
                candidates=[obs for obs in corrected.values()
                            if obs.get("source_wav_sha256")==digest(wav)]
                if len(candidates)!=1:
                    raise CorrectedAlignmentError("No unique SHA-bound corrected-clip ASR")
                recognized=candidates[0]
                reason="ASR_CAPTURED_FOR_CHANGED_WAV"
            else:
                wav=old/"audio"/f"slide{index}.wav"
                expected=source_media["clips"][index-1]["sha256"]
                if (wav.is_symlink() or not wav.is_file()
                    or digest(wav)!=expected
                    or clip["source"]!="LEGACY_ORIGINAL_AAC_DECODE"
                    or clip["new_word_timing_required"] is not False
                    or clip["original_sha256"]!=expected
                    or baseline.get("source_wav_sha256")!=expected):
                    raise CorrectedAlignmentError("Old ASR reused on a changed WAV")
                recognized=baseline
                reason="ASR_REUSED_ONLY_IDENTICAL_WAV_SHA"
            duration=_duration(wav)
            if (abs(duration-clip["duration_seconds"])>.04
                or abs(elapsed-clip["start_seconds"])>.04):
                raise CorrectedAlignmentError("Corrected shadow scene clock drift")
            spoken=_check_recognized_track(recognized,wav,duration)
            visible=conservative_unique_word_cues(pdf[index-1],spoken)
            for cue in visible:
                cues.append({"slide":index,"text":cue["text"],
                             "box":cue["box"],
                             "local_start":cue["local_start"],
                             "local_end":cue["local_end"],
                             "start_seconds":round(elapsed+cue["local_start"],5),
                             "end_seconds":round(elapsed+cue["local_end"],5),
                             "acoustic_word_identity_independently_verified":False})
            slides.append({
                "slide":index,"wav_sha256":digest(wav),
                "wav_path":str(wav),"duration_seconds":round(duration,6),
                "start_seconds":round(elapsed,6),
                "speech_timestamp_origin":reason,
                "recognized_words":len(spoken),"unique_pdf_cues":len(visible),
                "phonetic_approval":False
            })
            elapsed+=duration
    if (digest(source/"slides.pdf")!=receipt["source_pdf_sha256"]
        or digest(shadow_audio)!=shadow_receipt["shadow_sha256"]):
        raise CorrectedAlignmentError("A source changed during cue reconstruction")
    if abs(elapsed+shadow_receipt["tail_seconds"]-shadow_receipt["audio_seconds"])>.05:
        raise CorrectedAlignmentError("Final corrected shadow duration differs")
    doc={
        "schema_version":1,
        "status":"CORRECTED_SHADOW_SOURCE_BOUND_UNAPPROVED_WORD_CUES",
        "source_pdf_sha256":receipt["source_pdf_sha256"],
        "source_narration_sha256":receipt["narration_sha256"],
        "original_source_mp4_sha256":prior["source_mp4_sha256"],
        "original_asr_sha256":digest(legacy_asr_json),
        "corrected_asr_sha256":digest(corrected_asr_json),
        "selection_sha256":digest(selected/"selection_receipt.json"),
        "shadow_audio_sha256":shadow_receipt["shadow_sha256"],
        "shadow_scene_audio_seconds":round(elapsed,6),
        "shadow_full_audio_seconds":shadow_receipt["audio_seconds"],
        "slides":slides,"cues":cues,"slide_count":17,
        "corrected_slides":[5,6,10],
        "cue_count":len(cues),
        "old_original_scene_timestamps_reused_on_corrected_slides":False,
        "independent_word_ground_truth_verified":False,
        "single_speaker_verified":False,
        "math_equation_figure_semantics_verified":False,
        "publication_allowed":False
    }
    atomic_json(output,doc)
    return {"status":doc["status"],"slide_count":17,
            "cue_count":len(cues),"corrected_slides":3,
            "corrected_acoustic_timestamps_fresh":True,
            "publication_allowed":False,"report":str(output)}
