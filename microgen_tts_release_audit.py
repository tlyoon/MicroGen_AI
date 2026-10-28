"""Read-only automated TTS/video QA with optional human certification.

Mandatory technical evidence fails closed. Human approvals are advisory
by default under the 2026-10-20 autonomous-development contract. The
report never publishes, fabricates acoustic proof or certifies unchecked
academic, figure or element-level highlighting properties.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from microgen_quality import check_video
from microgen_tts_provenance import digest_file, wav_characteristics, verify_manifest
from microgen_tts_risk_register import build_risk_register
from microgen_tts_lexicon import check_lexicon_slides
from microgen_pronunciation import audit_slide_items
from microgen_tts_wave_integrity import analyze_pcm, WaveIntegrityError
from microgen_tts_release_policy import decide_release, AUTONOMOUS, MODES
from text_to_speech_v25 import normalize_scientific_speech as normalize

def file_hash(path:Path)->str:
    return digest_file(path)

def _approval(receipt:dict|None,video_hash:str,
              role:str="academic",trust:dict|None=None)->bool:
    from microgen_tts_review_trust import verify_review_receipt
    return (isinstance(receipt,dict) and
            receipt.get("video_sha256")==video_hash and
            bool(video_hash) and verify_review_receipt(receipt,role,trust))

def _listening(receipt:dict|None,hashes:list[str],trust:dict|None=None)->bool:
    from microgen_tts_review_trust import verify_review_receipt
    if not verify_review_receipt(receipt,"listening",trust):
        return False
    if not isinstance(receipt.get("slides"),list):
        return False
    approved=receipt["slides"]
    if len(approved)!=len(hashes):
        return False
    for number,(record,digest) in enumerate(zip(approved,hashes),1):
        if (record.get("slide")!=number or record.get("wav_sha256")!=digest or
            record.get("approved") is not True or
            not isinstance(record.get("reviewer"),str) or not record["reviewer"].strip()):
            return False
    return True

def _acoustic(receipt:dict|None,folder:Path, hashes:list[str],
              spoken:list[str]|None=None)->bool:
    from microgen_tts_evidence import verify_acoustic_evidence
    bound=folder/".microgen_tts_provenance.json"
    if spoken is None or not bound.is_file():
        return False
    valid,_=verify_acoustic_evidence(receipt,folder,spoken,hashes,file_hash(bound))
    return valid

def audit_stage(
    folder:Path, *,
    acoustic_report:dict|None=None, listening_receipt:dict|None=None,
    academic_receipt:dict|None=None, figure_receipt:dict|None=None,
    highlight_receipt:dict|None=None, reviewer_trust:dict|None=None,
    multipart_receipt:Path|None=None, independent_av_receipt:Path|None=None,
    qa_policy:str=AUTONOMOUS,
) -> dict:
    """No writes; returns fail-closed check matrix and isolated follow-up."""
    folder=Path(folder)
    source=json.loads((folder/"script_tts.json").read_text(encoding="utf8"))
    slides=source.get("slides",[])
    if not isinstance(slides,list) or not slides or [x.get("slide") for x in slides]!=list(range(1,len(slides)+1)):
        raise ValueError("Invalid/misordered source narration")
    raw=[str(x.get("tts_text") or x.get("narration") or "") for x in slides]
    spoken=[normalize(x) for x in raw]
    preflight=not audit_slide_items(slides,normalize)
    lexicon=not check_lexicon_slides(slides,normalize)
    audio_hash=[]
    seconds=[]
    for i in range(1,len(slides)+1):
        wav=folder/f"slide{i}.wav"
        audio_hash.append(file_hash(wav))
        seconds.append(wav_characteristics(wav)["duration_seconds"])
    manifest_ok=False
    try:
        verify_manifest(folder,spoken)
        manifest_ok=True
    except (OSError,ValueError,RuntimeError,KeyError):
        pass
    audio_ok=manifest_ok
    # Gross PCM defects remain automatic blockers even in no-manual-gate
    # mode. Provenance alone cannot establish that audible content exists.
    integrity_rows=[]
    for number in range(1,len(slides)+1):
        try:
            pcm=analyze_pcm(folder/f"slide{number}.wav")
            integrity_rows.append({"slide":number,
                                   "blocking_defects":pcm["blocking_defects"],
                                   "warnings":pcm["warnings"]})
        except (OSError,ValueError,RuntimeError,WaveIntegrityError):
            integrity_rows.append({"slide":number,
                                   "blocking_defects":["wav_integrity_unavailable"],
                                   "warnings":[]})
    pcm_ok=all(not x["blocking_defects"] for x in integrity_rows)
    audio_screen_ok=_acoustic(acoustic_report,folder,audio_hash,spoken)
    listening_ok=_listening(listening_receipt,audio_hash,reviewer_trust)
    video=folder/"slides.mp4"
    video_hash=file_hash(video) if video.is_file() else ""
    video_seconds=None
    video_ok=False
    if video.is_file():
        try:
            data=check_video(video,expected_seconds=sum(seconds))
            video_seconds=data["seconds"]
            video_ok=0<video_seconds<600
        except (OSError,ValueError,RuntimeError):
            video_ok=False
    multipart_evidence=None
    if multipart_receipt is not None or independent_av_receipt is not None:
        if multipart_receipt is None or independent_av_receipt is None:
            raise ValueError("Both independent multipart receipts required")
        if video.is_file():
            raise ValueError("Ambiguous single and multipart delivery evidence")
        from microgen_multipart_delivery_evidence import verify_multipart_delivery
        multipart_evidence=verify_multipart_delivery(
            folder,multipart_receipt,independent_av_receipt)
        video_ok=multipart_evidence["technical_multipart_av_pass"]
    academic_ok=_approval(academic_receipt,video_hash,"academic",reviewer_trust) if video_ok else False
    figures_ok=_approval(figure_receipt,video_hash,"figures",reviewer_trust) if video_ok else False
    highlights_ok=_approval(highlight_receipt,video_hash,"highlights",reviewer_trust) if video_ok else False
    risks=build_risk_register(slides,normalize,seconds,wav_sha256=audio_hash)
    checks={
        "pronunciation_text_preflight":preflight,
        "reviewed_lexicon":lexicon,
        "voice_bound_wav_provenance":audio_ok,
        "wav_pcm_integrity":pcm_ok,
        "independent_acoustic_screen":audio_screen_ok,
        "all_slide_listening_approved":listening_ok,
        "video_duration_and_av_integrity":video_ok,
        "academic_review_approved":academic_ok,
        "figures_review_approved":figures_ok,
        "element_level_highlights_approved":highlights_ok,
    }
    decision=decide_release(checks,qa_policy)
    # A pragmatic *progression* gate must not be confused with independent
    # acoustic acceptance or the final release gate above.
    from microgen_pragmatic_audio_qa import decide_media_progression
    progression=decide_media_progression(
        preflight=preflight, lexicon=lexicon, provenance=audio_ok,
        pcm=pcm_ok, acoustic_report=acoustic_report)
    return {
        "schema_version":1,
        "slide_count":len(slides),
        "video_sha256":video_hash or None,
        "video_duration_seconds":video_seconds,
        "multipart_delivery_evidence":multipart_evidence,
        "total_wav_seconds":round(sum(seconds),4),
        "wav_sha256":audio_hash,
        "source_risks":risks["risk_count"],
        "risk_review_slides":risks["risk_review_slides"],
        "checks":checks,
        "pcm_integrity":integrity_rows,
        "audio_generation_progression":progression,
        **decision,
        "note":("Read-only QA. Autonomous technical progression does NOT "
                "certify phonetic, scholarly or element-level visual quality. "
                "No Moodle promotion, original-file writes or forged approvals."),
    }

def main(argv=None)->int:
    parser=argparse.ArgumentParser(description="Strict read-only MicroGen lecture release audit")
    parser.add_argument("stage",type=Path)
    parser.add_argument("--qa-policy",choices=sorted(MODES),default=AUTONOMOUS,
                        help="Autonomous (default) has no manual approval gate; optional human-certified requires signatures")
    parser.add_argument("--acoustic",type=Path)
    parser.add_argument("--listening",type=Path)
    parser.add_argument("--academic",type=Path)
    parser.add_argument("--figures",type=Path)
    parser.add_argument("--highlights",type=Path)
    parser.add_argument("--new-report",type=Path)
    parser.add_argument("--review-trust-root",type=Path,
                        help="External role-key mapping file; NEVER under the lecture folder")
    args=parser.parse_args(argv)
    trusted=None
    if args.review_trust_root:
        root=args.review_trust_root.resolve()
        lesson=args.stage.resolve()
        if root==lesson or lesson in root.parents:
            parser.error("Reviewer trust keys must not be stored in lesson stage")
        values=json.loads(root.read_text(encoding="utf8"))
        from microgen_tts_review_trust import ROLES
        if not isinstance(values,dict) or set(values)-ROLES:
            parser.error("Unexpected reviewer trust-root roles")
        trusted={role:{key_id:bytes.fromhex(hex_value) for key_id,hex_value in keys.items()}
                 for role,keys in values.items()}
    def read(path):
        return json.loads(path.read_text(encoding="utf8")) if path else None
    audit=audit_stage(args.stage,acoustic_report=read(args.acoustic),
        listening_receipt=read(args.listening),
        academic_receipt=read(args.academic),
        figure_receipt=read(args.figures),
        highlight_receipt=read(args.highlights),reviewer_trust=trusted,
        qa_policy=args.qa_policy)
    out=json.dumps(audit,ensure_ascii=False,indent=2)
    if args.new_report:
        if args.new_report.exists() or args.new_report.is_symlink():
            parser.error("Refusing to overwrite a prior audit")
        with args.new_report.open("x",encoding="utf8") as f:
            f.write(out+"\n")
    else:
        print(out)
    return 0 if audit["ready_for_separate_promotion"] else 2
if __name__=="__main__":
    raise SystemExit(main())
