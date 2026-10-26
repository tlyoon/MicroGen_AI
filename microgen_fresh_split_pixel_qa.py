"""Independent actual-video pixel QA for unapproved fresh-source ASR word candidates."""
from __future__ import annotations
import io
import json
import math
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
import pymupdf as fitz

from microgen_fresh_split_highlight import (
    FPS, PreviewError, _get_slide_image, _draw_cue, sha, wav_evidence,
)


def _read_video_frame(ffmpeg, mp4, second):
    args=[str(ffmpeg),"-nostdin","-hide_banner","-loglevel","error",
          "-ss",f"{second:.5f}","-i",str(mp4),
          "-frames:v","1","-f","image2pipe","-vcodec","png","pipe:1"]
    p=subprocess.run(args,capture_output=True,timeout=22)
    if p.returncode or not p.stdout:
        raise PreviewError("Unable to decode independent visual frame: "+p.stderr[-320:].decode("utf8","replace"))
    with Image.open(io.BytesIO(p.stdout)) as im:
        return im.convert("RGB")


def _mae(first,second,box=None):
    if box:
        first=first.crop(box);second=second.crop(box)
    delta=ImageChops.difference(first,second)
    return sum(ImageStat.Stat(delta).mean)/3.0


def _pixel_box(geometry,source_box):
    scale,(dx,dy)=geometry
    x0,y0,x1,y1=source_box
    return (max(0,int(x0*scale+dx)-7),max(0,int(y0*scale+dy)-7),
            min(960,int(x1*scale+dx)+7),min(540,int(y1*scale+dy)+7))


def audit_preview_pixels(stage,preview,ffmpeg):
    stage=Path(stage).resolve(strict=True)
    preview=Path(preview).resolve(strict=True)
    ffmpeg=Path(ffmpeg).resolve(strict=True)
    reportfile=preview/"split_preview_receipt.json"
    cuefile=preview/"candidate_word_cues.json"
    if (not ffmpeg.is_file() or reportfile.is_symlink() or cuefile.is_symlink()
            or not reportfile.is_file() or not cuefile.is_file()):
        raise PreviewError("Missing independent pixel audit input")
    report=json.loads(reportfile.read_text(encoding="utf8"))
    cuepack=json.loads(cuefile.read_text(encoding="utf8"))
    if (report.get("publication_allowed") is not False
            or report.get("cue_packet_sha256")!=sha(cuefile)
            or cuepack.get("publication_allowed") is not False
            or sha(stage/"slides.pdf")!=report["source_evidence"]["slides_pdf_sha256"]):
        raise PreviewError("Input source receipt changed or incorrectly approved")
    out=preview/"independent_actual_video_pixel_qa.json"
    if out.exists() or out.is_symlink():
        raise PreviewError("Refusing to overwrite prior pixel evidence")
    candidates={int(i):rows for i,rows in cuepack["slide_word_rectangles"].items()}
    positive=[]
    negative=[]
    with fitz.open(stage/"slides.pdf") as pdf:
        for part in report["parts"]:
            mp4=preview/part["video"]
            if sha(mp4)!=part["video_sha256"]:
                raise PreviewError("Video bytes changed")
            elapsed=0.0
            for slide in part["slides"]:
                duration=wav_evidence(stage/f"slide{slide}.wav")["seconds"]
                base,geometry=_get_slide_image(pdf[slide-1])
                words=candidates[slide]
                # Choose a clearly measurable candidate interval; preserve time
                # rounding of the actual 8 fps video frame generator.
                feasible=[]
                for w in words:
                    midpoint=elapsed+(w["start"]+w["end"])/2
                    t=(math.floor(midpoint*FPS)+.5)/FPS
                    if (elapsed+w["start"] < t < elapsed+w["end"]
                            and t < elapsed+duration-1/FPS):
                        feasible.append((w["end"]-w["start"],t,w))
                if feasible:
                    _,t,chosen=max(feasible,key=lambda x:x[0])
                    active=[w for w in words if elapsed+w["start"]<=t<elapsed+w["end"]]
                    expected=base
                    for word in active:
                        expected=_draw_cue(expected,geometry,word["box"])
                    # Compare the *decoded* encoded frame, not the model
                    # source-only overlay. This catches absent visuals.
                    actual=_read_video_frame(ffmpeg,mp4,t)
                    rect=_pixel_box(geometry,chosen["box"])
                    plain_score=_mae(actual,base,rect)
                    highlighted_score=_mae(actual,expected,rect)
                    passed=(plain_score>=5 and highlighted_score<plain_score*.85)
                    positive.append({
                        "part":part["part"],"slide":slide,
                        "source_word":chosen["word"],"clock_seconds":round(t,4),
                        "plain_difference_mae":round(plain_score,3),
                        "expected_highlight_difference_mae":round(highlighted_score,3),
                        "positive_pass":passed,
                    })
                # A control must be a time at which NO cue is active.
                start_frame=math.ceil(elapsed*FPS)
                stop_frame=min(math.ceil((elapsed+duration)*FPS),start_frame+int(5*FPS))
                quiet=None
                for frame in range(start_frame,stop_frame):
                    t=(frame+.5)/FPS
                    if elapsed<t<elapsed+duration and not any(
                            elapsed+w["start"]<=t<elapsed+w["end"] for w in words):
                        quiet=t
                        break
                if quiet is not None:
                    unhighlighted=_read_video_frame(ffmpeg,mp4,quiet)
                    plain_score=_mae(unhighlighted,base)
                    passed=plain_score<=10
                    negative.append({
                        "part":part["part"],"slide":slide,
                        "clock_seconds":round(quiet,4),
                        "plain_image_mae":round(plain_score,3),
                        "negative_pass":passed})
                elapsed+=duration
    evidence={
        "status":"ACTUAL_VIDEO_WORD_PIXEL_SAMPLES_NOT_SEMANTIC_APPROVAL",
        "source_candidate_receipt_sha256":sha(reportfile),
        "cue_manifest_sha256":sha(cuefile),
        "positive_samples":positive,"negative_samples":negative,
        "positive_passed":sum(x["positive_pass"] for x in positive),
        "negative_passed":sum(x["negative_pass"] for x in negative),
        "publication_allowed":False,
        "academic_semantics_verified":False,
        "narrator_phenetic_correctness_verified":False,
        "figure_highlight_semantics_verified":False,
    }
    out.write_text(json.dumps(evidence,indent=2,sort_keys=True),encoding="utf8")
    return {k:evidence[k] for k in ("positive_passed","negative_passed")} | {
        "positive_total":len(positive),"negative_total":len(negative),
        "all_pixel_samples_passed":len(positive)>0 and len(negative)>0 and
        all(x["positive_pass"] for x in positive) and
        all(x["negative_pass"] for x in negative),
    }


if __name__=="__main__":
    if len(sys.argv)!=4:
        raise SystemExit("Usage: script STAGE PREVIEW FFMPEG")
    print(audit_preview_pixels(*sys.argv[1:]),flush=True)
