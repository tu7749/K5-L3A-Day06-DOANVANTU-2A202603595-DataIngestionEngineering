"""Đánh giá evidence đã truy xuất và giữ trace từng câu."""
import re
from collections import defaultdict
from typing import Any


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def gold_list(q: dict[str, Any]) -> list[dict[str, Any]]:
    """Gold chính + các nguồn thay thế hợp lệ (alt_gold)."""
    golds = [{"source_id": q["gold_source_id"], "page": q["gold_page"],
              "evidence_quote": q["evidence_quote"]}]
    for a in q.get("alt_gold") or []:
        golds.append({"source_id": (a.get("source_id") or a.get("gold_source_id") or q["gold_source_id"]),
                      "page": a.get("page", a.get("gold_page")), "evidence_quote": a["evidence_quote"]})
    return golds


def _meets_filter(hit: dict[str, Any], flt: dict[str, Any]) -> bool:
    for k, v in flt.items():
        if k == "page":
            val = hit["page"]
        elif k == "document_id":
            val = hit["document_id"]
        else:
            val = (hit.get("metadata") or {}).get(k)
        if val != v:
            return False
    return True


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Hit = đúng nguồn/trang gold VÀ chunk chứa nguyên văn evidence (sau chuẩn hóa
    khoảng trắng). page_hit chỉ là chỉ số phụ để chẩn đoán. Không suy ra nhãn
    coherence/grounding."""
    golds = gold_list(question)
    flt = question.get("filter")
    details = []
    for rank, h in enumerate(hits, 1):
        text = norm(h["text"])
        same_page = [g for g in golds
                     if h["document_id"] == g["source_id"] and h["page"] == g["page"]]
        details.append({
            "rank": rank, "chunk_id": h["chunk_id"], "page": h["page"],
            "page_hit": bool(same_page),
            "evidence_hit": any(norm(g["evidence_quote"]) in text for g in same_page),
            "filter_ok": _meets_filter(h, flt) if flt else None,
        })
    ev = [d["evidence_hit"] for d in details]
    pg = [d["page_hit"] for d in details]
    return {
        "id": question["id"], "split": question["split"], "type": question.get("type"),
        "hit_at_1": bool(ev[:1] and ev[0]),
        "hit_at_3": any(ev[:3]),
        "page_hit_at_1": bool(pg[:1] and pg[0]),
        "page_hit_at_3": any(pg[:3]),
        "first_evidence_rank": next((d["rank"] for d in details if d["evidence_hit"]), None),
        # đúng trang nhưng không chunk nào chứa đủ evidence: kiểm tra xem có bị cắt đôi không
        "page_hit_without_evidence": any(pg[:3]) and not any(ev[:3]),
        "filter_required": bool(flt),
        "filter_compliant": all(d["filter_ok"] for d in details) if flt else None,
        "hits_detail": details,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    groups = defaultdict(list)
    for t in traces:
        groups[(t["strategy"], t["split"])].append(t["evaluation"])
    out = {}
    for (s, sp), evs in sorted(groups.items()):
        ft = [e for e in evs if e["filter_required"]]
        out[f"{s}|{sp}"] = {
            "strategy": s, "split": sp, "n": len(evs),
            "hit1": sum(e["hit_at_1"] for e in evs),
            "hit3": sum(e["hit_at_3"] for e in evs),
            "page_hit3": sum(e["page_hit_at_3"] for e in evs),
            "filter_n": len(ft),
            "filter_ok": sum(bool(e["filter_compliant"]) for e in ft),
        }
    return out