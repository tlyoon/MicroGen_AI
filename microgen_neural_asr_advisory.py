"""No-cloud recognizer advisory for real neural narration, never a phonetic veto.

A small ASR model may transcribe "Planck" as "plank" and homophones
incorrectly. Exact text misses are clues, not pronunciation proof.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from microgen_pronunciation_closed_loop import sha_file

KEYWORD_ALIASES = {
  1: {"length":("length",),"mass":("mass",),"time":("time",)},
  2: {"standard":("standard","standards"),"meter":("meter","metre"),"kilogram":("kilogram","kilograms")},
  3: {"light":("light",),"vacuum":("vacuum",),"meter":("meter","metre","meters")},
  4: {"mass":("mass",),"kilogram":("kilogram","kilograms"),"planck":("planck","plank")},
  5: {"prototype":("prototype",),"clock":("clock","clocks"),"cesium":("cesium","caesium","cesium")},
  6: {"cesium":("cesium","caesium"),"second":("second","seconds"),"radiation":("radiation",)},
  7: {"time":("time",),"interval":("interval","intervals"),"nanosecond":("nanosecond","nanoseconds")},
  8: {"density":("density",),"aluminum":("aluminum","aluminium"),"iron":("iron",)}
}
class AdvisoryError(ValueError):pass

def check_terms(slide:int,words:list[str])->dict:
    if type(slide) is not int or slide not in KEYWORD_ALIASES:
        raise AdvisoryError("Unknown slide")
    if not isinstance(words,list) or len(words)>2000 or any(
        not isinstance(w,str) or not w.isascii() or len(w)>80 for w in words):
        raise AdvisoryError("Malformed independent ASR words")
    recognized={s.lower().strip() for s in words}
    detected={}
    for concept,alternatives in KEYWORD_ALIASES[slide].items():
        detected[concept]=next((w for w in alternatives if w in recognized),None)
    return {"slide":slide,"recognizer_key_terms_found":detected,
      "recognizer_unmatched_terms":[x for x,y in detected.items() if y is None],
      "missing_recognizer_terms_prove_mispronunciation":False,
      "acoustic_pronunciation_independently_verified":False}

def run_advisory(audio_dir:Path,formal_handoff:Path,model_dir:Path,
                 ffmpeg_executable:Path,new_report:Path)->dict:
    from vosk import Model,SetLogLevel
    from microgen_offline_vosk_capture import capture_offline_words
    audio_dir=Path(audio_dir);formal_handoff=Path(formal_handoff)
    model_dir=Path(model_dir);ffmpeg_executable=Path(ffmpeg_executable)
    output=Path(new_report).resolve(strict=False)
    if (not audio_dir.is_dir() or audio_dir.is_symlink()
        or not model_dir.is_dir() or model_dir.is_symlink()
        or not (model_dir/"am").is_dir()
        or not ffmpeg_executable.is_file()
        or not formal_handoff.is_file() or formal_handoff.is_symlink()
        or output.exists() or Path(new_report).is_symlink()
        or not output.parent.is_dir()
        or any(x.casefold()=="my drive" for x in output.parts)):
        raise AdvisoryError("Independent local model and fresh external ASR report required")
    ledger_file=audio_dir/"candidate_audio_receipt.json"
    ledger=json.loads(ledger_file.read_text(encoding="utf8"))
    formal=json.loads(formal_handoff.read_text(encoding="utf8"))
    if (ledger.get("status")!="EIGHT_OFFLINE_NEURAL_WAV_CANDIDATES_NOT_FORMAL"
        or ledger.get("formal_handoff_sha256")!=sha_file(formal_handoff)
        or ledger.get("slide_count")!=8 or ledger.get("publication_allowed") is not False
        or formal.get("formal_voice_name") is not None
        or formal.get("publication_allowed") is not False):
        raise AdvisoryError("Only already-verified nonformal neural evidence may be transcribed")
    SetLogLevel(-1)
    model=Model(str(model_dir))
    rows=[]
    for i,clip in enumerate(ledger["slides"],1):
        src=audio_dir/f"slide{i:02d}.wav"
        if (clip.get("slide")!=i or src.is_symlink() or not src.is_file()
            or sha_file(src)!=clip.get("probe_wav_sha256")):
            raise AdvisoryError("Source-bound WAV drift or identity mismatch")
        words=capture_offline_words(src,model,ffmpeg_executable)
        spoken=[w["word"] for w in words["words"]]
        rows.append({**check_terms(i,spoken),"wav_sha256":sha_file(src),
            "recognized_word_count":len(spoken),"spoken_word_content_unverified":True})
    report={"schema_version":1,"status":"OFFLINE_NEURAL_ASR_SPELLING_ADVISORY_NOT_PHONETIC_QA",
       "neural_wav_receipt_sha256":sha_file(ledger_file),
       "formal_handoff_sha256":sha_file(formal_handoff),
       "offline_model_dir_name":model_dir.name,
       "slides":rows,"word_spelling_differences_may_be_homophones":True,
       "manual_approval_required":False,"human_listening_performed":False,
       "formal_voice_authorized":False,"publication_allowed":False}
    with output.open("x",encoding="utf8") as out:json.dump(report,out,indent=2)
    return report

def main(argv=None):
    p=argparse.ArgumentParser()
    for x in ("audio-dir","formal-handoff","model-dir","ffmpeg-executable","new-report"):
        p.add_argument("--"+x,required=True,type=Path)
    a=p.parse_args(argv)
    doc=run_advisory(a.audio_dir,a.formal_handoff,a.model_dir,a.ffmpeg_executable,a.new_report)
    print(json.dumps({"slides":len(doc["slides"]),
        "all_term_gaps":sum(len(x["recognizer_unmatched_terms"]) for x in doc["slides"]),
        "phonetic_certification":False,"publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
