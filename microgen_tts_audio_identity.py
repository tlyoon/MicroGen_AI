"""Decode-level waveform identity across different WAV container encodings."""
from __future__ import annotations
import hashlib,struct,wave
from pathlib import Path
from microgen_tts_pcm_features import file_sha256

class PcmIdentityError(ValueError):pass
def decoded_pcm_sha256(path:Path)->str:
    path=Path(path);before=file_sha256(path)
    digest=hashlib.sha256()
    with wave.open(str(path),"rb") as f:
        if f.getnchannels()!=1 or f.getsampwidth()!=2 or f.getnframes()<=0:
            raise PcmIdentityError("Require nonempty mono PCM16")
        digest.update(struct.pack("<III",f.getframerate(),f.getnchannels(),f.getsampwidth()))
        remain=f.getnframes()
        while remain:
            frames=min(remain,16384)
            audio=f.readframes(frames)
            if len(audio)!=frames*2:raise PcmIdentityError("Truncated decoded WAV")
            digest.update(audio);remain-=frames
    if file_sha256(path)!=before:
        raise PcmIdentityError("WAV changed during PCM fingerprint")
    return digest.hexdigest()
