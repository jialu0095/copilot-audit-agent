from __future__ import annotations

from pathlib import Path

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}


def is_image_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in SUPPORTED_IMAGE_EXTS


def build_image_attachments(file_path: str) -> list[dict]:
    """
    Copilot SDK Python attachments: [{"type":"file","path": "..."}]
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Image file not found: {file_path}")
    return [{"type": "file", "path": str(p.resolve())}]