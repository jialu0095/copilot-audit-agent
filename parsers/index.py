from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .pdf import extract_pdf_text
from .docx import extract_docx_text
from .excel import extract_excel_text
from .image import is_image_file, build_image_attachments, SUPPORTED_IMAGE_EXTS


@dataclass
class ParsedInput:
    """
    kind:
      - "text": text not None => attachments is None
      - "image": attachments not None => text is None
    """
    kind: str
    text: str | None = None
    attachments: list[dict] | None = None


async def parse_input(file_path: str) -> ParsedInput:
    # Determine file type by extension
    ext = Path(file_path).suffix.lower()

    # img attachments
    if is_image_file(file_path):
        return ParsedInput(kind="image", attachments=build_image_attachments(file_path))

    # text
    if ext == ".pdf":
        return ParsedInput(kind="text", text=await extract_pdf_text(file_path))

    if ext == ".docx":
        return ParsedInput(kind="text", text=await extract_docx_text(file_path))

    if ext in (".xlsx", ".xls"):
        return ParsedInput(kind="text", text=await extract_excel_text(file_path))

    raise ValueError(
        f"Unsupported file format: {ext}. "
        f"Supported formats: .pdf, .docx, .xlsx, .xls, images({', '.join(sorted(SUPPORTED_IMAGE_EXTS))})"
    )
