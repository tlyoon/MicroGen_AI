import google.generativeai as genai
import os
import glob
import time
import xml.etree.ElementTree as ET
import html
from pathlib import Path
from dotenv import load_dotenv
import traceback
import io
import re, sys
from openai import OpenAI

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


# Force-disable pin_memory globally (as in your base file)
try:
    import torch.utils.data
    original_DataLoader = torch.utils.data.DataLoader

    class PatchedDataLoader(original_DataLoader):
        def __init__(self, *args, **kwargs):
            kwargs['pin_memory'] = False
            super().__init__(*args, **kwargs)

    torch.utils.data.DataLoader = PatchedDataLoader
    print("✅ DataLoader patched to force pin_memory=False")
except ImportError:
    print("⚠️ torch not available — skipping pin_memory patch")


##### apikey auto-selection ######
##### default choice is gemini ######
######## specify model_name, from most to least expensive ########
#model_name = "gpt-4.1-mini"; model_choice = 'openai'     ### worked
model_name = "gpt-4o"    ; model_choice = 'openai'       ### worked, use this as default
#model_name = "gpt-5"    ; model_choice = 'openai'        ### does not work
#model_name = "gpt-5-mini"    ; model_choice = 'openai'   ### does not work
#model_name = "gemini-3.1-pro-preview"    ; model_choice = 'gemini'  ### package-standard Gemini alternative
########  end of specify model_name, must be consistent with model_choice ########

# Load environment variables
env_path = '.env'
load_dotenv(dotenv_path=env_path)

# API key and model setup
api_key_dsk = os.getenv("DEEPSEEK_API_KEY")
api_key_oai = os.getenv("OPENAI_API_KEY")
api_key_gemini = os.getenv("GEMINI_API_KEY")

if model_choice == 'gemini':
    api_key = api_key_gemini
    print(f'model_choice: {model_choice}; model_name: {model_name}')
    if not api_key:
        print("❌ No valid API key found")
        sys.exit()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    client = genai.GenerativeModel(model_name)
    chat_session = model.start_chat()
    generation_config = genai.types.GenerationConfig(temperature=0.5)

elif model_choice == 'openai':
    api_key = api_key_oai
    print(f'model_choice: {model_choice}; model_name: {model_name}')
    if not api_key:
        print("❌ No valid API key found")
        sys.exit()
    client = OpenAI(api_key=api_key)

elif model_choice == 'deepseek':
    api_key = api_key_dsk
    print(f'model_choice: {model_choice}; model_name: {model_name}')
    if not api_key:
        print("❌ No valid API key found")
        sys.exit()
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
print(' ')


# ──────────────────────────────────────────────────────────────────────
# 0. CDATA support - Custom Writer Implementation
# ──────────────────────────────────────────────────────────────────────
class CDATA(str): pass  # Marker class

def _escape_cdata(text):
    """Escapes the CDATA closing sequence."""
    try:
        text_str = str(text) if text is not None else ""
        return text_str.replace(']]>', ']]]]><![CDATA[>')
    except Exception:
        return ""

def _write_element_recursive(writer_func, element, encoding, level=0, indent="  "):
    """Core recursive logic for writing elements with optional indentation."""
    if indent:
        writer_func((indent * level).encode(encoding))
    writer_func(f"<{element.tag}".encode(encoding))
    for key, value in element.attrib.items():
        writer_func(f' {key}="{html.escape(value, quote=True)}"'.encode(encoding))
    has_text = element.text and element.text.strip()
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
            if indent:
                writer_func("\n".encode(encoding))
            for child in element:
                _write_element_recursive(writer_func, child, encoding, level + 1, indent)
            if indent and has_children:
                writer_func((indent * level).encode(encoding))
        writer_func(f"</{element.tag}>".encode(encoding))
    if indent or level > 0:
        writer_func("\n".encode(encoding))

