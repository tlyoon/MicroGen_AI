"""Recover provisional per-slide WAVs from a verified original MP4 in staging.

Video scene changes are NOT word boundaries. This recovery retains the
original audio (including pronunciation errors); none of these clips are
approved as original TTS recordings or publication-ready.
"""
from __future__ import annotations
import math
import subprocess
import tempfile
import wave
from pathlib import Path
from microgen_quality import check_video
from microgen_source_safe_orchestrator import (
    OrchestratorError, atomic_json, digest, read_json, verify_workspace,
)

class LegacyRecoveryError(OrchestratorError):
    pass

def _number(x):
    return type(x) in (int,float) and math.isfinite(x)

def inspect_legacy_scene_receipt(workspace):
    receipt=verify_workspace(workspace)
    src=Path(receipt["source_root"]).resolve(strict=True)
    video=src/"slides.mp4"
    evidence_path=src/".microgen_legacy_video_evidence.json"
    if any(p.is_symlink() or not p.is_file() for p in (video,evidence_path)):
        raise LegacyRecoveryError("Regular MP4 and source-specific scene receipt required")
    evidence=read_json(evidence_path)
    if evidence.get("status")!="VIDEO_CANDIDATE_PASS_NOT_PUBLISHED":
        raise LegacyRecoveryError("Untrusted scene receipt state")
    sha=digest(video)
    if evidence.get("corrected_mp4_sha256")!=sha:
        raise LegacyRecoveryError("Source video SHA mismatch")
    if evidence.get("old_media_sha256",{}).get("corrected_pdf")!=receipt["source_pdf_sha256"]:
        raise LegacyRecoveryError("PDF fingerprint mismatch")
    prov=evidence.get("source_provenance",{})
    n=receipt["slide_count"]
    if prov.get("expected_pages")!=n or prov.get("narration_sidecar_sha256")!=receipt["narration_sha256"]:
        raise LegacyRecoveryError("Narration or page inventory differs")
    scenes=evidence.get("candidate_video_verification",{}).get("corrected_scene_validation")
    if not isinstance(scenes,list) or len(scenes)!=n or any(
       not isinstance(s,dict) or s.get("scene")!=i or s.get("matching_pdf_page")!=i
       for i,s in enumerate(scenes,1)):
        raise LegacyRecoveryError("Source slide-to-scene mapping missing")
    changes=evidence.get("video_slide_boundaries_seconds")
    duration=evidence.get("candidate_seconds")
    if not isinstance(changes,list) or len(changes)!=n-1 or not _number(duration) or not 0<duration<600:
        raise LegacyRecoveryError("Missing bounded scene timing")
    edges=[0.,*changes,float(duration)]
    if n>128 or any(not _number(x) for x in edges) or any(b-a<0.10 for a,b in zip(edges,edges[1:])):
        raise LegacyRecoveryError("Nonmonotone or unbounded scene timing")
    actual=check_video(video)
    if abs(actual["seconds"]-duration)>.25:
        raise LegacyRecoveryError("Source MP4 duration differs from receipt")
    return {"mp4_path":str(video),"mp4_sha256":sha,
      "evidence_sha256":digest(evidence_path),"scene_edges_seconds":edges,
      "slide_count":n,"actual_duration_seconds":actual["seconds"],
      "scene_timing_only":True,"word_alignment_verified":False,
      "phonetic_accuracy_verified":False,"ready_for_publication":False}

