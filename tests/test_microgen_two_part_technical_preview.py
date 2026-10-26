"""Static preview does not count as a published/element-highlighted lecture."""
from pathlib import Path
import pytest
from microgen_two_part_technical_preview import create_unapproved_previews


def test_missing_source_deck_fails_closed(tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError, ValueError, OSError)):
        create_unapproved_previews(tmp_path)


def test_invalid_split_fails_before_writing_parts(tmp_path):
    import pymupdf
    doc=pymupdf.open()
    for _ in range(23): doc.new_page()
    doc.save(tmp_path/"slides.pdf")
    doc.close()
    for split in (0,23,24):
        with pytest.raises(ValueError):
            create_unapproved_previews(tmp_path,boundary=split)
    assert not (tmp_path/"technical_previews_unapproved").exists()
