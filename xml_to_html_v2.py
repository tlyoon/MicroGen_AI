#!/usr/bin/env python3
"""
Convert all Moodle-style *.xml quiz files in the current directory
into simple *.html preview files for viewing in a web browser.

Example:
    SECTION_14-7_problemset.xml -> SECTION_14-7_problemset.html
"""

import glob
import os
import html
import xml.etree.ElementTree as ET


def get_first_text(elem, default=""):
    """
    Return the text content of the first <text> child under elem, unescaped.
    If not found, return default.
    """
    if elem is None:
        return default
    t_elem = elem.find("text")
    if t_elem is None or t_elem.text is None:
        return default
    # The content inside <text> is often HTML-escaped already
    return html.unescape(t_elem.text)


def render_question_html(q_index, q_elem):
    """
    Convert a <question> element into an HTML snippet (string).
    Handles 'essay' and 'multichoice'; falls back to generic for others.
    """
    qtype = q_elem.get("type", "unknown")
    # Question name (optional)
    name_el = q_elem.find("name")
    qname = get_first_text(name_el) if name_el is not None else f"Question {q_index}"

    # Main question text
    qtext_el = q_elem.find("questiontext")
    qtext_html = get_first_text(qtext_el, "")

    # Wrap everything in a container
    parts = []
    parts.append(f'<div class="question question-{qtype}">')
    parts.append(f'  <div class="q-header"><span class="q-number">{q_index}.</span> '
                 f'<span class="q-name">{html.escape(qname)}</span> '
                 f'<span class="q-type">[{qtype}]</span></div>')
    parts.append(f'  <div class="q-text">{qtext_html}</div>')

    if qtype == "multichoice":
        # Render MCQ options
        parts.append('  <ul class="q-options">')
        for ans_index, ans in enumerate(q_elem.findall("answer"), start=1):
            fraction = ans.get("fraction", "0")
            is_correct = False
            try:
                is_correct = float(fraction) > 0
            except ValueError:
                is_correct = False

            ans_text_html = get_first_text(ans, "")
            cls = "correct" if is_correct else "incorrect"
            badge = "✓" if is_correct else " "
            parts.append(
                f'    <li class="{cls}">'
                f'<span class="badge">{badge}</span> {ans_text_html}'
                f'</li>'
            )
        parts.append('  </ul>')

    parts.append('</div>')  # end .question
    return "\n".join(parts)


def convert_single_xml(xml_path: str) -> str:
    """
    Convert a single Moodle XML quiz file into an HTML preview file.

    Returns the path of the written HTML file.
    """
    print(f"Parsing XML: {xml_path}")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Derive base name and output path
    base = os.path.basename(xml_path)
    base_no_ext = os.path.splitext(base)[0]
    html_path = os.path.splitext(xml_path)[0] + ".html"

    # Optional: find the category question and use as heading
    category_text = ""
    for q in root.findall("question"):
        if q.get("type") == "category":
            cat = q.find("category")
            category_text = get_first_text(cat)
            break

    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html lang=\"en\">")
    html_parts.append("<head>")
    html_parts.append("  <meta charset=\"utf-8\">")
    html_parts.append(f"  <title>{html.escape(base_no_ext)}</title>")
    # Simple CSS for readability
    html_parts.append("""  <style>
      body {
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 1.5rem;
        line-height: 1.4;
        background: #fafafa;
      }
      h1 {
        font-size: 1.6rem;
        margin-bottom: 0.25rem;
      }
      h2 {
        font-size: 1.1rem;
        color: #555;
        margin-top: 0;
        margin-bottom: 1.5rem;
      }
      .question {
        background: #fff;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
      }
      .q-header {
        font-weight: 600;
        margin-bottom: 0.4rem;
      }
      .q-number {
        margin-right: 0.4rem;
      }
      .q-type {
        font-size: 0.8rem;
        color: #777;
        margin-left: 0.5rem;
      }
      .q-text p {
        margin: 0.35rem 0;
      }
      .q-options {
        list-style: none;
        padding-left: 1.2rem;
        margin-top: 0.5rem;
      }
      .q-options li {
        margin: 0.25rem 0;
      }
      .q-options li.correct {
        background: #e6ffed;
        border-radius: 4px;
        padding: 0.15rem 0.4rem;
      }
      .badge {
        display: inline-block;
        width: 1.2rem;
        text-align: center;
        font-weight: bold;
        margin-right: 0.3rem;
      }
      .file-meta {
        font-size: 0.85rem;
        color: #666;
        margin-bottom: 1rem;
      }
    </style>""")
    html_parts.append("</head>")
    html_parts.append("<body>")

    html_parts.append(f"<h1>{html.escape(base_no_ext)}</h1>")
    if category_text:
        html_parts.append(f"<h2>Category: {html.escape(category_text)}</h2>")
    else:
        html_parts.append("<h2>(No category found)</h2>")

    html_parts.append('<div class="file-meta">')
    html_parts.append(html.escape(xml_path))
    html_parts.append("</div>")

    # Render questions
    q_index = 0
    for q in root.findall("question"):
        qtype = q.get("type")
        if qtype == "category":
            continue  # skip category header entry

        q_index += 1
        html_parts.append(render_question_html(q_index, q))

    if q_index == 0:
        html_parts.append("<p><em>No questions found in this file.</em></p>")

    html_parts.append("</body>")
    html_parts.append("</html>")

    html_str = "\n".join(html_parts)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_str)

    print(f"  ➜ Wrote HTML preview: {html_path}")
    return html_path



# ---------------------------------------------------------------------
# NEW: Run batch mode *only* if script is executed directly
# ---------------------------------------------------------------------
if __name__ == "__main__":
    xml_files = sorted(glob.glob("*_mcq.xml"))
    if not xml_files:
        print("No *.xml files found in the current directory.")
    else:
        print(xml_files)
        print(f"Found {len(xml_files)} XML file(s). Converting to HTML previews...\n")
        for xml_path in xml_files:
            try:
                convert_single_xml(xml_path)
            except Exception as e:
                print(f"  [ERROR] Failed to convert {xml_path}: {e}")
