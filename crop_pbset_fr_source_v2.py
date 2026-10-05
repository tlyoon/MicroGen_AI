#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crop_pbset_fr_source.py  — robust, keyword-agnostic cropper for textbook "problem set" sections.
(End-index robustness upgrade; start-index logic intentionally unchanged.)
"""
from __future__ import annotations
import os, re, json, argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

# Prefer pypdf, fallback to PyPDF2
'''
try:
    from pypdf import PdfReader, PdfWriter  # pip install pypdf
except Exception:
    from PyPDF2 import PdfReader, PdfWriter  # type: ignore
'''

try:
    import pypdf
    from pypdf import PdfReader, PdfWriter
    BACKEND = f"pypdf {getattr(pypdf, '__version__', '?')}"
except Exception:
    import PyPDF2
    from PyPDF2 import PdfReader, PdfWriter  # type: ignore
    BACKEND = f"PyPDF2 {getattr(PyPDF2, '__version__', '?')}"

# Optional LLMs
try:
    import google.generativeai as genai  # pip install google-generativeai
except Exception:
    genai = None
try:
    from openai import OpenAI  # pip install openai
except Exception:
    OpenAI = None

def log(msg: str, level: str = "INFO") -> None:
    print(f"[{level}] {msg}")

@dataclass
class PageSignals:
    n_lines: int
    n_words: int
    ratio_digit_leading: float
    ratio_choice_tokens: float
    mean_line_len: float
    bullets_like: int
    dense_blocks: int
    digit_lead_count: int

# ====== Regexes (unchanged) ======
DIGIT_LEAD_RE   = re.compile(r"^\s*([0-9]{1,3}|[IVXLC]{1,6}|[a-zA-Z])[.)\]]\s+", re.M)
CHOICE_TOKEN_RE = re.compile(r"\(([A-D]|[a-e])\)|\b[A-D]\)|\b[a-e]\)", re.M)
BULLET_RE       = re.compile(r"^\s*[-\u2022\u25E6\u25CF]\s+", re.M)
DENSE_NUM_RE    = re.compile(r"^\s*\(?\d{1,3}\)?[.)]?\s+", re.M)

# ====== New/extra regex helpers (for end-side guards) ======
CHAPTER_WORD_RE   = re.compile(r"^\s*(Chapter\s+\d+)\b", re.I | re.M)
CHAPTER_NUM_TITLE = re.compile(r"^\s*\d+\s+[A-Z][A-Za-z].{0,80}$", re.M)  # “8 Conservation of Energy”
OUTLINE_NUM_RE    = re.compile(r"^\s*\d+\.\d+(\.\d+)?\b", re.M)           # “8.1”, “8.1.1”
PROBLEM_HEADER_RE = re.compile(
    r"\b(Problems?|Problem\s*Set|Exercises|End[-\s]?of[-\s]?Chapter|Homework|Tutorial\s*Problems|Practice\s*Problems|Multiple\s*Choice|Short\s*Answer|Questions?)\b",
    re.I,
)

def extract_page_texts(pdf_path: Path) -> List[str]:
    texts: List[str] = []
    reader = PdfReader(str(pdf_path))
    for p in reader.pages:
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        texts.append(t)
    return texts

def page_signals(text: str) -> PageSignals:
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    n_lines = len(lines)
    words = re.findall(r"\S+", text or "")
    n_words = len(words)
    if n_lines == 0:
        return PageSignals(0,0,0.0,0.0,0.0,0,0,0)
    digit_leads = len(DIGIT_LEAD_RE.findall(text))
    bullets     = len(BULLET_RE.findall(text))
    choices     = len(CHOICE_TOKEN_RE.findall(text))
    ratio_digit_leading = digit_leads / max(n_lines, 1)
    ratio_choice_tokens = choices / max(n_lines, 1)
    mean_line_len       = sum(len(ln) for ln in lines) / max(n_lines, 1)
    dense_blocks, consec = 0, 0
    for ln in lines:
        if DENSE_NUM_RE.match(ln) or BULLET_RE.match(ln):
            consec += 1
            if consec == 3:
                dense_blocks += 1
        else:
            consec = 0
    return PageSignals(n_lines, n_words, ratio_digit_leading, ratio_choice_tokens, mean_line_len,
                       bullets, dense_blocks, digit_leads)

def early_page_density(text: str, head_frac: float = 0.35) -> Tuple[float, int, int]:
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return 0.0, 0, 0
    cutoff = max(1, int(len(lines) * head_frac))
    head = "\n".join(lines[:cutoff])
    digit_leads_head = len(DIGIT_LEAD_RE.findall(head))
    dense_hits_head  = len(DENSE_NUM_RE.findall(head))
    ratio_head = digit_leads_head / max(cutoff, 1)
    return ratio_head, digit_leads_head, dense_hits_head

# ====== New helpers for end_idx guards ======
def looks_like_chapter_opener(text: str, sig: PageSignals) -> bool:
    """
    Heuristics for a chapter splash/TOC opener:
    - Presence of “Chapter <num>” at top OR a line like "<num> Title Case..." near top.
    - Very few numbered-leading lines overall and no dense blocks.
    - Outline numbering (8.1, 8.2, …) alone shouldn’t count as problems.
    """
    if not text:
        return False
    top_lines = [ln for ln in text.splitlines() if ln.strip()][:12]
    top_blob = "\n".join(top_lines)

    chapter_cue = bool(CHAPTER_WORD_RE.search(top_blob) or CHAPTER_NUM_TITLE.search(top_blob))
    # Opener pages typically have fewer lines and almost no problem-number runs
    opener_layout = (sig.n_lines <= 40 and sig.dense_blocks == 0 and sig.digit_lead_count <= 2)
    outline_only  = bool(OUTLINE_NUM_RE.search(top_blob))  # presence of 8.1, 8.2 list near header

    # Chapter opener if chapter cue present and problem signals are weak, even if outline numbers exist
    return (chapter_cue and opener_layout) or (chapter_cue and outline_only)

def has_problem_cue(text: str, sig: PageSignals, require_top_third: bool = True) -> bool:
    """
    Decide if page still contains actual problems (not TOC-like).
    Signals:
      - Problem-like numbering density (global or in top third),
      - explicit “Problems/Exercises/Questions” header,
      - choice tokens typical of MC.
    """
    if not text:
        return False
    if PROBLEM_HEADER_RE.search(text):
        return True
    # global signal
    if sig.dense_blocks >= 1 or sig.digit_lead_count >= 6 or sig.ratio_digit_leading >= 0.18:
        return True
    if not require_top_third:
        return False
    # early/top signal
    ratio_head, cnt_head, _ = early_page_density(text, head_frac=0.35)
    return (ratio_head >= 0.12) or (cnt_head >= 3)

def apply_end_guards(a: int, b: int, texts: List[str], sigs: List[PageSignals]) -> Tuple[int, int]:
    """
    Post-process end index only. Do not change 'a'.
    1) If page after b looks like a chapter opener, prefer stopping at b (but ensure b itself has problem cues).
    2) If b lacks problem cues, backtrack until a page with problem cues (>= a).
    3) If b is itself a chapter opener (shouldn’t happen often), backtrack.
    """
    n = len(texts)
    b0 = b

    # (3) If b is an opener, walk back
    while b >= a and looks_like_chapter_opener(texts[b], sigs[b]):
        b -= 1

    # (2) Ensure the chosen last page has problem cues
    while b >= a and not has_problem_cue(texts[b], sigs[b], require_top_third=False):
        b -= 1

    # (1) If next page is a chapter opener and current page is weak, retract
    if b + 1 < n and looks_like_chapter_opener(texts[b + 1], sigs[b + 1]):
        # Make sure last page truly contains problems; if weak, retract once more
        if not has_problem_cue(texts[b], sigs[b], require_top_third=False):
            b = max(a, b - 1)

    if b < a:
        b = a  # never cross start

    if b != b0:
        log(f"End guard adjusted end_idx: {b0} -> {b}", "INFO")
    return a, b

def guess_block_run_based(texts: List[str]):
    sigs = [page_signals(t) for t in texts]
    n = len(sigs)
    scores: List[float] = []
    for s in sigs:
        sc = (3.2*s.ratio_digit_leading + 2.4*s.dense_blocks + 1.2*s.ratio_choice_tokens +
              0.4*(1.0 if s.bullets_like >= 5 else 0.0))
        if s.n_lines < 8: sc -= 0.3
        if s.mean_line_len > 110: sc -= 0.2
        scores.append(sc)
    weak   = [ (s.ratio_digit_leading >= 0.12) or (s.digit_lead_count >= 5) or (s.dense_blocks >= 1) for s in sigs ]
    strong = [ (s.ratio_digit_leading >= 0.18) or (s.digit_lead_count >= 10) or (s.dense_blocks >= 1) for s in sigs ]
    best_len, best_pair = 0, (0, 0)
    i = 0
    while i < n:
        if not weak[i]:
            i += 1; continue
        j, has_strong = i, strong[i]
        while j + 1 < n and weak[j + 1]:
            j += 1
            has_strong = has_strong or strong[j]
        if has_strong and (j - i + 1) > best_len:
            best_len = j - i + 1; best_pair = (i, j)
        i = j + 1
    if best_len == 0:
        idx = max(range(n), key=lambda k: sigs[k].ratio_digit_leading if n else 0)
        return idx, idx, sigs, scores

    a, b = best_pair

    def very_weak(s: PageSignals) -> bool:
        return (s.digit_lead_count < 3 and s.ratio_digit_leading < 0.10 and s.dense_blocks == 0)

    # --- START SIDE (UNCHANGED) ---
    while a < b and very_weak(sigs[a]): a += 1
    # LEFT START GATE
    HEAD_RATIO_MIN, HEAD_MIN_COUNT = 0.10, 4
    while a < b:
        ratio_head, cnt_head, _ = early_page_density(texts[a], head_frac=0.35)
        if (ratio_head >= HEAD_RATIO_MIN) or (cnt_head >= HEAD_MIN_COUNT) or (sigs[a].dense_blocks >= 1):
            break
        a += 1
    # --- END SIDE (TAIL PROTECTION with stronger guards) ---
    def problem_dense(s: PageSignals) -> bool:
        return (s.ratio_digit_leading >= 0.18) or (s.digit_lead_count >= 8) or (s.dense_blocks >= 1)
    def looks_like_new_section_soft(s: PageSignals) -> bool:
        return (s.n_lines <= 8 and s.digit_lead_count == 0 and s.dense_blocks == 0)

    k, low_streak = b + 1, 0
    while k < n:
        # HARD STOP: chapter opener -> do NOT include k; break immediately
        if looks_like_chapter_opener(texts[k], sigs[k]):
            break
        if problem_dense(sigs[k]):
            low_streak = 0; b = k
        else:
            low_streak += 1
            if low_streak == 1:
                if (sigs[b].digit_lead_count >= 5) or (sigs[b].dense_blocks >= 1):
                    b = k
            elif low_streak >= 2:
                break
        k += 1

    # If the next page after b *softly* looks like a new section and current b is very weak, retract to stronger page
    if b + 1 < n and looks_like_new_section_soft(sigs[b + 1]) and very_weak(sigs[b]):
        while b > a and very_weak(sigs[b]): b -= 1

    # FINALIZE END USING GUARDS (does not alter 'a')
    a, b = apply_end_guards(a, b, texts, sigs)
    return a, b, sigs, scores

def llm_suggest_range(texts: List[str], backend: str, model_name: str) -> Optional[Tuple[int, int]]:
    backend = (backend or "").lower()
    have_key = False
    if backend == "gemini" and genai and os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY")); have_key = True
    elif backend in ("openai", "deepseek") and OpenAI and (os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")):
        have_key = True
    if not have_key: return None

    snippets = []
    for i, t in enumerate(texts):
        t_clean = re.sub(r"\s+", " ", t or "").strip()
        snippets.append(f"[{i}] {t_clean[:900]}")

    synonyms = ["Problems","Problem Set","Exercises","End-of-Chapter Problems","Review Questions",
                "Conceptual Questions","Multiple Choice","Short Answer","Problems & Applications",
                "Practice Problems","Homework Problems","Tutorial Problems","Challenge Problems",
                "Discussion Questions","Self-Test","Questions","End-of-Unit","End of Chapter",
                "Chapter Review","Test Yourself"]
    stops = ["Chapter","Chapter \\d+","Next Chapter","Appendix","References",
             "Further Reading","Bibliography","Index","Solutions"]

    prompt = f"""
