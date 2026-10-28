"""Verify external candidate snippets are exact byte-for-byte PCM source ranges.

This is structural provenance verification, not a pronunciation verifier.
"""
from __future__ import annotations
import json,math,re,wave
from pathlib import Path
from microgen_tts_pcm_features import file_sha256

class SnippetIntegrityError(ValueError):pass

def verify_snippets(source:Path,external_dir:Path)->dict:
    original=Path(source).resolve(strict=True)
    folder=Path(external_dir).resolve(strict=True)
    if original.parent==folder or original.parent in folder.parents:
        raise SnippetIntegrityError("Evidence cannot reside inside original source")
    receipt=json.loads((folder/"snippet_manifest.json").read_text(encoding="utf8"))
    rows=receipt.get("snippets")
    if (receipt.get("schema_version")!=1 or
        receipt.get("original_wav_sha256")!=file_sha256(original) or
        not isinstance(rows,list) or not rows or len(rows)>40):
        raise SnippetIntegrityError("Original WAV provenance or clip manifest invalid")
    before=file_sha256(original);verified=[];last=0
    with wave.open(str(original),"rb") as wave_src:
        rate=wave_src.getframerate();n=wave_src.getnframes()
        if wave_src.getnchannels()!=1 or wave_src.getsampwidth()!=2:
            raise SnippetIntegrityError("Only original mono PCM16 WAV supported")
        if receipt.get("source_sample_rate_hz")!=rate:
            raise SnippetIntegrityError("Source rate changed")
        for i,item in enumerate(rows,1):
            name=f"candidate_{i:02d}.wav"
            if (not isinstance(item,dict) or item.get("file")!=name or
                item.get("candidate_index")!=i or
                item.get("phoneme_label") is not None or
                item.get("label_status")!="UNLABELLED_AUDIO_CANDIDATE"):
                raise SnippetIntegrityError("Invalid or falsely labeled clip identity")
            a=item.get("start_sample");b=item.get("end_sample_exclusive")
            if (type(a)!=int or type(b)!=int or a<last or b<=a or b>n or
                (b-a)/rate>10):
                raise SnippetIntegrityError("Out-of-order or invalid sample interval")
            start=item.get("start_seconds");end=item.get("end_seconds")
            if (type(start) not in (int,float) or type(end) not in (int,float)
                or not math.isfinite(start) or not math.isfinite(end)
                or abs(start-a/rate)>0.000001 or abs(end-b/rate)>0.000001):
                raise SnippetIntegrityError("Timestamp/sample mismatch in clip provenance")
            wav=folder/name
            if wav.is_symlink() or file_sha256(wav)!=item.get("sha256"):
                raise SnippetIntegrityError("Output clip hash changed")
            with wave.open(str(wav),"rb") as clip:
                if (clip.getnchannels(),clip.getsampwidth(),clip.getframerate(),clip.getnframes())!=(1,2,rate,b-a):
                    raise SnippetIntegrityError("Clip sample rate or shape mismatch")
                audio=clip.readframes(b-a)
            wave_src.setpos(a)
            if wave_src.readframes(b-a)!=audio:
                raise SnippetIntegrityError("Clip PCM contents differ from pinned source samples")
            verified.append({"filename":name,"start_sample":a,"end_sample_exclusive":b,
                             "sha256":item["sha256"],"byte_exact_source_match":True,
                             "phoneme_label_verified":False})
            last=b
    if before!=file_sha256(original):
        raise SnippetIntegrityError("Source WAV changed during verification")
    return {"schema_version":1,"source_sha256":before,"verified_clip_count":len(verified),
            "clips":verified,"structural_integrity_passed":True,
            "phonetic_accuracy_certified":False,"human_approval_required":False}
