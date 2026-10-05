# MicroGen_AI Educational Automation Package
# © 2025 Dr. Yoon Tiem Leong, School of Physics, Universiti Sains Malaysia.
#
# This file is part of the MicroGen_AI package.
#
# Licensed under the MIT License (see LICENSE file in the project root).
# You may not use this file except in compliance with the License.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

# gen_xml_fr_pdf_v*.py
# Hybrid figure embedding (keyword + token), robust PDF text extraction,
# Moodle XML writer with CDATA, and auto-scan runner for *_problemset.pdf.
#
# Requirements:
#   PyMuPDF (aka fitz) RECOMMENDED and REQUIRED on Windows for consistent output.
#   Fallbacks: pdfminer.six, then PyPDF2.
#
# Notes:
# - Figures are embedded as <img src="data:image/...;base64,..."> inside CDATA.
# - Image matching is FLEXIBLE:
#     (1) Keyword pass: looks for "Figure ..." / "Fig ..." references and embeds.
#     (2) Token pass:   detects tokens like P28.26 / 28-26 / TP41.3a in text
#                       and embeds by filename-token index (no "Figure" needed).
# - Only the FIRST occurrence per token (per question) will embed an image.
# - Figures are discovered by scanning --figdir recursively for PNG/JPG/GIF files.
#   Tokens are extracted from filenames; aliases (drop letter prefixes, '-'→'.')
#   help match common naming variations.
#
# © 2025 - tailored for Dr. Y.T. Leong workflows.

import os
import re
import sys
import io
import html
import base64
import platform
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple

# ---------- Logging ----------
def log(msg: str, level: str = "INFO"):
    print(f"[{level}] {msg}", flush=True)

# ---------- Optional UTF-8 safety for stdout/stderr ----------
def _safe_set_utf8_stream():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        # Fallback wrapper
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass
_safe_set_utf8_stream()

# ---------- CDATA-aware XML writer ----------
import xml.etree.ElementTree as ET

class CDATA(str):
    pass

def _escape_cdata(text: str) -> str:
    try:
        return (text or "").replace("]]>", "]]]]><![CDATA[>")
    except Exception:
        return ""

def _write_element_recursive(writer_func, element, encoding, level=0, indent="  "):
    if indent: writer_func((indent * level).encode(encoding))
    writer_func(f"<{element.tag}".encode(encoding))
    for k, v in element.attrib.items():
        writer_func(f' {k}="{html.escape(v, quote=True)}"'.encode(encoding))
    has_text = (element.text is not None and element.text != "")
    has_children = len(element) > 0
    if not has_text and not has_children:
        writer_func("/>".encode(encoding))
    else:
        writer_func(">".encode(encoding))
        if has_text:
            if isinstance(element.text, CDATA):
                writer_func(f"<![CDATA[{_escape_cdata(element.text)}]]>".encode(encoding))
            else:
                writer_func(html.escape(element.text).encode(encoding))
        if has_children:
            if indent: writer_func("\n".encode(encoding))
            for child in element:
                _write_element_recursive(writer_func, child, encoding, level + 1, indent)
            if indent and has_children: writer_func((indent * level).encode(encoding))
        writer_func(f"</{element.tag}>".encode(encoding))
    if indent or level > 0: writer_func("\n".encode(encoding))

def write_xml_with_cdata(tree: ET.ElementTree, filename, encoding="utf-8", xml_declaration=True, indent="  "):
    fn = str(filename)
    os.makedirs(os.path.dirname(fn) or ".", exist_ok=True)
    with open(fn, "wb") as f:
        if xml_declaration:
            f.write(f'<?xml version="1.0" encoding="{encoding}"?>\n'.encode(encoding))
        _write_element_recursive(f.write, tree.getroot(), encoding, level=0, indent=indent or "")

# ---------- PDF text extraction backends (robust) ----------
# Try both import styles for PyMuPDF
pymupdf = None
try:
    import fitz as pymupdf  # older import name
