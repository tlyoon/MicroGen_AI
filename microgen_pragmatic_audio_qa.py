"""Pragmatic TTS workflow gate: permit progress with harmless uncertainty.

Missing/weak ASR and source notation flags are advisories, NOT automatic
synthesis retry requests. Broken WAV/provenance and explicitly flagged
serious lexical confusions remain blockers. Never assert phonetic proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from microgen_tts_provenance import verify_manifest
from microgen_tts_wave_integrity import analyze_pcm
from microgen_tts_risk_register import find_pronunciation_risks
from microgen_pronunciation import find_issues
from microgen_tts_lexicon import verify_spoken_rules
from text_to_speech_v25 import normalize_scientific_speech


class PragmaticAudioQAError(ValueError):
    pass


def _sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1048576),b""):
            h.update(block)
    return h.hexdigest()


def assess_pragmatic_audio_qa(folder, asr_dir=None):
    """Read-only check; only verified hard faults stop further *generation*.

    An absent optional transcript does not stop generation, but final academic
    and listening acceptance is NEVER automatically cleared.
    """
    root=Path(folder).resolve(strict=True)
    script=root/"script_tts.json"
    if script.is_symlink() or not script.is_file():
        raise PragmaticAudioQAError("Missing trusted narration")
    slides=json.loads(script.read_text(encoding="utf8")).get("slides")
    if not isinstance(slides,list) or not slides or [x.get("slide") for x in slides]!=list(range(1,len(slides)+1)):
        raise PragmaticAudioQAError("Incomplete or unordered slide narration")
    raw=[s.get("tts_text") for s in slides]
    if any(not isinstance(t,str) or not t.strip() for t in raw):
        raise PragmaticAudioQAError("Missing TTS input")
    spoken=[normalize_scientific_speech(t) for t in raw]
    # Source and normalized input must match TTS-side hashes, voice and WAVs.
    from microgen_tts_provenance import TTSProvenanceError
    try:
        verify_manifest(root,spoken)
    except (TTSProvenanceError,ValueError,KeyError,OSError) as exc:
        return {"schema_version":1,"stage":str(root),
                "can_continue_media_generation":False,
                "technical_audio_preflight_passed":False,
                "critical_audio_defects":["VOICE_OR_AUDIO_PROVENANCE_INVALID"],
                "advisories":[],"slides":[],"publication_allowed":False,
                "pronunciation_accepted":False}
    if asr_dir is not None:
        adir=Path(asr_dir).resolve(strict=True)
    else:
        adir=None
    report=[]
    critical=[]
    advisories=[]
    for number,(original,input_text) in enumerate(zip(raw,spoken),1):
        wav=root/f"slide{number}.wav"
        if not wav.is_file() or wav.is_symlink():
            critical.append({"slide":number,"code":"MISSING_OR_SYMLINK_WAV"})
            continue
        try:
            metrics=analyze_pcm(wav)
        except (OSError,ValueError,RuntimeError) as exc:
            critical.append({"slide":number,"code":"UNREADABLE_OR_INVALID_PCM"})
            continue
        for defect in metrics["blocking_defects"]:
            critical.append({"slide":number,"code":defect})
        for warning in metrics["warnings"]:
            advisories.append({"slide":number,"code":"PCM_"+warning})
        problems=find_issues(original,input_text)
        lexicon=verify_spoken_rules(original,input_text)
        for finding in problems:
            critical.append({"slide":number,"code":"UNSAFE_SPOKEN_TEXT_"+finding.code})
        for finding in lexicon:
            critical.append({"slide":number,"code":"REVIEWED_LEXICON_DRIFT_"+finding["rule"]})
        risks=find_pronunciation_risks(original,input_text)
        if risks:
            advisories.append({"slide":number,"code":"MATH_LETTER_REVIEW_ADVISORY",
                               "risk_count":len(risks)})
        transcript_status="NOT_REQUESTED"
        if adir is not None:
            observed=adir/f"slide{number:02d}.json"
            try:
                data=json.loads(observed.read_text(encoding="utf8"))
                if (data.get("slide")!=number or data.get("wav_sha256")!=_sha(wav) or
                    data.get("publication_allowed") is not False):
                    raise ValueError("ASR source identity mismatch")
                words=data["recognition"]["words"]
                if not isinstance(words,list):
                    raise ValueError("ASR word inventory missing")
                heard=" ".join(w["word"] for w in words if isinstance(w.get("word"),str)).lower()
                transcript_status="CHECKED_NON_AUTHORITATIVE"
                # High-priority *suspected* specific misread, not phonetic proof.
                # Keep these out of silent auto-pass and avoid re-generating on mere
                # edit-distance or innocuous spelling differences.
                if (any(x.code=="math_c_sentence" for x in risks) and
                    re.search(r"\b(?:circa|sarca|sirka)\b",heard)):
                    critical.append({"slide":number,"code":"SUSPECTED_MATH_C_SPOKEN_AS_CIRCA"})
                if (re.search(r"\byay\b",heard) and
                    any(re.search(r"\by\b|y[-\u2010-\u2015]",x.source,re.I) for x in risks)):
                    critical.append({"slide":number,"code":"SUSPECTED_MATH_Y_SPOKEN_AS_YAY"})
            except (OSError,KeyError,TypeError,ValueError):
                transcript_status="UNAVAILABLE_NOT_A_WAV_FAILURE"
                advisories.append({"slide":number,"code":"OPTIONAL_ASR_UNAVAILABLE"})
        report.append({"slide":number,"wav_sha256":_sha(wav),
                       "risk_count":len(risks),
                       "transcript_status":transcript_status,
                       "pcm_warnings":metrics["warnings"],
                       "pcm_blocking_defects":metrics["blocking_defects"]})
    safe=not critical
    return {"schema_version":1,"stage":str(root),
            "slide_count":len(slides),"slides":report,
            "can_continue_media_generation":safe,
            "technical_audio_preflight_passed":safe,
            "workflow_state":("CONTINUE_WITH_ADVISORIES" if safe and advisories else
                               "CONTINUE_TECHNICALLY" if safe else "REPAIR_CRITICAL_AUDIO_DEFECT"),
            "critical_audio_defects":critical,"advisories":advisories,
            "source_risk_flags":sum(row["risk_count"] for row in report),
            "optional_asr_used":adir is not None,
            "phonetic_accuracy_verified":False,"pronunciation_accepted":False,
            "academic_accuracy_verified":False,"publication_allowed":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("stage")
    p.add_argument("--asr-dir")
    p.add_argument("--new-report",type=Path)
    args=p.parse_args()
    result=assess_pragmatic_audio_qa(args.stage,args.asr_dir)
    output=json.dumps(result,indent=2)
    if args.new_report:
        if args.new_report.exists() or args.new_report.is_symlink():
            p.error("Refusing to overwrite report")
        args.new_report.write_text(output+"\n",encoding="utf8")
    print(json.dumps({k:result[k] for k in ("workflow_state","slide_count",
        "source_risk_flags","can_continue_media_generation","publication_allowed")}))
    return 0 if result["can_continue_media_generation"] else 2


if __name__=="__main__":
    raise SystemExit(main())


def decide_media_progression(*, preflight: bool, lexicon: bool,
                             provenance: bool, pcm: bool,
                             acoustic_report=None) -> dict:
    """Practical stage gate, independent of final acceptance or publication.

    A missing/nonfatal acoustic screen is an advisory. Explicit red flags in
    supplied recognition evidence cannot be ignored or downgraded.
    """
    values=(preflight,lexicon,provenance,pcm)
    if any(type(v) is not bool for v in values):
        raise PragmaticAudioQAError("Nonboolean technical evidence")
    names=("unsafe_spoken_input","reviewed_math_lexicon_drift",
           "untrusted_voice_or_wav","unusable_pcm")
    critical=[name for ok,name in zip(values,names) if not ok]
    advisories=[]
    if acoustic_report is None:
        advisories.append("OPTIONAL_ASR_EVIDENCE_NOT_PRESENT")
    elif not isinstance(acoustic_report,dict):
        critical.append("MALFORMED_ACOUSTIC_RECEIPT")
    else:
        rows=acoustic_report.get("slides")
        if not isinstance(rows,list):
            critical.append("MALFORMED_ACOUSTIC_ROWS")
        else:
            for n,row in enumerate(rows,1):
                if not isinstance(row,dict):
                    critical.append(f"INVALID_ACOUSTIC_ROW_{n}")
                    continue
                for finding in row.get("comparisons",[]) or []:
                    if isinstance(finding,dict) and (
                        finding.get("circa_red_flags",0)>0 or
                        finding.get("letter_y_yay_red_flags",0)>0):
                        critical.append(f"EXPLICIT_MATH_PHONETIC_RED_FLAG_{n}")
                if row.get("assessment") in (
                    "REVIEW_REQUIRED_PRONUNCIATION_RISK",
                    "REVIEW_REQUIRED_TRANSCRIBERS_DISAGREE",
                    "REVIEW_REQUIRED_UNCLEAR_SPEECH"):
                    critical.append(f"SUBSTANTIVE_ACOUSTIC_EXCEPTION_{n}")
                elif row.get("assessment") != "ASR_SCREEN_PASS_LISTENING_REQUIRED":
                    advisories.append(f"ACOUSTIC_REVIEW_PENDING_{n}")
    ok=not critical
    return {"can_continue_media_generation":ok,
            "workflow_state":("CONTINUE_WITH_ADVISORIES" if ok and advisories else
                              "CONTINUE_TECHNICALLY" if ok else
                              "REPAIR_CRITICAL_AUDIO_DEFECT"),
            "critical_audio_defects":critical,
            "nonblocking_audio_advisories":advisories,
            "independent_phonetic_acceptance":False,
            "publication_allowed":False}