def write_xml_with_cdata(tree, filename, encoding="utf-8", xml_declaration=True, indent=None):
    """Writes the ElementTree 'tree' to 'filename' using the custom CDATA writer."""
    filename_str = str(filename)
    if not filename_str:
        print("❌ [ERROR] Attempted write with empty filename.")
        return
    try:
        output_dir = os.path.dirname(filename_str)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(filename_str, "wb") as f:
            if xml_declaration:
                f.write(f'<?xml version="1.0" encoding="{encoding}"?>\n'.encode(encoding))
            _write_element_recursive(f.write, tree.getroot(), encoding, indent=indent or "")
    except Exception as e:
        print(f"❌ [ERROR] Failed XML write '{os.path.basename(filename_str)}': {e}")
        traceback.print_exc()

def element_to_string_with_cdata(element, encoding="unicode"):
    """Serializes a single element to a string using the custom CDATA logic."""
    if encoding.lower() == 'unicode':
        buffer = io.StringIO()
        string_writer = lambda data_bytes: buffer.write(data_bytes.decode('utf-8'))
        _write_element_recursive(string_writer, element, 'utf-8', level=0, indent="")  # No indent for string
        return buffer.getvalue().strip()
    else:
        buffer = io.BytesIO()
        _write_element_recursive(buffer.write, element, encoding, level=0, indent="")
        return buffer.getvalue()


# ──────────────────────────────────────────────────────────────────────
# 1. Image Placeholder Handling
# ──────────────────────────────────────────────────────────────────────
IMG_PATTERN = re.compile(r'(<img\s+[^>]*?src="data:image/[^;]+;base64,([^"]+)"[^>]*?>)', re.IGNORECASE | re.DOTALL)
PLACEHOLDER_PREFIX = "%%FIGURE_PLACEHOLDER_"
PLACEHOLDER_SUFFIX = "%%"

def find_and_replace_images_with_placeholders(xml_string: str) -> tuple[str, dict]:
    """Finds <img> tags with base64, replaces src with placeholder, stores originals."""
    placeholders = {}
    placeholder_index = 0

    def replacer(match):
        nonlocal placeholder_index
        original_img_tag = match.group(1)
        alt_match = re.search(r'alt="([^"]*)"', original_img_tag, re.IGNORECASE)
        alt_text = alt_match.group(1) if alt_match else f"img{placeholder_index}"
        sanitized_alt = re.sub(r'\W+', '_', alt_text).strip('_')[:30]
        placeholder_key = f"{PLACEHOLDER_PREFIX}{sanitized_alt}_{placeholder_index}{PLACEHOLDER_SUFFIX}"
        placeholder_index += 1
        placeholders[placeholder_key] = original_img_tag
        return placeholder_key

    modified_xml_string = IMG_PATTERN.sub(replacer, xml_string)
    return modified_xml_string, placeholders

def restore_images_from_placeholders(text_containing_placeholders: str, placeholders: dict) -> str:
    """Replaces placeholders back with their original full <img> tags."""
    restored_string = text_containing_placeholders
    if not placeholders:
        return restored_string
    placeholder_pattern = re.compile('|'.join(map(re.escape, placeholders.keys())))
    def get_replacement(match):
        placeholder = match.group(0)
        return placeholders.get(placeholder, placeholder)
    restored_string = placeholder_pattern.sub(get_replacement, restored_string)
    return restored_string


# ──────────────────────────────────────────────────────────────────────
# 2. XML Cleaning and Validation
# ──────────────────────────────────────────────────────────────────────
def clean_xml_content(xml_string: str) -> str:
    """Removes invalid XML characters and normalizes content."""
    cleaned = re.sub(r'[^\x20-\x7E\r\n\t]', '', xml_string)  # remove non-printables
    cleaned = cleaned.replace('', '(').replace('', ')')  # stray control chars
    return cleaned

def validate_and_parse_xml(xml_content: str) -> ET.ElementTree:
    """Validates and parses XML content with error handling."""
    try:
        return ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"❌ [XML PARSE ERROR] {e}")
        lines = xml_content.splitlines()
        if "line " in str(e) and "column " in str(e):
            try:
                line_no = int(str(e).split("line ")[1].split(",")[0])
                if line_no >= len(lines):  # Error at EOF → try trimming last line
                    return ET.fromstring('\n'.join(lines[:-1]))
            except (ValueError, IndexError):
                pass
        raise


