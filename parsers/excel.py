from __future__ import annotations

from pathlib import Path
from openpyxl import load_workbook


async def extract_excel_text(file_path: str) -> str:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    try:
        wb = load_workbook(filename=str(p), data_only=True)
        parts: list[str] = []

        for sheet in wb.worksheets:
            parts.append(f"\n=== Sheet: {sheet.title} ===")

            for row in sheet.iter_rows(values_only=True):
                # remove None and empty cells, and strip text
                cells = [
                    str(cell).strip()
                    for cell in row
                    if cell is not None and str(cell).strip() != ""
                ]

                if cells:
                    # join cells with " | " to preserve table structure in text form
                    parts.append(" | ".join(cells))

        return "\n".join(parts).strip()

    except Exception as e:
        raise RuntimeError(f"Failed to parse Excel: {e}") from e
