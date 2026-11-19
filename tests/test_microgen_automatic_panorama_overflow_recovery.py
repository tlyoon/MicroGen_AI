"""Production-wired automatic repair for LaTeX Beamer panoramic-image overflow.

All tests use synthetic, source-free figures. In particular, no figure is
cropped or rewritten; only the frame's existing graphic-size ceiling changes.
"""
import hashlib
import re
import shutil
import struct
import zlib

import pytest

from microgen_quality import (
    dependency_fingerprint, check_latex_overflow, check_slide_pdf,
)
from microgen_slide_reflow import (
    _math_evidence, reflow_document, repair_layout,
)


SOURCE = r"""
\documentclass{beamer}
\usetheme{Madrid}
\setbeamertemplate{headline}{\hfill\insertframenumber{} / \inserttotalframenumber\par}
\setbeamertemplate{footline}{}
\usepackage{graphicx}
\begin{document}
\begin{frame}{Acceleration graph}
The rate of change is $a=\frac{dv}{dt}$.
\begin{figure}
\centering
\includegraphics[height=0.4\textheight,keepaspectratio]{wide.png}
\end{figure}
\end{frame}
\end{document}
"""


def _make_png(path, width=800, height=228):
    """Generate a PNG without local models, Pillow or external images."""
    def chunk(kind, value):
        payload = kind + value
        return (struct.pack(">I", len(value)) + payload
                + struct.pack(">I", zlib.crc32(payload) & 0xffffffff))
    pixel_row = b"\x00" + b"\xff\xff\xff" * width
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(pixel_row * height))
           + chunk(b"IEND", b""))
    path.write_bytes(png)
    return hashlib.sha256(png).hexdigest()


def test_one_figure_ceiling_fixes_only_size_options():
    variants = reflow_document(SOURCE, "graphics")
    assert len(variants) == 1
    new, frame, units = variants[0]
    assert units == 1
    assert r"\includegraphics[height=0.4\textheight,keepaspectratio,width=\linewidth]{wide.png}" in new
    assert new.count(r"\begin{frame}") == SOURCE.count(r"\begin{frame}")
    assert _math_evidence(new) == _math_evidence(SOURCE)
    assert re.findall(r"\\includegraphics\[[^\]]+\]\{([^}]+)\}", new) == ["wide.png"]
    assert "Acceleration graph" in frame


@pytest.mark.parametrize("options", [
    r"width=0.9\linewidth,keepaspectratio",
    r"height=0.4\textheight,width=0.8\linewidth,keepaspectratio",
    r"height=0.4\textheight,scale=0.9",
    r"height=0.4\textheight,trim=5pt 0 0 0,clip",
    r"angle=90,height=0.4\textheight",
    r"height=0.4\textheight,unknown-key",
])
def test_already_bounded_or_unknown_options_not_modified(options):
    deck = SOURCE.replace(
        r"height=0.4\textheight,keepaspectratio", options)
    assert reflow_document(deck, "graphics") == []


def test_image_ceiling_does_not_mutate_math_or_figure_identity():
    additional = SOURCE.replace(
        r"\end{frame}", r"\[\int_0^T a(t)\,dt=v(T)-v(0)\]\end{frame}")
    variants = reflow_document(additional, "graphics")
    assert len(variants) == 1
    assert _math_evidence(additional) == _math_evidence(variants[0][0])
    assert variants[0][0].count("wide.png") == 1


def test_slide_stage_fingerprint_tracks_reflow_code(tmp_path):
    for name in (
        "source.pdf", "gen_slides_v20.py",
        "gen_slides_prompt_v20_hybrid.txt", "microgen_slide_reflow.py",
        "microgen_layout_retry_guard.py",
    ):
        (tmp_path / name).write_bytes(b"original")
    before = dependency_fingerprint(tmp_path, "slides")
    (tmp_path / "microgen_slide_reflow.py").write_bytes(b"improved on-path image fitting")
    assert before != dependency_fingerprint(tmp_path, "slides")
    changed = dependency_fingerprint(tmp_path, "slides")
    (tmp_path / "microgen_layout_retry_guard.py").write_bytes(b"new stop rule")
    assert changed != dependency_fingerprint(tmp_path, "slides")


def test_empty_or_unsupported_beamer_frame_no_reflow():
    broken = SOURCE.replace(r"\end{frame}", "")
    assert reflow_document(broken, "graphics") == []
    assert reflow_document(SOURCE.replace("height=0.4", "height=0.3"), "examples") == []


@pytest.mark.skipif(shutil.which("pdflatex") is None,
                    reason="local TeX distribution is not available")
def test_live_two_pass_latex_reflow_without_overwriting_original_figures(tmp_path):
    """With installed TeX, run the actual quality gate and receipt path."""
    tex = tmp_path / "slides.tex"
    tex.write_text(SOURCE, encoding="utf-8")
    source_hash = _make_png(tmp_path / "wide.png")
    result = repair_layout(tex, max_candidates=5, timeout=70)
    assert result["status"] == "accepted", result["attempts"]
    assert result["math_preserved"] is True
    assert result["original_frame_count"] == result["result_frame_count"] == 1
    assert len(result["operations"]) == 1
    assert result["operations"][0]["mode"] == "graphics"
    assert check_slide_pdf(tmp_path / "slides.pdf", require_footer=True)["pages"] == 1
    assert check_latex_overflow(tmp_path / "slides.log")["severe_count"] == 0
    assert hashlib.sha256((tmp_path / "wide.png").read_bytes()).hexdigest() == source_hash
    assert r"width=\linewidth" in tex.read_text(encoding="utf-8")
    backups = list(tmp_path.glob("slides.before_structural_reflow_*.tex"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == SOURCE