# ──────────────────────────────────────────────────────────────────────
# 3. LLM call + pre-parse sanitizers you already have
# ──────────────────────────────────────────────────────────────────────
PROMPT_FILE = "prompts_xml2mcq_v7.txt"

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(script_dir, PROMPT_FILE)
    with open(prompt_path, "r", encoding="utf-8") as pf:
        PROMPT_TEMPLATE = pf.read().strip()
    print(f"[INFO] Loaded prompt template from: {prompt_path}")
except Exception as e:
    print(f"❌ [ERROR] Failed to read prompt file {prompt_path}: {e}")
    exit(1)

def call_llm(prompt_content: str) -> str:
    """Sends prompt to LLM with retries and error handling."""
    max_retries = 3
    retry_delay = 5
    for attempt in range(max_retries):
        try:
            print(f"    [INFO] Calling LLM (Attempt {attempt + 1}/{max_retries})...")
            if model_choice == 'gemini':
                response = client.generate_content(prompt_content, generation_config=generation_config)
                if not response.candidates:
                    reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown'
                    print(f"    [WARN] Gemini blocked attempt {attempt+1}. Reason: {reason}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay); continue
                    else:
                        print("    [ERROR] Gemini blocked response after retries."); return ""
                return response.text or ""
            else:
                system_msg = (
                    "You are an assistant expert at converting Moodle XML questions to multiple-choice format. "
                    "Input is a single Moodle question XML. Output ONLY the converted `<question type='multichoice'>...</question>` XML element. "
                    "Preserve all original content like text, HTML, and placeholders (e.g., %%FIGURE_PLACEHOLDER_...%%) accurately within the new structure. "
                    "Do not include ```xml or any other explanations."
                )
                messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt_content}]
                chat = client.chat.completions.create(model=model_name, messages=messages, stream=False, temperature=0.3)
                return chat.choices[0].message.content or ""
        except Exception as e:
            print(f"  ❌ [ERROR] API call failed attempt {attempt+1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return ""
    return ""

_ILLEGAL_XML_CHARS = r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD]"
_BARE_AMP = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)")

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        parts = re.split(r"```", s)
        if len(parts) >= 2:
            s = parts[1].strip()
            if s.startswith(("xml", "html")):
                s = s[3:].strip()
    return s

def sanitize_llm_xml_response(s: str) -> str:
    """Make LLM XML parseable: remove BOM/control chars, fix bare '&', drop stray XML decl."""
    s = _strip_code_fences(s)
    start = s.find("<question")
    end = s.rfind("</question>")
    if start == -1 or end == -1:
        raise ValueError("LLM response missing <question> element")
    s = s[start:end + len("</question>")]
    s = re.sub(r"<\?xml[^>]*\?>", "", s)
    s = re.sub(_ILLEGAL_XML_CHARS, "", s)
    s = _BARE_AMP.sub("&amp;", s)
    return s

def cdata_wrap_text_nodes(xml_str: str) -> str:
    """Regex wrap inside <text>…</text> with CDATA; split embedded ']]>' safely."""
    def _wrap(m):
        open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
        if "<![CDATA[" in body:
            return f"{open_tag}{body}{close_tag}"
        body = body.replace("]]>", "]]]]><![CDATA[>")
        return f"{open_tag}<![CDATA[{body}]]>{close_tag}"
    return re.sub(r"(<text[^>]*>)(.*?)(</text>)", _wrap, xml_str, flags=re.DOTALL)

# ──────────────────────────────────────────────────────────────────────
# 3a. HTML math normalizer for Moodle (keeps Unicode Greek) — EXPANDED
# ──────────────────────────────────────────────────────────────────────
# Handle digits, letters, and {braced} forms; subscripts; sqrt; Delta/delta words
_SUP_NUM   = re.compile(r'(?<=\w|\))\^(\d+)')                 # x^2 -> x<sup>2</sup>
_SUP_LET   = re.compile(r'(?<=\w|\))\^([A-Za-z])')            # x^n -> x<sup>n</sup>
_SUP_BRACE = re.compile(r'(?<=\w|\))\^\{([^}]+)\}')           # x^{12} -> x<sup>12</sup>
_SUB_ONE   = re.compile(r'([A-Za-z])_([A-Za-z0-9])')          # v_f -> v<sub>f</sub>
_SUB_BRACE = re.compile(r'([A-Za-z])_\{([^}]+)\}')            # v_{avg} -> v<sub>avg</sub>
_DELTA_FIX = re.compile(r'\bDelta([A-Za-z])')                 # DeltaK -> ΔK
_delta_fix = re.compile(r'\bdelta([A-Za-z])')                 # deltaV -> δV
_SQRT_RE   = re.compile(r'\bsqrt\s*\(\s*([^()]+?)\s*\)')      # sqrt(…) -> √(…)

