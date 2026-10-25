"""Independent decoded video pixel audit of corrected PDF-word ASR overlays.

A visible rectangle is NOT independent evidence the corresponding spoken
word, equation, figure, or phoneme is correct. This compares actual encoded
pixels against freshly rasterized, SHA-bound source PDF, at actual current
WAV ASR cue frame windows, with control samples outside a word's interval.
"""
from __future__ import annotations
import math
import subprocess
from pathlib import Path
import pymupdf as fitz
from PIL import Image, ImageChops, ImageDraw, ImageStat

from microgen_source_safe_orchestrator import atomic_json, digest, read_json, verify_workspace
from microgen_corrected_word_video import _validated_inputs, WIDTH,HEIGHT,FPS

class HighlightPixelQAError(ValueError):
    pass


def _pdf_refs(source):
    path=Path(source)/"slides.pdf"
    digest_before=digest(path)
    pages=[]
    transforms=[]
    with fitz.open(path) as doc:
        if doc.page_count!=17:raise HighlightPixelQAError("Source PDF page count drift")
        for page in doc:
            scale=min(WIDTH/page.rect.width,HEIGHT/page.rect.height)
            pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
            img=Image.new("RGB",(WIDTH,HEIGHT),"white")
            img.paste(Image.frombytes("RGB",(pix.width,pix.height),pix.samples),
                      ((WIDTH-pix.width)//2,(HEIGHT-pix.height)//2))
            pages.append(img)
            transforms.append((scale,(WIDTH-pix.width)//2,(HEIGHT-pix.height)//2))
    if digest(path)!=digest_before:raise HighlightPixelQAError("Source PDF changed")
    return pages,transforms,digest_before


def _bbox(item,transform):
    scale,xoff,yoff=transform
    x0,y0,x1,y1=item["box"]
    rect=tuple(round(k) for k in
               (x0*scale+xoff,y0*scale+yoff,x1*scale+xoff,y1*scale+yoff))
    if not (0<=rect[0]<rect[2]<=WIDTH and 0<=rect[1]<rect[3]<=HEIGHT):
        raise HighlightPixelQAError("Expected rectangle is not within slide")
    return rect


def _frame_center_inside(start,end,fps):
    first=max(0,math.ceil(start*fps-.5))
    last=math.ceil(end*fps-.5)-1
    if last<first:
        return None
    return (first+last)//2


def _raw_diff(actual,reference):
    return ImageChops.difference(actual,reference)


def _mae(diff,mask=None):
    stat=ImageStat.Stat(diff,mask=mask)
    return sum(stat.mean)/3


def _capture(video,ffmpeg,t,scratch):
    cmd=[str(ffmpeg),"-nostdin","-hide_banner","-loglevel","error",
         "-y","-ss",f"{t:.6f}","-i",str(video),"-frames:v","1",str(scratch)]
    proc=subprocess.run(cmd,capture_output=True,timeout=30)
    if proc.returncode or not scratch.is_file():
        raise HighlightPixelQAError(
            "Independent decoded screenshot not available: "+proc.stderr.decode("utf8","replace")[-100:])
    with Image.open(scratch) as img:
        if img.size!=(WIDTH,HEIGHT):
            raise HighlightPixelQAError("Unexpected video sample dimensions")
        result=img.convert("RGB")
    scratch.unlink()
    return result


def audit_current_word_highlights(stage,selection,shadow,asr,video_folder,out,*,ffmpeg):
    plan,cues_path,grouped,count=_validated_inputs(stage,selection,shadow,asr)
    stage=Path(stage).resolve(strict=True)
    source=Path(plan["source"]["source_root"]).resolve(strict=True)
    folder=Path(video_folder).resolve(strict=True)
    dest=Path(out).resolve(strict=False)
    protect=(stage,source,Path(selection).resolve(strict=True),
             Path(shadow).resolve(strict=True),Path(asr).resolve(strict=True).parent,folder)
    if (dest.exists() or dest.is_symlink() or
            any(dest==p or dest.is_relative_to(p) or p.is_relative_to(dest) for p in protect)):
        raise HighlightPixelQAError("New independent audit destination required")
    movie=folder/"section25_CURRENT_ASR_WORD_HIGHLIGHTS_NOT_PUBLISHED.mp4"
    receipt=read_json(folder/"word_highlight_candidate_receipt.json")
    if (movie.is_symlink() or not movie.is_file() or
            receipt.get("status")!="ASR_WORD_HIGHLIGHT_TECHNICAL_CANDIDATE_NOT_APPROVED" or
            receipt.get("publication_allowed") is not False or
            receipt.get("word_highlight_pixels_independently_verified") is not False or
            receipt.get("video_sha256")!=digest(movie) or
            receipt.get("source_pdf_sha256")!=plan["source"]["source_pdf_sha256"] or
            receipt.get("cue_manifest_sha256")!=digest(cues_path) or
            receipt.get("recognition_report_sha256")!=digest(asr) or
            receipt.get("shadow_wav_sha256")!=digest(plan["shadow_wav"]) or
            receipt.get("corrected_pcm_sha256")!=plan["pcm"]["pcm_sha256"] or
            receipt.get("candidate_cues")!=count or receipt.get("fps")!=FPS or
            receipt.get("audio_pcm_identical") is not True):
        raise HighlightPixelQAError("Source-bound highlighted video or PCM proof missing")
    ff=Path(ffmpeg).resolve(strict=True)
    if ff.is_symlink() or not ff.is_file():
        raise HighlightPixelQAError("Explicit regular FFmpeg required")
    refs,transforms,pdf_sha=_pdf_refs(source)
    sha=digest(movie)
    dest.mkdir(parents=True,exist_ok=False)
    samples=[]
    no_frame=[]
    positives=0
    negatives=0
    failures=0
    scratch=dest/"_decoded_temporary.png"
    try:
        for slide in range(1,18):
            rows=grouped[slide]
            interval=plan["segments"][slide-1]
            for cue in rows:
                n=_frame_center_inside(cue["start"],cue["end"],FPS)
                if n is None:
                    no_frame.append(cue["id"])
                    continue
                t=(n+.5)/FPS
                if not interval["start"]<=t<interval["end"]:
                    no_frame.append(cue["id"])
                    continue
                actual=_capture(movie,ff,t,scratch)
                reference=refs[slide-1]
                diff=_raw_diff(actual,reference)
                roi=_bbox(cue,transforms[slide-1])
                inside=_mae(diff.crop(roi))
                # Exclude every simultaneously active cue from a background
                # mask, so another valid overlay cannot cause false mismatch.
                outside=Image.new("L",(WIDTH,HEIGHT),255)
                draw=ImageDraw.Draw(outside)
                for other in rows:
                    if other["start"]<=t<other["end"]:
                        draw.rectangle(_bbox(other,transforms[slide-1]),fill=0,width=3)
                background=_mae(diff,outside)
                good=inside>=5 and background<=3.5
                positives+=1
                failures+=not good
                samples.append({"kind":"inside","slide":slide,"id":cue["id"],
                                "time_seconds":round(t,4),
                                "inside_mae":round(inside,3),
                                "outside_mae":round(background,3),
                                "passed":bool(good)})
                # Decoder seek at the very first nominal post-cue frame
                # can return the preceding encoded frame near timestamps.
                # Enforce one full frame (125 ms at 8 fps) separation;
                # never claim instantaneous boundary timing acceptance.
                m=math.ceil((cue["end"]+1/FPS)*FPS-.5)
                off=(m+.5)/FPS
                if (off<interval["end"] and off>=cue["end"]):
                    other_active=[row for row in rows if row["start"]<=off<row["end"]]
                    box=roi
                    overlap=False
                    for other in other_active:
                        other_box=_bbox(other,transforms[slide-1])
                        if not (other_box[2]<box[0] or other_box[0]>box[2] or
                                other_box[3]<box[1] or other_box[1]>box[3]):
                            overlap=True
                            break
                    if not overlap:
                        candidate=_capture(movie,ff,off,scratch)
                        control=_mae(_raw_diff(candidate,reference).crop(roi))
                        # Independent clean-video baseline on real slide 14
                        # was 4.078 MAE from PDF due to H264 compression;
                        # allow 5.0, far below true active cue differences.
                        good=control<=5.0
                        negatives+=1
                        failures+=not good
                        samples.append({"kind":"after_end_control","slide":slide,
                                        "id":cue["id"],"time_seconds":round(off,4),
                                        "inside_mae":round(control,3),
                                        "passed":bool(good)})
        if (digest(movie)!=sha or digest(source/"slides.pdf")!=pdf_sha or
                digest(cues_path)!=receipt["cue_manifest_sha256"] or
                verify_workspace(stage)!=plan["source"]):
            raise HighlightPixelQAError("Source/video/cues changed during independent audit")
        passed=(positives==count and not no_frame and failures==0 and negatives>0)
        report={"schema_version":1,
                "status":"CURRENT_ASR_OVERLAY_PIXEL_AUDIT_TECHNICAL_PASS"
                    if passed else "CURRENT_ASR_OVERLAY_PIXEL_AUDIT_NEEDS_REVIEW",
                "video_sha256":sha,"source_pdf_sha256":pdf_sha,
                "asr_sha256":receipt["recognition_report_sha256"],
                "cues_sha256":receipt["cue_manifest_sha256"],
                "corrected_pcm_sha256":receipt["corrected_pcm_sha256"],
                "expected_cues":count,"positive_samples":positives,
                "post_cue_control_samples":negatives,"failed_samples":failures,
                "cues_without_frame_center":no_frame,"samples":samples,
                "actual_overlay_pixels_verified":passed,
                "spoken_word_identity_verified":False,
                "phonetic_correctness_verified":False,
                "figure_math_semantics_verified":False,
                "publication_allowed":False}
        atomic_json(dest/"word_pixel_audit_receipt.json",report)
        return {"status":report["status"],"positive":positives,"negative":negatives,
                "failed":failures,"missing_frames":len(no_frame),
                "publication_allowed":False}
    except Exception:
        scratch.unlink(missing_ok=True)
        import shutil
        shutil.rmtree(dest)
        raise