except Exception:
    try:
        import pymupdf  # newer import name
    except Exception:
        pymupdf = None

try:
    from pdfminer.high_level import extract_text as pdfminer_extract
except Exception:
    pdfminer_extract = None

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

def _extract_with_pymupdf(pdf_path: Path) -> Optional[str]:
    if pymupdf is None:
        return None
    try:
        doc = pymupdf.open(str(pdf_path))
        try:
            return "".join(page.get_text("text") for page in doc)
        finally:
            doc.close()
    except Exception as e:
        log(f"PyMuPDF extraction failed: {e}", "WARN")
        return None

def _extract_with_pdfminer(pdf_path: Path) -> Optional[str]:
    if pdfminer_extract is None:
        return None
    try:
        return pdfminer_extract(str(pdf_path)) or ""
    except Exception as e:
        log(f"pdfminer extraction failed: {e}", "WARN")
        return None

def _extract_with_pypdf2(pdf_path: Path) -> Optional[str]:
    if PdfReader is None:
        return None
    try:
        reader = PdfReader(str(pdf_path))
        return "".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        log(f"PyPDF2 extraction failed: {e}", "WARN")
        return None

def extract_pdf_text(pdf_path: Path) -> str:
    """
    Prefer PyMuPDF. If unavailable, try pdfminer.six, then PyPDF2.
    On Windows, require PyMuPDF to guarantee parity with WSL.
    """
    # Enforce PyMuPDF on Windows for consistent output
    if platform.system().lower().startswith("win") and pymupdf is None:
        raise RuntimeError(
            "PyMuPDF (fitz) is required on Windows for consistent text extraction.\n"
            "Install with:  py -m pip install -U PyMuPDF"
        )

    text = _extract_with_pymupdf(pdf_path)
    backend = "PyMuPDF" if text is not None else None

    if text is None:
        text = _extract_with_pdfminer(pdf_path)
        backend = backend or ("pdfminer.six" if text is not None else None)

    if text is None:
        text = _extract_with_pypdf2(pdf_path)
        backend = backend or ("PyPDF2" if text is not None else None)

    if text is None:
        raise RuntimeError("No PDF text backend available. Install PyMuPDF or pdfminer.six.")

    log(f"PDF text backend: {backend}")
    return text

def extract_first_page_text(pdf_path: Path) -> str:
    # Same backend policy as extract_pdf_text, but just first page
    if platform.system().lower().startswith("win") and pymupdf is None:
        # Keep behavior consistent with extract_pdf_text
        return ""
    # Try PyMuPDF
    if pymupdf is not None:
        try:
            doc = pymupdf.open(str(pdf_path))
            try:
                if len(doc) > 0:
                    return doc[0].get_text("text")
            finally:
                doc.close()
        except Exception:
            pass
    # Try pdfminer one-page (not directly supported; fall back to full then slice)
    if pdfminer_extract is not None:
        try:
            full = pdfminer_extract(str(pdf_path)) or ""
            return "\n".join(full.splitlines()[:80])
        except Exception:
            pass
    # Try PyPDF2
    if PdfReader is not None:
        try:
            reader = PdfReader(str(pdf_path))
            if len(reader.pages) > 0:
                return reader.pages[0].extract_text() or ""
        except Exception:
            pass
    return ""

