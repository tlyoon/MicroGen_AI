from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SLIDES_FILE = Path("slides.pdf")
SOURCE_FILE = Path("source.pdf")
SCRIPT_FILE = Path("script.txt")
TTS_SIDECAR = Path("script_tts.json")
NARRATION_WPM = int(os.environ.get("MICROVID_NARRATION_WPM", "130"))
MAX_SOURCE_CHARACTERS = int(os.environ.get("MICROVID_MAX_NARRATION_SOURCE_CHARS", "250000"))
DEFAULT_BODY_SECONDS = int(os.environ.get("MICROVID_DEFAULT_SLIDE_SECONDS", "45"))
MODEL_NAME = os.environ.get("MICROVID_NARRATION_MODEL", "gemini-flash-latest")
THINKING_LEVEL = os.environ.get("MICROVID_THINKING_LEVEL", "high").upper()

URL_RE = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.I)
PAGE_COUNTER_RE = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")
SECTION_RE = re.compile(r"^\s*\d+(?:\.\d+)*\s+[A-Za-z]")
NOISE_WORDS = {"large-corner", "small-corner", "corner", "footer", "header", "slide", "page", "untitled", "copyright"}


def _microvid_config_dir() -> Path:
    configured = os.environ.get("MICROVID_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Microvid"
    return Path.home() / "AppData" / "Local" / "Microvid"


def _load_runtime_environment() -> Path:
    config_dir = _microvid_config_dir()
    env_path = config_dir / ".env"
    if not env_path.is_file():
        raise RuntimeError(
            f"Shared Microvid credential file not found: {env_path}. "
            "Create %LOCALAPPDATA%\\Microvid\\.env (or set MICROVID_CONFIG_DIR)."
        )
    load_dotenv(dotenv_path=env_path, override=False)
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError(f"GEMINI_API_KEY is not set in {env_path} or the current environment.")
    print(f"Using shared Microvid API credentials from: {env_path}")
    return config_dir


def _read_prompt(name: str) -> str:
    path = Path(name)
    if not path.is_file():
        raise FileNotFoundError(
            f"Required pri narration prompt is missing: {path}. "
            "The v7 template must contain narration_polish.md and system_microcredential_architect.md."
        )
    return path.read_text(encoding="utf-8")


def clean_title_line(value: str) -> str:
    value = URL_RE.sub("", value or "")
    value = " ".join(value.split())
    if not value or PAGE_COUNTER_RE.match(value) or value.lower() in NOISE_WORDS or len(value) < 3:
        return ""
    return value


def pick_best_title(lines: list[str]) -> str:
    candidates: list[tuple[int, str]] = []
    for line in lines:
        cleaned = clean_title_line(line)
        if not cleaned:
            continue
        score = 100 if SECTION_RE.match(cleaned) else 0
        score += min(len(cleaned), 120)
        score += 5 * (len(cleaned.split()) >= 3)
        score -= sum(ch in "-_/\\|[]{}()" for ch in cleaned)
        candidates.append((score, cleaned))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_pdf_pages(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required PDF not found: {path}")
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to read slides.pdf and source.pdf.") from exc
    doc = fitz.open(path)
    try:
        pages: list[dict[str, Any]] = []
        for idx, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            pages.append({"page": idx, "text": text.strip(), "lines": lines})
        return pages
    finally:
        doc.close()


def _slide_manifest(slide_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for idx, page in enumerate(slide_pages, start=1):
        lines = list(page["lines"])
        title = pick_best_title(lines)
        onscreen = lines[:]
        initial_narration = title if idx == 1 else " ".join(lines)
        slides.append(
            {
                "id": f"slide_{idx:02d}",
                "slide_type": "title" if idx == 1 else "content",
                "title": title or (lines[0] if lines else f"Slide {idx}"),
                "onscreen": onscreen,
                "narration": initial_narration,
                "visual_direction": "The learner sees the fixed v7 PDF slide exactly as generated; explain it without changing its content.",
                "visual_type": "fixed_pdf_slide",
                "visual_panels": [],
                "table_headers": [],
                "table_rows": [],
                "equation_latex": None,
                "figure_ids": [],
                "figure_assets": [],
                "source_block_ids": [],
                "estimated_seconds": 8 if idx == 1 else DEFAULT_BODY_SECONDS,
            }
        )
    return slides


def _source_blocks(source_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks = []
    total = 0
    for page in source_pages:
        text = str(page["text"])
        total += len(text)
        blocks.append({"id": f"source_page_{page['page']:03d}", "page": page["page"], "text": text})
    if total > MAX_SOURCE_CHARACTERS:
        raise RuntimeError(
            f"source.pdf contains {total} extracted characters, exceeding the narration limit "
            f"of {MAX_SOURCE_CHARACTERS}. The source is not silently truncated."
        )
    return blocks


def _available_figures() -> list[dict[str, str]]:
    names = sorted({p.name for pattern in ("Figure*.png", "FIGURE*.png", "figure*.png") for p in Path.cwd().glob(pattern)})
    return [{"file": name} for name in names]


def _schema(slide_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "slides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "slide_id": {"type": "string", "enum": slide_ids},
                        "narration": {"type": "string"},
                        "tts_text": {"type": ["string", "null"]},
                    },
                    "required": ["slide_id", "narration", "tts_text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["slides"],
        "additionalProperties": False,
    }


def _compose_prompt(slides: list[dict[str, Any]], source_blocks: list[dict[str, Any]]) -> str:
    payload = {
        "narration_wpm": NARRATION_WPM,
        "source_document": {
            "path": str(SOURCE_FILE),
            "type": "textbook_subchapter",
            "page_count": len(source_blocks),
        },
        "available_figures": _available_figures(),
        "global_course_context": None,
        "lesson": {
            "title": slides[0]["title"] if slides else "",
            "instruction": "Keep the fixed v7 slide order and content; improve only the spoken explanation.",
        },
        "authoritative_core_blocks": source_blocks,
        "reference_blocks": [],
        "fixed_lesson_manifest": {
            "video_id": "v7_legacy_compat",
            "title": slides[0]["title"] if slides else "",
            "focus": "Explain the fixed v7 slide deck faithfully from source.pdf.",
            "learning_outcomes": [],
            "slides": slides,
        },
    }
    return "\n\n".join(
        [
            _read_prompt("system_microcredential_architect.md"),
            _read_prompt("narration_polish.md"),
            "## V7 COMPATIBILITY NOTE\n"
            "This is a v7 fixed-PDF slide deck. Preserve every slide exactly. Return narration for every slide ID. "
            "For slide_01 (the title card), keep narration brief and limited to the displayed title/topic; do not invent an introduction there. "
            "The real explanatory opening belongs on the first substantive slide.\n\n"
            "## FIXED LESSON AND SOURCE CONTEXT\n```json\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + "\n```",
        ]
    )


def _gemini_compatible_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _gemini_compatible_schema(v) for k, v in value.items() if k not in {"minItems", "maxItems"}}
    if isinstance(value, list):
        return [_gemini_compatible_schema(v) for v in value]
    return value


def _is_transient(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if callable(code):
        code = code()
    text = str(code).upper()
    return code in {408, 429, 500, 502, 503, 504} or any(x in text for x in ("RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED", "INTERNAL"))


def _generate_polished(slides: list[dict[str, Any]], source_blocks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("The pri narration engine requires google-genai. Install requirements.txt.") from exc

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=_gemini_compatible_schema(_schema([s["id"] for s in slides])),
        thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    prompt = _compose_prompt(slides, source_blocks)
    text = ""
    for attempt in range(3):
        try:
            chunks = client.models.generate_content_stream(model=MODEL_NAME, contents=prompt, config=config)
            text = "".join(chunk.text or "" for chunk in chunks)
            break
        except Exception as exc:
            if attempt == 2 or not _is_transient(exc):
                raise RuntimeError(f"Pri narration generation failed for {MODEL_NAME}: {exc}") from exc
            time.sleep(2**attempt)
    if not text:
        raise RuntimeError(f"Pri narration model {MODEL_NAME} returned an empty response.")
    try:
        response = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Pri narration model returned invalid JSON despite structured-output mode.") from exc

    items = response.get("slides", [])
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        slide_id = str(item.get("slide_id", ""))
        if slide_id in by_id:
            raise RuntimeError(f"Narration response returned duplicate slide ID {slide_id}.")
        by_id[slide_id] = item
    expected = {s["id"] for s in slides}
    if set(by_id) != expected:
        raise RuntimeError(f"Narration response must contain every slide exactly once. Missing={sorted(expected-set(by_id))}; extra={sorted(set(by_id)-expected)}")
    return by_id


def _speech_hygiene(text: str, slide_id: str) -> None:
    if not text.strip():
        raise RuntimeError(f"Empty narration returned for {slide_id}.")
    forbidden = [r"\\frac\b", r"\\begin\b", r"```", r"\$[^$]+\$", r"\bsource[_ ]block\b", r"\bjson schema\b", r"(?:cite|filecite|memcite)"]
    if any(re.search(pattern, text, flags=re.I) for pattern in forbidden):
        raise RuntimeError(f"Narration for {slide_id} contains production markup or raw mathematical notation unsuitable for TTS.")


def _reading_time(text: str) -> str:
    words = len(re.findall(r"\b[\w’'-]+\b", text))
    seconds = int(round(words * 60 / max(1, NARRATION_WPM)))
    if seconds < 60:
        return f"{seconds} sec"
    minutes, rem = divmod(seconds, 60)
    return f"{minutes} min {rem} sec"


def _rotate(path: Path) -> None:
    if not path.exists():
        return
    count = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{count}{path.suffix}")
        if not candidate.exists():
            path.rename(candidate)
            print(f"Existing {path.name} renamed to {candidate.name}")
            return
        count += 1


def main() -> None:
    _load_runtime_environment()
    slide_pages = _extract_pdf_pages(SLIDES_FILE)
    source_pages = _extract_pdf_pages(SOURCE_FILE)
    if not slide_pages:
        raise RuntimeError("slides.pdf contains no pages.")
    slides = _slide_manifest(slide_pages)
    source_blocks = _source_blocks(source_pages)
    polished = _generate_polished(slides, source_blocks)

    # Preserve v7 title-card behaviour: the first audio says the displayed title/topic only.
    first_title = slides[0]["title"].strip()
    if first_title:
        polished[slides[0]["id"]]["narration"] = first_title
        polished[slides[0]["id"]]["tts_text"] = first_title

    _rotate(SCRIPT_FILE)
    _rotate(TTS_SIDECAR)

    sidecar_slides = []
    with SCRIPT_FILE.open("w", encoding="utf-8") as out:
        for idx, slide in enumerate(slides, start=1):
            item = polished[slide["id"]]
            narration = str(item.get("narration", "")).strip().strip("*").strip()
            tts_text = item.get("tts_text")
            tts_text = str(tts_text).strip() if tts_text is not None and str(tts_text).strip() else narration
            _speech_hygiene(narration, slide["id"])
            _speech_hygiene(tts_text, slide["id"])
            timing = "1 sec" if idx == 1 else _reading_time(narration)
            out.write(f"**Slide {idx} [{timing}]: \n{narration}**\n\n")
            sidecar_slides.append(
                {
                    "slide": idx,
                    "slide_id": slide["id"],
                    "title": slide["title"],
                    "narration": narration,
                    "tts_text": tts_text,
                    "estimated_spoken_time": timing,
                }
            )
            print(f"Generated pri-style narration for Slide {idx}")

    TTS_SIDECAR.write_text(
        json.dumps(
            {
                "engine": "pri narration_polish compatibility adapter",
                "provider": "gemini",
                "model": MODEL_NAME,
                "thinking_level": THINKING_LEVEL,
                "narration_wpm": NARRATION_WPM,
                "slides": sidecar_slides,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Narration scripts saved to: {SCRIPT_FILE}")
    print(f"TTS sidecar saved to: {TTS_SIDECAR}")


if __name__ == "__main__":
    main()
