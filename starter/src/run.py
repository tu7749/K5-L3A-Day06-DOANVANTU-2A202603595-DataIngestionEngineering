"""Pipeline: corpus -> chunk -> embed -> pgvector -> top-3 trace -> metrics.

Chạy từ starter/:
  python -m src.run --validate-only     # chỉ kiểm tra benchmark
  python -m src.run --split dev         # chạy dev (mặc định)
  python -m src.run --split test        # CHỈ sau khi đã chốt cấu hình trên dev
"""
import argparse
import csv
import json
import os
import platform
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from . import chunking
from .evaluation import evaluate_query, gold_list, norm, summarize
from .sections import DOC_ID, ROOT, load_corpus
from .store import FILTER_COLUMNS, PgVectorStore

BENCH = ROOT / "benchmark" / "questions.json"
RESULTS = ROOT / "results"
TOP_K = 3

# C không có chunk riêng: dùng chunk/vector của B, khác duy nhất là áp filter.
STRATEGIES = {
    "A": {"chunker": "fixed_size", "params": {"size": 500, "overlap": 50}, "filter": False},
    "B": {"chunker": "by_paragraph", "params": {"max_size": 1000}, "filter": False},
    "C": {"chunker": "by_paragraph", "params": {"max_size": 1000}, "filter": True,
          "store_strategy": "B"},
}


def make_chunks(name, pages):
    cfg = STRATEGIES[name]
    fn = getattr(chunking, cfg["chunker"])
    return [c for p in pages for c in fn(p, **cfg["params"])]


def validate_benchmark(qs, pages):
    errs, warns = [], []
    required = ["id", "split", "question", "expected_answer",
                "gold_source_id", "gold_page", "evidence_quote"]
    page_text = defaultdict(list)
    for p in pages:
        page_text[p.page].append(norm(p.text))
    ids = set()
    for q in qs:
        qid = q.get("id", "?")
        missing = [k for k in required if q.get(k) in (None, "")]
        if missing:
            errs.append(f"{qid}: thiếu trường {missing}")
            continue
        if qid in ids:
            errs.append(f"{qid}: id trùng")
        ids.add(qid)
        if q["split"] not in ("dev", "test"):
            errs.append(f"{qid}: split phải là dev hoặc test")
        if q["gold_source_id"] != DOC_ID:
            errs.append(f"{qid}: gold_source_id phải là {DOC_ID}")
        for g in gold_list(q):
            ev = norm(g["evidence_quote"])
            if not any(ev in t for t in page_text.get(g["page"], [])):
                errs.append(f"{qid}: evidence không khớp văn bản trang {g['page']}")
            if len(ev) > 300:
                warns.append(f"{qid}: evidence dài {len(ev)} ký tự, chunk A dễ cắt đôi; "
                             "nên chọn một câu then chốt")
        for k in (q.get("filter") or {}):
            if k not in FILTER_COLUMNS:
                errs.append(f"{qid}: filter '{k}' không được phép {list(FILTER_COLUMNS)}")
    dev = [q for q in qs if q.get("split") == "dev"]
    test = [q for q in qs if q.get("split") == "test"]
    flt = [q for q in qs if q.get("filter")]
    if len(qs) < 20:
        errs.append(f"cần ≥20 câu, hiện có {len(qs)}")
    if len(dev) < 15 or len(test) < 5:
        errs.append(f"cần ≥15 dev / ≥5 test, hiện {len(dev)} / {len(test)}")
    if len(flt) < 3:
        errs.append(f"cần ≥3 câu có filter, hiện {len(flt)}")
    if not any(q.get("split") == "test" for q in flt):
        errs.append("cần ≥1 câu filter thuộc test")
    print(f"benchmark: {len(qs)} câu | dev {len(dev)} | test {len(test)} | filter {len(flt)}")
    for w in warns:
        print("  cảnh báo:", w)
    if errs:
        print("LỖI benchmark:")
        for e in errs:
            print("  -", e)
        raise SystemExit(1)
    print("benchmark hợp lệ.")


