import pypdf
import docx
import os


def extract_text_from_file(file_path, file_type):
    if file_type == 'pdf':
        return extract_from_pdf(file_path)
    elif file_type == 'docx':
        return extract_from_docx(file_path)
    elif file_type == 'txt':
        return extract_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def extract_from_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


def extract_from_docx(file_path):
    doc = docx.Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text += paragraph.text + "\n"
    return text.strip()


def extract_from_txt(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read().strip()