# ---------- Question parsing ----------
def split_into_questions(txt: str) -> List[dict]:
    # Basic ligature normalization
    txt = txt.replace("ﬁ", "fi").replace("ﬂ", "fl")
    # Split at "Question N"
    blocks = re.split(r"(?=^\s*Question\s+\d+)", txt, flags=re.IGNORECASE | re.MULTILINE)[1:]
    if not blocks:
        blocks = re.split(r"(?i)(?=Question\s+\d+)", txt)[1:]
    out = []
    qnum_pat = re.compile(r"^\s*Question\s+(\d+)", re.IGNORECASE | re.MULTILINE)
    opt_pat  = re.compile(r"^[ABCD]\s*[.)]\s*(.+)", re.MULTILINE)
    for i, b in enumerate(blocks, 1):
        m = qnum_pat.match(b)
        qnum = m.group(1) if m else str(i)
        stem = qnum_pat.sub("", b, count=1).strip()
        # Detect MCQ options
        opts = opt_pat.findall(stem)
        if len(opts) >= 2:
            typ = "multichoice"
            answers = []
            for idx, o in enumerate(opts):
                answers.append({"text": html.escape(o.strip()), "fraction": "100" if idx == 0 else "0"})
            stem = opt_pat.sub("", stem).strip()
        else:
            typ = "shortanswer"
            answers = [{"text": "*", "fraction": "100"}]
        out.append({"type": typ, "name": f"Question {qnum}", "questiontext": stem, "answers": answers})
    return out

# ---------- Tokenization &amp; index of image files ----------
IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif"}

# Tokens like: P28.26, TP41.3, 28-26, 41.3a, CP12.10
LABEL_RE = re.compile(r"\b([A-Z]{0,3}?\d{1,3}(?:[.\-]\d{1,3})[a-z]?)\b", re.IGNORECASE)

def normalize_token(token: str) -> str:
    s = token.upper().replace("-", ".")
    s = re.sub(r"[^A-Z0-9.]", "", s)
    s = re.sub(r"\.{2,}", ".", s)
    return s

def token_aliases(token_norm: str) -> Set[str]:
    aliases = {token_norm}
    drop = re.sub(r"^[A-Z]+", "", token_norm)
    if drop:
        aliases.add(drop)
    return aliases

def extract_tokens_from_string(s: str) -> Set[str]:
    toks = set()
    for m in LABEL_RE.finditer(s):
        toks.add(normalize_token(m.group(1)))
    return toks

def build_image_index(figures_dir: Path) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    for p in figures_dir.rglob("*"):
        if p.suffix.lower() not in IMG_EXTS:
            continue
        tokens = extract_tokens_from_string(p.stem)
        if not tokens:
            continue
        for t in tokens:
            for alias in token_aliases(t):
                if alias in index and index[alias] != p:
                    # Keep the first, warn about collisions
                    log(f"Token collision for '{alias}': {index[alias].name} vs {p.name} (keeping first).", "WARN")
                else:
                    index[alias] = p
    log(f"Indexed {len(index)} token→image mappings from {figures_dir}", "INFO")
    return index

def encode_image_b64(path: Path) -> str:
    data = path.read_bytes()
    ext = path.suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{base64.b64encode(data).decode('ascii')}"

# ---------- Hybrid embedding: keyword pass + token pass ----------
FIG_KEYWORD_RE = re.compile(r"\b(?:Figure|Fig\.)\s+([A-Z]?\d{1,3}(?:[.\-]\d{1,3})[a-z]?)\b", re.IGNORECASE)

def _embed_one(label_raw: str, image_index: Dict[str, Path]) -> Optional[str]:
    token = normalize_token(label_raw)
    resolved = None
    for key in token_aliases(token):
        if key in image_index:
            resolved = image_index[key]
            break
    if not resolved:
        return None
    data_uri = encode_image_b64(resolved)
    return (f'<img alt="{html.escape(label_raw)}" '
            f'style="max-width: 480px; height: auto; display:block; margin: 0.8em auto;" '
            f'src="{data_uri}"/>')

