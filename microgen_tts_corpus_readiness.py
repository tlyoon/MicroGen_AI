"""Read-only, real-WAV corpus-readiness audit, no fabricated phonetic truth."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from microgen_tts_snippet_integrity import verify_snippets
from microgen_tts_grouped_holdout import partition_corpus

class CorpusAuditError(ValueError):pass
def audit_corpus(entries:list[dict],*,max_sources:int=40)->dict:
    if (not isinstance(entries,list) or not entries or
        type(max_sources)!=int or not 1<=max_sources<=100 or len(entries)>max_sources):
        raise CorpusAuditError("Unbounded or missing corpus sources")
    samples=[];checks=[]
    for entry in entries:
        if not isinstance(entry,dict):raise CorpusAuditError("Invalid source entry")
        source=entry.get("source_wav");directory=entry.get("snippet_directory")
        group=entry.get("source_group_id")
        if (not isinstance(source,str) or not source or
            not isinstance(directory,str) or not directory or
            not isinstance(group,str) or not group.strip()):
            raise CorpusAuditError("Missing source, clip folder or grouping metadata")
        report=verify_snippets(Path(source),Path(directory))
        checks.append({"source_sha256":report["source_sha256"],
                       "verified_clip_count":report["verified_clip_count"],
                       "pcm_source_integrity_passed":True})
        for item in report["clips"]:
            samples.append({"source_wav_sha256":report["source_sha256"],
                            "clip_sha256":item["sha256"],
                            "source_group_id":group,"phoneme_label":None})
    split=partition_corpus(samples)
    blockers=split["scoring_blockers"]
    next_step=("Acquire independent real source/voice groups, not additional slices of this source"
        if not split["grouped_holdout_available"] else
        "Acquire independently verified time-localized phonetic labels without leakage")
    return {"schema_version":1,"sources_verified":checks,"sample_count":len(samples),
            "grouped_holdout":split,"status":"CORPUS_NOT_READY_FOR_PHONETIC_SCORING",
            "phonetic_accuracy_verified":False,"release_gate_modified":False,
            "manual_approval_required_for_development":False,
            "technical_blockers_to_phonetic_benchmark":blockers,
            "next_automated_development_dependency":next_step,"publication_performed":False}

def main(argv=None):
    p=argparse.ArgumentParser(description="Non-publishing real audio corpus audit")
    p.add_argument("source_list_json",type=Path);p.add_argument("new_external_report",type=Path)
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
    result=audit_corpus(entries)
    with output.open("x",encoding="utf8") as f:
        f.write(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"status":result["status"],"clips":result["sample_count"],
                      "sources":len(result["sources_verified"]),
                      "scoring_blockers":result["technical_blockers_to_phonetic_benchmark"],
                      "publication_performed":False}))
    return 0
if __name__=="__main__":raise SystemExit(main())
