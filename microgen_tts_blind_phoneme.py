"""Script-blind, conservative contrastive *audio* probe, NOT ASR.

Separately listen to WAV, ask about an actual sound, and preserve uncertainty.
Neither the textbook transcript nor the correct answer is sent to the judge.
Even two agreeing responses are not independently verified pronunciation.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Callable

PROMPT = (
    "Listen to the ACTUAL SOUND of this English university lecture audio. "
    "Do not correct pronunciation based on mathematical meaning or spellings. "
    "When a speaker says the letter sound before the noun 'value', does "
    "the sound rhyme with 'sigh' (answer WHY) or 'day' (answer YAY)? "
    "If both are present, unclear, missing, or unsure, answer UNKNOWN. "
    "Return exactly one of WHY, YAY, UNKNOWN; no punctuation or explanations."
)
LABELS=frozenset(("WHY","YAY","UNKNOWN"))
class PhonemeProbeError(RuntimeError):
    pass

def digest(path:Path)->str:
    h=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def canonical_label(reply:object)->str:
    if not isinstance(reply,str):
        return "UNKNOWN"
    text=reply.strip()
    return text if text in LABELS else "UNKNOWN"

def probe_wav(path:Path, judge:Callable[[Path,str],str], *,
              model_identity:str)->dict:
    if not model_identity or not isinstance(model_identity,str):
        raise PhonemeProbeError("Model identity required")
    path=Path(path)
    before=digest(path)
    try:
        answer=canonical_label(judge(path,PROMPT))
    except Exception:
        answer="UNKNOWN"
    after=digest(path)
    if before!=after:
        raise PhonemeProbeError("Audio source changed during phoneme probe")
    return {
        "schema_version":1,"model":model_identity,"wav_sha256":after,
        "label":answer,"interpretation":"audio_derived_closed_choice_unvalidated",
        "used_expected_narration":False,"human_approval":False,
        "phonetic_accuracy_certified":False,
    }

def gemini_phoneme_judge(api_key:str,*,model:str="gemini-3.5-flash"):
    """Real model adapter. No target narration is uploaded or hinted."""
    from google import genai
    from google.genai import types
    client=genai.Client(api_key=api_key,
        http_options=types.HttpOptions(timeout=90000))
    def judge(path:Path,prompt:str)->str:
        audio=Path(path).read_bytes()
        if not 44<=len(audio)<=18_000_000:
            raise PhonemeProbeError("Audio exceeds inline model budget")
        response=client.models.generate_content(
            model=model,
            contents=[types.Part.from_bytes(data=audio,mime_type="audio/wav"),prompt],
            config=types.GenerateContentConfig(
                temperature=0,max_output_tokens=40,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        return response.text or ""
    return judge