def _htmlize_once(s: str) -> str:
    s = _SUP_BRACE.sub(r'<sup>\1</sup>', s)
    s = _SUP_NUM.sub(r'<sup>\1</sup>', s)
    s = _SUP_LET.sub(r'<sup>\1</sup>', s)
    s = _SUB_BRACE.sub(r'\1<sub>\2</sub>', s)
    s = _SUB_ONE.sub(r'\1<sub>\2</sub>', s)
    s = _DELTA_FIX.sub(r'Δ\1', s)
    s = _delta_fix.sub(r'δ\1', s)
    s = _SQRT_RE.sub(r'√(\1)', s)  # use '&radic;' if you prefer entity
    s = s.replace('(1/2)', '½')
    return s

def htmlize_math_payload(s: str) -> str:
    """Conservative HTML math fixes suitable for Moodle HTML blocks."""
    if not s:
        return s
    # Apply repeatedly to catch multiple patterns
    prev = None
    cur = s
    for _ in range(6):  # small cap
        prev = cur
        cur = _htmlize_once(cur)
        if cur == prev:
            break
    return cur

def transform_cdata_text_nodes(xml_str: str, transform_fn) -> str:
    """
    Apply `transform_fn` to the inner payload of every <text> node
    while preserving CDATA wrapping (and splitting if ']]>' present).
    """
    def _tx(m):
        open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
        if body.strip().startswith("<![CDATA["):
            body_inner = body.strip()
            body_inner = body_inner[len("<![CDATA["):]
            if body_inner.endswith("]]>"):
                body_inner = body_inner[:-3]
            new_inner = transform_fn(body_inner)
            new_inner = new_inner.replace("]]>", "]]]]><![CDATA[>")
            return f"{open_tag}<![CDATA[{new_inner}]]>{close_tag}"
        else:
            new_inner = transform_fn(body)
            new_inner = new_inner.replace("]]>", "]]]]><![CDATA[>")
            return f"{open_tag}<![CDATA[{new_inner}]]>{close_tag}"
    return re.sub(r"(<text[^>]*>)(.*?)(</text>)", _tx, xml_str, flags=re.DOTALL)


# ──────────────────────────────────────────────────────────────────────
# 4. Core Conversion Logic
# ──────────────────────────────────────────────────────────────────────
def _dump_bad_xml(snippet: str, base: str):
    ts = int(time.time())
    fname = f"bad_llm_question_{base}_{ts}.xml"
    with open(fname, "w", encoding="utf-8") as fh:
        fh.write(snippet)
    print(f"    [DEBUG] Wrote failing LLM XML to {fname}")

