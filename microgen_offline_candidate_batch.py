"""Generate 8 SHA-bound offline neural WAV CANDIDATES, never silently formal.

Requires real local Piper and prior bounded probe. No cloud, provider fees,
TTS defaults, source edits, or publication.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from microgen_offline_neural_voice import (
    OfflineVoiceError, inspect_local_voice, inspect_voice_probe,
    MODEL_BASENAME, digest, digest_text)

class CandidateBatchError(ValueError):
    pass

def verify_candidate_audio(folder:Path,formal_handoff:Path,voice_probe:Path,model_dir:Path)->dict:
    folder=Path(folder)
    inputs=inspect_local_voice(model_dir,formal_handoff)
    formal=json.loads(Path(formal_handoff).read_text(encoding="utf8"))
    probe=json.loads(Path(voice_probe).read_text(encoding="utf8"))
    if (probe.get("status")!="OFFLINE_NEURAL_VOICE_PROBE_PASSED_NOT_FORMAL"
        or probe.get("model_sha256")!=inputs["model_sha256"]
        or probe.get("formal_handoff_sha256")!=inputs["formal_handoff_sha256"]
        or probe.get("formal_voice_authorized") is not False
        or probe.get("production_wavs_generated") is not False
        or probe.get("publication_allowed") is not False
        or not folder.is_dir() or folder.is_symlink()):
        raise CandidateBatchError("Previous independent local voice probe is not valid")
    probe_wave=Path(voice_probe).parent/"probe_local_neural_candidate.wav"
    if (not probe_wave.is_file() or probe_wave.is_symlink()
        or digest(probe_wave)!=probe["probe_wav_sha256"]):
        raise CandidateBatchError("Actual voice probe WAV lost or changed")
    items=[]
    for i,request in enumerate(formal["requests"],1):
        wav=folder/f"slide{i:02d}.wav"
        if wav.is_symlink() or not wav.is_file():
            raise CandidateBatchError(f"Missing actual slide {i} neural WAV")
        inspected=inspect_voice_probe(wav,min_seconds=20,max_seconds=240)
        if request.get("slide")!=i or digest_text(request["input_text"])!=request["text_sha256"]:
            raise CandidateBatchError("Narration source identity changed")
        items.append({"slide":i,"text_sha256":request["text_sha256"],
            "source_pdf_sha256":request["source_pdf_sha256"],
            "teaching_pdf_sha256":request["teaching_pdf_sha256"],
            "wav_filename":wav.name,**inspected,
            "local_candidate_not_formal":True})
    if len(items)!=8:raise CandidateBatchError("Eight source-aligned WAV candidates required")
    return {"schema_version":1,"status":"EIGHT_OFFLINE_NEURAL_WAV_CANDIDATES_NOT_FORMAL",
      "model_name":inputs["model_name"],"model_sha256":inputs["model_sha256"],
      "voice_model_card_sha256":inputs["model_card_sha256"],
      "probe_receipt_sha256":digest(voice_probe),
      "formal_handoff_sha256":inputs["formal_handoff_sha256"],
      "slide_count":8,"total_duration_seconds":round(sum(x["seconds"] for x in items),3),
      "slides":items,"voice_engine":"piper-tts",
      "acoustic_phoneme_accuracy_proven":False,
      "formal_voice_authorized":False,"production_wavs_generated":False,
      "cloud_provider_calls":0,"publication_allowed":False}

def synthesize_candidate_batch(piper_python:Path,model_dir:Path,formal_handoff:Path,
                               voice_probe:Path,new_dir:Path)->dict:
    info=inspect_local_voice(model_dir,formal_handoff)
    target=Path(new_dir).resolve(strict=False)
    py=Path(piper_python)
    if (not py.is_file() or py.is_symlink() or target.exists()
        or Path(new_dir).is_symlink() or not target.parent.is_dir()
        or Path(model_dir).resolve(strict=True) in target.parents
        or any(part.casefold()=="my drive" for part in target.parts)):
        raise CandidateBatchError("Fresh external HP offline output and Python required")
    probe=json.loads(Path(voice_probe).read_text(encoding="utf8"))
    if (probe.get("model_sha256")!=info["model_sha256"]
        or probe.get("formal_handoff_sha256")!=info["formal_handoff_sha256"]
        or probe.get("status")!="OFFLINE_NEURAL_VOICE_PROBE_PASSED_NOT_FORMAL"):
        raise CandidateBatchError("No complete bound local Piper model preflight")
    order=json.loads(Path(formal_handoff).read_text(encoding="utf8"))
    staged=Path(tempfile.mkdtemp(prefix=".microgen-local-neural-batch-",dir=target.parent))
    try:
        payload=staged/"private_speech_input.json"
        payload.write_text(json.dumps([
            {"slide":row["slide"],"text":row["input_text"]} for row in order["requests"]
        ]),encoding="utf8")
        python_code=(
            "import json,sys,wave,pathlib;"
            "from piper import PiperVoice;"
            "v=PiperVoice.load(sys.argv[1]);"
            "rows=json.load(open(sys.argv[2],encoding='utf8'));"
            "folder=pathlib.Path(sys.argv[3]);"
            "assert len(rows)==8;"
            "\nfor row in rows:"
            "\n p=folder/('slide%02d.wav'%row['slide']);"
            "\n with wave.open(str(p),'wb') as f:v.synthesize_wav(row['text'],f)"
        )
        proc=subprocess.run([str(py),"-c",python_code,
            str(Path(model_dir)/MODEL_BASENAME),str(payload),str(staged)],
            capture_output=True,text=True,timeout=900)
        if proc.returncode:
            raise CandidateBatchError("Local synthesis error: "+proc.stderr[-600:])
        # Input text exists only in original verified private handoff, not the report.
        payload.unlink()
        evidence=verify_candidate_audio(staged,formal_handoff,voice_probe,model_dir)
        if digest(Path(model_dir)/MODEL_BASENAME)!=info["model_sha256"]:
            raise CandidateBatchError("Model changed during offline neural synthesis")
        (staged/"candidate_audio_receipt.json").write_text(
            json.dumps(evidence,indent=2),encoding="utf8")
        if target.exists():raise CandidateBatchError("Output appeared during synthesis")
        os.rename(staged,target)
        return evidence
    finally:
        if staged.exists():shutil.rmtree(staged)

def main(argv=None):
    p=argparse.ArgumentParser()
    for x in ("piper-python","model-dir","formal-handoff","voice-probe","new-dir"):
        p.add_argument("--"+x,required=True,type=Path)
    v=p.parse_args(argv)
    res=synthesize_candidate_batch(v.piper_python,v.model_dir,v.formal_handoff,
                                   v.voice_probe,v.new_dir)
    print(json.dumps({"status":res["status"],"slides":res["slide_count"],
                      "total_seconds":res["total_duration_seconds"],
                      "publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
