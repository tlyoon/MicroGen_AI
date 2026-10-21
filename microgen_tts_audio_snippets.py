"""Create byte-accurate, SHA-bound *candidate* PCM audio snippets externally.

Snippets are unlabelled excerpts. Only independent reference annotation can
say that a particular snippet contains the target y/why phoneme.
"""
from __future__ import annotations
import hashlib,json,re,wave
from pathlib import Path
from microgen_tts_pcm_features import file_sha256

class ClipError(ValueError):pass

def extract_clips(source:Path,source_sha256:str,intervals:list[dict],
                  new_dir:Path,*,max_clips:int=16)->dict:
    wav=Path(source).resolve(strict=True)
    dest=Path(new_dir).resolve(strict=False)
    if (not isinstance(source_sha256,str) or
        not re.fullmatch("[a-f0-9]{64}",source_sha256) or
        file_sha256(wav)!=source_sha256):
        raise ClipError("Source WAV hash does not match pinned reference")
    if (dest.exists() or dest.is_symlink() or dest==wav.parent or
        wav.parent in dest.parents or dest in wav.parent.parents or
        not dest.parent.is_dir()):
        raise ClipError("Clips must be in a new external directory")
    if (not isinstance(intervals,list) or not intervals or
        type(max_clips)!=int or not 1<=max_clips<=40 or len(intervals)>max_clips):
        raise ClipError("Invalid bounded clip request")
    with wave.open(str(wav),"rb") as w:
        rate=w.getframerate();count=w.getnframes()
        if w.getnchannels()!=1 or w.getsampwidth()!=2 or count<=0:
            raise ClipError("Only nonempty mono PCM16 source WAVs")
        plan=[];last=0
        for i,entry in enumerate(intervals,1):
            if not isinstance(entry,dict):raise ClipError("Invalid clip interval")
            start=entry.get("start_seconds");end=entry.get("end_seconds")
            if (type(start) not in (int,float) or type(end) not in (int,float) or
                not 0<=start<end<=count/rate or end-start>10):
                raise ClipError("Clip exceeds source boundaries or duration budget")
            a=round(start*rate);b=round(end*rate)
            if a<last or b<=a:raise ClipError("Clips must be nonoverlapping, ordered samples")
            plan.append((i,a,b))
            last=b
        payloads=[]
        for i,a,b in plan:
            w.setpos(a)
            data=w.readframes(b-a)
            if len(data)!=(b-a)*2:raise ClipError("Truncated PCM frames")
            payloads.append((i,a,b,data))
    if file_sha256(wav)!=source_sha256:
        raise ClipError("Source changed while extracting snippets")
    # All preflight checks complete before first disk write.
    dest.mkdir(exist_ok=False)
    rows=[]
    for i,a,b,data in payloads:
        output=dest/f"candidate_{i:02d}.wav"
        with output.open("xb") as exclusive:
            with wave.open(exclusive,"wb") as clip:
                clip.setnchannels(1);clip.setsampwidth(2);clip.setframerate(rate)
                clip.writeframes(data)
        rows.append({"candidate_index":i,"file":output.name,
                     "sha256":file_sha256(output),
                     "start_sample":a,"end_sample_exclusive":b,
                     "start_seconds":round(a/rate,6),"end_seconds":round(b/rate,6),
                     "phoneme_label":None,"label_status":"UNLABELLED_AUDIO_CANDIDATE"})
    receipt={"schema_version":1,"original_wav_sha256":source_sha256,
             "source_sample_rate_hz":rate,"snippets":rows,
             "can_certify_phoneme":False,"human_gate_required":False}
    with (dest/"snippet_manifest.json").open("x",encoding="utf8") as f:
        json.dump(receipt,f,indent=2)
    return receipt
