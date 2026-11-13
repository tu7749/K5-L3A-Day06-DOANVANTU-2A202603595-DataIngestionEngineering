"""Read and normalize source data."""
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage

_REPL = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi",
         "\ufb04": "ffl", "\u00a0": " ", "\u00ad": "", "\u200b": ""}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    for k, v in _REPL.items():
        text = text.replace(k, v)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=[A-Za-z])-\n(?=[a-z])", "", text)   # nối từ bị ngắt dòng
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    reader = PdfReader(str(path))
    pages = []
    for i, p in enumerate(reader.pages, start=1):
        meta = {}
        try:
            raw = p.extract_text() or ""
        except Exception as e:                  # ghi lỗi, không bỏ qua âm thầm
            raw, meta["error"] = "", repr(e)
        text = normalize_text(raw)
        if not text:
            meta["empty"] = True
        pages.append(DocumentPage(document_id, source, i, text, meta))
    return pages