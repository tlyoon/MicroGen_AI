import xml.etree.ElementTree as ET
from pathlib import Path

def read_moodle_quiz(xml_file: Path):
    """
    Reads a Moodle XML quiz file and extracts question data.
    
    Args:
        xml_file: The path to the Moodle XML file.
    """
    # Check if the file exists
    if not xml_file.is_file():
        print(f"Error: The file '{xml_file}' does not exist.")
        return

    try:
        # Parse the XML file
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # The root element is '<quiz>'. We want to iterate through all '<question>' elements.
        print(f"--- Processing Quiz from '{xml_file.name}' ---")
        
        for question in root.findall('question'):
            # Skip the category question
            if question.attrib.get('type') == 'category':
                continue

            # Extract question name and text
            q_name = question.find('name/text').text
            # The question text is inside a CDATA section, which ElementTree handles.
            q_text_html = question.find('questiontext/text').text
            
            # Print question details
            print(f"\nQuestion Name: {q_name}")
            print(f"----------------------------------------")
            # To clean up the HTML, you might need a dedicated library like BeautifulSoup,
            # but for a simple display, this is sufficient.
            print(f"Question Text (HTML): {q_text_html.strip()}")

            # Find all answers for the question
            print("\nAnswers:")
            for answer in question.findall('answer'):
                fraction = answer.attrib.get('fraction')
                answer_text = answer.find('text').text
                feedback = answer.find('feedback/text').text
                
                # Check if it's the correct answer
                is_correct = "Correct" if fraction == "100" else "Incorrect"
                
                # Print answer details
                print(f"  - [{is_correct}] Answer Text: {answer_text.strip()}")
                print(f"    Feedback: {feedback.strip()}")
        
        print("\n--- End of Quiz ---")

    except ET.ParseError as e:
        print(f"Error parsing the XML file: {e}")
    except AttributeError as e:
        print(f"Error accessing a tag. The XML structure might be different than expected: {e}")

# --- Example Usage ---
# Ensure your XML file is in the same directory as this script.

xml_file_path = Path("Section_30_6_Eddy_Currents_mcq.xml")
read_moodle_quiz(xml_file_path)

