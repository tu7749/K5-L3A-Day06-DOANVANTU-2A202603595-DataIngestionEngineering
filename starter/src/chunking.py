"""Fixed-size and paragraph-aware chunking."""
import re

from .models import Chunk, DocumentPage


def _make(page: DocumentPage, kind: str, i: int, text: str, extra: dict | None = None) -> Chunk:
    sid = page.metadata.get("section_id", "na")
    meta = dict(page.metadata)
    meta.update({"chunker": kind, "chunk_index": i, **(extra or {})})
    return Chunk(chunk_id=f"{page.document_id}:p{page.page:03d}:s{sid}:{kind}{i:03d}",
                 document_id=page.document_id, source=page.source, page=page.page,
                 text=text, metadata=meta)


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if not 0 <= overlap < size:
        raise ValueError("overlap phải nhỏ hơn size")
    t, step, out = page.text, size - overlap, []
    for start in range(0, len(t), step):
        piece = t[start:start + size].strip()
        if piece:
            out.append(_make(page, "fix", len(out), piece, {"char_start": start}))
        if start + size >= len(t):
            break
    return out


def _split_long(par: str, max_size: int) -> list[str]:
    parts, buf = [], ""
    for s in re.split(r"(?<=[.!?])\s+", par):
        while len(s) > max_size:                       # câu quá dài: cắt cứng
            if buf:
                parts.append(buf); buf = ""
            parts.append(s[:max_size]); s = s[max_size:]
        if buf and len(buf) + 1 + len(s) > max_size:
            parts.append(buf); buf = s
        else:
            buf = f"{buf} {s}".strip()
    if buf:
        parts.append(buf)
    return parts


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    paras = [p.strip() for p in re.split(r"\n{2,}", page.text) if p.strip()]
    pieces = []
    for p in paras:
        pieces += [p] if len(p) <= max_size else _split_long(p, max_size)
    out, buf = [], ""
    for p in pieces:
        if buf and len(buf) + 2 + len(p) > max_size:
            out.append(_make(page, "par", len(out), buf)); buf = ""
        buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        out.append(_make(page, "par", len(out), buf))
    return out