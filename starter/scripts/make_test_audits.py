import csv
import json

from src.sections import ROOT

RES = ROOT / "results"
qs = {q["id"]: q for q in json.loads(
    (ROOT / "benchmark" / "questions.json").read_text(encoding="utf-8"))}
traces = [json.loads(l) for l in
          (RES / "traces_test.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def write_if_missing(path, header, rows):
    if path.exists():
        print("giữ nguyên", path.name, "(đã tồn tại)")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("đã tạo", path.name, len(rows), "dòng")


meta_rows, ground_rows = [], []
for t in traces:
    q = qs[t["id"]]
    for rank, h in enumerate(t["hits"], 1):
        m = h["metadata"]
        meta_rows.append([t["strategy"], t["id"], rank, h["chunk_id"], h["source"],
                          h["page"], m.get("printed_page"), m.get("chapter"),
                          m.get("section_id"), "", "", "", ""])
    top3 = "\n\n".join(f"[{i}] (p{h['page']}) {h['text']}"
                       for i, h in enumerate(t["hits"], 1))
    ground_rows.append([t["strategy"], t["id"], q["question"], q["expected_answer"],
                        q["evidence_quote"], top3, "", ""])

write_if_missing(RES / "metadata_audit.csv",
                 ["strategy", "qid", "rank", "chunk_id", "source", "page", "printed_page",
                  "chapter", "section_id", "source_ok", "page_ok", "field_ok", "note"],
                 meta_rows)
write_if_missing(RES / "grounding_audit.csv",
                 ["strategy", "qid", "question", "expected_answer", "evidence_quote",
                  "top3", "label_0_2", "reason"], ground_rows)