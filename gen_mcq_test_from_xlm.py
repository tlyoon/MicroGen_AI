## Run this code in the presence of sample_sol.tex, and a host of mcq xml files, such as SECTION*-*_problemset_mcq.xml (e.g. SECTION_8-4_problemset_mcq.xml)
## It will generate mcq test set containing a default of 25 questions with 5 options.
## The MCQ questions are randomly selected from the *.xml files present. 
## By default it will generate one mcq per *.xml file. 
## Edit var=1 to generate only 1 set of mcq test question, or set var to any positive integer for $var shuffled mcq test sets. 
## Files generated are in the form of {t1.tex, t1.pdf}, {t2.tex, t2.pdf}, ...,{t{var}}.tex, t{var}.pdf}.
### set var here. Default is var = 1, correspond to only one set of test set. 
var=1
### end of set var here 

import random
import re, glob, os
import subprocess

import os
from typing import List
import google.generativeai as genai

# ---------------------------------------------------
# 1. CONFIGURE GEMINI
# ---------------------------------------------------
# Set your API key in environment variable:
#   export GEMINI_API_KEY="your_key_here"
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL_NAME = "gemini-2.5-pro"   # adjust if your endpoint uses a slightly different name


# ---------------------------------------------------
# 2. SYSTEM / INSTRUCTION PROMPT (SHORT, INLINE)
#    You can also move this into a separate .txt file
# ---------------------------------------------------
# ---------------------------------------------------
# 2. SYSTEM / INSTRUCTION PROMPT (COMPREHENSIVE)
# ---------------------------------------------------
# ---------------------------------------------------
# 2. SYSTEM / INSTRUCTION PROMPT (FIXED & INCLUSIVE)
# ---------------------------------------------------
GEMINI_INSTRUCTION = """
You are an expert in:
- Moodle XML MCQ parsing,
- LaTeX document generation, and
- Mathematics/physics education.

GOAL:
Produce ONE compilable LaTeX file based on a provided template and XML question banks. The output must be pedagogical, accurate, properly formatted, and must include the correct answer for each question.

--- CORE QUALITY & LOGIC RULES ---

1) INDEPENDENT VERIFICATION:
- Do NOT rely solely on the correctness markers (fraction="100") in the XML files .
- You MUST internally perform the required mathematical or physical calculations to verify the correct answer for every question.
- If an XML source contains an error, you must correct it in the generated version.

2) UNIQUENESS & VALIDITY:
- Ensure each MCQ has EXACTLY ONE unique correct answer.
- Verify that no other option (B, C, or D) is accidentally correct or mathematically equivalent to the correct one (e.g., ensure 0.5 and 1/2 do not appear as separate options).

3) CONTENT MODIFICATION (NO VERBATIM COPYING):
- Do NOT copy questions verbatim from the XML source.
- Introduce minor but meaningful modifications:
    * Change numerical values (e.g., change 10kg to 15kg).
    * Change variable names (e.g., change 'x' to 't').
    * Rephrase the question stem while preserving the learning objective.
- Recalculate all options AND the answer key based on your new values to ensure consistency.

--- FORMATTING & PARSING RULES ---

4) XML Parsing & Selection:
- Parse only <question type="multichoice"> blocks.
- Select representative MCQs from each file, avoiding those with figures or images.
- Use the requested number of questions per XML (defaulting to 2 if not specified).

5) MCQ Normalization & SOLUTION INCLUSION:
- Clean and simplify the stem while preserving the mathematical meaning.
- Ensure 5 options total: A, B, C, D (mix of correct + distractors), and E.
- Option E is ALWAYS: "No matched answer" and is always incorrect.
- If the original has fewer than 4 options, create plausible distractors based on common student errors.
- MANDATORY: Include the correct answer immediately after each question block in the format: **Answer: (X)** (where X is the correct letter).

6) Math Rendering & LaTeX:
- Convert ALL math to LaTeX commands (e.g., use \\theta for θ, \\times for ×).
- Use \( ... \) for inline math and \[ ... \] for display math.
- No raw Unicode math characters are allowed in the final output.

7) Template Integration:
- Follow the provided LaTeX template (margins, columns, header/footer) EXACTLY [cite: 76-78].
- Insert the modified MCQs and their corresponding **Answer: (X)** lines into the appropriate region using the template's environments.
- Ensure the result is fully compilable with pdfLaTeX.

--- OUTPUT CONTRACT ---
- OUTPUT ONLY the complete LaTeX document as plain text. 
- Do NOT wrap the code in markdown, JSON, or backticks.
"""