def recover_legacy_scene_wavs(workspace,*,ffmpeg):
    root=Path(workspace).resolve(strict=True)
    proof=inspect_legacy_scene_receipt(root)
    audio=root/"audio"
    inventory_path=root/"audio_inventory.json"
    expected=list(range(1,proof["slide_count"]+1))
    if not audio.is_dir() or audio.is_symlink() or not inventory_path.is_file():
        raise LegacyRecoveryError("Preflight staging with empty audio inventory first")
    old=read_json(inventory_path)
    if old.get("entries")!=[] or old.get("missing")!=expected or any(audio.iterdir()):
        raise LegacyRecoveryError("Mixed previous audio not allowed")
    ffmpeg_path=Path(ffmpeg)
    if not ffmpeg_path.is_file():
        raise LegacyRecoveryError("Explicit local ffmpeg executable missing")
    video=Path(proof["mp4_path"])
    paths=[]
    with tempfile.TemporaryDirectory(prefix="microgen_demux_",dir=str(root)) as tmp:
        pcm_path=Path(tmp)/"audio.wav"
        cmd=[str(ffmpeg_path),"-nostdin","-hide_banner","-loglevel","error",
             "-n","-i",str(video),"-map","0:a:0","-vn","-ac","1",
             "-ar","16000","-c:a","pcm_s16le","-f","wav",str(pcm_path)]
        try:
            result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
        except (OSError,subprocess.TimeoutExpired) as e:
            raise LegacyRecoveryError("FFmpeg decode unavailable or timeout") from e
        if result.returncode or not pcm_path.is_file() or pcm_path.stat().st_size>45_000_000:
            raise LegacyRecoveryError("AAC decoding failed or exceeded size budget")
        with wave.open(str(pcm_path),"rb") as w:
            frames=w.getnframes()
            if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getframerate()!=16000:
                raise LegacyRecoveryError("Unexpected PCM format")
            if not frames or frames>16000*600:
                raise LegacyRecoveryError("Decoded PCM exceeds budget")
            overhang=frames/16000-proof["actual_duration_seconds"]
            if overhang < -.25 or overhang > 3.0:
                raise LegacyRecoveryError("Decoded PCM differs excessively from video")
            raw=w.readframes(frames)
        if len(raw)!=frames*2:
            raise LegacyRecoveryError("Truncated PCM")
        video_end_tick=min(frames,round(proof["actual_duration_seconds"]*16000))
        ticks=[round(t*16000) for t in proof["scene_edges_seconds"][:-1]]+[video_end_tick]
        if ticks[-2]>=video_end_tick or any(a>=b for a,b in zip(ticks,ticks[1:])):
            raise LegacyRecoveryError("Scene transition exceeds PCM samples")
        records=[]
        tail_info={"tail_seconds":0.0,"tail_sha256":None,"requires_review":False}
        try:
            for i,(a,b) in enumerate(zip(ticks,ticks[1:]),1):
                dst=audio/f"slide{i}.wav"
                if dst.exists() or dst.is_symlink():
                    raise LegacyRecoveryError("Refuse overwrite")
                with wave.open(str(dst),"wb") as w:
                    w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
                    w.writeframes(raw[2*a:2*b])
                paths.append(dst)
                records.append({"slide":i,"sha256":digest(dst),
                  "source":"legacy_mp4_aac_demux_scene_partition",
                  "start_seconds":round(a/16000,6),
                  "end_seconds":round(b/16000,6),
                  "duration_seconds":round((b-a)/16000,6),
                  "speaker_authenticated":False,"phonemes_verified":False})
            if frames>video_end_tick:
                tail=audio/"audio_after_video_end.wav"
                with wave.open(str(tail),"wb") as w:
                    w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
                    w.writeframes(raw[2*video_end_tick:2*frames])
                paths.append(tail)
                import array
                values=array.array("h")
                values.frombytes(raw[2*video_end_tick:2*frames])
                rms=(sum(x*x for x in values)/len(values))**.5/32768 if values else 0.
                tail_info={"tail_seconds":round((frames-video_end_tick)/16000,6),
                    "tail_sha256":digest(tail),"tail_rms":round(rms,6),
                    "requires_review":True,"acoustic_energy_present":rms>=.02,
                    "speech_content_known":False}
            if digest(video)!=proof["mp4_sha256"]:
                raise LegacyRecoveryError("Source MP4 changed during demux")
            verify_workspace(root)
            receipt={"version":1,"status":"PROVISIONAL_NOT_PUBLISHABLE",
                "scene_evidence":proof,"clips":records,
                "audio_beyond_video_end":tail_info,
                "legacy_speech_retained":True,"original_tts_wavs_recreated":False,
                "word_alignment_verified":False,"pronunciation_verified":False,
                "publication_allowed":False,"source_modified":False}
            atomic_json(root/"legacy_mp4_audio_receipt.json",receipt)
            atomic_json(inventory_path,{"entries":[{"slide":r["slide"],
                "sha256":r["sha256"],"source":r["source"],
                "speaker_authenticated":False} for r in records],
                "missing":[],"speech_correctness_verified":False,
                "audio_from_legacy_mp4":True})
        except Exception:
            for path in paths:path.unlink(missing_ok=True)
            (root/"legacy_mp4_audio_receipt.json").unlink(missing_ok=True)
            raise
    return {"status":"PROVISIONAL_LEGACY_AUDIO_AVAILABLE","wav_count":len(records),
        "total_seconds":round(sum(x["duration_seconds"] for x in records),4),
        "audio_overhang_seconds":tail_info["tail_seconds"],
        "overhang_rms":tail_info.get("tail_rms"),
        "overhang_acoustic_energy_present":tail_info.get("acoustic_energy_present",False),
        "overhang_requires_listening_review":tail_info["requires_review"],
        "source_mp4_sha256":proof["mp4_sha256"],
        "audio_source":"AAC decoded from historical MP4 at video scene boundaries",
        "phonetic_accuracy_verified":False,"true_word_alignment_verified":False,
        "ready_for_publication":False,"source_modified":False}
