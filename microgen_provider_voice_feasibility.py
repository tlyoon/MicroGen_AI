"""Offline, source-bound narrator feasibility; NO provider calls."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import wave
from pathlib import Path
import pymupdf as fitz

ORIGINAL_VOICE="en-US-Chirp-HD-F"
DIAGNOSTIC_VOICE="Microsoft Zira Desktop"
SOURCE_EXCERPT="In mechanics, the three fundamental quantities are length, mass, and time."
class VoiceFeasibilityError(ValueError):
    pass

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def normalize(text):
    return re.sub("[^a-z0-9]","",text.casefold())

def check_diagnostic(source, audio, *, production_voice=ORIGINAL_VOICE,
                     diagnostic_voice=DIAGNOSTIC_VOICE):
    src=Path(source)
    wav=Path(audio)
    if not src.is_file() or src.is_symlink() or not wav.is_file() or wav.is_symlink():
        raise VoiceFeasibilityError("Original PDF and diagnostic WAV required")
    first_hash=digest(src)
    with fitz.open(src) as doc:
        if len(doc)<1 or normalize(SOURCE_EXCERPT) not in normalize(doc[0].get_text("text")):
            raise VoiceFeasibilityError("The spoken excerpt is not verbatim source page 1")
    try:
        with wave.open(str(wav),"rb") as item:
            channels=item.getnchannels()
            rate=item.getframerate()
            width=item.getsampwidth()
            frames=item.getnframes()
            pcm=item.readframes(frames)
    except (OSError, EOFError, wave.Error) as exc:
        raise VoiceFeasibilityError("WAV is not readable PCM") from exc
    if channels!=1 or width!=2 or rate<8000 or frames<=rate//4:
        raise VoiceFeasibilityError("WAV shape invalid")
    from array import array
    import math
    samples = array("h")
    samples.frombytes(pcm)
    rms = round(math.sqrt(sum(x * x for x in samples) / len(samples)))
    if rms<3:
        raise VoiceFeasibilityError("WAV is silent")
    if digest(src)!=first_hash:
        raise VoiceFeasibilityError("Original source changed during check")
    return {
        "status":"REAL_OFFLINE_SPEECH_TEST_PRODUCTION_VOICE_NOT_VERIFIED",
        "source_pdf_sha256":first_hash,
        "source_page":1,
        "spoken_excerpt":SOURCE_EXCERPT,
        "diagnostic_wav_sha256":digest(wav),
        "diagnostic_duration_seconds":round(frames/rate,3),
        "diagnostic_sample_rate_hz":rate,
        "diagnostic_pcm_rms":rms,
        "diagnostic_voice_name":diagnostic_voice,
        "production_voice_name":production_voice,
        "voice_name_mismatch":diagnostic_voice!=production_voice,
        "production_voice_identity_verified":False,
        "speech_content_phonetically_verified":False,
        "cloud_tts_invoked":False,
        "gemini_invoked":False,
        "billed_provider_invoked":False,
        "publication_allowed":False,
        "complete_serway_lecture_generated":False,
        "next_action":"Verify genuinely compatible no-cost narrator, or obtain explicit billing-policy change"
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-pdf",type=Path,required=True)
    parser.add_argument("--existing-diagnostic-wav",type=Path,required=True)
    parser.add_argument("--new-report",type=Path,required=True)
    args=parser.parse_args()
    if args.new_report.exists() or args.new_report.is_symlink():
        raise VoiceFeasibilityError("Do not overwrite old report")
    report=check_diagnostic(args.source_pdf,args.existing_diagnostic_wav)
    args.new_report.parent.mkdir(parents=True,exist_ok=True)
    with args.new_report.open("x",encoding="utf8") as stream:
        json.dump(report,stream,indent=2)
    print(json.dumps({key:report[key] for key in
          ("status","diagnostic_duration_seconds","diagnostic_voice_name",
           "production_voice_name","publication_allowed")}))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
