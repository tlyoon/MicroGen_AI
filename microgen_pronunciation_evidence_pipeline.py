"""Post-TTS pronunciation evidence bridge, independent of any billed provider.

A completed technical TTS step can automatically save an offline, per-WAV
SHA-anchored pronunciation plan. A later offline Vosk capture can enrich it
with *unverified* term candidates; never auto-approve phonemes/publication.
No ASR installation/network on this path. The immutable receipt is versioned
by its exact source+WAV+recognition inputs, safe for resumable campaigns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Callable

from microgen_pronunciation_closed_loop import (
    PronunciationClosedLoopError, plan_slide_repairs, sha_file,
)

class PronunciationEvidenceError(PronunciationClosedLoopError):
    pass


def _hash_json(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_post_tts_evidence(
    folder: Path, slides: list[dict], normalize: Callable[[str], str], *,
    observations: list[dict | None] | None = None,
    provenance_required: bool = True,
) -> dict:
    root = Path(folder).resolve(strict=True)
    if not root.is_dir():
        raise PronunciationEvidenceError("Existing lesson stage required")
    if not slides or len(slides) > 500:
        raise PronunciationEvidenceError("Invalid slide count")
    n = len(slides)
    if [x.get("slide") for x in slides] != list(range(1,n+1)):
        raise PronunciationEvidenceError("Source slide order must be contiguous")
    wavs = [root / f"slide{i}.wav" for i in range(1,n+1)]
    for wav in wavs:
        if wav.is_symlink() or not wav.is_file() or wav.stat().st_size < 100:
            raise PronunciationEvidenceError("Missing/invalid real slide WAV: " + wav.name)
    hashes = [sha_file(x) for x in wavs]
    provenance = root / ".microgen_tts_provenance.json"
    if provenance_required and (
        not provenance.is_file() or provenance.is_symlink()
    ):
        raise PronunciationEvidenceError("TTS provider provenance manifest required")
    manifest_hash = sha_file(provenance) if provenance.is_file() else None
    source = root / "script_tts.json"
    if source.is_file() and not source.is_symlink():
        actual = json.loads(source.read_text(encoding="utf-8"))
        actual_slides=actual.get("slides", [])
        if len(actual_slides)!=n:
            raise PronunciationEvidenceError("Source narration sidecar does not match slide count")
        for a,b in zip(actual_slides,slides):
            if str(a.get("tts_text") or a.get("narration") or "") != str(
                    b.get("tts_text") or b.get("narration") or ""):
                raise PronunciationEvidenceError("Source narration identity mismatch")
    source_hash = sha_file(source) if source.is_file() else None
    if observations is not None and len(observations)!=n:
        raise PronunciationEvidenceError("Partial offline recognizer evidence")
    plan=plan_slide_repairs(
        slides, normalize,
        observations=observations, wav_hashes=hashes if observations is not None else None
    )
    words=defaultdict(lambda: {"slides":set(),"examples":[]})
    for row in plan["slides"]:
        for mismatch in row["screening"]["word_mismatches"]:
            left=mismatch["expected"]
            right=mismatch["recognized"]
            if not left or not right or left==right:
                continue
            # Candidates are word-pair hypotheses, *never* a confirmed error.
            key=(" ".join(left)[:90]," ".join(right)[:90])
            value=words[key]
            value["slides"].add(row["slide"])
            if len(value["examples"])<3:
                value["examples"].append({
                    "slide":row["slide"],
                    "wav_sha256":hashes[row["slide"]-1],
                    "expected":key[0],"recognized":key[1]
                })
    candidates=[]
    # ASR lexical spellings are *not* evidence of wrong audio. These are
    # common context/orthography variants, not a definitive phonetic mapping.
    low_variant_pairs = {
        ("sine","sign"),("sign","sine"),("see","sea"),
        ("c","see"),("see","c"),("b","be"),("be","b"),
        ("ex","x"),("ex","acts"),("ex","eggs"),
        ("why","y"),("two","too"),("two","to"),("too","two"),
        ("four","for"),("eight","ate"),("root","route"),
        ("sum","some"),("one","won"),("nonzero","non zero"),
    }
    for (expected,recognized),value in words.items():
        if not expected or not recognized:
            priority="ALIGNMENT_INSERTION_OR_OMISSION_UNVERIFIED"
        elif (expected,recognized) in low_variant_pairs:
            priority="POSSIBLE_HOMOPHONE_OR_ASR_VARIANT"
        elif set(expected.split()) & {
            "derivative","derivatives","integral","integrals",
            "continuity","continuous","discontinuity","denominator",
            "numerator","fraction","exponent","subscript","sine",
            "cosine","tangent","logarithm","asymptote","infinite",
            "infinity","intercept","polynomial","gradient","slope",
            "theorem","root","limit","limits","coefficient","equation",
            "plus","minus","positive","negative","equals","equal",
        }:
            priority="POTENTIAL_TECHNICAL_TERM_DIFFERENCE_UNVERIFIED"
        elif len(value["slides"])>=2:
            priority="REPEATED_GENERAL_WORD_DIFFERENCE_ADVISORY"
        else:
            priority="ISOLATED_UNVERIFIED_WORD_DIFFERENCE"
        candidates.append({
            "expected":expected, "recognized":recognized,
            "slide_count":len(value["slides"]),
            "slides":sorted(value["slides"]),
            "examples":value["examples"],
            "priority":priority,
            "automatic_rule_authorized":False,
            "mispronunciation_confirmed":False,
        })
    order = {"POTENTIAL_TECHNICAL_TERM_DIFFERENCE_UNVERIFIED":0,
             "REPEATED_GENERAL_WORD_DIFFERENCE_ADVISORY":1,
             "ISOLATED_UNVERIFIED_WORD_DIFFERENCE":2,
             "POSSIBLE_HOMOPHONE_OR_ASR_VARIANT":3,
             "ALIGNMENT_INSERTION_OR_OMISSION_UNVERIFIED":4}
    candidates.sort(key=lambda x:(order[x["priority"]],
                                 -x["slide_count"],x["expected"],x["recognized"]))
    receipt={
        "schema_version":1,
        "status":"PRONUNCIATION_EVIDENCE_CAPTURED_NOT_ACOUSTIC_RELEASE_QA",
        "slide_count":n,
        "original_script_tts_sha256":source_hash,
        "tts_provenance_manifest_sha256":manifest_hash,
        "slide_wav_sha256":hashes,
        "asr_evidence_attached":observations is not None,
        "unverified_word_pair_candidates":candidates,
        "candidate_count":len(candidates),
        "review_priority_count":sum(
            x["priority"]=="POTENTIAL_TECHNICAL_TERM_DIFFERENCE_UNVERIFIED"
            for x in candidates),
        "potential_homophone_or_asr_variant_count":sum(x["priority"]=="POSSIBLE_HOMOPHONE_OR_ASR_VARIANT"
                                                      for x in candidates),
        "alignment_only_candidate_count":sum(x["priority"]=="ALIGNMENT_INSERTION_OR_OMISSION_UNVERIFIED"
                                             for x in candidates),
        "high_confidence_diagnostic_candidate_slides":plan["selective_diagnostic_slides"],
        "source_risk_count":sum(x["source_risks"] for x in plan["slides"]),
        "asr_mismatch_slide_count":sum(bool(x["screening"]["word_mismatches"])
                                      for x in plan["slides"]),
        "qa_plan":plan,
        "provider_calls":0,
        "automatically_repaired_production_wavs":False,
        "formal_tts_provider_changed":False,
        "phonetic_identity_verified":False,
        "academic_qa_approved":False,
        "publication_allowed":False,
    }
    if any(sha_file(x)!=h for x,h in zip(wavs,hashes)):
        raise PronunciationEvidenceError("Slide WAV changed during evidence capture")
    if manifest_hash and sha_file(provenance)!=manifest_hash:
        raise PronunciationEvidenceError("TTS provider evidence changed during capture")
    if source_hash and sha_file(source)!=source_hash:
        raise PronunciationEvidenceError("Narration sidecar changed during capture")
    return receipt


def save_stage_evidence(folder: Path, evidence: dict, *,
                        output_directory: Path | None = None) -> Path:
    root=Path(output_directory) if output_directory else Path(folder)/".microgen_tts_cache"
    if any(x.casefold()=="my drive" for x in root.parts):
        raise PronunciationEvidenceError("New QA evidence cannot write into original source Drive")
    if root.exists() and root.is_symlink():
        raise PronunciationEvidenceError("QA evidence directory symlink refused")
    identity=_hash_json(evidence)
    path=root/f"pronunciation_evidence_{identity[:20]}.json"
    if path.exists():
        try:
            old=json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PronunciationEvidenceError("Existing evidence corrupted") from exc
        if old!=evidence or path.is_symlink():
            raise PronunciationEvidenceError("Existing evidence identity mismatch")
        return path
    root.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as stream:
        json.dump(evidence,stream,ensure_ascii=False,indent=2)
    return path


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--offline-asr-dir",type=Path)
    p.add_argument("--new-external-directory",type=Path)
    options=p.parse_args(argv)
    stage=options.stage.resolve(strict=True)
    source=stage/"script_tts.json"
    if not source.is_file():
        raise PronunciationEvidenceError("Stage script_tts.json required for offline CLI")
    slides=json.loads(source.read_text(encoding="utf-8"))["slides"]
    observed=None
    if options.offline_asr_dir:
        observed=[]
        for i in range(1,len(slides)+1):
            wav=stage/f"slide{i}.wav"
            report=options.offline_asr_dir/f"slide{i:02d}.json"
            if report.is_symlink() or not report.is_file():
                raise PronunciationEvidenceError("Missing offline ASR slide receipt")
            item=json.loads(report.read_text(encoding="utf-8"))
            if item.get("slide")!=i or item.get("wav_sha256")!=sha_file(wav):
                raise PronunciationEvidenceError("Offline ASR audio identity mismatch")
            observed.append(item["recognition"])
    from text_to_speech_v25 import normalize_scientific_speech
    receipt=build_post_tts_evidence(stage,slides,normalize_scientific_speech,
        observations=observed)
    dest=save_stage_evidence(stage,receipt,output_directory=options.new_external_directory)
    print(json.dumps({"receipt":str(dest),"slide_count":receipt["slide_count"],
        "candidate_count":receipt["candidate_count"],
        "publication_allowed":False}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
