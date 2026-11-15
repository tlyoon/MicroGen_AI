"""General source-bound mathematical subscript and graph-panel spoken input.

No original narration, textbook page, math constant, figure, or source
PDF is edited. Old/G2 letter repairs continue to be applied.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import pytest

from microgen_reviewed_math_voice import (
    reviewed_math_voice, voice_input_risk_status,
)
from text_to_speech_v25 import normalize_scientific_speech


@pytest.mark.parametrize(("original", "expected"), [
    ("delta x equals x sub f minus x sub i",
     "delta ex equals ex sub eff minus ex sub eye"),
    ("x sub f equals x sub i plus one half v sub x",
     "ex sub eff equals ex sub eye plus one half vee sub ex"),
    ("the car initial position is x B equals 45 meters",
     "the car initial position is ex bee equals 45 meters"),
    ("x car equals x B plus v x car times t",
     "ex car equals ex bee plus vee ex car times t"),
    ("setting x trooper equal to x car aligns their locations",
     "setting ex trooper equal to ex car aligns their locations"),
    ("In Graph c we examine the slope",
     "In Graph panel see we examine the slope"),
    ("Graph a and Graph b",
     "Graph panel ay and Graph panel bee"),
    ("graph labeled a, b, and c",
     "graph labeled panel ay, panel bee, and panel see"),
    ("graphs a, b, and c",
     "graphs panel ay, panel bee, and panel see"),
    ("x-ray diffraction is not a graph",
     "x-ray diffraction is not a graph"),
    ("this x car is a brand name",
     "this x car is a brand name"),
    ("coefficient c is unchanged", "coefficient c is unchanged"),
])
def test_math_context_only_voice_corrections(original, expected):
    assert reviewed_math_voice(original) == expected


@pytest.mark.skipif(
    not os.environ.get("MICROGEN_REAL_G3_SECTION27_STAGE"),
    reason="Opt-in exact 20-slide original source/provider response replay on HP",
)
def test_actual_serway27_all_20_cached_slides_have_zero_predictable_math_risk():
    stage = Path(os.environ["MICROGEN_REAL_G3_SECTION27_STAGE"])
    files = sorted((stage/".microgen_narration_batches").glob("batch_*.json"))
    assert len(files) == 3
    count = 0
    changed = 0
    for f in files:
        result = json.loads(f.read_text(encoding="utf8"))
        assert isinstance(result.get("key"), str) and len(result["key"]) == 64
        for row in result["narration"].values():
            raw = str(row.get("tts_text") or row["narration"])
            proof = voice_input_risk_status(raw, normalize_scientific_speech)
            assert proof["unresolved_source_risk_count"] == 0
            assert proof["phoneme_certified"] is False
            assert proof["publication_allowed"] is False
            changed += bool(proof["changed_for_tts_only"])
            count += 1
    assert count == 20
    assert changed >= 5
