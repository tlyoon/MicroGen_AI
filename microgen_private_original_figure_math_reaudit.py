"""Re-check original source figure pixels, vector equation geometry and typed math.

Reuses existing exact private source figure and equation verifiers, not a newly
trained model, and never publishes copyrighted content.
"""
from __future__ import annotations
from pathlib import Path
import pymupdf as fitz

from microgen_portable_slide_render import checked_figures
from microgen_portable_source_equations import checked_equations
from microgen_portable_source_figure_regions import checked_source_figure_regions
from microgen_portable_source_math_claims import verified_source_math_claims
from microgen_pronunciation_closed_loop import sha_file


def audit_original_figure_math(stage:Path,source:Path,manifest:dict,narration:dict):
    stage,source=Path(stage),Path(source)
    files=checked_figures(stage,manifest,len(narration["slides"]))
    guard={str(p):sha_file(p) for p,_,_ in files.values()}
    with fitz.open(source) as pdf:
        equations=checked_equations(pdf,manifest,narration,set(files))
        regions=checked_source_figure_regions(pdf,manifest.get("figures",[]),files)
        math=verified_source_math_claims(pdf,manifest,equations,regions)
    if any(sha_file(Path(p))!=expected for p,expected in guard.items()):
        raise ValueError("Original figure file changed during scientific geometry and math audit")
    return {
        "original_figures_hashed":len(files),
        "original_source_raster_figures_checked":len(regions),
        "source_vector_equation_crops_checked":len(equations),
        "independently_recalculated_source_typed_math_claims":len(math),
        "all_math_semantics_proven":False,
        "figure_and_source_copyright_rights_cleared":False,
        "publication_allowed":False
    }
