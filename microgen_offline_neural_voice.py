"""Cost-free OFFLINE Piper voice feasibility, not formal voice authorization.

Run with the explicitly isolated Piper environment. No downloads, network,
cloud calls, model distribution, release, or protected textbook mutations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

MODEL_BASENAME = "en_US-ljspeech-medium.onnx"
MODEL_NAME = "en_US-ljspeech-medium"
VOICE_PROBE_TEXT = (
    "In mechanics, the three fundamental quantities are length, mass, and time. "
    "A kilogram is a unit of mass, not weight."
)

class OfflineVoiceError(ValueError):
    pass

def digest(path: Path)->str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def inspect_local_voice(model_folder:Path,formal_handoff:Path)->dict:
    folder=Path(model_folder)
    handoff=Path(formal_handoff)
    model=folder/MODEL_BASENAME
    config=folder/(MODEL_BASENAME+".json")
    card=folder/"MODEL_CARD"
    if folder.is_symlink() or not folder.is_dir() or any(
        not f.is_file() or f.is_symlink() for f in (model,config,card,handoff)
    ):
        raise OfflineVoiceError("Complete local original ONNX model/config/card and trusted handoff required")
    initial={str(f):digest(f) for f in (model,config,card,handoff)}
    card_text=card.read_text(encoding="utf8").lower()
    if not all(term in card_text for term in (
        "model card for ljspeech", "license: public domain",
        "trained from scratch", "us english female voice"
    )):
        raise OfflineVoiceError("Voice model license or training declaration unverified")
    meta=json.loads(config.read_text(encoding="utf8"))
    doc=json.loads(handoff.read_text(encoding="utf8"))
    if (meta.get("audio",{}).get("sample_rate")!=22050
        or meta.get("num_speakers")!=1
        or not str(meta.get("language",{}).get("code","")).startswith("en_US")
        or model.stat().st_size < 10000
        or doc.get("status")!="FORMAL_TTS_INPUT_BUNDLE_READY_PRODUCTION_BLOCKED"
        or doc.get("formal_voice_provider") is not None
        or doc.get("formal_voice_name") is not None
        or doc.get("publication_allowed") is not False
        or doc.get("formal_production_ready") is not False
        or doc.get("slide_count")!=8
        or len(doc.get("requests",[]))!=8):
        raise OfflineVoiceError("Voice config or source-narration handoff contract invalid")
    for i,row in enumerate(doc["requests"],1):
        speech=row.get("input_text")
        if (type(row.get("slide")) is not int or row["slide"]!=i
            or not isinstance(speech,str)
            or digest_text(speech)!=row.get("text_sha256")
            or row.get("production_tts_authorized") is not False):
            raise OfflineVoiceError("SHA-pinned input narration is not unmodified")
    if any(digest(Path(p))!=v for p,v in initial.items()):
        raise OfflineVoiceError("Input changed during local voice inspection")
    return {
        "schema_version":1,"status":"OFFLINE_NEURAL_VOICE_MODEL_FEASIBLE_NOT_FORMAL",
        "engine":"piper-tts","model_name":MODEL_NAME,
        "model_sha256":initial[str(model)],"config_sha256":initial[str(config)],
        "model_card_sha256":initial[str(card)],
        "formal_handoff_sha256":initial[str(handoff)],
        "model_card_dataset_license":"public domain",
        "model_card_train_status":"trained from scratch",
        "model_training_license_independently_legal_certified":False,
        "sample_rate_hz":22050,"spoken_slide_count":8,
        "formal_voice_selected":False,"provider_calls":0,
        "publication_allowed":False
    }

def digest_text(value:str)->str:
    return hashlib.sha256(value.encode("utf8")).hexdigest()

def inspect_voice_probe(wav_path:Path,*,min_seconds:float=1,max_seconds:float=30)->dict:
    wav_path=Path(wav_path)
    if not wav_path.is_file() or wav_path.is_symlink():
        raise OfflineVoiceError("Fresh real PCM16 probe WAV required")
    try:
        with wave.open(str(wav_path),"rb") as w:
            sample_rate=w.getframerate()
            channels=w.getnchannels()
            width=w.getsampwidth()
            frames=w.getnframes()
            pcm=w.readframes(frames)
    except (OSError,EOFError,wave.Error) as e:
        raise OfflineVoiceError("Unusable PCM16 wave probe") from e
    seconds=frames/sample_rate if sample_rate else 0
    if (channels!=1 or width!=2 or sample_rate!=22050
        or not min_seconds<=seconds<=max_seconds
        or len(pcm)!=frames*2):
        raise OfflineVoiceError("Model probe WAV shape/duration invalid")
    from array import array
    import math
    data=array("h")
    data.frombytes(pcm)
    rms=math.sqrt(sum(v*v for v in data)/len(data))
    silence=sum(v==0 for v in data)/len(data)
    clipping=sum(abs(v)>=32767 for v in data)/len(data)
    if rms<25 or silence>.995 or clipping>.01:
        raise OfflineVoiceError("Model probe has severe silence/clipping")
    return {"probe_wav_sha256":digest(wav_path),"seconds":round(seconds,3),
            "rms_pcm":round(rms),"digital_silence_fraction":round(silence,5),
            "saturation_fraction":round(clipping,6),
            "pronunciation_acoustically_verified":False}

def run_probe(piper_python:Path,model_folder:Path,formal_handoff:Path,new_dir:Path)->dict:
    info=inspect_local_voice(model_folder,formal_handoff)
    executable=Path(piper_python)
    output=Path(new_dir).resolve(strict=False)
    if (not executable.is_file() or executable.is_symlink()
        or output.exists() or Path(new_dir).is_symlink()
        or not output.parent.is_dir()
        or model_folder.resolve(strict=True) in output.parents
        or any(x.casefold()=="my drive" for x in output.parts)):
        raise OfflineVoiceError("Isolated interpreter and fresh HP output directory required")
    staged=Path(tempfile.mkdtemp(prefix=".microgen-piper-probe-",dir=output.parent))
    try:
        wav=staged/"probe_local_neural_candidate.wav"
        expression=(
            "import sys,wave;"
            "from piper import PiperVoice;"
            "voice=PiperVoice.load(sys.argv[1]);"
            "wf=wave.open(sys.argv[2],'wb');"
            "voice.synthesize_wav(sys.argv[3],wf);wf.close()"
        )
        result=subprocess.run([
            str(executable),"-c",expression,
            str(Path(model_folder)/MODEL_BASENAME),str(wav),VOICE_PROBE_TEXT
        ],capture_output=True,text=True,timeout=180,check=False)
        if result.returncode:
            raise OfflineVoiceError("Offline Piper sample failed: "+result.stderr[-500:])
        probe=inspect_voice_probe(wav)
        if info["model_sha256"]!=digest(Path(model_folder)/MODEL_BASENAME):
            raise OfflineVoiceError("Model tampered during local generation")
        manifest={**info,**probe,
            "status":"OFFLINE_NEURAL_VOICE_PROBE_PASSED_NOT_FORMAL",
            "probe_text":VOICE_PROBE_TEXT,
            "formal_voice_authorized":False,
            "production_wavs_generated":False,
            "provider_calls":0,"publication_allowed":False}
        (staged/"voice_probe_receipt.json").write_text(
            json.dumps(manifest,indent=2),encoding="utf8")
        if output.exists(): raise OfflineVoiceError("Output appeared during local voice test")
        os.rename(staged,output)
        return manifest
    finally:
        if staged.exists():shutil.rmtree(staged)

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--piper-python",type=Path,required=True)
    parser.add_argument("--model-dir",type=Path,required=True)
    parser.add_argument("--formal-handoff",type=Path,required=True)
    parser.add_argument("--new-dir",type=Path,required=True)
    arg=parser.parse_args(argv)
    m=run_probe(arg.piper_python,arg.model_dir,arg.formal_handoff,arg.new_dir)
    print(json.dumps({"status":m["status"],"seconds":m["seconds"],
                      "voice":m["model_name"],"publication_allowed":False}))
    return 0

if __name__=="__main__":raise SystemExit(main())