You are given page-wise text snippets from a textbook-like PDF. Your task is to select the SINGLE contiguous
block that corresponds to the end-of-chapter PROBLEM SET.

STRICT REQUIREMENTS:
1) Return STRICT JSON ONLY: {{"start_idx": INT, "end_idx": INT}} using 0-based page indexes (inclusive).
2) Choose the FIRST page that is clearly part of the Problems/Exercises section as start_idx.
   - If a page contains only the tail of a prior subsection (e.g., worked example, summary) with a few numbers,
     DO NOT start there. Start on the first page where the numbered problems clearly begin.
3) Prefer STRUCTURAL CUES over headers, because many PDFs lack clear labels:
   Positive signals (strongest at the top of page):
   - Many lines begin with numerals or letters then ')' or '.'  e.g., "1)", "2.", "a)" early in the page.
   - Repeated choice tokens like "(A) (B) (C) (D)" or "A) B) C) D)".
   - Short problem stems followed by subparts (a), (b), (c)…
   - A sequence of at least ~8–10 numbered items, or multiple short numbered paragraphs.
   Negative signals (do NOT start on these):
   - Long prose paragraphs at the top with few/no numbered lines in the top third of the page.
   - Worked EXAMPLES with labels or multi-line derivations dominating the top of page.
   - Summaries, “Analysis Models for Problem Solving”, “Storyline”, or review prose before the problem list.