# ---------------------------------------------------
# 3. SIMPLE ONE-CALL WRAPPER
# ---------------------------------------------------
def generate_latex_mcq_from_xml(
    xml_paths: List[str],
    latex_template_path: str,
    output_tex_path: str = "generated_mcq_test.tex",
    questions_per_xml: int = 1,
) -> str:
    """
    Reads XML question banks + LaTeX template, calls Gemini 2.5 Pro once,
    and returns the generated LaTeX test document as a string.
    Also saves it to `output_tex_path`.
    """

    # Read XML contents
    xml_blobs = []
    for p in xml_paths:
        with open(p, "r", encoding="utf-8") as f:
            xml_blobs.append(f.read())

    # Read LaTeX template
    with open(latex_template_path, "r", encoding="utf-8") as f:
        latex_template = f.read()

    # Build user message to pass XML + template
    # Keep structure simple, but clearly separated.
    user_message = f"""
You are given the following Moodle XML question banks (as text),
followed by a LaTeX template.

Number of MCQs to sample per XML file: {questions_per_xml}.

---------------- XML FILES START ----------------
"""

    for i, xml in enumerate(xml_blobs, start=1):
        user_message += f"\n[XML FILE {i} START]\n{xml}\n[XML FILE {i} END]\n"

    user_message += """
---------------- XML FILES END ----------------

---------------- LATEX TEMPLATE START ----------------
"""
    user_message += latex_template
    user_message += """
---------------- LATEX TEMPLATE END ----------------

TASK:
Using ONLY the information above and the SYSTEM INSTRUCTION,
generate ONE complete LaTeX test document that follows the template
and contains properly formatted MCQs as instructed.
"""

    # Create model
    # Create model
    model = genai.GenerativeModel(MODEL_NAME)
    
    # Combine instruction + data into one prompt
    full_prompt = GEMINI_INSTRUCTION + "\n\n" + user_message
    
    # Call Gemini ONCE (simple 1-call)
    response = model.generate_content(full_prompt)


    latex_output = response.text  # Gemini returns plain text

    # Save to .tex file
    with open(output_tex_path, "w", encoding="utf-8") as f:
        f.write(latex_output)

    return latex_output


