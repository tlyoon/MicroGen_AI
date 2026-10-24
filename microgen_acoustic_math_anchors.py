"""Conservative original ASR phrase clocks against math-line PDF text.

Matching text on the same slide is NOT proof of intended equation teaching
semantics. Only unique >=2-token precise anchors within a short window.
"""
from pathlib import Path
import re
from collections import Counter
from microgen_source_safe_orchestrator import read_json,digest,atomic_json,OrchestratorError
from microgen_offline_vosk_capture import validate_vosk_words

class MathAnchorError(OrchestratorError):
    pass

_SKIP={"about","which","their","there","where","would","could","these",
       "those","because","function","value","values","point","since",
       "continuous","equation","formula"}

def _terms(text):
    return [x.lower() for x in re.findall(r"[A-Za-z]{5,}",text)
            if x.lower() not in _SKIP]

def match_acoustic_math_anchors(math_report,asr_report,output):
    m=read_json(math_report)
    a=read_json(asr_report)
    dest=Path(output).resolve(strict=False)
    if (dest.exists() or dest.is_symlink() or
        m.get("status")!="PDF_MATH_LINE_GEOMETRY_CANDIDATES" or
        a.get("status")!="SOURCE_BOUND_OFFLINE_17_SLIDE_ASR" or
        m.get("source_pdf_sha256")!=a.get("source_pdf_sha256") or
        a.get("publication_allowed") is not False or
        m.get("slide_count")!=17 or len(a.get("results",[]))!=17):
        raise MathAnchorError("Untrusted or incomplete math/acoustic source")
    result=[]
    for i in range(17):
        slide=m["slides"][i]
        speech=a["results"][i]
        if slide["slide"]!=i+1 or speech["slide"]!=i+1:
            raise MathAnchorError("Slide index differs")
        words=validate_vosk_words(speech["words"])
        tokens=[w["word"].lower() for w in words]
        count=Counter(tokens)
        for entry in slide["regions"]:
            terms=list(dict.fromkeys(_terms(entry["line_text"])))
            if len(terms)<2:continue
            matches=[]
            for j,w in enumerate(words):
                if w["word"].lower() not in terms or count[w["word"].lower()]!=1 or w["conf"]<.90:
                    continue
                for k in range(j+1,min(len(words),j+9)):
                    other=words[k]
                    if (other["word"].lower() in terms and
                        other["word"].lower()!=w["word"].lower() and
                        count[other["word"].lower()]==1 and other["conf"]>=.90 and
                        0<other["start"]-w["start"]<=3):
                        matches.append((j,k))
            if len(matches)!=1:continue
            j,k=matches[0]
            result.append({"slide":i+1,"line_text":entry["line_text"][:200],
                 "bbox":entry["bbox"],"matched_words":[tokens[j],tokens[k]],
                 "asr_start_seconds":words[j]["start"],
                 "asr_end_seconds":words[k]["end"],
                 "context_only_not_equation_semantic_proof":True})
    doc={"schema_version":1,"status":"AUDIO_TO_PDF_MATH_LINE_CONTEXT_CANDIDATES",
        "source_pdf_sha256":m["source_pdf_sha256"],
        "source_asr_sha256":digest(asr_report),
        "context_anchors":result,"proposed":len(result),
        "actual_equation_spoken_alignment_verified":False,
        "academic_math_QA_verified":False,"publication_allowed":False}
    atomic_json(dest,doc)
    return {"proposed":len(result),"requires_semantic_review":True,
        "publication_allowed":False}
