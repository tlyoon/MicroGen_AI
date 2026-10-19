"""Checksum-verified WAV excerpt extraction for flagged mathematical pronunciation.

Offsets are *rough reading-position estimates*, NOT forced alignment.
Full-slide listening is still required when excerpt positioning is wrong.
No ASR/Whisper dependency and no edits to input WAVs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import struct
import wave
from pathlib import Path

class ExcerptError(RuntimeError):
    pass

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def pcm_analysis(path: Path) -> dict:
    with wave.open(str(path),"rb") as w:
        rate=w.getframerate()
        if w.getsampwidth()!=2 or w.getnchannels()!=1 or rate<=0 or w.getnframes()<=0:
            raise ExcerptError("Expected nonempty mono 16-bit WAV")
        pcm=w.readframes(w.getnframes())
    samples=[x[0] for x in struct.iter_unpack("<h",pcm)]
    if not samples: raise ExcerptError("No PCM samples")
    rms=math.sqrt(sum(float(s)*s for s in samples)/len(samples))
    return {
       "duration_seconds":len(samples)/rate,
       "sample_rate_hz":rate,
       "rms_fraction_full_scale":round(rms/32768,7),
       "silent_or_near_silent":rms<50,
       "clipping_fraction":round(sum(abs(x)>=32767 for x in samples)/len(samples),7),
    }

def render_excerpts(
    wav_dir:Path, sidecar: list[dict], risk_report:dict, out_dir:Path,
    *, clip_seconds:float=7.0, max_excerpts:int=60,
) -> dict:
    if clip_seconds<2 or clip_seconds>18 or max_excerpts<1:
        raise ExcerptError("Unsafe clip configuration")
    if out_dir.exists() or out_dir.is_symlink():
        raise ExcerptError("Refusing to reuse output directory")
    if risk_report.get("slide_count")!=len(sidecar):
        raise ExcerptError("Risk report / sidecar slide count mismatch")
    if [r.get("slide") for r in risk_report.get("slides",[])]!=list(range(1,len(sidecar)+1)):
        raise ExcerptError("Bad slide numbering in risk report")
    plan=[]
    for number,(source,row) in enumerate(zip(sidecar,risk_report["slides"]),1):
        original=str(source.get("tts_text") or source.get("narration") or "")
        if hashlib.sha256(original.encode("utf8")).hexdigest()!=row.get("tts_source_sha256"):
            raise ExcerptError(f"Narration source SHA drift on slide {number}")
        wav=wav_dir/f"slide{number}.wav"
        if digest(wav)!=row.get("audio_wav_sha256"):
            raise ExcerptError(f"Audio SHA drift on slide {number}")
        if not row.get("risks"):
            continue
        with wave.open(str(wav),"rb") as audio:
            if audio.getsampwidth()!=2 or audio.getnchannels()!=1 or audio.getframerate()<=0:
                raise ExcerptError("Unsupported WAV format")
            rate=audio.getframerate()
            duration=audio.getnframes()/rate
            # Rough cue from relative *character position*. Speech timing
            # varies, so an excerpt can miss the spoken token.
            for j,risk in enumerate(row["risks"],1):
                if len(plan)>=max_excerpts:
                    raise ExcerptError("Too many flagged risks for one bounded review batch")
                start=int(risk["start"]);end=int(risk["end"])
                if not (0<=start<end<=len(original)):
                    raise ExcerptError(f"Risk offset invalid, slide {number}")
                center=duration*((start+end)/2/max(1,len(original)))
                first=max(0,center-clip_seconds/2)
                last=min(duration,center+clip_seconds/2)
                first_frame=max(0,int(first*rate))
                last_frame=min(audio.getnframes(),int(last*rate))
                plan.append({
                    "slide":number,"risk_index":j,"risk_code":risk["code"],
                    "source_excerpt":risk["source"],
                    "offset_estimated_seconds":round(center,3),
                    "window_first_seconds":round(first_frame/rate,3),
                    "window_last_seconds":round(last_frame/rate,3),
                    "first_frame":first_frame,"last_frame":last_frame,
                    "input_wav":str(wav),"input_sha256":row["audio_wav_sha256"],
                    "sample_rate":rate,
                    "alignment_method":"approximate_raw_character_fraction_not_word_alignment",
                })
    # Verify ALL input evidence before creating any output.
    out_dir.mkdir(parents=True,exist_ok=False)
    try:
        for entry in plan:
            src=Path(entry["input_wav"])
            with wave.open(str(src),"rb") as input_w:
                input_w.setpos(entry["first_frame"])
                chunk=input_w.readframes(entry["last_frame"]-entry["first_frame"])
            filename=f"slide{entry['slide']:02d}_risk{entry['risk_index']:02d}.wav"
            target=out_dir/filename
            with wave.open(str(target),"wb") as output_w:
                output_w.setnchannels(1)
                output_w.setsampwidth(2)
                output_w.setframerate(entry["sample_rate"])
                output_w.writeframes(chunk)
            entry["clip_name"]=filename
            entry["clip_sha256"]=digest(target)
            entry.pop("input_wav")
            entry.pop("first_frame")
            entry.pop("last_frame")
        report={
            "schema_version":1,"excerpts":plan,
            "clips_created":len(plan),
            "automated_listening_approval":False,
            "publishable":False,
            "disclaimer":"Approximate positions; human reviewer must seek in full WAV if clip misses word.",
        }
        (out_dir/"review_clip_manifest.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        return report
    except Exception:
        # Never silently claim success on partial audio.
        raise

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("wav_folder",type=Path)
    parser.add_argument("sidecar",type=Path)
    parser.add_argument("risk_report",type=Path)
    parser.add_argument("new_output_dir",type=Path)
    args=parser.parse_args(argv)
    slides=json.loads(args.sidecar.read_text(encoding="utf8"))["slides"]
    risk=json.loads(args.risk_report.read_text(encoding="utf8"))
    res=render_excerpts(args.wav_folder,slides,risk,args.new_output_dir)
    print(json.dumps({"clips_created":res["clips_created"],"output_dir":str(args.new_output_dir),
                      "publishable":False}))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
