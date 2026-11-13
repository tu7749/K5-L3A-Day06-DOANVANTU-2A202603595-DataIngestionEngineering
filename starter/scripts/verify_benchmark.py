import json, re
from pathlib import Path
from src.sections import load_corpus

def norm(s): return re.sub(r"\s+", " ", s).strip()

pages = {}
for p in load_corpus():
    pages.setdefault(p.page, []).append(norm(p.text))
qs = json.loads(Path("../benchmark/questions.json").read_text(encoding="utf-8"))
bad = 0
for q in qs:
    ok = any(norm(q["evidence_quote"]) in t for t in pages.get(q["gold_page"], []))
    if not ok:
        bad += 1
    print(q["id"], q["split"], "OK" if ok else "EVIDENCE KHÔNG KHỚP")
sp = {s: sum(q["split"] == s for q in qs) for s in ("dev", "test")}
nf = [q["id"] for q in qs if q.get("filter")]
print("tổng", len(qs), sp, "| câu filter:", nf, "| lỗi:", bad)