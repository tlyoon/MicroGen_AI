"""Bounded source-exact vs single sensitive ASR mismatch recheck.

Two independently blind initial Gemini models are mandatory. When one is
SOURCE-EXACT and the other has exactly one sensitive edit, that is evidence
of possible recognizer instability, not proof of defective TTS. Recheck ONLY
the dissenting recognizer once on the exact same WAV. Accept the retake only
if the dissenting model newly aligns with both the original exact-model
transcript and the source, with no numerical/sign/exponent/variable red flag.
No weak or forged pass, no model-name switch, no TTS on uncertainty.
"""
from __future__ import annotations
from typing import Callable


MAX_RECHECK_SLIDES=2


def source_exact_vs_one_sensitive(expected:str,a:str,b:str)->int|None:
    """Return dissenting reviewer index, or None if any safety condition fails."""
    from microgen_tts_acoustic_qa import mismatch_details
    try:
        stats=[mismatch_details(expected,value) for value in (a,b)]
    except (RuntimeError,ValueError,TypeError):
        return None
    exact=[
        d["difference_fraction_upper_bound"]==0
        and d["sensitive_mismatches"]==0
        and d["circa_red_flags"]==0
        and d["letter_y_yay_red_flags"]==0
        for d in stats
    ]
    if exact not in ([True,False],[False,True]):
        return None
    wrong=1 if exact[0] else 0
    suspect=stats[wrong]
    if (suspect["sensitive_mismatches"]!=1 or
            suspect["difference_fraction_upper_bound"]>0.03 or
            suspect["circa_red_flags"] or suspect["letter_y_yay_red_flags"]):
        return None
    return wrong


def recheck_one_sided_sensitive(stage,report,texts,engines,memo,*,max_slides=MAX_RECHECK_SLIDES):
    """Perform finite independent recognition retakes before TTS.

    The cache is bound to actual WAV hashes by the existing production
    _transcripts function. This helper never accepts a contradiction,
    never reruns both original Gemini reviews and never changes source audio.
    """
    from pathlib import Path
    from microgen_autonomous_acoustic_gate import _transcripts, PASS
    from microgen_tts_acoustic_qa import mismatch_details
    from microgen_tts_provenance import digest_file

    stage=Path(stage)
    if (not isinstance(report,dict) or not isinstance(texts,list)
            or not isinstance(engines,tuple) or len(engines)!=2
            or not isinstance(memo,dict) or not 1<=max_slides<=2):
        raise ValueError("Unsafe source-exact ASR recheck scope")
    candidates=[]
    for row in report.get("slides",[]):
        n=row.get("slide")
        if (row.get("assessment")!=
                "REVIEW_REQUIRED_PRONUNCIATION_RISK"
                or row.get("source_pronunciation_risks")
                or type(n) is not int or n<1 or n>len(texts)
                or not isinstance(row.get("transcripts"),list)
                or len(row["transcripts"])!=2):
            continue
        index=source_exact_vs_one_sensitive(
            texts[n-1],*row["transcripts"])
        if index is not None:
            candidates.append((n,index))
    if len(candidates)>max_slides:
        return report
    attempted=[]
    resolved=[]
    for n,index in candidates:
        wav=stage/f"slide{n}.wav"
        try:
            voice=str(engines[index](wav)).strip()
            if len(voice)<5 or any(
                    marker in voice.casefold()
                    for marker in ("[unclear]","[inaudible]")):
                continue
            exact=mismatch_details(texts[n-1],voice)
            if (exact["sensitive_mismatches"] or
                    exact["circa_red_flags"] or
                    exact["letter_y_yay_red_flags"] or
                    exact["difference_fraction_upper_bound"]>0.02):
                continue
            first=report["slides"][n-1]["transcripts"][1-index]
            consistency=mismatch_details(first,voice)
            if (consistency["sensitive_mismatches"] or
                    consistency["difference_fraction_upper_bound"]>0.02):
                continue
            memo[(index,digest_file(wav))]=voice
            resolved.append(n)
        except (RuntimeError,ValueError,OSError,TypeError):
            # An uncertain paid provider attempt is NOT a verified pass.
            continue
        finally:
            attempted.append(n)
    if resolved:
        models=tuple(report["recognition_models"])
        report=_transcripts(stage,texts,engines,models,memo=memo)
    report["independent_one_sided_sensitive_rechecks"]={
        "attempted_slides":attempted,
        "resolved_slides":resolved,
        "max_recheck_slides":max_slides,
        "publication_allowed":False,
    }
    return report
