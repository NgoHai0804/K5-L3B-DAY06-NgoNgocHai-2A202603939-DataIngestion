"""Implement fixed-size and structure-aware chunking."""
import hashlib

from .models import Chunk, DocumentPage


def _stable_id(document_id: str, page: int, idx: int, text: str) -> str:
    h = hashlib.sha1(f"{document_id}:{page}:{idx}:{text}".encode("utf-8")).hexdigest()
    return f"{document_id}-p{page}-c{idx}-{h[:8]}"


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split text into overlapping windows and retain page metadata."""
    assert 0 <= overlap < size, "overlap phải nhỏ hơn size"
    text, step, chunks, idx = page.text, size - overlap, [], 0
    for start in range(0, len(text), step):
        piece = text[start:start + size]
        if not piece.strip():
            continue
        chunks.append(
            Chunk(
                chunk_id=_stable_id(page.document_id, page.page, idx, piece),
                document_id=page.document_id,
                source=page.source,
                page=page.page,
                text=piece,
                metadata={**page.metadata, "chunking": "fixed_size"},
            )
        )
        idx += 1
        if start + size >= len(text):
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Group paragraphs, split oversized paragraphs and retain metadata."""
    paras = [p.strip() for p in page.text.split("\n\n") if p.strip()]
    pieces: list[str] = []
    buf = ""
    for para in paras:
        if len(para) > max_size:  # đoạn quá dài -> cắt nhỏ
            if buf:
                pieces.append(buf)
                buf = ""
            for s in range(0, len(para), max_size):
                pieces.append(para[s:s + max_size])
        elif buf and len(buf) + len(para) + 2 > max_size:
            pieces.append(buf)
            buf = para
        else:
            buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        pieces.append(buf)
    return [
        Chunk(
            chunk_id=_stable_id(page.document_id, page.page, i, piece),
            document_id=page.document_id,
            source=page.source,
            page=page.page,
            text=piece,
            metadata={**page.metadata, "chunking": "by_paragraph"},
        )
        for i, piece in enumerate(pieces)
    ]