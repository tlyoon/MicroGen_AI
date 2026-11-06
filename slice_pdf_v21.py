"""Stable, source-preserving slide-PDF slicing.

Retains previously verified slide PDFs rather than overwriting them after
earlier measured-cue TTS has already bound their hashes.
"""
from pathlib import Path

from microgen_timed_cue_planner import prepare_slide_pages


def main() -> None:
    pages = prepare_slide_pages(Path.cwd())
    print(f"Verified {len(pages)} source-backed slide PDF pages (existing valid pages reused).")


if __name__ == "__main__":
    main()