def process_and_compile_tex(file_pattern="t*.tex"):
    """
    1. Scans for var_*.tex files.
    2. Removes \textbf{Answer: (**)} lines.
    3. Saves as t*Q.tex.
    4. Compiles t*Q.tex using pdflatex.
    """
    # Find the original source files
    files = glob.glob(file_pattern)
    
    if not files:
        print(f"No files found matching pattern: {file_pattern}")
        return

    # Regex to match the answer line regardless of the letter/parentheses
    answer_regex = re.compile(r'^\\textbf\{Answer:\s*\(?.*?\)?\}\s*$', re.MULTILINE | re.IGNORECASE)

    for file_path in files:
        # Define the new filename (e.g., var_1.tex -> var_1Q.tex)
        base_name = os.path.splitext(file_path)[0]
        new_tex_name = f"{base_name}Q.tex"
        
        print(f"Processing {file_path} -> {new_tex_name}...")
        
        try:
            # Read original content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Remove the answer lines [cite: 187, 190, 195, 204, 318]
            cleaned_content = answer_regex.sub('', content)

            # Save to the new 'Q' file
            with open(new_tex_name, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            
            print(f"  Successfully created {new_tex_name}.")

            
            # Compile the new file with pdflatex
            print(f"  Compiling {new_tex_name}...")
            # Using -interaction=nonstopmode to prevent the script from hanging on LaTeX errors
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', new_tex_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode == 0:
                print(f"  Successfully compiled {new_tex_name} to PDF.")
            else:
                print(f"  Error during compilation of {new_tex_name}.")
                                
            #############################################
            # Compile base_name file with pdflatex
            print(f"  Compiling {base_name}...")
            # Using -interaction=nonstopmode to prevent the script from hanging on LaTeX errors
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', base_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode == 0:
                print(f"  Successfully compiled {base_name} to PDF.")
            else:
                print(f"  Error during compilation of {base_name}.")                    
        except Exception as e:
            print(f"  Failed to process {file_path}: {e}")



def shuffle_latex_questions_flexible(file_path, output_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Identify the header (everything before Question 1)
    header_match = re.search(r'(.*?)(\\textbf\{Question 1:\})', content, re.DOTALL)
    if not header_match:
        print("Could not find Question 1.")
        return
    
    header = header_match.group(1)
    
    # 2. Identify the footer (everything from \end{document} onwards)
    footer_match = re.search(r'(\\end\{document\}.*)', content, re.DOTALL)
    footer = footer_match.group(1) if footer_match else ""

    # 3. Extract the body containing all questions
    # We take everything from Question 1 up to \end{document}
    body_pattern = r'(\\textbf\{Question 1:\}.*?)\\end\{document\}'
    body_match = re.search(body_pattern, content, re.DOTALL)
    if not body_match:
        print("Could not isolate question body.")
        return
    body = body_match.group(1)

    # 4. Split the body into individual question blocks.
    # This regex splits by the "Question X:" pattern but keeps the delimiter.
    # It works even if "Answer: (X)" is missing.
    raw_questions = re.split(r'(\\textbf\{Question \d+:\})', body)
    
    # re.split with capturing groups returns [empty, delimiter, content, delimiter, content...]
    questions_list = []
    for i in range(1, len(raw_questions), 2):
        q_header = raw_questions[i]
        q_content = raw_questions[i+1]
        questions_list.append(q_header + q_content)

    # 5. Shuffle and Re-index
    random.shuffle(questions_list)
    
    shuffled_body = ""
    for i, q_text in enumerate(questions_list, 1):
        # Replace the old question number with the new sequential index
        indexed_q = re.sub(r'\\textbf\{Question \d+:\}', f'\\\\textbf{{Question {i}:}}', q_text)
        shuffled_body += indexed_q.strip() + "\n\n"

    # 6. Reassemble
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(header + shuffled_body + footer)
    
    print(f"Successfully shuffled {len(questions_list)} questions into {output_path}")


from dotenv import load_dotenv
load_dotenv()  # loads .env file
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
xml_files = []
var = var + 1 #### setting, do not alter

if __name__ == "__main__":
    pattern=glob.glob('*.xml')
    for i in pattern:
        xml_files.append(i)
    latex_template = "sample_sol.tex"
    
     
    for j in range(1,var):        
        filename = f"t{j}.tex"
        tex = generate_latex_mcq_from_xml(
            xml_paths=xml_files,
            latex_template_path=latex_template,
            output_tex_path=filename,
            questions_per_xml=1,
        )
        print("Generated LaTeX length:", len(tex))
        print(f"Saved to {filename}")
        
    for i in range(1,var):
        pattern = [f't{i}.tex']            
        if i != var:
            print('*** i, var *** ',i,var)
            process_and_compile_tex(pattern[0])            
            shuffle_latex_questions_flexible(f't{i}.tex', f't{i+1}.tex')
            print('')

pattern = glob.glob('*.log') + glob.glob('*.aux') + glob.glob('*.synctex.gz')
for i in pattern:
    os.remove(i)