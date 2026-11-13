import json
import os

from dotenv import load_dotenv

from src.embeddings import MyEmbedder
from src.evaluation import gold_list, norm
from src.sections import ROOT
from src.store import PgVectorStore

load_dotenv()
emb = MyEmbedder()
store = PgVectorStore(os.environ["DATABASE_URL"], emb.dimensions)
qs = [q for q in json.loads((ROOT / "benchmark" / "questions.json").read_text(encoding="utf-8"))
      if q["split"] == "dev"]

for q in qs:
    qv = emb.embed_query(q["question"])
    golds = gold_list(q)
    for s in ("A", "B", "C"):
        flt = q.get("filter") if s == "C" else None
        if s == "C" and not flt:
            continue
        hits = store.search("B" if s == "C" else s, qv, 200, flt)
        r_ev = next((i for i, h in enumerate(hits, 1)
                     if any(h["page"] == g["page"] and norm(g["evidence_quote"]) in norm(h["text"])
                            for g in golds)), None)
        r_pg = next((i for i, h in enumerate(hits, 1)
                     if any(h["page"] == g["page"] for g in golds)), None)
        if r_ev is None or r_ev > 3:
            print(f"{q['id']} {s}: hạng chunk chứa đủ evidence = {r_ev} | hạng chunk đúng trang đầu tiên = {r_pg}")