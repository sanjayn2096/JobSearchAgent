from __future__ import annotations

import io
from pathlib import Path


def extract_text(data: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(data)
    if suffix in (".docx", ".doc"):
        return _from_docx(data)
    raise ValueError(f"Unsupported format: {suffix}. Use PDF or DOCX.")


def _from_pdf(data: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages).strip()


def _from_docx(data: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
