"""Chọn trang, bỏ header/footer, tách section, dựng lại đoạn.
Chạy từ starter/:  python -m src.sections"""
import json
import re
import time
from collections import Counter
from pathlib import Path

from .ingestion import load_pdf
from .models import DocumentPage

ROOT = Path(__file__).resolve().parents[2]      # src -> starter -> gốc repo
PDF_PATH = ROOT / "data" / "raw" / "principles-management.pdf"
SOURCE = "data/raw/principles-management.pdf"   # ghi vào metadata, tương đối với gốc repo
OUT = ROOT / "data" / "processed" / "sections.jsonl"
STATS = ROOT / "results" / "ingestion_stats.json"
ERRORS = ROOT / "results" / "errors.jsonl"

DOC_ID = "openstax_management_ch13_ch14"
PRINTED_OFFSET = 360
RANGES = [(2, 31, 13, "Leadership"), (41, 74, 14, "Work Motivation for Performance")]
SECTIONS = {
    "13.1": ("The Nature of Leadership", 2), "13.2": ("The Leadership Process", 4),
    "13.3": ("Leader Emergence", 8), "13.4": ("The Trait Approach to Leadership", 13),
    "13.5": ("Behavioral Approaches to Leadership", 16),
    "13.6": ("Situational (Contingency) Approaches to Leadership", 19),
    "13.7": ("Substitutes for and Neutralizers of Leadership", 23),
    "13.8": ("Transformational, Visionary, and Charismatic Leadership", 26),
    "13.9": ("Leadership Needs in the 21st Century", 30),
    "14.1": ("Motivation: Direction and Intensity", 41),
    "14.2": ("Content Theories of Motivation", 44),
    "14.3": ("Process Theories of Motivation", 57),
    "14.4": ("Recent Research on Motivation Theories", 72),
}
HEADINGS = {f"{sid} {t}": sid for sid, (t, _) in SECTIONS.items()}

# Header chạy của trang, ví dụ '366 13 • Leadership' và '13.4 • The Trait Approach to Leadership 375'
RUNNING = [re.compile(r"^\d{3} 1[34] • .+$"),
           re.compile(r"^1[34]\.\d • .+ \d{3}$")]


def chapter_of(page):
    for a, b, ch, title in RANGES:
        if a <= page <= b:
            return ch, title
    return None, None


def is_noise(line: str, boiler: set) -> bool:
    s = line.strip()
    return s in boiler or any(r.match(s) for r in RUNNING)


def reflow(lines: list[str], width: float) -> str:
    """Nối dòng thành đoạn; dòng ngắn hơn 0.8*width coi là cuối đoạn."""
    paras, cur = [], []
    for l in lines:
        l = l.strip()
        if not l:
            continue
        cur.append(l)
        if len(l) < 0.8 * width:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)


def page_width(lines):
    ls = sorted(len(l) for l in lines if l.strip())
    return ls[int(0.95 * (len(ls) - 1))] if ls else 0


def build():
    t0 = time.time()
    pages = load_pdf(PDF_PATH, DOC_ID, SOURCE)
    chosen = [p for p in pages if chapter_of(p.page)[0]]
    cnt = Counter()
    for p in chosen:
        ls = [l.strip() for l in p.text.splitlines() if l.strip()]
        cnt.update(set(ls[:1] + ls[-1:]))
    boiler = {l for l, n in cnt.items() if n > 0.3 * len(chosen)}
    print("boilerplate nghi ngờ (kiểm tra bằng mắt):", boiler)

    errors = [{"page": p.page, **p.metadata} for p in chosen if p.metadata]
    recs, found, intro_chars, current = [], {}, 0, None
    for p in chosen:
        ch, ch_title = chapter_of(p.page)
        if current and not current.startswith(f"{ch}."):
            current = None                      # sang chương mới
        blocks, buf = [], []
        lines = [l for l in p.text.splitlines() if not is_noise(l, boiler)]
        width = page_width(lines)
        for line in lines:
            s = re.sub(r"\s+", " ", line).strip()
            if s in HEADINGS:
                blocks.append((current, buf))
                buf = []
                current = HEADINGS[s]
                found[current] = p.page
            else:
                buf.append(line)
        blocks.append((current, buf))
        for sid, bl in blocks:
            text = reflow(bl, width)
            if not text:
                continue
            if sid is None:
                intro_chars += len(text)        # phần trước tiêu đề đầu chương, loại
                continue
            recs.append({
                "document_id": DOC_ID, "source": SOURCE, "page": p.page, "text": text,
                "metadata": {
                    "printed_page": p.page + PRINTED_OFFSET, "chapter": ch,
                    "chapter_title": ch_title, "section_id": sid,
                    "section_title": SECTIONS[sid][0], "language": "en",
                    "char_count": len(text)}})
    for sid, (t, start) in SECTIONS.items():
        if found.get(sid) != start:
            print(f"!! {sid}: mong đợi trang {start}, thực tế {found.get(sid)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    STATS.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
                   encoding="utf-8")
    ERRORS.write_text("\n".join(json.dumps(e) for e in errors), encoding="utf-8")
    content_pages = sorted({r["page"] for r in recs})
    stats = {"pdf_pages": len(pages), "selected_pages": len(chosen),
             "content_pages": len(content_pages), "records": len(recs),
             "total_chars": sum(r["metadata"]["char_count"] for r in recs),
             "excluded_intro_chars": intro_chars,
             "records_per_section": dict(Counter(r["metadata"]["section_id"] for r in recs)),
             "seconds": round(time.time() - t0, 2)}
    STATS.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


def load_corpus(path: Path = OUT) -> list[DocumentPage]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out.append(DocumentPage(r["document_id"], r["source"], r["page"],
                                    r["text"], r["metadata"]))
    return out


if __name__ == "__main__":
    build()