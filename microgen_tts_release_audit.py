"""Read-only end-to-end TTS / video release-evidence audit.

No publication action. Releases require independent acoustic evidence,
hash-bound explicit human listening, academic, figure and element-level
highlight approvals. Existing QA video with only slide transitions fails.
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
from text_to_speech_v25 import normalize_scientific_speech as normalize

def file_hash(path:Path)->str:
    return digest_file(path)

def _approval(receipt:dict|None,video_hash:str)->bool:
    return (isinstance(receipt,dict) and receipt.get("approved") is True
            and receipt.get("video_sha256")==video_hash and
            isinstance(receipt.get("reviewer"),str) and bool(receipt["reviewer"].strip()))

def _listening(receipt:dict|None,hashes:list[str])->bool:
    if not isinstance(receipt,dict) or not isinstance(receipt.get("slides"),list):
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

def _acoustic(receipt:dict|None,folder:Path, hashes:list[str])->bool:
    if not isinstance(receipt,dict) or receipt.get("slide_count")!=len(hashes):
        return False
    bound=folder/".microgen_tts_provenance.json"
    if not bound.is_file() or receipt.get("voice_provenance_sha256")!=file_hash(bound):
        return False
    if receipt.get("unavailable_recognizer_passes"):
        return False
    rows=receipt.get("slides")
    if not isinstance(rows,list) or len(rows)!=len(hashes):
        return False
    return all(
        item.get("slide")==i and item.get("audio_sha256")==digest and
        item.get("assessment") in (
            "ASR_SCREEN_PASS_LISTENING_REQUIRED",
            "REVIEW_REQUIRED_SOURCE_PRONUNCIATION_RISK",
        )
        for i,(item,digest) in enumerate(zip(rows,hashes),1)
    )

def audit_stage(
    folder:Path, *,
    acoustic_report:dict|None=None, listening_receipt:dict|None=None,
    academic_receipt:dict|None=None, figure_receipt:dict|None=None,
    highlight_receipt:dict|None=None,
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
    audio_screen_ok=_acoustic(acoustic_report,folder,audio_hash)
    listening_ok=_listening(listening_receipt,audio_hash)
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
    academic_ok=_approval(academic_receipt,video_hash) if video_ok else False
    figures_ok=_approval(figure_receipt,video_hash) if video_ok else False
    highlights_ok=_approval(highlight_receipt,video_hash) if video_ok else False
    risks=build_risk_register(slides,normalize,seconds,wav_sha256=audio_hash)
    checks={
        "pronunciation_text_preflight":preflight,
        "reviewed_lexicon":lexicon,
        "voice_bound_wav_provenance":audio_ok,
        "independent_acoustic_screen":audio_screen_ok,
        "all_slide_listening_approved":listening_ok,
        "video_duration_and_av_integrity":video_ok,
        "academic_review_approved":academic_ok,
        "figures_review_approved":figures_ok,
        "element_level_highlights_approved":highlights_ok,
    }
    blockers=[name for name,value in checks.items() if not value]
    return {
        "schema_version":1,
        "slide_count":len(slides),
        "video_sha256":video_hash or None,
        "video_duration_seconds":video_seconds,
        "total_wav_seconds":round(sum(seconds),4),
        "wav_sha256":audio_hash,
        "source_risks":risks["risk_count"],
        "risk_review_slides":risks["risk_review_slides"],
        "checks":checks,
        "blockers":blockers,
        "ready_for_separate_promotion":not blockers,
        "publication_performed":False,
        "note":"Read-only audit; external reviewer receipts must be trusted separately. No automatic Moodle promotion.",
    }

def main(argv=None)->int:
    parser=argparse.ArgumentParser(description="Strict read-only MicroGen lecture release audit")
    parser.add_argument("stage",type=Path)
    parser.add_argument("--acoustic",type=Path)
    parser.add_argument("--listening",type=Path)
    parser.add_argument("--academic",type=Path)
    parser.add_argument("--figures",type=Path)
    parser.add_argument("--highlights",type=Path)
    parser.add_argument("--new-report",type=Path)
    args=parser.parse_args(argv)
    def read(path):
        return json.loads(path.read_text(encoding="utf8")) if path else None
    audit=audit_stage(args.stage,acoustic_report=read(args.acoustic),
        listening_receipt=read(args.listening),
        academic_receipt=read(args.academic),
        figure_receipt=read(args.figures),
        highlight_receipt=read(args.highlights))
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
