import os
import sys
from PyPDF2 import PdfReader, PdfWriter

slidesfiles = ["slides.pdf"]

### pick up  the last existing item in slidesfiles ###
for i in slidesfiles:
    if os.path.isfile(i):
        slidesfile = i

print('slidesfile:', slidesfile)

input_pdf_path = slidesfile
if not input_pdf_path:
    print(f"Warning: The source file {slidesfile} is absent. Check again.")
    sys.exit(1)
else:
    print(f"Found the source file {slidesfile}")
    """
    Splits a PDF presentation into individual PDF slide files, named slide1.pdf, slide2.pdf, etc.

    Args:
        input_pdf_path (str): Path to the input PDF presentation file.
        output_dir (str, optional): Directory to save the individual slide PDFs. Defaults to "slides".
                                     If the directory doesn't exist, it will be created.
    """
    try:
        with open(input_pdf_path, 'rb') as input_pdf_file:
            pdf_reader = PdfReader(input_pdf_file)

            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                pdf_writer = PdfWriter()
                pdf_writer.add_page(page)

                output_filename = f"slide{page_num + 1}.pdf"

                with open(output_filename, 'wb') as output_pdf_file:
                    pdf_writer.write(output_pdf_file)
                print(f"Slide {page_num + 1} saved to: {output_filename}")           

        print(f"\nSuccessfully split '{input_pdf_path}' into individual slides ")

    except Exception as e:
        print(f"An error occurred while splitting PDF: {e}")




