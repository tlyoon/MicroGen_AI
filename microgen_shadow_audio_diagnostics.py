"""Bounded amplitude/seam analysis for corrected-trial shadow audio.

Loudness and zero crossing rate may expose joins, but never authenticate
speaker identity, correct phonemes, accent, mathematical meaning or timing.
"""
from __future__ import annotations
import array
import math
import wave
from pathlib import Path
from microgen_source_safe_orchestrator import digest,read_json,atomic_json,OrchestratorError

class ShadowSeamError(OrchestratorError):
    pass

def _stats(pcm):
    values=array.array("h");values.frombytes(pcm)
    if not values:raise ShadowSeamError("No samples to analyze")
    rms=math.sqrt(sum(v*v for v in values)/len(values))/32768
    zero=sum((a<0)!=(b<0) for a,b in zip(values,values[1:]))/max(1,len(values)-1)
    return {"rms":round(rms,8),"zcr":round(zero,6),
            "dbfs":round(20*math.log10(max(rms,1e-9)),3)}

def inspect_shadow_seams(folder,output,*,window_seconds=.45):
    src=Path(folder).resolve(strict=True)
    report=read_json(src/"shadow_receipt.json")
    wav=Path(report["shadow_wav"]).resolve(strict=True)
    target=Path(output).resolve(strict=False)
    if (target.exists() or target.is_symlink() or target.is_relative_to(src) or
        wav.is_symlink() or digest(wav)!=report["shadow_sha256"] or
        report.get("publication_allowed") is not False):
        raise ShadowSeamError("Unsafe output or altered shadow WAV")
    if not .15<=window_seconds<=1.0:
        raise ShadowSeamError("Bounded acoustic window required")
    joins=[]
    with wave.open(str(wav),"rb") as stream:
        if (stream.getnchannels(),stream.getsampwidth(),stream.getframerate())!=(1,2,16000):
            raise ShadowSeamError("Expected mono PCM16 at 16 kHz")
        total=stream.getnframes()
        length=round(window_seconds*16000)
        for row in report["audio_segments"][1:]:
            frame=round(row["start_seconds"]*16000)
            if frame<length or frame+length>=total:
                raise ShadowSeamError("Invalid source-specific audio boundary")
            stream.setpos(frame-length);left=_stats(stream.readframes(length))
            stream.setpos(frame);right=_stats(stream.readframes(length))
            db_change=round(abs(left["dbfs"]-right["dbfs"]),3)
            joins.append({"before_slide":row["slide"]-1,"after_slide":row["slide"],
              "left_dbfs":left["dbfs"],"right_dbfs":right["dbfs"],
              "db_change":db_change,"zero_crossing_change":round(abs(left["zcr"]-right["zcr"]),6),
              "acoustic_seam_flag":db_change>8,
              "speaker_identity_verified":False})
    if digest(wav)!=report["shadow_sha256"]:
        raise ShadowSeamError("Shadow changed during analysis")
    flagged=[x for x in joins if x["acoustic_seam_flag"]]
    output_doc={"schema_version":1,"status":"SHADOW_ACOUSTIC_SEAM_DIAGNOSTIC",
       "shadow_wav_sha256":report["shadow_sha256"],
       "join_count":len(joins),"flagged_loudness_joins":len(flagged),
       "joins":joins,"new_word_clock_required":True,
       "speaker_consistency_verified":False,"phonetic_correctness_verified":False,
       "publication_allowed":False}
    atomic_json(target,output_doc)
    return {"joins":len(joins),"flagged":len(flagged),
       "speaker_identity_certified":False,"publication_allowed":False}
