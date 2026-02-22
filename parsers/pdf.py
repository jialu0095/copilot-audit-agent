from __future__ import annotations
from pathlib import Path
from pypdf import PdfReader


async def extract_pdf_text(file_path: str) -> str:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    try:
        reader = PdfReader(str(p))
        texts: list[str] = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                texts.append(t)
        return "\n".join(texts).strip()
    except Exception as e:
        raise RuntimeError(f"Failed to parse PDF: {e}") from e