4) End the block at the LAST page that still contains problems. Exclude the next chapter’s opener.
   Ending cues:
   - If a page is lighter (few items) but still contains problems, include it.
   - Stop once you encounter two consecutive non-problem pages or a clear new-chapter opener
     (very few lines, zero numbering, and different layout).
5) If uncertain, choose the LONGEST run that satisfies (2) and (4).

Possible labels you might see (not required): {", ".join(synonyms)}.
Hard stop indicators include: {", ".join(stops)}.

HINT: The correct start_idx is the first page whose TOP THIRD already looks like a problem list.

Pages:
{chr(10).join(snippets)}
JSON:
""".strip()

    try:
        if backend == "gemini":
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            text = getattr(resp, "text", "") or ""
        else:
            if backend == "openai":
                key = os.getenv("OPENAI_API_KEY"); client = OpenAI(api_key=key)
            else:
                key = os.getenv("DEEPSEEK_API_KEY"); client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
            cr = client.chat.completions.create(model=model_name, messages=[{"role":"user","content":prompt}], temperature=0.1)
            text = cr.choices[0].message.content
        m = re.search(r"\{.*\}", text, re.S)
        if not m: log("LLM did not return JSON; ignoring.", "WARN"); return None
        data = json.loads(m.group(0)); si, ei = int(data["start_idx"]), int(data["end_idx"])
        si = max(0, min(si, len(texts)-1)); ei = max(si, min(ei, len(texts)-1))
        return (si, ei)
    except Exception as e:
        log(f"LLM classification failed: {e}", "WARN"); return None

def write_cropped(pdf_in: Path, pdf_out: Path, start: int, end: int) -> None:
    reader = PdfReader(str(pdf_in)); writer = PdfWriter()
    n = len(reader.pages); start = max(0, min(start, n-1)); end = max(start, min(end, n-1))
    for i in range(start, end+1): writer.add_page(reader.pages[i])
    with open(pdf_out, "wb") as f: writer.write(f)

# ====== CLI & pipeline ======
ap = argparse.ArgumentParser()
ap.add_argument("--in",  dest="pdf_in",  default="source.pdf")
ap.add_argument("--out", dest="pdf_out", default="problems.pdf")
ap.add_argument("--llm", dest="llm_backend", default=os.getenv("CROP_LLM", "gemini"))
ap.add_argument("--model", dest="model_name", default=os.getenv("CROP_MODEL", "gemini-2.5-flash-lite"))
ap.add_argument("--debug", action="store_true")
args = ap.parse_args()

pdf_in, pdf_out = Path(args.pdf_in), Path(args.pdf_out)
if not pdf_in.exists(): log(f"Input not found: {pdf_in}", "ERROR"); raise SystemExit(1)

texts = extract_page_texts(pdf_in)
n_pages = len(texts)
log(f"Loaded {n_pages} pages from {pdf_in}")

# Heuristic pass
h_start, h_end, sigs, scores = guess_block_run_based(texts)
log(f"Heuristic suggests {h_start}..{h_end}")

# Optional LLM reconciliation (UNCHANGED), followed by end-side guard clipping
start_end = llm_suggest_range(texts, args.llm_backend, args.model_name)
if start_end:
    s1, e1 = start_end
    overlap = max(0, min(e1, h_end) - max(s1, h_start) + 1)
    span = max(e1, h_end) - min(s1, h_start) + 1
    if overlap / max(span, 1) >= 0.33:
        start, end = min(s1, h_start), max(e1, h_end)
    else:
        start, end = (s1, e1) if (e1 - s1) >= (h_end - h_start) else (h_start, h_end)
    # Apply end-guards without touching start
    _, end = apply_end_guards(start, end, texts, sigs)
    log(f"LLM suggested {s1}..{e1} -> using {start}..{end} (after end-guards)")
else:
    start, end = h_start, h_end

write_cropped(pdf_in, pdf_out, start, end)

diag = {
    "input": str(pdf_in),
    "output": str(pdf_out),
    "pages_total": n_pages,
    "start_idx": start,
    "end_idx": end,
    "notes": "Structure-based selection with start-gate; end safeguarded by chapter-opener/Problem-cue checks; optional LLM with end-guard clipping."
}
with open(pdf_out.with_suffix(".json"), "w", encoding="utf-8") as f:
    json.dump(diag, f, ensure_ascii=False, indent=2)

if args.debug:
    from csv import writer
    dbg = pdf_out.with_suffix(".signals.csv")
    with open(dbg, "w", newline="", encoding="utf-8") as f:
        w = writer(f)
        w.writerow(["page","n_lines","digit_leads","dense_blocks","ratio_digit_leading",
                    "ratio_choice_tokens","mean_line_len","score"])
        for i,(s,sc) in enumerate(zip(sigs, scores)):
            w.writerow([i, s.n_lines, s.digit_lead_count, s.dense_blocks,
                        f"{s.ratio_digit_leading:.3f}", f"{s.ratio_choice_tokens:.3f}",
                        f"{s.mean_line_len:.1f}", f"{sc:.3f}"])
    log(f"Signals CSV -> {dbg}")

log(f"Cropped to pages {start}..{end} -> {pdf_out}")
log(f"Diagnostics -> {pdf_out.with_suffix('.json')}")
log(f"PDF backend: {BACKEND}")


##
p = Path.cwd()
target_dir = p.parent / "problems"   # same as p.parents[0] / "problems"
os.makedirs(target_dir, exist_ok=True)

src = p / "problems.pdf"
dst = target_dir / "problems.pdf"

import shutil
shutil.move(str(src), str(dst))
print(f"problems.pdf Moved to: {dst}")

# also save problems.pdf as source.pdf in target_dir
dst2 = target_dir / "source.pdf"
shutil.copy(str(dst), str(dst2))
print(f"cp problems.pdf as source.pdf in {target_dir}")

## crop source.pdf from page 1 until the begining page of problems.pdf
pdf_path = Path("source.pdf")
# === Step 1: Rename 'source.pdf' to 'source_orig.pdf' ===
orig_path = pdf_path.with_name("source_orig.pdf")
if not orig_path.exists():
    shutil.move(pdf_path, orig_path)
    print(f"Renamed '{pdf_path}' → '{orig_path}'")
else:
    print(f"'{orig_path}' already exists; keeping it.")

# === Step 2: Copy pages from 1 to 'start' into new 'source.pdf' ===
reader = PdfReader(orig_path)
writer = PdfWriter()

# Ensure we don’t exceed total page count
end_page = min(start, len(reader.pages))

for i in range(end_page):  # PyPDF2 uses 0-based indexing
    writer.add_page(reader.pages[i])

# Write out the new file
with open(pdf_path, "wb") as f_out:
    writer.write(f_out)

print(f"Extracted pages 1–{end_page} from '{orig_path}' → '{pdf_path}'")
##