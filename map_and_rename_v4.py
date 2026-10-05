#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
map_and_rename_v4.py
--------------------
Performs caption extraction and figure–caption mapping using LLM (Gemini/OpenAI/DeepSeek),
and merges multiple cropped figures (from the same page) that correspond to the same
figure label into one horizontally stacked composite image.

Update from v3:
- All *.png files overwrite existing files without suffix numbering.
- No file renaming fallback (i.e. Figure 7.1.png always overwrites any old file).
"""

import os, re, time, shutil, base64, sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

## set ikB. PNG image of filesize smaller than ikB kB will be filtered out and not saved.
ikB = 2.55    ### ikb = 2.55 works for Serway v10.  This is the default.
#ikB = 4.9    ### ikb = 4.9 works for Resnick and Halliday.
#ikB = 4.0    ### ikb = 4.0 works for Thomas Calculus 13 ed.

## gpt model pricing ##
#Model	            Input	Cached input	Output
#gpt-5	            $2.50	$0.25	        $20.00
#gpt-5-mini	        $0.45	$0.045	        $3.60
#gpt-5-codex	    $2.50	$0.25	        $20.00
#gpt-4.1	        $3.50	$0.875	        $14.00
#gpt-4.1-mini	    $0.70	$0.175	        $2.80
#gpt-4.1-nano	    $0.20	$0.05	        $0.80
#gpt-4o	            $4.25	$2.125	        $17.00
#gpt-4o-2024-05-13	$8.75	-	            $26.25
#gpt-4o-mini	    $0.25	$0.125	        $1.00
#o3	                $3.50	$0.875	        $14.00
#o4-mini	        $2.00	$0.50	        $8.00
## end of gpt model pricing ##

### specify model here ###
model_name = "gpt-5-mini"    ### worked. Use this a default
#model_name = "gpt-4o-mini"
#model_name = "gpt-4.1-mini"  ### non-ideal
model_choice = "openai"
### end of specify model here ###

# --- Load environment and API key from shared Microvid config ---
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

api_key_dsk = os.getenv("DEEPSEEK_API_KEY")
api_key_oai = os.getenv("OPENAI_API_KEY")
api_key_gemini = os.getenv("GEMINI_API_KEY")

if model_choice == "gemini":
    api_key = api_key_gemini
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    chat_session = model.start_chat()
elif model_choice == "openai":
    api_key = api_key_oai
    client = OpenAI(api_key=api_key)
elif model_choice == "deepseek":
    api_key = api_key_dsk
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
else:
    raise ValueError("Unsupported model_choice")

print(f"✅ Using model: {model_choice} ({model_name})")


# --- Utility functions ---
def encode_image_b64(path: Path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def merge_images_horizontally(image_paths, output_path):
    """Merge several images horizontally (side-by-side) into one composite image."""
    imgs = [Image.open(p) for p in image_paths if Path(p).exists()]
    if not imgs:
        return
    widths, heights = zip(*(im.size for im in imgs))
    merged = Image.new("RGB", (sum(widths), max(heights)), (255, 255, 255))
    x_offset = 0
    for im in imgs:
        merged.paste(im, (x_offset, 0))
        x_offset += im.width
    merged.save(output_path)
    for im in imgs:
        im.close()
    print(f"🖼️  Merged {len(image_paths)} images → {output_path.name} (horizontally)")



# --- Caption Extraction Prompt ---
caption_prompt = """
Please examine the following textbook page image and extract all figure captions.

Guidelines:
1. Only extract captions that actually appear in the image — do not invent or hallucinate any figure numbers or labels.
2. Not all images on the page are formally captioned. If an image lacks a label like "Figure XX", do not assign one.
3. Use visual layout reasoning to associate text blocks with figures.
4. Format output like:
   - "Figure 21-3": Caption text here...
   - "Figure 21.3": Caption text here...
   - "Figure 20": Caption text here...
   - "Figure 20a": Caption text here...
   - "Unlabeled image": Description of image content...
