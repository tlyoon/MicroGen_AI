"""Audio signal-quality triage for candidate dataset clips, NOT pronunciation QA."""
from __future__ import annotations
from pathlib import Path
from microgen_tts_pcm_features import pcm_envelope
class QualityError(ValueError):pass

def screen_clip(path:Path,*,min_rms:float=0.001,
                min_speechlike_fraction:float=0.1,
                max_clipped_fraction:float=0.01)->dict:
    if (not isinstance(min_rms,(float,int)) or not 0<min_rms<=0.05 or
        not isinstance(min_speechlike_fraction,(float,int)) or
        not 0<min_speechlike_fraction<=1 or
        not isinstance(max_clipped_fraction,(float,int)) or
        not 0<=max_clipped_fraction<1):
        raise QualityError("Invalid clip quality thresholds")
    info=pcm_envelope(path,max_seconds=10.)
    energy=info["frame_rms"]
    clipping=info["frame_clipping_fraction"]
    active=sum(v>=min_rms for v in energy)/len(energy)
    clipped=sum(clipping)/len(clipping)
    blockers=[]
    if info["whole_rms"]<min_rms or active<min_speechlike_fraction:
        blockers.append("LOW_INFORMATION_AUDIO")
    if clipped>max_clipped_fraction:
        blockers.append("HIGH_CLIPPING_AUDIO")
    return {"schema_version":1,"wav_sha256":info["wav_sha256"],
            "duration_seconds":info["duration_seconds"],
            "mean_rms":info["whole_rms"],
            "speechlike_frame_fraction":round(active,6),
            "mean_clipping_fraction":round(clipped,6),
            "training_sample_usable_by_signal_only":not blockers,
            "dataset_readiness_blockers":blockers,
            "phoneme_label_validated":False,"phonetic_accuracy_certified":False,
            "production_release_gate_changed":False}
