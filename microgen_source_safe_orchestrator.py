"""Bounded, source-pinned original MicroGen_AI lecture rendering workspaces.

This is a staging tool, not automatic permission to publish, and it never
calls a fee-bearing synthesis API. PDF geometry does not prove semantic
narration alignment. Source MP4 cannot be used as a WAV provenance oracle.
"""
from __future__ import annotations
import argparse,hashlib,json,math,os,shutil,tempfile,wave
from pathlib import Path
import pymupdf as fitz

class OrchestratorError(ValueError):
    pass

def digest(p):
    hasher=hashlib.sha256()
    with Path(p).open("rb") as inp:
        for chunk in iter(lambda:inp.read(1024*1024),b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def read_json(p):
    def unique(items):
        output={}
        for k,v in items:
            if k in output:raise OrchestratorError("Duplicate JSON field")
            output[k]=v
        return output
    return json.loads(Path(p).read_text(encoding="utf8"),object_pairs_hook=unique)

def atomic_json(p,contents):
    p=Path(p)
    temp=p.with_name(p.name+".new")
    if temp.exists():raise OrchestratorError("Unclean interrupted JSON write")
    try:
        temp.write_text(json.dumps(contents,sort_keys=True,indent=2),encoding="utf8")
        os.replace(temp,p)
    finally:
        if temp.exists():temp.unlink()

def source_audio_inventory(source):
    from microgen_pipeline_completion import production_contract
    src=Path(source).resolve(strict=True)
    contract=production_contract(src)
    rows=[]
    for i in range(1,contract["slide_count"]+1):
        p=src/f"slide{i}.wav"
        if p.is_symlink():raise OrchestratorError("Source WAV symlink rejected")
        rows.append({"slide":i,"present":p.is_file(),
             "sha256":digest(p) if p.is_file() else None})
    return {"contract":contract,"slides":rows,
        "missing":[r["slide"] for r in rows if not r["present"]],
        "wave_provenance_verified":False,"original_assets_modified":False}

def create_workspace(source,destination):
    from microgen_pipeline_completion import _new_stage
    src=Path(source).resolve(strict=True)
    dst=_new_stage(src,destination)
    report=source_audio_inventory(src)
    dst.mkdir(parents=True,exist_ok=False)
    try:
        contract=report["contract"]
        receipt={"version":1,"source_root":str(src),
          "source_pdf_sha256":contract["source_pdf_sha256"],
          "narration_sha256":contract["narration_sha256"],
          "slide_count":contract["slide_count"],"publication_permitted":False}
        atomic_json(dst/"workspace_receipt.json",receipt)
        atomic_json(dst/".microgen_safe_staging.json",
                   {"source_root":str(src),"source_sha256":contract["source_pdf_sha256"]})
    except Exception:
        shutil.rmtree(dst)
        raise
    return {"workspace":str(dst),"receipt":receipt,"source_modified":False}

def verify_workspace(destination):
    dest=Path(destination).resolve(strict=True)
    receipt=read_json(dest/"workspace_receipt.json")
    if set(receipt)!={"version","source_root","source_pdf_sha256","narration_sha256","slide_count","publication_permitted"} or receipt["version"]!=1 or receipt["publication_permitted"] is not False:
        raise OrchestratorError("Invalid workspace receipt")
    src=Path(receipt["source_root"]).resolve(strict=True)
    if dest==src or dest in src.parents or src in dest.parents:
        raise OrchestratorError("Workspace inside source")
    if digest(src/"slides.pdf")!=receipt["source_pdf_sha256"] or digest(src/"script_tts.json")!=receipt["narration_sha256"]:
        raise OrchestratorError("Lecture source has changed since staging")
    marker=read_json(dest/".microgen_safe_staging.json")
    if marker!={"source_root":str(src),"source_sha256":receipt["source_pdf_sha256"]}:
        raise OrchestratorError("Invalid source-bound compositor marker")
    return receipt

def stage_existing_root_wavs(workspace):
    receipt=verify_workspace(workspace)
    src=Path(receipt["source_root"]);root=Path(workspace).resolve(strict=True)
    audio=root/"audio"
    if audio.exists():raise OrchestratorError("Audio stage already exists")
    inventory=source_audio_inventory(src)
    audio.mkdir()
    entries=[]
    try:
        for row in inventory["slides"]:
            if not row["present"]:continue
            from_path=src/f"slide{row['slide']}.wav"
            target=audio/from_path.name
            shutil.copyfile(from_path,target)
            if digest(target)!=row["sha256"]:
                raise OrchestratorError("Source WAV changed during recovery")
            entries.append({"slide":row["slide"],"sha256":row["sha256"],
                            "source":"unchanged_root_wav","speaker_authenticated":False})
        atomic_json(root/"audio_inventory.json",{"entries":entries,
            "missing":inventory["missing"],"speech_correctness_verified":False})
    except Exception:
        shutil.rmtree(audio)
        (root/"audio_inventory.json").unlink(missing_ok=True)
        raise
    verify_workspace(root)
    return {"copied":len(entries),"missing":inventory["missing"],"source_modified":False}

def discover_qa_audio_candidates(source,*,limit=128):
    src=Path(source).resolve(strict=True)
    if type(limit) is not int or not 1<=limit<=512:raise OrchestratorError("Invalid candidate cap")
    items=[]
    for folder in sorted(src.iterdir(),key=lambda p:p.name.casefold()):
        if not folder.is_dir() or folder.is_symlink() or not folder.name.startswith("QA_"):
            continue
        for p in sorted(folder.glob("*.wav")):
            if p.is_symlink() or not p.is_file():continue
            items.append({"relative_path":str(p.relative_to(src)),
                "sha256":digest(p),"narration_binding_verified":False,
                "approved_for_reuse":False})
            if len(items)>limit:raise OrchestratorError("Too many QA WAV candidates")
    return {"candidates":items,"auto_recovered":0,
            "human_review_replaced":False}

def adopt_verified_wav(workspace,slide,offered,*,sha256,narration_sha256):
    receipt=verify_workspace(workspace)
    root=Path(workspace).resolve(strict=True)
    src=Path(receipt["source_root"])
    script=read_json(src/"script_tts.json")["slides"]
    if type(slide) is not int or not 1<=slide<=len(script):
        raise OrchestratorError("Invalid slide number")
    from microgen_pipeline_completion import _tts_digest
    wav=Path(offered).resolve(strict=True)
    if wav.suffix.lower()!=".wav" or wav.is_symlink() or not wav.is_file() or digest(wav)!=sha256 or narration_sha256!=_tts_digest(script[slide-1]):
        raise OrchestratorError("Unverified WAV source and exact narration binding")
    with wave.open(str(wav),"rb") as f:
        seconds=f.getnframes()/f.getframerate()
    if not .05<=seconds<600:raise OrchestratorError("Invalid WAV duration")
    audio=root/"audio"
    if not audio.is_dir():raise OrchestratorError("Audio stage not created")
    output=audio/f"slide{slide}.wav"
    if output.exists() or output.is_symlink():
        raise OrchestratorError("Never overwrite staged audio")
    shutil.copyfile(wav,output)
    if digest(output)!=sha256:
        output.unlink(missing_ok=True)
        raise OrchestratorError("WAV modified during adoption")
    manifest=read_json(root/"audio_inventory.json")
    manifest["entries"].append({"slide":slide,"sha256":sha256,
          "source":"explicit_external_source_binding","speaker_authenticated":False})
    manifest["missing"]=[x for x in manifest["missing"] if x!=slide]
    atomic_json(root/"audio_inventory.json",manifest)
    return {"adopted":slide,"wav_sha256":sha256,"human_speech_quality_verified":False}

def source_bound_timeline(workspace):
    from microgen_pipeline_completion import _timeline
    receipt=verify_workspace(workspace)
    root=Path(workspace).resolve(strict=True)
    tracks=[root/"audio"/f"slide{i}.wav" for i in range(1,receipt["slide_count"]+1)]
    if any(not p.is_file() or p.is_symlink() for p in tracks):
        raise OrchestratorError("Incomplete staged WAV inventory")
    inventory=read_json(root/"audio_inventory.json")
    if inventory["missing"] or len(inventory["entries"])!=receipt["slide_count"]:
        raise OrchestratorError("Unverified audio inventory")
    for i,p in enumerate(tracks,1):
        rows=[x for x in inventory["entries"] if x["slide"]==i]
        if len(rows)!=1 or digest(p)!=rows[0]["sha256"]:
            raise OrchestratorError("Staged audio or manifest tampered")
    timeline=_timeline(root/"audio",receipt["slide_count"])
    atomic_json(root/"measured_timeline.json",timeline)
    return {"duration_seconds":timeline["duration_seconds"],
            "slides":receipt["slide_count"],"speech_word_alignment_verified":False}

def plan_source_bound_cues(workspace,anchors):
    from microgen_pipeline_completion import bind_narration_anchors
    receipt=verify_workspace(workspace);root=Path(workspace).resolve(strict=True)
    src=Path(receipt["source_root"])
    timeline=read_json(root/"measured_timeline.json")
    aligned=bind_narration_anchors(src/"slides.pdf",timeline,anchors)
    converted=[]
    for cue in aligned["cues"]:
        interval=timeline["slide_intervals"][cue["slide"]-1]
        converted.append({**cue,"local_start":round(cue["start_seconds"]-interval["start_seconds"],6),
                          "local_end":round(cue["end_seconds"]-interval["start_seconds"],6)})
    atomic_json(root/"cues.json",{"version":1,"elements":converted,
         "spoken_word_alignment_verified":False,"cue_timestamps_provided_externally":True})
    return {"cue_count":len(converted),"true_spoken_word_alignment_verified":False}

def render_complete_staged_lesson(workspace,*,ffmpeg=None):
    from microgen_production_bridge import render_staged_highlight
    from microgen_quality import check_video
    receipt=verify_workspace(workspace)
    root=Path(workspace).resolve(strict=True)
    src=Path(receipt["source_root"])
    timeline=read_json(root/"measured_timeline.json")
    cue_doc=read_json(root/"cues.json")
    if cue_doc.get("version")!=1 or "elements" not in cue_doc:
        raise OrchestratorError("Missing bounded cue evidence")
    output=root/"rendered";pages=root/"page_pdf"
    if output.exists() or pages.exists():
        raise OrchestratorError("Candidate render already attempted; no overwrite")
    output.mkdir();pages.mkdir()
    results=[]
    with fitz.open(src/"slides.pdf") as original:
        if original.page_count!=receipt["slide_count"]:
            raise OrchestratorError("Slide deck changed")
        for i in range(1,original.page_count+1):
            verify_workspace(root)
            doc=pages/f"slide{i}.pdf"
            with fitz.open() as slice_pdf:
                slice_pdf.insert_pdf(original,from_page=i-1,to_page=i-1)
                slice_pdf.save(doc)
            cues=[{"start_seconds":c["local_start"],"end_seconds":c["local_end"],
                   "box":c["box"]} for c in cue_doc["elements"] if c["slide"]==i]
            vid=output/f"slide{i}.mp4"
            info=render_staged_highlight(doc,root/"audio"/f"slide{i}.wav",
                     cues,vid,ffmpeg_exe=ffmpeg)
            result=check_video(vid)
            if result["seconds"]>=600:
                raise OrchestratorError("Slide output violates absolute duration ceiling")
            results.append({"slide":i,"duration_seconds":result["seconds"],
                            "sha256":result["sha256"],"cues":len(cues)})
    atomic_json(root/"render_receipt.json",{"slides":results,
        "source_pdf_sha256":receipt["source_pdf_sha256"],
        "narration_element_sync_certified":False})
    return {"rendered_slides":len(results),"true_spoken_alignment_verified":False}
