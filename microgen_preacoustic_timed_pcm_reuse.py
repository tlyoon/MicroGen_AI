"""Source- and voice-bound reuse of original pre-acoustic measured PCM.

Production TTS-stage fallback ONLY for a new, separately authorized HP
private campaign after a prior accepted acoustic whole-slide correction left
its measured cue manifest stale and blocked video. Original source and
existing successful QA evidence remain immutable. The old 88 PCM chunks
reconstruct the initial whole-slide WAVs byte-exactly; the *new* campaign
must still perform independent acoustic QA, any <=2 slide cue repair, and
decoded synchronized video QA. No historical acoustic approval is imported.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import tempfile

from microgen_verified_tts_reuse import (
    OWNER, SOURCE, MATH_POLICY, TIMED, DIRS,
    _read, _sha, _inventory, _verify, MAX_BYTES, MAX_FILES,
)

RECEIPT=".microgen_preacoustic_pcm_recovery.json"
# Speech-producing algorithms and voice policy MUST remain byte-identical.
# Changes to the PDF/PCM validators are allowed ONLY because the recovered
# candidate is re-proven under the NEW strict source/geometry/math verifier.
SPEECH_PRODUCER=(
    "text_to_speech_v25.py",
    "microgen_flash_tts.py",
    "microgen_timed_cue_planner.py",
    "microgen_cue_semantic_mapping.py",
    "microgen_reviewed_math_voice.py",
    "microgen_tts_provenance.py",
    "microgen_worked_equation_recovery.py",
    "microgen_private_dev_policy.py",
    "microgen_campaign_authorization.py",
)
MAX_CHANGED_SLIDES=2
MAX_CHANGED_CUES=12


class PreAcousticReuseError(RuntimeError):
    pass


# These exact routines are readers/verifiers, never paid speech producers.
# Fail if ANY other code inside their modules changed since old synthesis.
VERIFIER_ONLY_UPGRADES={
    "microgen_timed_cue_tts.py":{"_verified_plan"},
    "microgen_source_math_cue.py":{"verified_source_math_row"},
    "microgen_timed_highlight_contract.py":{
        "_equivalent_text","inspect_timed_highlights",
    },
}


def _unchanged_except_verifiers(old:Path,new:Path,ignored:set[str])->bool:
    if (not old.is_file() or not new.is_file() or
            old.is_symlink() or new.is_symlink()):
        return False
    try:
        def protected_ast(path):
            tree=ast.parse(path.read_text(encoding="utf8"))
            tree.body=[
                node for node in tree.body
                if not (isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
                        and node.name in ignored)
            ]
            return ast.dump(tree,include_attributes=False)
        return protected_ast(old)==protected_ast(new)
    except (OSError,UnicodeError,SyntaxError):
        return False


def _same_source_and_speech_producer(old:Path,stage:Path)->bool:
    return (
        all((old/name).is_file() and (stage/name).is_file()
            and not (old/name).is_symlink()
            and not (stage/name).is_symlink()
            and _sha(old/name)==_sha(stage/name)
            for name in SOURCE+SPEECH_PRODUCER)
        and all(_unchanged_except_verifiers(
            old/name,stage/name,ignored)
            for name,ignored in VERIFIER_ONLY_UPGRADES.items())
    )


def _original_pcm_candidate(old:Path,new_stage:Path,candidate:Path,count:int):
    from microgen_flash_tts import _merge_wavs
    from microgen_tts_provenance import make_record,write_manifest
    from microgen_autonomous_acoustic_gate import _normalized
    from microgen_timed_highlight_contract import inspect_timed_highlights

    if not _same_source_and_speech_producer(old,new_stage):
        raise PreAcousticReuseError("Voice producer or source policy changed")
    _, inventory = _inventory(old,count)
    for name in SOURCE:
        shutil.copy2(new_stage/name,candidate/name)
    for name in MATH_POLICY:
        shutil.copy2(old/name,candidate/name)
    # First revalidate the authentic historical plan and original exact
    # math-policy bytes. Only after the old cue audio checks pass may the
    # validator-only policy hash be rebound to the new, independently
    # rederived PDF/math source. No cue content or TTS text changes.
    shutil.copy2(old/TIMED[0],candidate/TIMED[0])
    for n in range(1,count+1):
        if (_sha(old/f"slide{n}.pdf")!=_sha(new_stage/f"slide{n}.pdf")):
            raise PreAcousticReuseError("Source slide PDF not identical")
        shutil.copy2(new_stage/f"slide{n}.pdf",candidate/f"slide{n}.pdf")
    for name,digest in inventory.items():
        target=candidate/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(old/name,target)
        if _sha(target)!=digest:
            raise PreAcousticReuseError("Old audio inventory changed during copy")

    manifest=json.loads((candidate/TIMED[1]).read_text(encoding="utf8"))
    provenance=json.loads((candidate/TIMED[2]).read_text(encoding="utf8"))
    texts=_normalized(candidate)
    if (not isinstance(texts,list) or len(texts)!=count
            or not isinstance(provenance,dict)
            or not isinstance(provenance.get("slides"),list)
            or len(provenance["slides"])!=count):
        raise PreAcousticReuseError("Invalid narration or voice provenance")
    records=provenance["slides"]
    changed=[]
    total_cues=0
    for row in manifest["slides"]:
        n=row["slide"]
        original=_merge_wavs(
            [(candidate/cue["audio_chunk"]).read_bytes()
             for cue in row["cues"]])
        if hashlib.sha256(original).hexdigest()!=row["slide_wav_sha256"]:
            raise PreAcousticReuseError("Original cue PCM cannot reconstruct WAV")
        if _sha(candidate/f"slide{n}.wav")!=row["slide_wav_sha256"]:
            changed.append(n)
            total_cues+=len(row["cues"])
            (candidate/f"slide{n}.wav").write_bytes(original)
            previous=records[n-1]
            records[n-1]=make_record(
                slide=n,path=candidate/f"slide{n}.wav",text=texts[n-1],
                provider=previous["provider"],key=previous["key"],
                voice_name=previous["voice_name"],
                language_code=previous["language_code"],
                speaking_rate=previous["speaking_rate"],
                location=previous["location"])
            (candidate/".microgen_tts_cache"/f"slide{n}.json").write_text(
                json.dumps(records[n-1],indent=2),encoding="utf8")
    if not 1<=len(changed)<=MAX_CHANGED_SLIDES or total_cues>MAX_CHANGED_CUES:
        raise PreAcousticReuseError("Unexpected prior whole-slide repair scope")
    write_manifest(candidate,records,texts)
    if inspect_timed_highlights(candidate)["slide_count"]!=count:
        raise PreAcousticReuseError("Restored original measured PCM invalid")
    _verify(candidate,count)  # Historic original source math policy proof.

    # The new policy differs only in verifier functions, as proved by AST
    # comparison above. Re-attest ALL source math cues against the same PDF
    # with new exact character decoding and a new code SHA; do not borrow
    # old code-approval metadata or alter any spoken/PDF/cue content.
    previous_plan=json.loads(
        (candidate/TIMED[0]).read_text(encoding="utf8"))
    new_sha=_sha(new_stage/"microgen_source_math_cue.py")
    recovered=previous_plan.get("automatic_math_recovery")
    if (not isinstance(recovered,dict) or
            recovered.get("math_policy_sha256") !=
            _sha(candidate/"microgen_source_math_cue.py")):
        raise PreAcousticReuseError("Old mathematical source policy unbound")
    recovered["math_policy_sha256"]=new_sha
    if (new_stage/TIMED[0]).is_file():
        stage_plan=json.loads((new_stage/TIMED[0]).read_text(encoding="utf8"))
        if stage_plan!=previous_plan:
            raise PreAcousticReuseError("Independent new cue plan differs")
    shutil.copy2(new_stage/"microgen_source_math_cue.py",
                 candidate/"microgen_source_math_cue.py")
    (candidate/TIMED[0]).write_text(
        json.dumps(previous_plan,indent=2,ensure_ascii=False),
        encoding="utf8")
    _verify(candidate,count)  # New strict producer-source/math proof.
    return inventory,changed,total_cues


def maybe_reuse_preacoustic_timed_pcm(
    stage:Path,*,work_root:Path,source_sha:str,cp:dict,
    checkpoint_path:Path,mark_complete,stage_valid,dest:Path,
)->dict|None:
    """No-provider attempt at legitimate normal TTS stage boundary.

    Only new accepted-source campaigns with explicit original private HP
    grants are eligible. Any data uncertainty returns None (normal bounded
    TTS path) or raises a deterministic safety hold before copying anything.
    """
    stage=Path(stage)
    work_root=Path(work_root)
    root=work_root.parent
    if (os.name!="nt" or socket.gethostname().casefold()!="hp"
            or stage.parent!=work_root or
            root!=Path(os.environ.get("LOCALAPPDATA","/unavailable"))/
                 "MicroGen_AI_Checkpoints"):
        return None
    new_grant=_read(work_root/OWNER)
    if (new_grant is None or new_grant.get("publication_authorized") is not False
            or new_grant.get("scope",{}).get("host")!="hp"
            or new_grant.get("scope",{}).get("source_sha256")!=source_sha
            or new_grant.get("scope",{}).get("stop_after")!="acceptance"
            or new_grant.get("scope",{}).get("work_root")!=str(work_root)
            or new_grant.get("scope",{}).get("code_revision")!=cp.get("package_commit")
            or _sha(stage/"source.pdf")!=source_sha
            or not all(cp.get("completed",{}).get(name) for name in (
                "figure_extraction","figure_mapping","figure_merge",
                "slides","narration","science_qa"))):
        return None
    if ((stage/RECEIPT).exists()
            or any((stage/name).exists() for name in TIMED[1:]+DIRS)
            or list(stage.glob("slide*.wav"))):
        return None

    def voice_env(scope):
        raw=scope.get("provider_environment")
        if not isinstance(raw,dict):return None
        return {key:value for key,value in raw.items()
                if key not in ("MICROGEN_ACOUSTIC_MODEL_A",
                               "MICROGEN_ACOUSTIC_MODEL_B")}

    new_voice_environment=voice_env(new_grant.get("scope",{}))
    if new_voice_environment is None:
        return None
    from microgen_quality import check_slide_pdf
    from microgen_autonomous_acoustic_gate import verify_receipt
    count=check_slide_pdf(stage/"slides.pdf",require_footer=True)["pages"]
    compatible=[]
    for campaign in root.iterdir():
        if campaign==work_root or campaign.is_symlink() or not campaign.is_dir():
            continue
        old_grant=_read(campaign/OWNER)
        if (old_grant is None or old_grant.get("publication_authorized") is not False
                or old_grant.get("scope",{}).get("host")!="hp"
                or old_grant.get("scope",{}).get("work_root")!=str(campaign)
                or old_grant.get("scope",{}).get("source_sha256")!=source_sha
                or voice_env(old_grant.get("scope",{}))!=new_voice_environment):
            continue
        old=campaign/stage.name
        old_cp=_read(old/".microgen_checkpoint.json")
        if (old_cp is None
                or old_cp.get("package_commit")!=old_grant["scope"].get("code_revision")
                or not all(old_cp.get("completed",{}).get(n)
                           for n in ("tts","acoustic_qa"))
                or not _same_source_and_speech_producer(old,stage)):
            continue
        try:
            asr=verify_receipt(old)
            if not 1<=asr["repaired_audio_slides"]<=MAX_CHANGED_SLIDES:
                continue
            if not (old/TIMED[0]).is_file():
                continue
            if ((stage/TIMED[0]).exists() and
                    _sha(old/TIMED[0])!=_sha(stage/TIMED[0])):
                continue
            if not all((old/f"slide{i}.pdf").is_file()
                       and (stage/f"slide{i}.pdf").is_file()
                       and _sha(old/f"slide{i}.pdf")==_sha(stage/f"slide{i}.pdf")
                       for i in range(1,count+1)):
                continue
            _, inventory=_inventory(old,count)
            compatible.append(
                (old_cp["completed"]["acoustic_qa"],old,len(inventory)))
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):
            continue
    if not compatible:
        return None
    compatible.sort(key=lambda item:item[0],reverse=True)
    if len(compatible)>1 and compatible[0][0]==compatible[1][0]:
        raise PreAcousticReuseError("Ambiguous equally recent repaired acoustic stages")
    _, old,_=compatible[0]
    with tempfile.TemporaryDirectory(prefix=".microgen-preasr-timed-",
                                     dir=work_root) as tmp:
        prepared=Path(tmp)
        inventory,changed,cues=_original_pcm_candidate(old,stage,prepared,count)
        # This is an old audio restoration, NOT the new approved repair.
        # Verify original cue input under new code before any stage mutation.
        from microgen_verified_tts_reuse import _verify
        _verify(prepared,count)
        from microgen_exclusive_audio_import import (
            import_verified_audio_assets,
        )
        receipt={
            "schema_version":1,
            "status":"ORIGINAL_MEASURED_PCM_RESTORED_ASR_REQUIRED",
            "source_sha256":source_sha,
            "old_campaign":old.parent.name,
            "original_timed_manifest_sha256":_sha(prepared/TIMED[1]),
            "rebound_math_source_plan_sha256":_sha(prepared/TIMED[0]),
            "restored_slide_numbers":changed,
            "restored_timed_cues":cues,
            "old_acoustic_approval_reused":False,
            "paid_provider_calls_made":False,
            "publication_allowed":False,
        }
        (prepared/RECEIPT).write_text(
            json.dumps(receipt,indent=2),encoding="utf8")
        assets={name:prepared/name for name in inventory}
        if not (stage/TIMED[0]).exists():
            assets[TIMED[0]]=prepared/TIMED[0]
        assets[RECEIPT]=prepared/RECEIPT

        def accept_private_pcm():
            _verify(stage,count)
            if not stage_valid(stage,"tts",dest):
                raise PreAcousticReuseError("New-code old-PCM TTS stage failed")
            mark_complete(cp,checkpoint_path,"tts",stage)

        # Fsync journal first; crash and exception injection must never
        # leave a half-imported audio inventory that triggers paid replay.
        import_verified_audio_assets(stage,assets,accept_private_pcm)
    return {
        "status":"ORIGINAL_MEASURED_PCM_RESTORED_ASR_REQUIRED",
        "from":old.parent.name,
        "restored_slide_numbers":changed,
        "restored_cues":cues,
        "old_acoustic_approval_reused":False,
        "new_provider_calls":False,
    }
