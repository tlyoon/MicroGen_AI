import google.generativeai as genai
import os
import glob
import time
import re
import sys
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# --- LLM CONFIGURATION ---
load_dotenv()
model_name = "gemini-2.5-flash"  ### best with flash version; pro may not work as robustly
api_key_gemini = os.getenv("GEMINI_API_KEY")

if not api_key_gemini:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ No valid GEMINI_API_KEY found.")
    sys.exit()

genai.configure(api_key=api_key_gemini)
model = genai.GenerativeModel(model_name)

# --- UTILITIES ---

def extract_images_and_placeholders(xml_content):
    """Replaces base64 image strings with placeholders."""
    placeholders = {}
    pattern = re.compile(r'src="([^"]{50,})"')
    def replacer(match):
        val = match.group(1)
        idx = len(placeholders)
        placeholder = f"%%B64_IMG_{idx}%%"
        placeholders[placeholder] = val
        return f'src="{placeholder}"'
    return pattern.sub(replacer, xml_content), placeholders

def restore_images(xml_content, placeholders):
    """Re-injects original strings and repairs prefixes."""
    for placeholder, val in placeholders.items():
        if val.startswith("iVBOR") and not val.startswith("data:"):
            val = "data:image/png;base64," + val
        elif val.startswith("/9j/") and not val.startswith("data:"):
            val = "data:image/jpeg;base64," + val
        xml_content = xml_content.replace(placeholder, val)
    return xml_content

def validate_xml_well_formed(xml_string):
    """Verifies XML syntax using ElementTree."""
    try:
        test_string = xml_string.strip()
        if not test_string.startswith("<quiz>"):
            test_string = f"<quiz>{test_string}</quiz>"
        ET.fromstring(test_string)
        return True
    except ET.ParseError as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ XML Validation Failed: {e}")
        return False

def sanitize_xml_response(text):
    """Rigorous cleaning to ensure raw, non-nested XML."""
    # 1. Force-strip all markdown code fences
    text = re.sub(r'```xml\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*', '', text)
    text = re.sub(r'\s*```', '', text)

    # 2. Extract core XML payload (ignoring preamble/postscript)
    match = re.search(r'(<(quiz|question).*</\2>)', text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)

    # 3. Strip ALL existing CDATA wrappers to prevent nesting errors
    # This removes <![CDATA[ and ]]> but keeps the content inside
    text = re.sub(r'<!\[CDATA\[', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\]\]>', '', text)

    # 4. Global cleanup: fix naked ampersands and control chars
    text = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[a-f\d]+);)', '&amp;', text)
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\r\t")

    # 5. Apply fresh CDATA wrapping to every <text> node
    def wrap_node(m):
        tag_open = m.group(1)
        inner_content = m.group(2).strip()
        tag_close = m.group(3)
        # Re-escape nested CDATA end-tokens just in case
        safe_inner = inner_content.replace("]]>", "]]]]><![CDATA[>")
        return f"{tag_open}<![CDATA[{safe_inner}]]>{tag_close}"

    text = re.sub(r'(<text[^>]*>)(.*?)(</text>)', wrap_node, text, flags=re.DOTALL)

    return text.strip()

def call_gemini_sme(xml_data, prompt_text):
    """Submits XML to Gemini for audit."""
    try:
        full_prompt = f"{prompt_text}\n\nTARGET XML FOR AUDIT:\n{xml_data}"
        start_inference = time.time()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 Gemini auditing internal physics logic...")
        response = model.generate_content(full_prompt)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Received ({time.time() - start_inference:.2f}s)")
        return sanitize_xml_response(response.text)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ API Error: {e}")
        return None

# --- MAIN EXECUTION ---
def main():
    prompt_f = "check_mcq_prompt.txt"
    stats = {"processed": 0, "altered": 0, "unchanged": 0, "errors": 0, "invalid_xml": 0}

    if not os.path.exists(prompt_f):
        print(f"❌ {prompt_f} missing."); return

    with open(prompt_f, "r", encoding="utf-8") as f:
        audit_instructions = f.read()

    mcq_files = [f for f in glob.glob("*_mcq.xml") if not f.endswith("_orig.xml")]
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Auditing {len(mcq_files)} files.")

    for xml_path in mcq_files:
        print("-" * 60)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 File: {xml_path}")
        try:
            with open(xml_path, "r", encoding="utf-8") as f:
                original_raw = f.read()
            
            clean_api_xml, img_map = extract_images_and_placeholders(original_raw)
            corrected = call_gemini_sme(clean_api_xml, audit_instructions)
            
            if corrected:
                if corrected.strip() == clean_api_xml.strip():
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏭️  Status: [NO CHANGES DETECTED]")
                    stats["unchanged"] += 1
                else:
                    if validate_xml_well_formed(corrected):
                        final_xml = restore_images(corrected, img_map)
                        if validate_xml_well_formed(final_xml):
                            shutil.copy2(xml_path, xml_path.replace(".xml", "_orig.xml"))
                            with open(xml_path, "w", encoding="utf-8") as f:
                                f.write(final_xml)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 💾 Status: [ALTERED, VALIDATED & SAVED]")
                            stats["altered"] += 1
                        else:
                            stats["invalid_xml"] += 1
                    else:
                        stats["invalid_xml"] += 1
            else:
                stats["errors"] += 1
            stats["processed"] += 1
        except Exception as e:
            print(f"❌ System Error: {e}"); stats["errors"] += 1

    print("=" * 60)
    print(f"FINAL REPORT: {stats['processed']} total, {stats['altered']} altered, {stats['invalid_xml']} rejected.")

if __name__ == "__main__":
    main()