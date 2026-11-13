import hashlib
import json
import re

from src.sections import (DOC_ID, OUT, PDF_PATH, PRINTED_OFFSET, RANGES, ROOT,
                          SOURCE, load_corpus)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


pages = load_corpus()
content_pages = sorted({p.page for p in pages})
attr = None
for p in pages:
    m = re.search(r"\(Attribution:[^)]*\)", p.text)
    if m:
        attr = m.group(0)
        break

manifest = {
    "source_id": DOC_ID,
    "title": "Principles of Management (OpenStax), chương 13 và 14, PDF trích 80 trang",
    "source_path_or_url": {
        "file": SOURCE,
        "book_page": "https://openstax.org/details/books/principles-management"},
    "license_or_permission": {
        "attribution_line_found_in_pdf": attr,
        "full_license_text": "TODO: chép nguyên văn từ trang bản quyền của đúng bản PDF này"},
    "accessed_at": "TODO: ngày bạn tải file (YYYY-MM-DD)",
    "snapshot_or_version": "TODO: ghi version/ngày xuất bản nếu PDF có",
    "physical_pages": 80,
    "page_numbering": f"page = trang trong PDF 80 trang (bắt đầu từ 1); printed_page = page + {PRINTED_OFFSET}",
    "counted_page_ranges": [{"chapter": ch, "title": t, "pdf_pages": [a, b]}
                            for a, b, ch, t in RANGES],
    "counting_rule": "Chỉ tính trang có nội dung section; loại trang 1, 32-40, 75-80 "
                     "(giới thiệu, thuật ngữ, tổng kết, bài tập, case), header chạy, "
                     "dòng 'Access for free at openstax.org' và phần trước tiêu đề đầu chương",
    "content_pages": content_pages,
    "content_page_count": len(content_pages),
    "total_chars": sum(p.metadata["char_count"] for p in pages),
    "records": len(pages),
    "sha256": {"pdf": sha(PDF_PATH), "sections_jsonl": sha(OUT)},
}
(ROOT / "data" / "manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(manifest, indent=2, ensure_ascii=False)[:1500])