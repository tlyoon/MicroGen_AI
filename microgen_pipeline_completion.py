"""Source-safe integration pieces for original MicroGen_AI production workflow.

Physical source WAV/slide evidence and staged outputs only. No background
generation, no paid calls, no Whisper, no publication, and no false
phonetic/word-level synchronization or mathematics verification.
"""
from __future__ import annotations
import hashlib,json,math,re,shutil,subprocess,tempfile,wave
from pathlib import Path
import pymupdf as fitz
from microgen_production_bridge import BridgeError,measured_wav_timeline as _timeline

class CampaignError(ValueError):
    pass

def _finite(x):
    return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)

def _sha(file):
    sha=hashlib.sha256()
    with Path(file).open("rb") as f:
        for chunk in iter(lambda:f.read(2**20),b""):sha.update(chunk)
    return sha.hexdigest()

def _tts_digest(item):
    text=str(item.get("tts_text") or item.get("narration") or "")
    if not text.strip():raise CampaignError("Empty source narration")
    return hashlib.sha256(text.encode("utf8")).hexdigest()

def _new_stage(source,destination):
    source=Path(source).resolve(strict=True)
    dest=Path(destination).resolve(strict=False)
    if (dest==source or source in dest.parents or dest in source.parents or
        dest.exists() or dest.is_symlink()):
        raise CampaignError("Stage must be a new independent directory outside source")
    return dest

def production_contract(source):
    from microgen_production_bridge import inspect_lesson
    p=Path(source)
    evidence=inspect_lesson(p)
    n=evidence["page_count"]
    return {"schema_version":1,"source_root":str(p.resolve()),
       "source_pdf_sha256":evidence["slide_pdf_sha256"],
       "narration_sha256":evidence["narration_sha256"],
       "slide_count":n,"source_audio_complete":evidence["complete_audio_set"],
       "next_action":"PLAN_AND_STAGE" if evidence["complete_audio_set"] else "RECOVER_OR_SYNTHESIZE_MISSING_AUDIO",
       "source_modified":False,"ready_for_publication":False}

def recover_source_bound_wavs(source,stage,entries):
    """Manifest must bind every offered waveform to exactly the current slide text."""
    src=Path(source).resolve(strict=True)
    dest=_new_stage(src,stage)
    data=json.loads((src/"script_tts.json").read_text(encoding="utf8"))
    rows=data["slides"]; n=len(rows)
    if not isinstance(entries,list) or len(entries)!=n:
        raise CampaignError("Full explicit WAV inventory required")
    if sorted(x.get("slide") for x in entries)!=list(range(1,n+1)):
        raise CampaignError("Duplicate, missing, or extra audio slide")
    checked=[]
    for entry in sorted(entries,key=lambda e:e["slide"]):
        number=entry["slide"];origin=Path(entry["path"]).resolve(strict=True)
        expected=_tts_digest(rows[number-1])
        if (origin.suffix.lower()!=".wav" or origin.is_symlink() or
            not origin.is_file() or entry.get("narration_sha256")!=expected or
            entry.get("wav_sha256")!=_sha(origin)):
            raise CampaignError("Untrusted external WAV or narration binding")
        with wave.open(str(origin),"rb") as wav:
            length=wav.getnframes()/wav.getframerate()
        if not _finite(length) or not .05<=length<600:
            raise CampaignError("Invalid WAV evidence")
        checked.append((number,origin))
    # No staging side effects until every source has been verified.
    dest.mkdir(parents=True)
    try:
        for number,origin in checked:
            target=dest/f"slide{number}.wav"
            shutil.copyfile(origin,target)
            if _sha(target)!=_sha(origin):raise CampaignError("WAV changed in copy")
    except Exception:
        shutil.rmtree(dest)
        raise
    return {"audio_stage":str(dest),"slide_count":n,
            "source_bound":True,"source_modified":False}

def produce_spoken_inputs(source):
    from text_to_speech_v25 import normalize_scientific_speech
    p=Path(source)
    data=json.loads((p/"script_tts.json").read_text(encoding="utf8"))
    result=[]
    for index,row in enumerate(data["slides"],1):
        if row.get("slide")!=index:raise CampaignError("Unordered slide narration")
        raw=str(row.get("tts_text") or row.get("narration") or "")
        spoken=normalize_scientific_speech(raw)
        if not raw.strip() or not spoken.strip():
            raise CampaignError("Empty narration")
        result.append({"slide":index,"source_hash":hashlib.sha256(raw.encode()).hexdigest(),
            "speech_input_sha256":hashlib.sha256(spoken.encode()).hexdigest(),
            "speech_input":spoken,"changed":raw!=spoken})
    return {"slides":result,"provider_called":False,
            "phonetic_accuracy_established":False}

