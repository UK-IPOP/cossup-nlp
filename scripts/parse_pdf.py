from PyPDF2 import PdfReader

reader = PdfReader("example.pdf")
for page in reader.pages:
    print(page.extract_text())
    print("-----")