"""


# --- Core Mapping Function ---
def mapping():
    pages_root = Path("pages")
    page_dirs = sorted(pages_root.glob("page_*"))
    BATCH_SIZE = 4

    for page_dir in page_dirs:
        print(f"\n📘 Processing {page_dir.name}")
        full_page_image = page_dir / f"{page_dir.name}.png"
        caption_file = page_dir / f"{page_dir.name}_captions.txt"

        # Step 1: Caption extraction
        print(f"📤 Submitting {full_page_image.name} for caption extraction...")
        image_b64 = encode_image_b64(full_page_image)
        visual_prompt = [
            {"role": "user",
             "content": [
                 {"type": "text", "text": caption_prompt},
                 {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
             ]}
        ]
        try:
            if model_choice == "gemini":
                response = chat_session.send_message(visual_prompt)
                result_text = response.text.strip()
            else:
                response = client.chat.completions.create(model=model_name, messages=visual_prompt)
                result_text = response.choices[0].message.content.strip()

            with open(caption_file, "w", encoding="utf-8") as f:
                f.write(result_text)
            print(f"📝 Captions saved to: {caption_file.name}")
        except Exception as e:
            print(f"❌ Error processing {full_page_image.name}: {e}")
            continue

        # Step 2: Mapping
        fig_files = sorted(page_dir.glob("fig_*.png"), key=lambda x: int(re.findall(r'\d+', x.stem)[0]))
        if not fig_files:
            print("⚠️  No figures to map — skipping page.")
            continue

        caption_text = Path(caption_file).read_text(encoding="utf-8").strip()
        page_image_b64 = encode_image_b64(full_page_image)

        for i in range(0, len(fig_files), BATCH_SIZE):
            batch = fig_files[i:i + BATCH_SIZE]
            print(f"📤 Submitting batch {i//BATCH_SIZE + 1} ({[f.name for f in batch]})")
            batch_filenames = "\n".join([f"- {fig.name}" for fig in batch])
            mapping_prompt = f"""
You are shown several extracted figure images from a textbook page, along with the page scan and extracted captions.
Match each figure file to its most appropriate caption.

Respond in lines like:
fig_2.png : "Figure 21-5" : Figure 21-5.png

Use only the following files:
{batch_filenames}
"""

            messages = [
                {"role": "user",
                 "content": [
                     {"type": "text", "text": mapping_prompt},
                     {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{page_image_b64}"}} ,
                     {"type": "text", "text": f"Figure captions:\n{caption_text}"},
                 ]
                 + [
                     item
                     for fig in batch
                     for item in [
                         {"type": "text", "text": f"Image: {fig.name}"},
                         {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image_b64(fig)}"}}
                     ]
                 ]}
            ]

            try:
                if model_choice == "gemini":
                    response = chat_session.send_message(messages)
                    response_text = response.text.strip()
                else:
                    response = client.chat.completions.create(model=model_name, messages=messages)
                    response_text = response.choices[0].message.content.strip()

                mapped_pairs = {}  # {dst_path: [src_paths]}
                for line in response_text.splitlines():
                    if line.strip().startswith("fig_"):
                        parts = line.strip().split(":", 2)
                        if len(parts) >= 3:
                            src = page_dir / parts[0].strip()
                            dst = page_dir.parent / parts[2].strip()
                            if src.exists():
                                # always overwrite destination
                                shutil.copy2(src, dst)
                                print(f"✅ Copied (overwrite): {src.name} → {dst.name}")
                                mapped_pairs.setdefault(dst, []).append(src)

                # Merge duplicates (keep originals)
                for dst_path, src_list in mapped_pairs.items():
                    if len(src_list) > 1:
                        print(f"🔗 Merging {len(src_list)} images into {dst_path.name} ...")
                        merge_images_horizontally(src_list, dst_path)
                        #for s in src_list:44
                        #    try: s.unlink()
                        #    except Exception: pass

                print("✅ Batch processed successfully.")
            except Exception as e:
                print(f"❌ Error mapping batch: {e}")

    # --- Move final images to current directory (overwrite allowed) ---
    src_dir = Path("pages")
    dst_dir = Path(".")
    for png in src_dir.glob("*.png"):  # non-recursive
        target = dst_dir / png.name
        # Always overwrite, no suffixing
        shutil.move(png, target)
        print(f"Moved (overwrite): {png} → {target}")
    print("\n✅ All mappings completed.")


# --- Main ---
import merge_lettered_figs_v2
print("🚀 Starting mapping process...")
mapping()
merge_lettered_figs_v2.main()

## thinks that not repeating would give better results by chatpgt 5
'''
time.sleep(5)
print("\n🕒 Re-running mapping after 5 seconds...")
mapping()
merge_lettered_figs_v2.main()
print("\n✅ Mapping finished.")
'''