def embed_images_hybrid(plain_text: str, image_index: Dict[str, Path]) -> Tuple[str, Set[str]]:
    """
    Returns (html_text, embedded_tokens_set).
    Strategy:
      1) Keyword pass: detect "Figure ..."/"Fig. ..." → embed under first mention.
      2) Token pass:   detect generic tokens (LABEL_RE) and embed if not already embedded.
    """
    inserted: Set[str] = set()
    text = plain_text

    # Keyword pass
    def repl_kw(m: re.Match) -> str:
        raw_label = m.group(1)
        norm = normalize_token(raw_label)
        if norm in inserted:
            return m.group(0)
        img = _embed_one(raw_label, image_index)
        if not img:
            return m.group(0)
        inserted.add(norm)
        return f'{m.group(0)}\n{img}'

    text = FIG_KEYWORD_RE.sub(repl_kw, text)

    # Token pass
    def repl_token(m: re.Match) -> str:
        raw = m.group(1)
        norm = normalize_token(raw)
        if norm in inserted:
            return m.group(0)
        img = _embed_one(raw, image_index)
        if not img:
            return m.group(0)
        inserted.add(norm)
        return f'{m.group(0)}\n{img}'

    text = LABEL_RE.sub(repl_token, text)

    # Wrap with <p> if not already HTML
    html_text = text if text.strip().startswith("<p>") else f"<p>{text}</p>"
    return html_text, inserted

# ---------- Title helpers ----------
def section_id_from_filename(pdf_path: Path) -> str:
    # e.g., SECTION_28-4_problemset.pdf -> 28.4
    base = pdf_path.stem
    base_up = base.upper()
    if base_up.startswith("SECTION_"):
        rest = base[8:]
    else:
        rest = base
    rest = re.sub(r"_problemset$", "", rest, flags=re.IGNORECASE)
    return rest.replace("-", ".")

def title_from_pdf_or_filename(pdf_path: Path) -> str:
    # Try to sniff a nice title from the first page
    first = extract_first_page_text(pdf_path)
    for line in (first or "").splitlines():
        line = line.strip()
        if not line: 
            continue
        # Prefer lines that look like section headers or titles
        if re.search(r"(Problem Set|Tutorial|Section|Sources of|Fields|Electric|Magnetic)", line, re.IGNORECASE):
            return line
    # Fallback to "Section <id>"
    sid = section_id_from_filename(pdf_path)
    return f"Section {sid}" if sid else pdf_path.stem

# ---------- Build Moodle XML ----------
def build_xml(pdf_path: Path, out_path: Path, figures_dir: Path) -> Dict[str, int]:
    """
    Returns a dict summary: {"questions": N, "embedded": M}
    """
    title = title_from_pdf_or_filename(pdf_path)
    full_text = extract_pdf_text(pdf_path)
    questions = split_into_questions(full_text)
    if not questions:
        raise RuntimeError("No questions detected in PDF text.")

    image_index = build_image_index(figures_dir)

    quiz = ET.Element("quiz")

    # Category header
    cq = ET.SubElement(quiz, "question", type="category")
    cat = ET.SubElement(cq, "category")
    ET.SubElement(cat, "text").text = CDATA(f"$course$/top/{title}")
    info = ET.SubElement(cq, "info", format="moodle_auto_format")
    ET.SubElement(info, "text").text = CDATA(f"Questions for {title}")
    ET.SubElement(cq, "idnumber")

    total_embedded = 0

    for q in questions:
        qn = ET.SubElement(quiz, "question", type=q["type"])

        name = ET.SubElement(qn, "name")
        ET.SubElement(name, "text").text = CDATA(q["name"])

        stem_html, embedded = embed_images_hybrid(q["questiontext"], image_index)
        total_embedded += len(embedded)

        qt = ET.SubElement(qn, "questiontext", format="html")
        ET.SubElement(qt, "text").text = CDATA(stem_html)

        gf = ET.SubElement(qn, "generalfeedback", format="html")
        ET.SubElement(gf, "text").text = CDATA("")

        ET.SubElement(qn, "defaultgrade").text = "1.0000000"
        ET.SubElement(qn, "penalty").text = "0.3333333"
        ET.SubElement(qn, "hidden").text = "0"
        ET.SubElement(qn, "idnumber")

        if q["type"] == "multichoice":
            ET.SubElement(qn, "single").text = "true"
            ET.SubElement(qn, "shuffleanswers").text = "true"
            ET.SubElement(qn, "answernumbering").text = "abc"
            for tag, txt in (
                ("correctfeedback", "Your answer is correct."),
                ("partiallycorrectfeedback", "Your answer is partially correct."),
                ("incorrectfeedback", "Your answer is incorrect."),
            ):
                fb = ET.SubElement(qn, tag, format="html")
                ET.SubElement(fb, "text").text = CDATA(f"<p>{txt}</p>")
        else:
            ET.SubElement(qn, "usecase").text = "0"

        for a in q["answers"]:
            ans = ET.SubElement(qn, "answer", fraction=a["fraction"], format="html")
            ET.SubElement(ans, "text").text = CDATA(a["text"])
            fb = ET.SubElement(ans, "feedback", format="html")
            ET.SubElement(fb, "text").text = CDATA("")

    tree = ET.ElementTree(quiz)
    write_xml_with_cdata(tree, out_path, encoding="utf-8", xml_declaration=True, indent="  ")
    log(f"wrote: {out_path.name}")
    return {"questions": len(questions), "embedded": total_embedded}