def convert_file(src_path: Path) -> None:
    """Processes XML file through LLM conversion pipeline."""
    print(f"\n[INFO] Processing {src_path.name}...")
    out_path = src_path.with_name(src_path.stem + "_mcq.xml")

    try:
        with open(src_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        cleaned_content = clean_xml_content(raw_content)
        source_root = validate_and_parse_xml(cleaned_content)
        tree = ET.ElementTree(source_root)
    except Exception as e:
        print(f"❌ [ERROR] Failed XML parse/read: {src_path.name}. Error: {e}")
        return

    new_quiz_root = ET.Element("quiz")
    processed_questions_count = 0
    conversion_errors = 0

    def ensure_cdata_recursive(element):
        """Applies CDATA marker class to text nodes needing it."""
        if element.text and ('<' in element.text or '&' in element.text or '>' in element.text):
            if not isinstance(element.text, CDATA):
                element.text = CDATA(element.text)
        for child in element:
            ensure_cdata_recursive(child)

    for element in source_root:
        if element.tag == "question":
            q_type = element.get("type")
            q_name_elem = element.find(".//name/text")
            q_name = q_name_elem.text.strip() if q_name_elem is not None and q_name_elem.text else f"Question_{processed_questions_count+1}"

            if q_type == "category":
                cat_text_elem = element.find('.//category/text')
                cat_text = cat_text_elem.text if cat_text_elem is not None else 'Unknown Category'
                print(f"  - Copying category: '{cat_text}'")
                ensure_cdata_recursive(element)
                new_quiz_root.append(element)
            else:
                print(f"  - Processing Question: '{q_name}' (Type: {q_type})")
                image_placeholders = {}
                try:
                    ensure_cdata_recursive(element)
                    original_single_q_str = element_to_string_with_cdata(element, encoding='unicode')
                    q_str_for_llm, image_placeholders = find_and_replace_images_with_placeholders(original_single_q_str)
                    if image_placeholders:
                        print(f"    - Replaced {len(image_placeholders)} image(s) with placeholders.")

                    prompt = (
                        f"{PROMPT_TEMPLATE}\n\n"
                        f"--- BEGIN SINGLE QUESTION XML ---\n{q_str_for_llm}\n--- END SINGLE QUESTION XML ---\n\n"
                        "Convert the above question into Moodle MCQ XML format. "
                        "Output ONLY the single, valid <question type=\"multichoice\">...</question> element. "
                        "Preserve all original text, formatting, and image placeholders."
                    )

                    llm_response_str = call_llm(prompt)
                    if not llm_response_str.strip():
                        raise ValueError("LLM returned an empty response.")

                    # 1) Sanitize core XML from LLM
                    mcq_xml_str_placeholders = sanitize_llm_xml_response(llm_response_str)

                    # 2) Put images back
                    mcq_xml_str_restored = restore_images_from_placeholders(mcq_xml_str_placeholders, image_placeholders)
                    if image_placeholders:
                        print(f"    - Restored {len(image_placeholders)} image(s).")

                    # 3) Wrap <text> bodies in CDATA to protect math/HTML
                    mcq_xml_str_cdata = cdata_wrap_text_nodes(mcq_xml_str_restored)

                    # 3a) HTML-ize math (sup/sub, Δ/δ, sqrt→√) inside every <text> payload
                    mcq_xml_str_cdata = transform_cdata_text_nodes(mcq_xml_str_cdata, htmlize_math_payload)

                    # 4) Parse (strict). If it still fails, dump and raise.
                    try:
                        converted_question_element = ET.fromstring(mcq_xml_str_cdata)
                    except ET.ParseError as e:
                        _dump_bad_xml(mcq_xml_str_cdata, q_name.replace(" ", "_"))
                        raise

                    ensure_cdata_recursive(converted_question_element)
                    new_quiz_root.append(converted_question_element)
                    print(f"    + OK: Added converted '{q_name}'.")
                    processed_questions_count += 1

                except Exception as e:
                    print(f"  ❌ [ERROR] Processing Fail for '{q_name}'. Error: {e}")
                    conversion_errors += 1
        else:
            print(f"  [WARN] Ignoring non-<question> top-level element: <{element.tag}>")

    if len(new_quiz_root) > 0:
        if conversion_errors > 0:
            print(f"  [WARN] Writing file '{out_path.name}' despite {conversion_errors} conversion error(s).")
        try:
            final_tree = ET.ElementTree(new_quiz_root)
            write_xml_with_cdata(final_tree, out_path, encoding="utf-8", xml_declaration=True, indent="  ")
            # ─────────────────────────────────────────────────────────────
            # Post-LLM file-level sanitization pass (kept)
            # ─────────────────────────────────────────────────────────────
            try:
                changed, nodes, removed = post_sanitize_mcq_file(out_path)
                print(f"🧼 [POST] Sanitized '{out_path.name}': cleaned_nodes={nodes}, tokens_removed={removed}, file_rewritten={changed}")
            except Exception as se:
                print(f"⚠️ [POST] Sanitization skipped due to error: {se}")
            # ─────────────────────────────────────────────────────────────
            print(f"✅ [SUCCESS] Wrote {processed_questions_count} converted question(s) to {out_path.name}\n")
        except Exception as e_write:
            print(f"      -> Failed to save final output for {src_path.name}")
    else:
        print(f"  [INFO] No category or processed questions found for {src_path.name}. Skipping writing {out_path.name}.")


# ──────────────────────────────────────────────────────────────────────
# 5. Post-LLM file-level sanitization
# ──────────────────────────────────────────────────────────────────────
# Match CDATA tokens even if spaced/newlined: < ! [ CDATA [
_CDATA_START_VAR = re.compile(r"<\s*!\s*\[\s*CDATA\s*\[", re.IGNORECASE)
_CDATA_END_VAR   = re.compile(r"\]\s*\]\s*>", re.IGNORECASE)
# Code fences lines
_FENCE_LINE      = re.compile(r"^\s*(```+|~~~+).*$", re.M)

def _strip_outer_lonely_angle_brackets(payload: str) -> str:
    """
    If payload is only wrapped by a single leading '<' and trailing '>'
    (with no other tag-like chars inside), strip them. Keeps real HTML tags.
    """
    if not payload:
        return payload
    s = payload.strip()
    if s.startswith("<") and s.endswith(">"):
        inner = s[1:-1].strip()
        if "<" not in inner and ">" not in inner and "/" not in inner:
            return inner
    return payload

def _remove_cdata_tokens_variants(s: str) -> tuple[str, int]:
    """Remove any literal CDATA start/end tokens (with whitespace/newlines) from text payload."""
    if not s:
        return s, 0
    count_before = len(_CDATA_START_VAR.findall(s)) + len(_CDATA_END_VAR.findall(s))
    s = _CDATA_START_VAR.sub("", s)
    s = _CDATA_END_VAR.sub("", s)
    # Also canonical markers echoed as text:
    count_before += s.count("<![CDATA[") + s.count("]]>")
    s = s.replace("<![CDATA[", "").replace("]]>", "")
    return s, count_before

def sanitize_text_payload(payload: str) -> tuple[str, int]:
    """
    Strong payload sanitizer for <text> bodies:
      • remove ANY variant of CDATA tokens,
      • strip lonely '<' '>' wrapper if just bracket noise,
      • drop code-fence lines if present.
    Returns (cleaned_text, tokens_removed_count).
    """
    if payload is None:
        payload = ""
    tokens_removed = 0
    # Remove CDATA token variants
    payload, removed = _remove_cdata_tokens_variants(payload)
    tokens_removed += removed
    # Strip lonely bracket wrapper (keeps actual HTML)
    payload = _strip_outer_lonely_angle_brackets(payload)
    # Remove fence lines (if model echoed them inside payload)
    payload = _FENCE_LINE.sub("", payload)
    return payload, tokens_removed

def _rewrite_tree_with_cdata(root: ET.Element) -> str:
    """Serialize the given root using the custom CDATA writer and return as text."""
    tree = ET.ElementTree(root)
    out_buf = io.BytesIO()
    def _w(b: bytes):
        out_buf.write(b)
    _write_element_recursive(_w, root, 'utf-8', level=0, indent="  ")
    return out_buf.getvalue().decode('utf-8')

def post_sanitize_mcq_file(file_path: Path) -> tuple[bool, int, int]:
    """
    Re-open <file_path>, parse it, sanitize every <text> payload in the whole <quiz>,
    wrap them as single CDATA, then re-write the file with the custom writer.

    Returns: (file_rewritten, total_text_nodes_sanitized, total_tokens_removed)
    """
    xml_text = Path(file_path).read_text(encoding="utf-8")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        # File should already be well-formed; if not, give up quietly
        raise RuntimeError(f"Post-parse failed: {e}")

    if root.tag != "quiz":
        quiz = root.find(".//quiz")
        if quiz is None:
            return (False, 0, 0)
        root = quiz

    total_nodes = 0
    total_tokens_removed = 0

    for t in root.iter("text"):
        payload = t.text or ""
        cleaned, removed = sanitize_text_payload(payload)
        total_tokens_removed += removed
        t.text = CDATA(cleaned)
        total_nodes += 1

    tree = ET.ElementTree(root)
    write_xml_with_cdata(tree, file_path, encoding="utf-8", xml_declaration=True, indent="  ")
    return (True, total_nodes, total_tokens_removed)


# ──────────────────────────────────────────────────────────────────────
# 6. Main Execution
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    source_pattern = "*_problemset.xml"
    exclude_suffix = "_mcq.xml"
    output_subdir = "."

    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"[INFO] Running in directory: {script_dir}")

    source_search_path = os.path.join(script_dir, source_pattern)
    all_xml_files = glob.glob(source_search_path)
    xml_files_to_process = [
        Path(p) for p in all_xml_files
        if not p.endswith(exclude_suffix) and os.path.isfile(p)
    ]

    if not xml_files_to_process:
        print(f"\n❌ No source XML files found matching '{source_pattern}' (excluding '{exclude_suffix}') in '{script_dir}'.")
        sys.exit()

    output_directory = os.path.join(script_dir, output_subdir)
    print(f"Found {len(xml_files_to_process)} source XML files to process.")
    print(f"Outputting converted MCQ XML files to: '{output_directory}'")
    print("=" * 40)

    total_processed = 0
    total_errors = 0
    start_time = time.time()

    for src_file_path in sorted(xml_files_to_process):
        print(f"\n{'='*10} Starting: {src_file_path.name} {'='*10}")
        try:
            convert_file(src_file_path)
            total_processed += 1
        except Exception as e:
            total_errors += 1
            print(f"  ‼️ CRITICAL Error during conversion: {e}")

    end_time = time.time()
    print("\n" + "=" * 40)
    print("Processing complete.")
    print(f"  Total files processed: {total_processed}")
    print(f"  Total critical errors during processing: {total_errors}")
    print(f"  Total time: {end_time - start_time:.2f} seconds")
    print(f"  Output files are in: '{os.path.abspath(output_directory)}'")
    print("=" * 40)

    import sanitize_xml_v2
    sanitize_xml_v2.main("*_problemset_mcq.xml")

    # ============================================================
    # Second & Third targeted passes for missed *_problemset_mcq.xml
    # (mirrors fix_convert*.py behavior)
    # ============================================================
    from pathlib import Path
    import glob
    import time

    def _compute_missed_files(script_dir: str):
        """
        Return a list of source *_problemset.xml Paths that STILL do not have a
        matching *_problemset_mcq.xml (files renamed to *_mcq__error.xml do NOT
        count as success and will be retried).
        """
        xml_files = [Path(p) for p in glob.glob(str(Path(script_dir) / "*_problemset.xml"))]
        mcq_files = [Path(p) for p in glob.glob(str(Path(script_dir) / "*_problemset_mcq.xml"))]

        def src_base(p: Path) -> str:
            return p.with_suffix('').name  # drop .xml safely

        def out_base(p: Path) -> str:
            stem = p.with_suffix('').name  # e.g., "SECTION_28-3_problemset_mcq"
            return stem[:-4] if stem.endswith("_mcq") else stem

        src_bases = {src_base(p) for p in xml_files}
        out_bases = {out_base(p) for p in mcq_files}

        missed_bases = sorted(src_bases - out_bases)
        missed_xml_files = [Path(script_dir) / f"{b}.xml" for b in missed_bases]
        return missed_xml_files

    def _retry_missed_pass(pass_label: str, script_dir: str):
        missed_xml_files = _compute_missed_files(script_dir)
        if missed_xml_files:
            print(f"{pass_label} attempt to generate *_mcq.xml for",
                  [p.name for p in missed_xml_files])
            for src in missed_xml_files:
                try:
                    convert_file(src)
                except Exception as e:
                    print(f"  [WARN] {src.name} failed again: {e}")

            try:
                import sanitize_xml_v2
                sanitize_xml_v2.main("*_problemset_mcq.xml")
            except Exception as se:
                print(f"[WARN] sanitize_xml failed during {pass_label.lower()} attempt: {se}")

            print(f"{pass_label} attempt to generate *_mcq.xml for",
                  [p.name for p in missed_xml_files], "FINISHES")
        else:
            print(f"{pass_label} attempt: no missed files detected.")

    print("")
    _retry_missed_pass("Second", script_dir)
    print("")
    time.sleep(1.0)
    _retry_missed_pass("Third", script_dir)
