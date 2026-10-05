### use this code to generate individual *.wav file for the script of a specific slide in script.txt.

## set the slide number of which a *.wav file is to be generated:
slide_no = 14 ###

import shutil
import sys
from pathlib import Path
import os
import re
import glob
import contractions
from google.cloud import texttospeech
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
#sys.stdout.reconfigure(encoding='utf-8')

## begin main here ###
credential_file = 'google_cloud_credentials.json'
###    
try:    
    json_path1 = Path(__file__).resolve().parent.parent.parent / credential_file  ## default
    json_path = str(json_path1)
except NameError:        
    json_path1 = Path(os.getcwd()).parent.parent.parent / credential_file  ## default
    json_path = str(json_path1)

if json_path1.is_file():
    print(f"✅ 1 File exists: {json_path}")
else:
    json_path1 = credential_file 
    json_path = str(json_path1)    
    print(f"✅ 2 File exists: {json_path}")
###
    
#print(f'{credential_file} found in json_path = {json_path}? {os.path.isfile(json_path)}')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_path
if os.path.isfile(json_path) == False:
    print(f'{credential_file} not found in {json_path1}. Set the path of the credential file and try again.')
    os._exit(1)
else:
    print(f'{credential_file} found in {json_path1}.')


scriptfile = f"script.txt"
input_file = f"{scriptfile}"


def read_slides_from_file(file_path):
    """
    Reads the input text file and returns a list of slide blocks.
    Each slide block is assumed to start with "**Slide" (including the header)
    and continue until the next occurrence or the end of file.
    """
    with open(file_path, "r", encoding="cp1252") as f:
        text = f.read()
    # Split the file into blocks at every occurrence of "**Slide" (keeping the marker with each block)
    slides = re.split(r'(?=\*\*Slide)', text)
    # Remove any empty blocks
    slides = [slide.strip() for slide in slides if slide.strip()]
    return slides

def remove_header(slide_block):
    """
    Removes the header line from a slide block.
    The header is assumed to be the first line that starts with "**Slide".
    Returns the narration text without the header.
    """
    lines = slide_block.splitlines()
    if lines and lines[0].strip().startswith("**Slide"):
        lines = lines[1:]
    narration = "\n".join(lines)
    # Remove any trailing asterisks and extra whitespace.
    narration = narration.strip().rstrip("*").strip()
    return narration

def text_to_speech(text, output_filename):
    """
    Converts the given text to speech using Google Cloud Text-to-Speech API
    and saves the output as a WAV file.
    """
    # Normalize apostrophes and expand contractions
    text = text.replace("`", "'").replace("’", "'").replace("‘", "'")    
    clean_text = contractions.fix(text)

    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=clean_text)

    #voice = texttospeech.VoiceSelectionParams(
    #    language_code="en-US",
    #    name="en-US-Chirp3-HD-Puck",
    #    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    #)
    
    #voice = texttospeech.VoiceSelectionParams(
    #    language_code="en-US",
    #    name="en-US-Chirp3-HD-Aoede",
    #    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    #)   

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Chirp-HD-F",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        speaking_rate=0.9
    )

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    with open(output_filename, "wb") as out:
        out.write(response.audio_content)
    #print(f'Audio content written to file "{output_filename}"')
    

slides = read_slides_from_file(input_file)
num_slides = len(slides)
print(f"Total slide block found in {input_file}: {num_slides}")
    
# Process each slide separately.
# Enumerate slides starting at 1 so that the first slide is slide1.wav, etc.
for idx, slide in enumerate(slides, start=1):    
    try:
        narration = remove_header(slide)
        if idx == slide_no:
            # back up the *.wav file
            output_file = f"slide{idx}.wav"
            backup_file = f"slide{idx}_bk.wav"
            if os.path.exists(output_file): 
                print(f"⚠️ Overwriting {backup_file}")
                shutil.copyfile(output_file, backup_file)
            text_to_speech(narration, output_file)
            print(f'The script for slide {idx} has been written to {output_file}')
    except Exception as e:
        print(f"Error processing slide {idx}: {e}")
    
# Verify that the number of generated WAV files matches the slide count.
produced_files = glob.glob("slide*.wav")
produced_count = len(produced_files)


#if produced_count == num_slides:
#    print(f"Success: Produced {produced_count} audio files, matching the number of slides.")
#else:
#    print(f"Error: Expected {num_slides} audio files, but found {produced_count}.")
   

"""
Name: en-AU-Chirp-HD-F
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Chirp-HD-O
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Chirp3-HD-Aoede
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Chirp3-HD-Kore
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Chirp3-HD-Leda
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Chirp3-HD-Zephyr
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Neural2-A
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Neural2-C
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-News-E
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-News-F
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Standard-A
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Standard-C
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Wavenet-A
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-AU-Wavenet-C
Supported Languages: en-AU
SSML Gender: FEMALE

Name: en-GB-Chirp-HD-F
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Chirp-HD-O
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Chirp3-HD-Aoede
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Chirp3-HD-Kore
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Chirp3-HD-Leda
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Chirp3-HD-Zephyr
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Neural2-A
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Neural2-C
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Neural2-F
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Neural2-N
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-News-G
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-News-H
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-News-I
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Standard-A
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Standard-C
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Standard-F
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Standard-N
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Studio-C
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Wavenet-A
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Wavenet-C
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Wavenet-F
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-GB-Wavenet-N
Supported Languages: en-GB
SSML Gender: FEMALE

Name: en-IN-Chirp-HD-F
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Chirp-HD-O
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Chirp3-HD-Aoede
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Chirp3-HD-Kore
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Chirp3-HD-Leda
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Chirp3-HD-Zephyr
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Neural2-A
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Neural2-D
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Standard-A
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Standard-D
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Standard-E
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Wavenet-A
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Wavenet-D
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-IN-Wavenet-E
Supported Languages: en-IN
SSML Gender: FEMALE

Name: en-US-Chirp-HD-F
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Chirp-HD-O
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Chirp3-HD-Aoede
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Chirp3-HD-Kore
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Chirp3-HD-Leda
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Chirp3-HD-Zephyr
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Neural2-C
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Neural2-E
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Neural2-F
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Neural2-G
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Neural2-H
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-News-K
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-News-L
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Standard-C
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Standard-E
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Standard-F
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Standard-G
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Standard-H
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Studio-O
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Wavenet-C
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Wavenet-E
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Wavenet-F
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Wavenet-G
Supported Languages: en-US
SSML Gender: FEMALE

Name: en-US-Wavenet-H
Supported Languages: en-US
SSML Gender: FEMALE
"""

