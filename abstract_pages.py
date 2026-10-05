from PyPDF2 import PdfReader, PdfWriter

def extract_pages(input_file, init_page, last_page, output_file):
  """
  Extracts a range of pages from a PDF file.

  Args:
      input_file: Path to the input PDF file.
      init_page: Starting page number (1-indexed).
      last_page: Ending page number (1-indexed).
      output_file: Path to the output PDF file.
  """

  with open(input_file, 'rb') as infile:
      reader = PdfReader(infile)

      writer = PdfWriter()
      for page_num in range(init_page - 1, last_page):  # Adjust for 0-based indexing
          writer.add_page(reader.pages[page_num])  # Use reader.pages with proper indexing

      with open(output_file, 'wb') as outfile:
          writer.write(outfile)

input_pdf = 'source.pdf'
start_page = 29
end_page = 40
output_pdf = str(start_page) + '_' + str(end_page) + '.pdf'
extract_pages(input_pdf, start_page, end_page, output_pdf)
