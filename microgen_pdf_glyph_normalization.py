"""Lossless decoding of individually source-attested PDF label mojibake.

Only the exact seven UTF-8-as-Windows-1252 three-codepoint sequences found
in the original Serway 2.7 figure extractor are recognized. No symbol is
discarded or changed to a different mathematical operation.
"""
from __future__ import annotations

ATTESTED_GLYPHS = (
    ("\u00e2\u20ac\u2122", "\u2019"),  # typographic right apostrophe
    ("\u00e2\u02c6\u2019", "\u2212"),  # mathematical minus
    ("\u00e2\u02c6\u2020", "\u2206"),  # change/delta
    ("\u00e2\u20ac\u201c", "\u2013"),  # en dash
    ("\u00e2\u2020\u2019", "\u2192"),  # right arrow
    ("\u00e2\u2030\u02c6", "\u2248"),  # approximately equal
    ("\u00e2\u02c6\u0161", "\u221a"),  # square root
)


def correct_attested_glyphs(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("Source glyph decoding requires text")
    for corrupted, correct in ATTESTED_GLYPHS:
        text = text.replace(corrupted, correct)
    return text


def exact_source_glyph_equal(original, reconstructed) -> bool:
    """Only text values may receive exact encoding correction; structure stays fixed."""
    if type(original) is not type(reconstructed):
        return False
    if isinstance(original, str):
        return correct_attested_glyphs(original) == correct_attested_glyphs(reconstructed)
    if isinstance(original, list):
        return len(original) == len(reconstructed) and all(
            exact_source_glyph_equal(a, b) for a, b in zip(original, reconstructed))
    return original == reconstructed
