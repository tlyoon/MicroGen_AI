#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gemini-native figure caption mapping for v7.

Preserves map_and_rename_v4 output behavior while using the shared Microvid
GEMINI_API_KEY and the modern google-genai SDK.
"""
import os, re, shutil, sys
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
from google import genai
from google.genai import types

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MODEL_NAME = os.environ.get("MICROVID_FIGURE_MODEL", "gemini-2.5-pro")
BATCH_SIZE = 4


def _microvid_config_dir() -> Path:
    configured = os.environ.get("MICROVID_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Microvid"
    return Path.home() / "AppData" / "Local" / "Microvid"


env_path = _microvid_config_dir() / ".env"
if not env_path.is_file():
    raise RuntimeError(f"Shared Microvid credential file not found: {env_path}")
print(f"Using shared Microvid API credentials from: {env_path}")
load_dotenv(dotenv_path=env_path, override=False)
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set in the shared Microvid .env")
client = genai.Client(api_key=api_key)
print(f"Using Gemini model for figure mapping: {MODEL_NAME}")


def image_part(path: Path):
    return types.Part.from_bytes(data=path.read_bytes(), mime_type="image/png")


def generate(parts):
    response = client.models.generate_content(model=MODEL_NAME, contents=parts)
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response")
    return text


def merge_images_horizontally(image_paths, output_path):
    imgs = [Image.open(p).convert("RGB") for p in image_paths if Path(p).exists()]
    if not imgs:
        return
    widths, heights = zip(*(im.size for im in imgs))
    merged = Image.new("RGB", (sum(widths), max(heights)), (255, 255, 255))
    x = 0
    for im in imgs:
        merged.paste(im, (x, 0))
        x += im.width
    merged.save(output_path)
    for im in imgs:
        im.close()
    print(f"Merged {len(image_paths)} images -> {output_path.name}")


CAPTION_PROMPT = """Examine this textbook page image and extract every figure caption that visibly appears on the page.
Rules:
1. Do not invent figure numbers or labels.
2. If an image is not formally labelled, do not assign it a Figure number.
3. Use layout reasoning to associate captions with figures.
4. Return concise lines such as:
- Figure 1.7: caption text
- Figure 1.8a: caption text
- Unlabeled image: short description
"""


def safe_destination(name: str, page_dir: Path) -> Path | None:
    name = name.strip().strip('"').strip("'")
    name = name.replace("\\", "/").split("/")[-1]
    if not name.lower().endswith(".png"):
        name += ".png"
    if not re.match(r"^[A-Za-z0-9 ._()\-]+\.png$", name, re.I):
        return None
    return page_dir.parent / name


def mapping():
    pages_root = Path("pages")
    page_dirs = sorted(
        [p for p in pages_root.glob("page_*") if p.is_dir()],
        key=lambda p: int(re.search(r"(\d+)$", p.name).group(1)),
    )

    for page_dir in page_dirs:
        print(f"\nProcessing {page_dir.name}")
        full_page_image = page_dir / f"{page_dir.name}.png"
        caption_file = page_dir / f"{page_dir.name}_captions.txt"
        if not full_page_image.is_file():
            print(f"Missing page image: {full_page_image}; skipping")
            continue

        try:
            caption_text = generate([CAPTION_PROMPT, image_part(full_page_image)])
            caption_file.write_text(caption_text, encoding="utf-8")
            print(f"Captions saved to: {caption_file.name}")
        except Exception as exc:
            print(f"Caption extraction failed for {page_dir.name}: {exc}")
            continue

        fig_files = sorted(
            page_dir.glob("fig_*.png"),
            key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)),
        )
        if not fig_files:
            print("No extracted figures to map on this page")
            continue

        for start in range(0, len(fig_files), BATCH_SIZE):
            batch = fig_files[start:start + BATCH_SIZE]
            batch_names = "\n".join(f"- {p.name}" for p in batch)
            prompt = f"""You are mapping extracted textbook figure crops back to the visible captions on the same page.
Use only the provided files and the captions actually visible on the page. Never invent a figure number.
For each crop, return exactly one line in this format:
fig_2.png : \"Figure 1.7\" : Figure 1.7.png
If a crop is not a formally captioned textbook figure, return:
fig_2.png : \"UNLABELED\" : SKIP

Files in this batch:
{batch_names}

Extracted caption text:
{caption_text}
"""
            parts = [prompt, "Full textbook page:", image_part(full_page_image)]
            for fig in batch:
                parts.extend([f"Crop file: {fig.name}", image_part(fig)])

            try:
                response_text = generate(parts)
                mapped_pairs = {}
                for raw in response_text.splitlines():
                    line = raw.strip().lstrip("- ")
                    m = re.match(r"^(fig_\d+\.png)\s*:\s*.*?\s*:\s*(.+?)\s*$", line, re.I)
                    if not m:
                        continue
                    src = page_dir / m.group(1)
                    dest_text = m.group(2).strip().strip('`')
                    if dest_text.upper().startswith("SKIP") or not src.is_file():
                        continue
                    dst = safe_destination(dest_text, page_dir)
                    if dst is None:
                        print(f"Rejected unsafe destination: {dest_text}")
                        continue
                    shutil.copy2(src, dst)
                    print(f"Mapped: {src.name} -> {dst.name}")
                    mapped_pairs.setdefault(dst, []).append(src)

                for dst, srcs in mapped_pairs.items():
                    if len(srcs) > 1:
                        merge_images_horizontally(srcs, dst)
            except Exception as exc:
                print(f"Mapping batch failed on {page_dir.name}: {exc}")

    for png in pages_root.glob("*.png"):
        target = Path.cwd() / png.name
        shutil.move(str(png), str(target))
        print(f"Moved: {png.name} -> {target.name}")


if __name__ == "__main__":
    import merge_lettered_figs_v2
    print("Starting Gemini figure mapping process...")
    mapping()
    merge_lettered_figs_v2.main()
    print("Figure mapping completed.")