def length_stats(chunks, tokenizer):
    lens = sorted(len(c.text) for c in chunks)
    toks = [len(tokenizer.encode(c.text, add_special_tokens=True)) for c in chunks]
    q = lambda xs, f: xs[int(f * (len(xs) - 1))]
    return {"chunks": len(chunks), "total_chars": sum(lens),
            "total_tokens": sum(toks),
            "chars_min": lens[0], "chars_p25": q(lens, .25), "chars_median": q(lens, .5),
            "chars_p75": q(lens, .75), "chars_max": lens[-1],
            "chars_mean": round(statistics.mean(lens), 1)}


def write_csv_if_missing(path, header, rows):
    if path.exists():
        print(f"  giữ nguyên {path.name} (đã tồn tại, không ghi đè nhãn thủ công)")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  đã tạo {path.name}")


def coherence_sheet(pages, chunks_by):
    """10 vị trí cố định: đầu bản ghi của 10 trang đầu tiên (chọn trước khi xem điểm)."""
    seen, positions = set(), []
    for p in pages:
        if p.page not in seen:
            seen.add(p.page)
            positions.append(p)
        if len(positions) == 10:
            break
    rows = []
    for i, p in enumerate(positions, 1):
        for s in ("A", "B"):                       # C dùng chunk của B
            c = next(c for c in chunks_by[s]
                     if c.page == p.page and c.metadata["section_id"] == p.metadata["section_id"]
                     and c.metadata["chunk_index"] == 0)
            rows.append([s, f"pos{i:02d}", p.page, p.metadata["section_id"],
                         c.chunk_id, len(c.text), c.text, "", ""])
    write_csv_if_missing(RESULTS / "coherence_audit.csv",
                         ["strategy", "position", "page", "section_id", "chunk_id",
                          "chars", "text", "label_0_2", "reason"], rows)


