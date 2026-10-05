#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, json, sys, time
from pathlib import Path
from PyPDF2 import PdfReader
from dotenv import load_dotenv

# Optional clients
from openai import OpenAI
import google.generativeai as genai

# --- Console encoding (Windows safe) ---
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# --- Load .env ---
try:
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
except NameError:
    env_path = Path(os.getcwd()).parent.parent.parent / '.env'
if not env_path.is_file():
    env_path = '.env'
load_dotenv(dotenv_path=env_path)

# --- API keys & model selection (prefer Gemini if present) ---
api_key_dsk    = os.getenv("DEEPSEEK_API_KEY")
api_key_oai    = os.getenv("OPENAI_API_KEY")
api_key_gemini = os.getenv("GEMINI_API_KEY")

model_choice = None
model_name   = None
client       = None

if api_key_gemini:
    model_choice = 'gemini'
    model_name   = "gemini-3.1-pro-preview"
    genai.configure(api_key=api_key_gemini)
elif api_key_oai:
    model_choice = 'openai'
    model_name   = "gpt-4o"
    client = OpenAI(api_key=api_key_oai)
elif api_key_dsk:
    model_choice = 'deepseek'
    model_name   = "deepseek-reasoner"
    client = OpenAI(api_key=api_key_dsk, base_url="https://api.deepseek.com")
else:
    raise EnvironmentError("❌ No valid API key found in .env (GEMINI_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY).")

print(f"Using model_choice = {model_choice}, model_name = {model_name}")

# ------------- Config -------------
start_time = time.time()
start_page = 1
end_page   = 36
output_filename = f"{start_page}_{end_page}.pdf"   # this PDF slice will be included as a binary part
final_md = "source.md"                              # inlined as text

# ------------- Read TOC from the PDF slice -------------
INPUT_PDF = output_filename
p_pdf = Path(INPUT_PDF)
if not p_pdf.is_file():
    raise FileNotFoundError(f"❌ PDF slice not found: {INPUT_PDF}")

reader = PdfReader(INPUT_PDF)
toc_text = ""
for i in range(min(50, len(reader.pages))):
    page = reader.pages[i].extract_text() or ""
    if page:
        toc_text += page + "\n"

if not toc_text.strip():
    raise RuntimeError("❌ TOC text could not be extracted from the PDF slice.")

# ------------- Read Markdown content -------------
markdown_path = final_md
p_md = Path(markdown_path)
if not p_md.is_file():
    raise FileNotFoundError(f"❌ Markdown body not found: {markdown_path}")
markdown_text = p_md.read_text(encoding="utf-8")
markdown_excerpt = markdown_text  # use full text

# ------------- Prompt (explicitly mentions the attached PDF) -------------
prompt = f"""
You are a textbook analysis assistant.

You are provided with THREE inputs:
1) A **TOC text** extracted from the first {end_page} pages of a searchable textbook PDF (includes visible page numbers).
2) A **Markdown body** (`{final_md}`) containing the textbook content (inline in this message).
3) An **attached PDF slice** file named `{output_filename}` (the same TOC region/pages), which you can open to inspect printed page numbers, headings, and local context.

Your task is to return a structured JSON list of **all subchapter entries and unnumbered subsections** that appear in the TOC, with correct begin/end pages (visible) and physical pages, using a single page offset.

(1) Enumerate ALL subchapters / subsections
- Parse ALL TOC lines to extract:
  • Every **numbered subchapter** (e.g., "1.1", "2.3", "22.6.4.1") under each chapter (no omissions).
  • Any **unnumbered TOC subsections** (e.g., "Practice Exercises", "Questions", "Review Problems", "Summary") that belong to the most recent chapter.
- For unnumbered items, assign them to the current chapter scope (e.g., title "2 Problem Set").

(2) Determine a SINGLE page offset
- Compute one integer offset so that: physical_page = visible_page + offset.
- Derive it by matching at least **three** subchapter titles between the TOC and the Markdown body (normalize titles: lowercase, collapse whitespace, remove dot leaders, de-hyphenate line breaks, Unicode NFKC).
- You may consult the **attached PDF** to confirm printed page numbers in headers/footers or to disambiguate locations.
- Apply this single offset to all items:
  • begin_physical = begin + offset
  • end_physical   = end   + offset

(3) Begin/End rules (visible pages)
- For each numbered subchapter within a chapter: set begin = its TOC page; set end = (next sibling’s TOC page) within the same chapter.
- For unnumbered items: treat exactly like subchapters (use their TOC page as begin; end is next item’s begin within the same chapter).
- For the final item in a chapter: if no next chapter is present in the TOC context, set end = begin + 5.

(4) Output format (JSON only; no commentary, no code fences)
{{
  "offset": <integer>,
  "subchapters": [
    {{
      "title": "<exact title as printed in TOC>",
      "begin": <int visible>,
      "begin_physical": <int>,
      "end": <int visible>,
      "end_physical": <int>
    }}
  ]
}}

===== BEGIN TOC =====
{toc_text}
===== END TOC =====

===== BEGIN MARKDOWN BODY =====
{markdown_excerpt}
===== END MARKDOWN BODY =====
"""

# ------------- LLM call -------------
if model_choice == 'gemini':
    # Inline the PDF as a binary part (no upload, no RAG store)
    pdf_bytes = p_pdf.read_bytes()
    parts = [
        {"text": prompt},
        {"mime_type": "application/pdf", "data": pdf_bytes},
    ]
    response_text = genai.GenerativeModel(model_name).generate_content(
        parts,
        request_options={"timeout": 600},
    ).text
elif model_choice in ['openai', 'deepseek']:
    response_text = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    ).choices[0].message.content
else:
    raise ValueError("Invalid model.")

print("🔎 Raw LLM Response:\n", response_text)

# ------------- Strip markdown fences -------------
response_text = (response_text or "").strip()
if response_text.startswith("```json"):
    response_text = response_text[7:]
elif response_text.startswith("```"):
    response_text = response_text[3:]
if response_text.endswith("```"):
    response_text = response_text[:-3]

if not response_text:
    raise RuntimeError("❌ Empty response from LLM.")

# ------------- Parse JSON -------------
try:
    result = json.loads(response_text)
except Exception as e:
    Path("subchapter_index_physical.raw.txt").write_text(response_text, encoding="utf-8")
    raise RuntimeError(f"❌ Failed to parse JSON from LLM. Raw saved to subchapter_index_physical.raw.txt ({e})")

# ------------- Save (subchapters list) -------------
Path("subchapter_index_physical.json").write_text(
    json.dumps(result.get("subchapters", []), indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(f"✅ subchapter_index_physical.json created with offset {result.get('offset', 'N/A')}. Elapsed {time.time()-start_time:.2f}s")
