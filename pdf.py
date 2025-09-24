import PyPDF2

def pdf_to_md(pdf_path, md_path, start_page=8, end_page=739):
    # Open the PDF file
    with open(pdf_path, "rb") as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        num_pages = len(reader.pages)

        # Safety check
        if start_page < 1 or end_page > num_pages:
            raise ValueError(f"PDF has {num_pages} pages, but requested {start_page}-{end_page}")

        with open(md_path, "w", encoding="utf-8") as md_file:
            for page_num in range(start_page - 1, end_page):  # PyPDF2 uses 0-based indexing
                page = reader.pages[page_num]
                text = page.extract_text()

                # Basic markdown formatting
                md_file.write(f"\n\n---\n\n# Page {page_num+1}\n\n")
                if text:
                    md_file.write(text)
                else:
                    md_file.write("_[No extractable text on this page]_")

    print(f"✅ Saved Markdown file to {md_path}")


if __name__ == "__main__":
    pdf_path = "c5.pdf"        # path to your PDF
    md_path = "output.md"         # path to save markdown
    pdf_to_md(pdf_path, md_path, start_page=8, end_page=739)