def regenerate_staged_wav(source,stage,slide,synthesize,*,voice="en-US-Chirp-HD-F",
                          provider="google_cloud_chirp3",attempts=3):
    src=Path(source).resolve(strict=True)
    dest=_new_stage(src,stage)
    inputs=produce_spoken_inputs(src)["slides"]
    if type(slide) is not int or not 1<=slide<=len(inputs):
        raise CampaignError("Invalid slide")
    if not callable(synthesize) or type(attempts) is not int or not 1<=attempts<=3:
        raise CampaignError("Invalid synthesis backend or retry bound")
    if not isinstance(voice,str) or not voice or not isinstance(provider,str) or not provider:
        raise CampaignError("Voice and provider must be pinned")
    dest.mkdir(parents=True)
    text=inputs[slide-1]["speech_input"]
    statuses=[]
    for attempt in range(1,attempts+1):
        output=dest/f"slide{slide}.attempt{attempt:02d}.wav"
        try:
            metadata=synthesize(text,output,voice=voice,provider=provider)
            if not isinstance(metadata,dict) or metadata.get("voice")!=voice or metadata.get("provider")!=provider:
                raise CampaignError("Mixed TTS voice or provider")
            if not output.is_file() or output.is_symlink():raise CampaignError("Missing generated WAV")
            with wave.open(str(output),"rb") as wav:
                seconds=wav.getnframes()/wav.getframerate()
            if not _finite(seconds) or not .05<=seconds<600:
                raise CampaignError("Invalid regenerated WAV duration")
            statuses.append({"attempt":attempt,"status":"STAGED","wav_sha256":_sha(output)})
            return {"status":"REVIEW_REQUIRED","slide":slide,"output":str(output),
                  "voice":voice,"provider":provider,"attempts":statuses,
                  "pronunciation_verified":False,"source_modified":False}
        except Exception as e:
            statuses.append({"attempt":attempt,"status":"FAILED","error_type":type(e).__name__})
            if output.exists() and not output.is_symlink():output.unlink()
    return {"status":"REGENERATION_FAILED","slide":slide,"attempts":statuses,
        "source_modified":False,"pronunciation_verified":False}

def observe_acoustic_activity(wav_path,*,window_ms=20,floor=.02):
    """Detect amplitude only; no phonetic or word-alignment certification."""
    import struct
    p=Path(wav_path)
    if p.is_symlink() or not p.is_file():raise CampaignError("Actual WAV required")
    if not _finite(floor) or not 0<floor<.8 or window_ms not in (10,20,40):
        raise CampaignError("Invalid audio analysis policy")
    with wave.open(str(p),"rb") as audio:
        if audio.getnchannels()!=1 or audio.getsampwidth()!=2 or not 8000<=audio.getframerate()<=48000:
            raise CampaignError("Mono 16-bit PCM required")
        rate=audio.getframerate();frames=audio.getnframes()
        if frames/rate>600 or frames<=0:raise CampaignError("Unbounded PCM source")
        raw=audio.readframes(frames)
    if len(raw)!=frames*2:raise CampaignError("Incomplete wave data")
    samples=struct.unpack("<"+"h"*frames,raw)
    block=max(1,round(rate*window_ms/1000))
    flags=[]
    for i in range(0,frames,block):
        segment=samples[i:i+block]
        rms=(sum(x*x for x in segment)/len(segment))**.5/32768
        flags.append(rms>=floor)
    intervals=[];left=None
    for j,active in enumerate(flags+[False]):
        if active and left is None:left=j
        if not active and left is not None:
            intervals.append([round(left*block/rate,5),
              round(min(j*block,frames)/rate,5)]);left=None
    return {"activity_intervals_seconds":intervals,
            "sample_rate":rate,"waveform_sha256":_sha(p),
            "phoneme_identity_verified":False,"word_alignment_verified":False}

def bind_narration_anchors(pdf,timeline,anchors):
    from microgen_production_bridge import pdf_element_inventory,validate_highlight_cues
    pages=pdf_element_inventory(pdf)
    if not isinstance(anchors,list) or not anchors:
        raise CampaignError("Explicit narration anchors required")
    cues=[]
    for anchor in anchors:
        if not isinstance(anchor,dict) or set(anchor)!={"slide","word","start_seconds","end_seconds","spoken_phrase"}:
            raise CampaignError("Untrusted anchor schema")
        if type(anchor["slide"]) is not int or not 1<=anchor["slide"]<=len(pages):
            raise CampaignError("Invalid slide anchor")
        words=[w for w in pages[anchor["slide"]-1]["words"] if
                 w["text"].casefold()==anchor["word"].casefold()]
        if len(words)!=1 or not isinstance(anchor["spoken_phrase"],str) or not anchor["spoken_phrase"].strip():
            raise CampaignError("Ambiguous or missing PDF word mapping")
        cues.append({"slide":anchor["slide"],"text":words[0]["text"],
               "box":words[0]["box"],"start_seconds":anchor["start_seconds"],
               "end_seconds":anchor["end_seconds"]})
    result=validate_highlight_cues(cues,pages,timeline)
    return {"cues":cues,"real_pdf_geometry_verified":result["cue_geometry_validated"],
        "narration_phrase_timing_ground_truth_verified":False}

