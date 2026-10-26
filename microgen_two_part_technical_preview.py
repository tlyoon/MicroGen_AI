"""Source-bound two-part *technical preview* renderer (NOT approved teaching media).

Renders static slide frames and unchanged TTS audio in a separate AppData
campaign folder. No semantic narration highlights are claimed or inserted.
"""
from __future__ import annotations
import json
import hashlib
import os
import sys
from pathlib import Path

import pymupdf
from microgen_quality import check_video, check_wavs, sha256
from gen_video_v22 import _make_segment, _concat

def create_unapproved_previews(stage: Path, *, boundary: int = 13) -> dict:
    stage = Path(stage).resolve(strict=True)
    pdf = stage/"slides.pdf"
    with pymupdf.open(pdf) as book:
        count = len(book)
    if count != 23 or boundary < 1 or boundary >= count:
        raise ValueError("Requires fresh 23-slide Section 2.5 deck and valid split")
    audit = check_wavs(stage, count)
    durations = audit["seconds"]
    splits = [list(range(1,boundary+1)),list(range(boundary+1,count+1))]
    if any(sum(durations[i-1] for i in numbers)>=570 for numbers in splits):
        raise ValueError("Audio split exceeds the cautious <570s media limit")
    output = stage/"technical_previews_unapproved"
    output.mkdir(exist_ok=True)
    source_signature={"pdf_sha256":sha256(pdf),"wav_sha256":audit["sha256"],
                      "render":"static_slides_and_source_wav_AAC_not_element_synchronized"}
    clips=[]
    with pymupdf.open(pdf) as book:
        for index in range(1,count+1):
            f=stage/f"slide{index}.wav"
            sub=output/f"slide{index:02d}.pdf"
            fragment=pymupdf.open()
            try:
                fragment.insert_pdf(book,from_page=index-1,to_page=index-1)
                if not sub.exists():
                    fragment.save(sub)
                elif sha256(sub)!=hashlib.sha256(fragment.tobytes()).hexdigest():
                    raise ValueError(f"Existing slide preview PDF changed: {index}")
            finally:fragment.close()
            candidate=output/f"slide{index:02d}.mp4"
            item=output/f"slide{index:02d}.json"
            key=hashlib.sha256(f"{sha256(sub)}:{sha256(f)}".encode()).hexdigest()
            good=False
            if candidate.exists() and item.exists():
                try:
                    state=json.loads(item.read_text())
                    good=state.get("key")==key and state.get("sha256")==sha256(candidate)
                    if good:check_video(candidate,expected_seconds=durations[index-1])
                except (ValueError,OSError,RuntimeError):good=False
            if not good:
                temporary=output/f"slide{index:02d}.tmp.mp4"
                temporary.unlink(missing_ok=True)
                _make_segment(sub,f,temporary)
                check_video(temporary,expected_seconds=durations[index-1])
                os.replace(temporary,candidate)
                item.write_text(json.dumps({"key":key,"sha256":sha256(candidate)}))
            clips.append(candidate)
    parts=[]
    for n,numbers in enumerate(splits,1):
        target=output/f"section25_part{n:02d}_STATIC_REVIEW_NOT_PUBLISHABLE.mp4"
        temporary=output/f"section25_part{n:02d}.candidate.mp4"
        if target.exists():
            raise ValueError("Refuse to overwrite prior technical review part")
        _concat([clips[i-1] for i in numbers],temporary)
        info=check_video(temporary,expected_seconds=sum(durations[i-1] for i in numbers))
        if info["seconds"]>=600:
            raise ValueError("Encoded part exceeds 600 seconds")
        os.replace(temporary,target)
        parts.append({"part":n,"slide_start":numbers[0],"slide_end":numbers[-1],
                      "seconds":info["seconds"],"file":str(target),"sha256":sha256(target)})
        print("TECHNICAL_PART_READY",n,round(info["seconds"],2),flush=True)
    receipt={"schema_version":1,"status":"TECHNICAL_STATIC_PREVIEW_ONLY",
             "input":source_signature,"parts":parts,
             "publication_allowed":False,"element_highlights_verified":False,
             "math_figures_approved":False,"phonetic_audio_approved":False}
    (output/"review_receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf8")
    return receipt

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Pass one isolated chapter stage directory")
    print(create_unapproved_previews(Path(sys.argv[1])))
