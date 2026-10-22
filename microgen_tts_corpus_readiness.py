"""Read-only, real-WAV corpus-readiness audit, no fabricated phonetic truth."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from microgen_tts_snippet_integrity import verify_snippets
from microgen_tts_grouped_holdout import partition_corpus
from microgen_tts_audio_identity import decoded_pcm_sha256
from microgen_tts_clip_quality import screen_clip
from microgen_tts_inventory_integrity import revalidate_inventory

class CorpusAuditError(ValueError):pass
def audit_corpus(entries:list[dict],*,max_sources:int=40,
                 inventory_snapshot:dict|None=None)->dict:
    if (not isinstance(entries,list) or not entries or
        type(max_sources)!=int or not 1<=max_sources<=100 or len(entries)>max_sources):
        raise CorpusAuditError("Unbounded or missing corpus sources")
    inventory_ok=False;allowed_sources={}
    if inventory_snapshot is not None:
        result=revalidate_inventory(inventory_snapshot)
        if not result["inventory_complete"]:
            raise CorpusAuditError("Incomplete source inventory cannot authorize corpus evidence")
        for row in inventory_snapshot["real_wav_candidates"]:
            allowed_sources[str(Path(row["source_wav"]).resolve(strict=True))]=row
        inventory_ok=True
    samples=[];checks=[];clip_diagnostics=[];low_signal=0
    for entry in entries:
        if not isinstance(entry,dict):raise CorpusAuditError("Invalid source entry")
        source=entry.get("source_wav");directory=entry.get("snippet_directory")
        group=entry.get("source_group_id")
        if (not isinstance(source,str) or not source or
            not isinstance(directory,str) or not directory or
            not isinstance(group,str) or not group.strip()):
            raise CorpusAuditError("Missing source, clip folder or grouping metadata")
        if inventory_ok and str(Path(source).resolve(strict=True)) not in allowed_sources:
            raise CorpusAuditError("Corpus source absent from validated WAV inventory")
        report=verify_snippets(Path(source),Path(directory))
        if inventory_ok and allowed_sources[str(Path(source).resolve(strict=True))]["source_sha256"]!=report["source_sha256"]:
            raise CorpusAuditError("Corpus source checksum differs from authorized inventory")
        pcm_id=decoded_pcm_sha256(Path(source))
        checks.append({"pcm_sha256":pcm_id,"source_sha256":report["source_sha256"],
                       "verified_clip_count":report["verified_clip_count"],
                       "pcm_source_integrity_passed":True})
        for item in report["clips"]:
            quality=screen_clip(Path(directory)/item["filename"])
            if quality["wav_sha256"]!=item["sha256"]:
                raise CorpusAuditError("Clip changed between PCM and quality verification")
            if quality["dataset_readiness_blockers"]:
                low_signal+=1
            clip_diagnostics.append({"source_sha256":report["source_sha256"],
                                     "clip_sha256":item["sha256"],
                                     "signal_quality":quality})
            clip_pcm_id=decoded_pcm_sha256(Path(directory)/item["filename"])
            samples.append({"clip_pcm_sha256":clip_pcm_id,
                            "source_pcm_sha256":pcm_id,
                            "source_wav_sha256":report["source_sha256"],
                            "clip_sha256":item["sha256"],
                            "source_group_id":group,"phoneme_label":None})
    split=partition_corpus(samples)
    blockers=list(split["scoring_blockers"])
    if low_signal:blockers.append("LOW_INFORMATION_AUDIO_CLIPS")
    if not inventory_ok:blockers.append("SOURCE_INVENTORY_NOT_CROSSCHECKED")
    next_step=("Acquire independent real source/voice groups, not additional slices of this source"
        if not split["grouped_holdout_available"] else
        "Acquire independently verified time-localized phonetic labels without leakage")
    return {"schema_version":1,"sources_verified":checks,"sample_count":len(samples),
            "grouped_holdout":split,"source_inventory_revalidated":inventory_ok,
            "clip_signal_diagnostics":clip_diagnostics,
            "low_information_clip_count":low_signal,
            "status":"CORPUS_NOT_READY_FOR_PHONETIC_SCORING",
            "phonetic_accuracy_verified":False,"release_gate_modified":False,
            "manual_approval_required_for_development":False,
            "technical_blockers_to_phonetic_benchmark":blockers,
            "next_automated_development_dependency":next_step,"publication_performed":False}

def main(argv=None):
    p=argparse.ArgumentParser(description="Non-publishing real audio corpus audit")
    p.add_argument("source_list_json",type=Path);p.add_argument("new_external_report",type=Path)
    p.add_argument("--inventory",type=Path,help="Optional independently revalidated original WAV inventory")
    args=p.parse_args(argv)
    entries=json.loads(args.source_list_json.read_text(encoding="utf8"))
    if not isinstance(entries,list):p.error("Source list must be JSON array")
    output=args.new_external_report.resolve(strict=False)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        p.error("Output path must be unused in existing external folder")
    for item in entries:
        if isinstance(item,dict):
            for key in ("source_wav","snippet_directory"):
                value=item.get(key)
                if isinstance(value,str):
                    parent=Path(value).resolve(strict=True)
                    parent=parent.parent if key=="source_wav" else parent
                    if output==parent or parent in output.parents or output in parent.parents:
                        p.error("Report cannot be inside or above source/clip directories")
    inventory=json.loads(args.inventory.read_text(encoding="utf8")) if args.inventory else None
    result=audit_corpus(entries,inventory_snapshot=inventory)
    with output.open("x",encoding="utf8") as f:
        f.write(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"status":result["status"],"clips":result["sample_count"],
                      "sources":len(result["sources_verified"]),
                      "scoring_blockers":result["technical_blockers_to_phonetic_benchmark"],
                      "publication_performed":False}))
    return 0
if __name__=="__main__":raise SystemExit(main())