def render_slide_candidate(source,slide,wav_path,cues,stage):
    from microgen_production_bridge import render_staged_highlight
    from microgen_quality import check_video
    src=Path(source).resolve(strict=True)
    outdir=_new_stage(src,stage)
    if type(slide) is not int:raise CampaignError("Invalid slide")
    with fitz.open(src/"slides.pdf") as doc:
        if not 1<=slide<=doc.page_count:raise CampaignError("Slide out of bounds")
        outdir.mkdir(parents=True)
        pages=outdir/"input_pages";pages.mkdir()
        one=pages/f"slide{slide}.pdf"
        with fitz.open() as single:
            single.insert_pdf(doc,from_page=slide-1,to_page=slide-1)
            single.save(one)
    video_dir=outdir/"rendered";video_dir.mkdir()
    media=video_dir/f"slide{slide}.mp4"
    report=render_staged_highlight(one,Path(wav_path),cues,media)
    actual=check_video(media)
    return {"source_pdf_slide":slide,"video_sha256":_sha(media),
      "duration_seconds":actual["seconds"],"cue_count":len(cues),
      "technical_overlay_rendered":True,"real_spoken_word_sync_verified":False,
      "source_modified":False}

def compose_stage_parts(stage,timeline,ffmpeg_exe):
    from microgen_production_bridge import strict_slide_part_plan
    from microgen_quality import check_video
    root=Path(stage).resolve(strict=True)
    plan=strict_slide_part_plan(timeline)
    results=[]
    for part in plan["parts"]:
        number=len(results)+1
        dest=root/f"part{number:02d}.mp4"
        if dest.exists():raise CampaignError("Will not overwrite any video")
        clips=[root/"rendered"/f"slide{i}.mp4" for i in part["slides"]]
        if any(not p.is_file() or p.is_symlink() for p in clips):
            raise CampaignError("Staged slide video missing")
        with tempfile.TemporaryDirectory(prefix="microgen_concat_") as temp:
            listing=Path(temp)/"inputs.txt"
            # Copy all clips to trusted temporary path so concat paths need no quoting.
            items=[]
            for i,clip in enumerate(clips):
                checked=check_video(clip)
                if not 0<checked["seconds"]<600:raise CampaignError("Invalid slide MP4")
                target=Path(temp)/f"{i:04}.mp4"
                shutil.copy2(clip,target)
                items.append(target)
            listing.write_text("\n".join("file '%s'"%p.as_posix() for p in items),encoding="utf8")
            args=[str(ffmpeg_exe),"-nostdin","-loglevel","error","-y","-f","concat",
                  "-safe","0","-i",str(listing),"-c","copy",str(dest)]
            proc=subprocess.run(args,capture_output=True,timeout=120)
            if proc.returncode:raise CampaignError("FFmpeg multipart concat failed")
        out=check_video(dest)
        if out["seconds"]>=600:
            dest.unlink(missing_ok=True)
            raise CampaignError("Part fails absolute video duration contract")
        results.append({"slides":part["slides"],"duration_seconds":out["seconds"],
             "sha256":_sha(dest)})
    return {"parts":results,"all_parts_below_600":True,"published":False}

def candidate_technical_gate(part_reports,*,audio_complete,element_manifest_grounded,
                             academic_review_passed=False,phonetic_review_passed=False):
    if not isinstance(part_reports,list) or not part_reports:
        raise CampaignError("Actual verified candidate parts required")
    for row in part_reports:
        if (not isinstance(row,dict) or
            not _finite(row.get("duration_seconds")) or
            not 0<row["duration_seconds"]<600 or
            not isinstance(row.get("sha256"),str) or len(row["sha256"])!=64):
            raise CampaignError("Invalid part verification evidence")
    blockers=[]
    if not audio_complete:blockers.append("MISSING_SOURCE_BOUND_WAVS")
    if not element_manifest_grounded:blockers.append("NO_GROUNDED_SPEECH_ELEMENT_ALIGNMENT")
    if not academic_review_passed:blockers.append("ACADEMIC_QA_NOT_VERIFIED")
    if not phonetic_review_passed:blockers.append("PRONUNCIATION_NOT_VERIFIED")
    return {"technical_video_durations_pass":True,
        "candidate_parts":len(part_reports),"unresolved_gates":blockers,
        "eligible_for_release":not blockers,"publish_performed":False}
