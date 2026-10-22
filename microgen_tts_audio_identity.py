"""Decode-level waveform identity across different WAV container encodings."""
from __future__ import annotations
import hashlib,struct,wave
from pathlib import Path
from microgen_tts_pcm_features import file_sha256

class PcmIdentityError(ValueError):pass
def decoded_pcm_sha256(path:Path,*,max_bytes:int=18_000_000,max_seconds:float=600)->str:
    if (type(max_bytes) is not int or max_bytes<1024 or
        type(max_seconds) not in (int,float) or not 0<max_seconds<=600):
        raise PcmIdentityError("Invalid decoded audio budgets")
    path=Path(path)
    if path.stat().st_size>max_bytes:
        raise PcmIdentityError("WAV bytes exceed fingerprint budget")
    before=file_sha256(path)
    digest=hashlib.sha256()
    with wave.open(str(path),"rb") as f:
        if (f.getnchannels()!=1 or f.getsampwidth()!=2 or f.getnframes()<=0
            or f.getframerate()<=0 or f.getnframes()/f.getframerate()>max_seconds):
            raise PcmIdentityError("Require nonempty mono PCM16")
        digest.update(struct.pack("<III",f.getframerate(),f.getnchannels(),f.getsampwidth()))
        remain=f.getnframes()
        while remain:
            frames=min(remain,16384)
            audio=f.readframes(frames)
            if len(audio)!=frames*2:raise PcmIdentityError("Truncated decoded WAV")
            digest.update(audio);remain-=frames
    if path.stat().st_size>max_bytes or file_sha256(path)!=before:
        raise PcmIdentityError("WAV changed during PCM fingerprint")
    return digest.hexdigest()
