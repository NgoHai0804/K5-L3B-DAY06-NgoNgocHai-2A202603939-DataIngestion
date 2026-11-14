"""Read and normalize source data."""
import re
import unicodedata
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .models import DocumentPage


def normalize_text(text: str) -> str:
    """Normalize Unicode (NFC) and whitespace while keeping useful structure.

    - NFC keeps Vietnamese diacritics canonical.
    - Spaces/tabs inside a line collapse to one space; line breaks are kept so
      paragraph boundaries (\n\n) survive for structure-aware chunking.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_pdf(
    path: Path,
    document_id: str,
    source: str,
    doc_metadata: dict[str, Any] | None = None,
    section_map: dict[str, list[int]] | None = None,
) -> list[DocumentPage]:
    """Extract each physical page, keep page number + source, and tag metadata.

    Empty (no text) pages are recorded with ``is_empty`` so they can be logged.
    Metadata used for filtering (section/year/language/document_type) comes from
    the manifest, never invented here.
    """
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    for i, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        norm = normalize_text(raw)
        meta: dict[str, Any] = dict(doc_metadata or {})
        meta["is_empty"] = len(norm) == 0
        if section_map:
            for name, ids in section_map.items():
                if i in ids:
                    meta["section"] = name
                    break
        pages.append(
            DocumentPage(document_id=document_id, source=source, page=i, text=norm, metadata=meta)
        )
    return pages