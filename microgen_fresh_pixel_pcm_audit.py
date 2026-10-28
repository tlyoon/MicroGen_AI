"""Independent decoded H264 pixel and ALAC PCM checks for CURRENT HP split.

Testing visible cues does not prove phonetic, mathematical, diagram or
element-level semantic correctness. No source or finished media edits.
"""
from __future__ import annotations
import hashlib
import json
import math
import statistics
import subprocess
import wave
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
from microgen_source_safe_orchestrator import atomic_json,digest,read_json
from microgen_two_part_word_highlight import WIDTH,HEIGHT,FPS,_frames,validate


class FreshPixelError(ValueError):
    pass


def _decoded_frame(ffmpeg,video,when):
    cmd=[str(ffmpeg),"-nostdin","-loglevel","error","-ss",f"{when:.6f}",
         "-i",str(video),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","pipe:1"]
    out=subprocess.run(cmd,capture_output=True,timeout=90,check=True).stdout
    if len(out)!=WIDTH*HEIGHT*3:
        raise FreshPixelError("Invalid decoded video pixel sample")
    return Image.frombytes("RGB",(WIDTH,HEIGHT),out)


def _decoded_pcm_sha(ffmpeg,video):
    cmd=[str(ffmpeg),"-nostdin","-loglevel","error","-i",str(video),
         "-map","0:a:0","-vn","-ac","1","-ar","24000",
         "-c:a","pcm_s16le","-f","s16le","pipe:1"]
    out=subprocess.run(cmd,capture_output=True,timeout=120,check=True).stdout
    return hashlib.sha256(out).hexdigest(),len(out)


def independent_pixel_pcm_audit(stage,cues_dir,videos_dir,ffmpeg,output):
    stage,curr,obs=validate(stage,Path(cues_dir)/"current_tts_cues.json")
    files=Path(videos_dir).resolve(strict=True)
    receipt=read_json(files/"highlighted_part_receipt.json")
    if (receipt.get("status")!="TWO_HIGHLIGHTED_WORD_CANDIDATES_NOT_PUBLICATION_APPROVAL"
        or receipt.get("publication_allowed") is not False
        or receipt.get("source")!=curr
        or receipt.get("cue_report_sha256")!=digest(Path(cues_dir)/"current_tts_cues.json")
        or len(receipt.get("parts",[]))!=2):
        raise FreshPixelError("Source-bound candidate parts not authenticated")
    out=Path(output).absolute()
    if out.exists() or out.is_symlink() or out.is_relative_to(files):
        raise FreshPixelError("Independent unused QA output required")
    frames=_frames(stage)
    proof=[]
    positives=negatives=0
    for index,part in enumerate(receipt["parts"],1):
        name=files/part["video_file"]
        audio=files/part["audio_file"]
        if (part["part"]!=index or digest(name)!=part["video_sha256"]
            or name.is_symlink() or audio.is_symlink()):
            raise FreshPixelError("Encoded part bytes or index changed")
        with wave.open(str(audio),"rb") as wavef:
            raw=wavef.readframes(wavef.getnframes())
        rawhash=hashlib.sha256(raw).hexdigest()
        decoded,length=_decoded_pcm_sha(ffmpeg,name)
        if (decoded!=rawhash or decoded!=part["raw_audio_pcm_sha256"]
            or length!=len(raw)):
            raise FreshPixelError("Encoded ALAC not bit identical to original current TTS PCM")
        sample_rows=[]
        offset=0.0
        for slide in range(part["slides"][0],part["slides"][1]+1):
            cues=obs["slides"][slide-1]["cues"]
            frame,scale,pos=frames[slide-1]
            duration=curr["wav_inventory"][slide-1]["duration_seconds"]
            ticks=math.ceil(duration*FPS)
            chosen=None
            for k in range(ticks):
                t=(k+.5)/FPS
                if t>=duration:continue
                on=[q for q in cues if q["start"]<=t<q["end"]]
                if on and chosen is None and qbox_ok(on[0],scale,pos):
                    chosen=("active",t,on)
                if chosen:break
            if chosen and positives<48:
                kind,t,on=chosen
                absolute=offset+t
                actual=_decoded_frame(ffmpeg,name,absolute)
                x0,y0,x1,y1=on[0]["box"]
                box=(max(0,round(x0*scale+pos[0])),
                     max(0,round(y0*scale+pos[1])),
                     min(WIDTH,round(x1*scale+pos[0])),
                     min(HEIGHT,round(y1*scale+pos[1])))
                diff=ImageChops.difference(actual,frame).crop(box)
                mae=sum(ImageStat.Stat(diff).mean)/3
                if mae<7:
                    raise FreshPixelError(f"Highlighted pixels absent slide {slide}: {mae:.2f}")
                sample_rows.append({"slide":slide,"kind":"positive","seconds":round(absolute,4),
                                    "bbox":list(box),"local_mae":round(mae,2)})
                positives+=1
            # Find one negative frame in slide 1 or near start of each part.
            if (slide in (part["slides"][0],part["slides"][0]+1) and negatives<8):
                for k in range(min(ticks,24)):
                    t=(k+.5)/FPS
                    if t>=duration:break
                    if all(not(c["start"]<=t<c["end"]) for c in cues):
                        decoded_frame=_decoded_frame(ffmpeg,name,offset+t)
                        mae=sum(ImageStat.Stat(ImageChops.difference(decoded_frame,frame)).mean)/3
                        if mae>20:
                            raise FreshPixelError(f"Negative control has unexpected image differences slide {slide}: {mae:.2f}")
                        sample_rows.append({"slide":slide,"kind":"negative","seconds":round(offset+t,4),
                                            "global_mae":round(mae,2)})
                        negatives+=1
                        break
            offset+=duration
        proof.append({"part":index,"mp4_sha256":part["video_sha256"],
                      "decoded_audio_pcm_sha256":decoded,
                      "sampled_pixels":sample_rows})
    if positives<8 or negatives<2:
        raise FreshPixelError("Insufficient positive/negative actual decoded checks")
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report={"status":"CURRENT_WORD_PIXEL_AND_PCM_TECHNICAL_PASS_NOT_ACADEMIC_APPROVAL",
            "publication_allowed":False,"source":curr,"candidate_videos_sha256":
            digest(files/"highlighted_part_receipt.json"),
            "cue_report_sha256":digest(Path(cues_dir)/"current_tts_cues.json"),
            "positive_checks":positives,"negative_controls":negatives,
            "full_pcm_hash_matches":True,
            "parts":proof,
            "phonetic_correctness_verified":False,
            "mathematical_figure_alignment_verified":False}
    atomic_json(output/"independent_pixel_pcm_receipt.json",report)
    return {"positives":positives,"negative_controls":negatives,
            "audio_lossless":True,"publication_allowed":False}


def qbox_ok(cue,scale,pos):
    x0,y0,x1,y1=cue["box"]
    return (x1-x0)*scale>7 and (y1-y0)*scale>5


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--stage",required=True);p.add_argument("--cues-dir",required=True)
    p.add_argument("--videos",required=True);p.add_argument("--ffmpeg",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(independent_pixel_pcm_audit(a.stage,a.cues_dir,a.videos,a.ffmpeg,a.output))