def test_audit_sheets(traces, questions_by_id):
    meta_rows, ground_rows = [], []
    for t in traces:
        q = questions_by_id[t["id"]]
        for h in t["hits"]:
            m = h["metadata"]
            meta_rows.append([t["strategy"], t["id"], h["rank"], h["chunk_id"], h["source"],
                              h["page"], m.get("printed_page"), m.get("chapter"),
                              m.get("section_id"), "", "", "", ""])
        top3 = "\n\n".join(f"[{h['rank']}] (p{h['page']}) {h['text']}" for h in t["hits"])
        ground_rows.append([t["strategy"], t["id"], q["question"], q["expected_answer"],
                            q["evidence_quote"], top3, "", ""])
    write_csv_if_missing(RESULTS / "metadata_audit.csv",
                         ["strategy", "qid", "rank", "chunk_id", "source", "page",
                          "printed_page", "chapter", "section_id",
                          "source_ok", "page_ok", "field_ok", "note"], meta_rows)
    write_csv_if_missing(RESULTS / "grounding_audit.csv",
                         ["strategy", "qid", "question", "expected_answer", "evidence_quote",
                          "top3", "label_0_2", "reason"], ground_rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()
    load_dotenv()
    RESULTS.mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(exist_ok=True)

    pages = load_corpus()
    n_pages = len({p.page for p in pages})
    if n_pages < 30:
        raise SystemExit(f"corpus chỉ có {n_pages} trang nội dung, cần ≥30")
    print(f"corpus: {n_pages} trang nội dung, {len(pages)} bản ghi")
    all_qs = json.loads(BENCH.read_text(encoding="utf-8"))
    validate_benchmark(all_qs, pages)
    if args.validate_only:
        return
    qs = [q for q in all_qs if q["split"] == args.split]
    qby = {q["id"]: q for q in all_qs}

    if args.split == "test":
        log = RESULTS / "test_runs.log"
        prev = len(log.read_text().splitlines()) if log.exists() else 0
        with log.open("a") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} chạy test lần {prev + 1}\n")
        print(f"CHẠY TEST lần {prev + 1}. Nếu >1, ghi rõ trong báo cáo lý do chạy lại "
              "và test không còn độc lập.")

    from .embeddings import MyEmbedder             # import muộn: --validate-only không tải model
    emb = MyEmbedder()
    store = PgVectorStore(os.environ["DATABASE_URL"], emb.dimensions)
    store.create_schema()

    stats, chunks_by = {}, {}
    for name in [n for n, c in STRATEGIES.items() if "store_strategy" not in c]:
        t0 = time.time()
        chunks = make_chunks(name, pages)
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise SystemExit(f"chunk_id trùng ở chiến lược {name}")
        texts = [c.text for c in chunks]
        truncated = emb.count_truncated(texts)
        if truncated:
            raise SystemExit(f"{truncated} chunk của {name} vượt {emb.max_tokens} token")
        vecs = emb.embed_documents(texts)
        store.upsert(name, chunks, vecs)
        if store.count(name) != len(chunks):
            raise SystemExit(f"store {name}: số dòng {store.count(name)} ≠ {len(chunks)}")
        chunks_by[name] = chunks
        stats[name] = {**length_stats(chunks, emb.model.tokenizer),
                       "ingest_seconds": round(time.time() - t0, 2), "cost_usd": 0,
                       "chunker": STRATEGIES[name]["chunker"], **STRATEGIES[name]["params"]}
        print(f"ingest {name}: {stats[name]['chunks']} chunk, {stats[name]['ingest_seconds']}s")

    import sentence_transformers
    import torch
    meta = {"run_at": datetime.now().isoformat(timespec="seconds"),
            "model": emb.model_name, "dimensions": emb.dimensions, "metric": "cosine (exact)",
            "sentence_transformers": sentence_transformers.__version__,
            "torch": torch.__version__, "python": platform.python_version(),
            "strategies": stats}
    (RESULTS / "strategy_stats.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "artifacts" / "strategies.json").write_text(
        json.dumps(STRATEGIES, indent=2), encoding="utf-8")
    coherence_sheet(pages, chunks_by)

    qvecs = {q["id"]: emb.embed_query(q["question"]) for q in qs}
    traces = []
    for name, cfg in STRATEGIES.items():
        store_name = cfg.get("store_strategy", name)
        t0 = time.time()
        for q in qs:
            flt = q.get("filter") if cfg["filter"] else None   # C chỉ lọc khi câu có filter
            t1 = time.perf_counter()
            hits = store.search(store_name, qvecs[q["id"]], TOP_K, flt)
            ms = round((time.perf_counter() - t1) * 1000, 2)
            traces.append({"strategy": name, "split": q["split"], "id": q["id"],
                           "question": q["question"], "type": q.get("type"),
                           "store_strategy": store_name, "filter_applied": flt,
                           "hits": hits, "search_ms": ms, "evaluation": evaluate_query(q, hits)})
        print(f"search {name}: {round(time.time() - t0, 2)}s")

    with (RESULTS / f"traces_{args.split}.jsonl").open("w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    summ = summarize(traces)
    with (RESULTS / f"metrics_{args.split}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "split", "n", "hit@1", "hit@3", "page_hit@3",
                    "filter_ok/filter_n"])
        for r in summ.values():
            w.writerow([r["strategy"], r["split"], r["n"], f"{r['hit1']}/{r['n']}",
                        f"{r['hit3']}/{r['n']}", f"{r['page_hit3']}/{r['n']}",
                        f"{r['filter_ok']}/{r['filter_n']}" if r["filter_n"] else "N/A"])
    print(f"\n{'strategy':8} {'split':5} {'Hit@1':>7} {'Hit@3':>7} {'page@3':>7}  filter")
    for r in summ.values():
        flt = f"{r['filter_ok']}/{r['filter_n']}" if r["filter_n"] else "N/A"
        print(f"{r['strategy']:8} {r['split']:5} {r['hit1']:>3}/{r['n']:<3} "
              f"{r['hit3']:>3}/{r['n']:<3} {r['page_hit3']:>3}/{r['n']:<3}  {flt}")

    if args.split == "test":
        test_audit_sheets(traces, qby)
    print("\nđã lưu: results/traces_*.jsonl, metrics_*.csv, strategy_stats.json")


if __name__ == "__main__":
    main()