# ---------- Runner ----------
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Convert problemset PDF(s) to Moodle XML with embedded figures (Base64).")
    parser.add_argument(
        "pdfs", nargs="*",
        help="Specific PDF file(s) to convert. If omitted, the script auto-scans for '*_problemset.pdf'.")
    parser.add_argument(
        "--figdir", default=None,
        help="Directory containing figure images (default: script folder).")
    parser.add_argument(
        "--outdir", default=None,
        help="Output directory for XML (default: alongside each PDF).")
    parser.add_argument(
        "--pattern", default="*_problemset.pdf",
        help="Pattern used when auto-scanning (default: *_problemset.pdf).")
    parser.add_argument(
        "--recursive", action="store_true",
        help="Recurse into subfolders when scanning.")
    args = parser.parse_args()

    # Resolve dirs
    script_dir = Path(__file__).resolve().parent
    figures_dir = Path(args.figdir).resolve() if args.figdir else script_dir

    # Build list of PDFs:
    pdf_list = []
    if args.pdfs:
        for p in args.pdfs:
            pp = Path(p).resolve()
            if pp.exists() and pp.suffix.lower() == ".pdf":
                pdf_list.append(pp)
            else:
                log(f"Skipping non-PDF or missing file: {p}", "WARN")
    else:
        # AUTO-SCAN by default
        if args.recursive:
            pdf_list = sorted(Path(".").rglob(args.pattern))
        else:
            pdf_list = sorted(Path(".").glob(args.pattern))
        pdf_list = [p.resolve() for p in pdf_list if p.is_file()]

    if not pdf_list:
        log("No PDF files to process.", "WARN")
        return

    # Output dir handling
    out_dir_global = Path(args.outdir).resolve() if args.outdir else None
    if out_dir_global:
        out_dir_global.mkdir(parents=True, exist_ok=True)

    log(f"Found {len(pdf_list)} PDF(s). Figures dir: {figures_dir}")
    total_ok = 0
    total_err = 0
    total_emb = 0
    for pdf in pdf_list:
        try:
            out_dir = out_dir_global if out_dir_global else pdf.parent
            out_path = out_dir / f"{pdf.stem}.xml"
            summary = build_xml(pdf, out_path, figures_dir)
            total_ok += 1
            total_emb += summary.get("embedded", 0)
        except Exception as e:
            total_err += 1
            log(f"‼️ Error processing {pdf.name}: {e}", "ERR")
        print("-" * 40)

    log(f"Processing complete. OK={total_ok}, ERR={total_err}, Figures embedded={total_emb}", "INFO")

main()
#PATTERNS = ["*_problemset_mcq.xml", "*_problemset.xml"]
import sanitize_xml
sanitize_xml.main("*_problemset.xml")
#sanitize_xml.main("*_problemset_mcq.xml")
