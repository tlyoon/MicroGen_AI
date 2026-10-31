"""Optional offline ASR glossary observations for fourteen candidate WAVs.

Transcription homophones must never be mistaken for established phonetic errors.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from microgen_pronunciation_closed_loop import sha_file
from microgen_offline_neural_voice import inspect_voice_probe

ALIASES = {
1:("length","mass","time"),2:("standard","measurement"),
3:("yard","foot","meter"),4:("light","meter","year"),
5:("earth","atom","scale"),6:("kilogram","planck","mass"),
7:("prototype","clock","cesium"),8:("mass","weight","pound"),
9:("cesium","second","atomic"),10:("time","interval","instant"),
11:("foot","slug","second"),12:("milli","nano","kilo"),
13:("derived","area","speed"),14:("density","aluminum","iron")}
SPELLINGS = {
"planck":("planck","plank"),"cesium":("cesium","caesium","season"),
"meter":("meter","metre","meters"),"foot":("foot","feet"),
"aluminum":("aluminum","aluminium"),"milli":("milli","millimeter","millimeters"),
"nano":("nano","nanosecond","nanoseconds"),
"kilo":("kilo","kilometer","kilometers"),"pound":("pound","pounds"),
"standard":("standard","standards"),"second":("second","seconds")}

class ExpandedAsrError(ValueError): pass

def annotate(slide:int,source_text:str,words:list[str])->dict:
    if (type(slide) is not int or slide not in ALIASES
        or not isinstance(source_text,str) or not isinstance(words,list)
        or len(words)>2500 or any(not isinstance(x,str) or len(x)>80 for x in words)):
        raise ExpandedAsrError("Invalid ASR words or slide ID")
    recognized={w.casefold() for w in words}
    found={k: next((w for w in SPELLINGS.get(k,(k,)) if w in recognized),None)
           for k in ALIASES[slide]}
    hazards=[]
    if re.search(r"\\dot\{C\}|\bC\s+dot\b",source_text) and "circa" in recognized:
        hazards.append("C_DOT_POSSIBLY_PRONOUNCED_CIRCA")
    if re.search(r"\\dot\{y\}|\by\s+dot\b",source_text) and "yay" in recognized:
        hazards.append("Y_DOT_POSSIBLY_PRONOUNCED_YAY")
    return {"slide":slide,"recognized_terms":found,
      "unmatched_terms":[k for k,v in found.items() if v is None],
      "targeted_phonetic_hazards":hazards,
      "ASR_errors_are_not_phonetic_proof":True}

def audit_asr(folder:Path,narration:Path,model_dir:Path,ffmpeg:Path,new_report:Path):
    from vosk import Model,SetLogLevel
    from microgen_offline_vosk_capture import capture_offline_words
    root=Path(folder);narration=Path(narration);model_dir=Path(model_dir)
    ffmpeg=Path(ffmpeg);out=Path(new_report).resolve(strict=False)
    receipt=root/"expanded_neural_qa_receipt.json"
    if (not root.is_dir() or root.is_symlink() or not narration.is_file()
        or not receipt.is_file() or not model_dir.is_dir()
        or not (model_dir/"am").is_dir() or not ffmpeg.is_file()
        or out.exists() or not out.parent.is_dir()
        or any(x.casefold()=="my drive" for x in out.parts)):
        raise ExpandedAsrError("No trustworthy local ASR and new output location")
    n=json.loads(narration.read_text(encoding="utf8"))
    a=json.loads(receipt.read_text(encoding="utf8"))
    if (a.get("status")!="FOURTEEN_REAL_NEURAL_WAV_CANDIDATES_NOT_FORMAL"
        or a.get("slide_count")!=14 or n.get("slide_count")!=14
        or a.get("narration_qa_sha256")!=sha_file(narration)
        or a.get("publication_allowed") is not False
        or n.get("publication_allowed") is not False):
        raise ExpandedAsrError("Full source-locked 14-slide chain required")
    SetLogLevel(-1)
    recognizer_model=Model(str(model_dir))
    rows=[]
    for i,(x,s) in enumerate(zip(a["slides"],n["slides"]),1):
        wav=root/f"slide{i:02d}.wav"
        if (x.get("slide")!=i or s.get("slide")!=i or not wav.is_file()
            or x.get("probe_wav_sha256")!=sha_file(wav)
            or x.get("original_text_sha256")!=s.get("spoken_text_sha256")):
            raise ExpandedAsrError("Audio or original narration provenance changed")
        technical=inspect_voice_probe(wav,min_seconds=20,max_seconds=240)
        decoded=capture_offline_words(wav,recognizer_model,ffmpeg)
        row=annotate(i,s["narration"],[word["word"] for word in decoded["words"]])
        rows.append({**row,"wav_sha256":sha_file(wav),
            "recognized_word_count":len(decoded["words"]),
            "pcm_rms":technical["rms_pcm"],
            "clipped_fraction":technical["saturation_fraction"]})
    report={"schema_version":1,"status":"FOURTEEN_NEURAL_WAV_ASR_ADVISORY",
        "slide_count":14,"slides":rows,
        "audio_receipt_sha256":sha_file(receipt),
        "narration_sha256":sha_file(narration),
        "recognizer_glossary_gaps":sum(len(x["unmatched_terms"]) for x in rows),
        "targeted_hazard_count":sum(len(x["targeted_phonetic_hazards"]) for x in rows),
        "all_phonemes_independently_verified":False,
        "manual_academic_signoff_required":False,
        "formal_voice_authorized":False,
        "publication_allowed":False}
    with out.open("x",encoding="utf8") as stream:json.dump(report,stream,indent=2)
    return report

def main(argv=None):
    p=argparse.ArgumentParser()
    for name in ("folder","narration","model-dir","ffmpeg","new-report"):
        p.add_argument("--"+name,type=Path,required=True)
    x=p.parse_args(argv)
    r=audit_asr(x.folder,x.narration,x.model_dir,x.ffmpeg,x.new_report)
    print(json.dumps({"slides":r["slide_count"],
        "glossary_gaps":r["recognizer_glossary_gaps"],
        "targeted_hazards":r["targeted_hazard_count"],
        "publication_allowed":False}))
    return 0
if __name__=="__main__":raise SystemExit(main())
