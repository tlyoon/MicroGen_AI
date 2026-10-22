"""Independently revalidate a read-only source WAV discovery snapshot."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from microgen_tts_real_wav_discovery import discover_wavs

class InventoryIntegrityError(ValueError):pass
def revalidate_inventory(snapshot:dict)->dict:
    if not isinstance(snapshot,dict) or snapshot.get("schema_version")!=1:
        raise InventoryIntegrityError("Invalid source inventory schema")
    root=snapshot.get("root")
    rows=snapshot.get("real_wav_candidates")
    if not isinstance(root,str) or not isinstance(rows,list) or len(rows)>80:
        raise InventoryIntegrityError("Missing or unbounded discovery data")
    current=discover_wavs(Path(root))
    if (snapshot.get("candidate_count")!=len(rows) or
        current["candidate_count"]!=len(rows)):
        raise InventoryIntegrityError("Source inventory size drift")
    if (type(snapshot.get("files_skipped")) is not int or
        snapshot["files_skipped"]!=current["files_skipped"] or
        snapshot.get("publication_performed") is not False):
        raise InventoryIntegrityError("Source discovery summary fields changed")
    if (snapshot.get("discovery_complete") is not current["discovery_complete"] or
        snapshot.get("discovery_status")!=current["discovery_status"]):
        raise InventoryIntegrityError("Source discovery coverage statement changed")
    previous={x.get("relative_path"):x for x in rows if isinstance(x,dict)}
    latest={x["relative_path"]:x for x in current["real_wav_candidates"]}
    if len(previous)!=len(rows) or set(previous)!=set(latest):
        raise InventoryIntegrityError("Source WAV set added, removed or duplicated")
    for rel in sorted(latest):
        before=previous[rel];after=latest[rel]
        for key in ("source_wav","source_sha256","source_pcm_sha256",
                    "duration_seconds","inferred_source_group","relative_path"):
            if before.get(key)!=after[key]:
                raise InventoryIntegrityError(f"Stale source inventory field: {rel}:{key}")
        if (before.get("independent_voice_proven") is not False or
            before.get("phoneme_label") is not None):
            raise InventoryIntegrityError("Unverified phoneme labels or voice IDs were asserted")
    if (snapshot.get("independent_source_groups_verified") is not False or
        snapshot.get("phonetic_ground_truth_available") is not False):
        raise InventoryIntegrityError("Source inventory falsely claims phonetic certification")
    return {"schema_version":1,"status":"SOURCE_WAV_INVENTORY_REVALIDATED",
            "source_root":current["root"],"verified_wav_count":len(rows),
            "unique_decoded_pcm_count":len(set(x["source_pcm_sha256"] for x in latest.values())),
            "inventory_complete":current["discovery_complete"],
            "inventory_partial":not current["discovery_complete"],
            "verified_actual_phoneme_labels":0,"independent_voice_groups_proven":False,
            "phonetic_benchmark_ready":False,"publication_performed":False,
            "manual_development_gate_required":False}
def main(argv=None):
    p=argparse.ArgumentParser(description="Revalidate saved real WAV source inventory")
    p.add_argument("inventory_json",type=Path);p.add_argument("new_external_report",type=Path)
    args=p.parse_args(argv)
    snapshot=json.loads(args.inventory_json.read_text(encoding="utf8"))
    root=Path(snapshot["root"]).resolve(strict=True)
    output=args.new_external_report.resolve(strict=False)
    if (output.exists() or output.is_symlink() or not output.parent.is_dir() or
        output==root or root in output.parents or output in root.parents):
        p.error("Output must be a new file outside source directory")
    result=revalidate_inventory(snapshot)
    with output.open("x",encoding="utf8") as f:
        f.write(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"status":result["status"],"wavs":result["verified_wav_count"],
                      "phonetic_benchmark_ready":False}))
    return 0
if __name__=="__main__":raise SystemExit(main())
