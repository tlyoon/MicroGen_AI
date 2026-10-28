"""Independent original-WAV/MP4 differential check for source-equation highlights.

This checks actual new encoded frames and audio against prior reference MP4s.
Does not certify mathematical correctness, phonetics or full-element timing.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import pymupdf as fitz

from microgen_source_safe_orchestrator import atomic_json,digest,read_json
from microgen_fresh_source_cues import source_inventory
from microgen_single_figure_frame_diff_qa import _decoded_frame,frame_difference_metrics


class EquationVideoQAError(ValueError):
    pass


def visible_equation_change(local, frame):
    return (math.isfinite(local) and math.isfinite(frame)
            and local >= 10 and local >= 5 * max(frame, 0.01))


def audit_equation_videos(stage, receipt, old_dir, new_dir,
                           old_av, new_av, ffmpeg, output):
    base,source=source_inventory(stage)
    receipt_file=Path(receipt).resolve(strict=True)
    old=Path(old_dir).resolve(strict=True)
    new=Path(new_dir).resolve(strict=True)
    ff=Path(ffmpeg).resolve(strict=True)
    old_qa_file=Path(old_av).resolve(strict=True)
    new_qa_file=Path(new_av).resolve(strict=True)
    dest=Path(output).resolve(strict=False)
    if (dest.exists() or dest.is_symlink() or dest==base or
            dest.is_relative_to(base) or base.is_relative_to(dest) or
            any(dest.is_relative_to(x) for x in
                (old,new,receipt_file.parent,old_qa_file.parent,new_qa_file.parent)) or
            not ff.is_file() or ff.is_symlink()):
        raise EquationVideoQAError("Use independent QA output and real FFmpeg")
    note=read_json(receipt_file)
    cue_file=receipt_file.parent/"equation_augmented_cues.json"
    old_meta=read_json(old/"highlighted_part_receipt.json")
    new_meta=read_json(new/"highlighted_part_receipt.json")
    prior_qa=read_json(old_qa_file)
    current_qa=read_json(new_qa_file)
    if (note.get("source") != source or note.get("publication_allowed") is not False
            or note.get("mathematics_verified") is not False
            or note.get("full_element_sync_verified") is not False
            or note.get("augmented_cue_sha256") != digest(cue_file)
            or note.get("slide_pdf_sha256") != digest(base/"slides.pdf")
            or note.get("script_sha256") != digest(base/"script_tts.json")):
        raise EquationVideoQAError("Untrusted original equation receipt")
    augmented=read_json(cue_file)
    if (new_meta.get("cue_report_sha256") != digest(cue_file)
            or old_meta.get("cue_report_sha256") != note.get("base_cue_sha256")
            or any(x.get("source")!=source or x.get("publication_allowed") is not False
                   for x in (old_meta,new_meta,prior_qa,current_qa))
            or not prior_qa.get("full_pcm_hash_matches")
            or not current_qa.get("full_pcm_hash_matches")
            or len(old_meta.get("parts",[]))!=2 or len(new_meta.get("parts",[]))!=2
            or len(prior_qa.get("parts",[]))!=2 or len(current_qa.get("parts",[]))!=2):
        raise EquationVideoQAError("Independent pre/post AV contract failed")
    for index,(a,b) in enumerate(zip(old_meta["parts"],new_meta["parts"])):
        prior=prior_qa["parts"][index];current=current_qa["parts"][index]
        if (a["part"]!=index+1 or b["part"]!=index+1
                or a["slides"]!=b["slides"]
                or a["input_wav_sha256"]!=b["input_wav_sha256"]
                or a["raw_audio_pcm_sha256"]!=b["raw_audio_pcm_sha256"]
                or prior.get("decoded_audio_pcm_sha256")!=a["raw_audio_pcm_sha256"]
                or current.get("decoded_audio_pcm_sha256")!=b["raw_audio_pcm_sha256"]
                or prior.get("mp4_sha256")!=a["video_sha256"]
                or current.get("mp4_sha256")!=b["video_sha256"]):
            raise EquationVideoQAError("Audio or part identity mismatch")
        for folder,item in ((old,a),(new,b)):
            if (item["seconds"]>=600 or digest(folder/item["video_file"])!=item["video_sha256"]):
                raise EquationVideoQAError("Part duration or MP4 hash mismatch")
    files=(receipt_file,cue_file,base/"slides.pdf",base/"script_tts.json",
           old/"highlighted_part_receipt.json",new/"highlighted_part_receipt.json",
           old_qa_file,new_qa_file)
    originals={str(p):digest(p) for p in files}
    sample_rows=[]
    candidates=note.get("candidate_slides")
    if (not isinstance(candidates,list) or not candidates or
            sum(len(x.get("cues",[])) for x in candidates)!=note.get("equation_candidate_count")):
        raise EquationVideoQAError("No verified selected equation cues")
    with fitz.open(base/"slides.pdf") as pdf:
        for row in candidates:
            slide=row.get("slide")
            if type(slide) is not int or not 1<=slide<=len(pdf):
                raise EquationVideoQAError("Invalid source slide number")
            part=1 if slide<=13 else 2
            first=1 if part==1 else 14
            offset=sum(source["wav_inventory"][j-1]["duration_seconds"]
                       for j in range(first,slide))
            page=pdf[slide-1]
            scale=min(640/page.rect.width,360/page.rect.height)
            margins=((640-page.rect.width*scale)/2,(360-page.rect.height*scale)/2)
            before=old_meta["parts"][part-1]
            after=new_meta["parts"][part-1]
            for cue in row["cues"]:
                if (cue not in augmented["slides"][slide-1]["cues"] or
                        cue.get("mathematical_equivalence_verified") is not False or
                        cue.get("equation_phrase_fully_synchronized") is not False):
                    raise EquationVideoQAError("Source equation or approval forged")
                box=cue["box"]
                if (len(box)!=4 or any(not isinstance(v,(int,float)) or
                    not math.isfinite(v) for v in box)):
                    raise EquationVideoQAError("Invalid equation geometry")
                region=(max(0,int(box[0]*scale+margins[0])),
                        max(0,int(box[1]*scale+margins[1])),
                        min(640,math.ceil(box[2]*scale+margins[0])),
                        min(360,math.ceil(box[3]*scale+margins[1])))
                when=offset+(cue["start"]+cue["end"])/2
                left=_decoded_frame(ff,old/before["video_file"],when)
                right=_decoded_frame(ff,new/after["video_file"],when)
                local,entire=frame_difference_metrics(left,right,region)
                sample_rows.append({"slide":slide,"part":part,
                    "absolute_video_second":round(when,3),
                    "equation_region_mae":round(local,3),
                    "whole_frame_mae":round(entire,3),
                    "visible_incremental_equation_highlight":visible_equation_change(local,entire),
                    "equation_math_verified":False})
    if (not all(row["visible_incremental_equation_highlight"] for row in sample_rows)
            or source_inventory(base)[1]!=source
            or any(digest(Path(f))!=h for f,h in originals.items())):
        raise EquationVideoQAError("Actual PDF/WAV/video equation highlight not proven")
    dest.mkdir(parents=True,exist_ok=False)
    result={"status":"ACTUAL_EQUATION_BOX_AUDIO_TIMING_DIFFERENCE_NOT_MATH_APPROVAL",
        "schema_version":1,"source":source,"source_file_sha256":originals,
        "measured_equations":sample_rows,"sample_count":len(sample_rows),
        "actual_equation_pixel_overlay_verified":True,
        "lossless_source_audio_verified":True,
        "mathematical_equivalence_verified":False,
        "full_element_sync_verified":False,
        "phonetic_correctness_verified":False,
        "publication_allowed":False}
    atomic_json(dest/"equation_video_diff_receipt.json",result)
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for field in ("stage","receipt","old_dir","new_dir","old_av","new_av","ffmpeg","output"):
        p.add_argument("--"+field.replace("_","-"),required=True)
    args=p.parse_args()
    result=audit_equation_videos(args.stage,args.receipt,args.old_dir,args.new_dir,
                                 args.old_av,args.new_av,args.ffmpeg,args.output)
    print(json.dumps({"sample_count":result["sample_count"],"publication_allowed":False}))
