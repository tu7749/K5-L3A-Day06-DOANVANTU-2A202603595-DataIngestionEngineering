from pathlib import Path


def patch(path, pairs):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in s:
            print(f"BỎ QUA (không thấy chuỗi): {path}: {old[:45]!r}")
            continue
        s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("đã vá", path)


patch("src/evaluation.py", [
    ('a.get("source_id", q["gold_source_id"])',
     '(a.get("source_id") or a.get("gold_source_id") or q["gold_source_id"])'),
    ('"page": a["page"]', '"page": a.get("page", a.get("gold_page"))'),
])
patch("src/store.py", [
    ("ORDER BY distance LIMIT %s", "ORDER BY distance, chunk_id LIMIT %s"),
])
patch("src/run.py", [
    ('            hits = store.search(store_name, qvecs[q["id"]], TOP_K, flt)\n',
     '            t1 = time.perf_counter()\n'
     '            hits = store.search(store_name, qvecs[q["id"]], TOP_K, flt)\n'
     '            ms = round((time.perf_counter() - t1) * 1000, 2)\n'),
    ('"hits": hits, "evaluation"', '"hits": hits, "search_ms": ms, "evaluation"'),
])