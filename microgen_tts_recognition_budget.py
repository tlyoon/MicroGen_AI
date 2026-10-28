"""Bound expensive all-slide acoustic recognition before any provider call.

This budgets REQUEST COUNT and AUDIO INPUT DURATION, not actual currency.
Provider billing units and prices are external and are never invented.
"""
from __future__ import annotations
import wave
from pathlib import Path

class RecognitionBudgetExceeded(ValueError):
    pass

def plan_recognition(
    folder:Path,slide_count:int,*,
    passes:int=2,max_audio_seconds:float=1200.,
    max_requests:int=120,max_wav_bytes:int=18_000_000,
)->dict:
    if type(slide_count) is not int or slide_count<1:
        raise RecognitionBudgetExceeded("Invalid slide count")
    if (type(passes) is not int or passes!=2 or
        type(max_requests) is not int or max_requests<1 or
        type(max_audio_seconds) not in (int,float) or max_audio_seconds<=0 or
        type(max_wav_bytes) is not int or max_wav_bytes<1024):
        raise RecognitionBudgetExceeded("Invalid resource limits")
    requested=passes*slide_count
    if requested>max_requests:
        raise RecognitionBudgetExceeded("Acoustic request count exceeds configured cap")
    total=0.0
    rows=[]
    for i in range(1,slide_count+1):
        wav=Path(folder)/f"slide{i}.wav"
        size=wav.stat().st_size
        if size>max_wav_bytes:
            raise RecognitionBudgetExceeded(f"WAV slide {i} exceeds per-request input cap")
        with wave.open(str(wav),"rb") as audio:
            if (audio.getnframes()<=0 or audio.getframerate()<=0 or
                audio.getnchannels()!=1 or audio.getsampwidth()!=2):
                raise RecognitionBudgetExceeded(f"Invalid WAV format on slide {i}")
            seconds=audio.getnframes()/audio.getframerate()
        total+=seconds
        if total*passes>max_audio_seconds:
            raise RecognitionBudgetExceeded("Planned acoustic audio-seconds exceed cap")
        rows.append({"slide":i,"wav_bytes":size,"audio_seconds":round(seconds,6)})
    return {
        "slide_count":slide_count,"independent_passes":passes,
        "planned_recognition_requests":requested,
        "planned_input_audio_seconds":round(total*passes,6),
        "configured_audio_seconds_cap":max_audio_seconds,
        "configured_request_cap":max_requests,
        "max_single_wav_bytes":max_wav_bytes,
        "slides":rows,
        "price_estimate":None,
        "notice":"Input-duration budget is NOT provider billing or a monetary estimate.",
    }
