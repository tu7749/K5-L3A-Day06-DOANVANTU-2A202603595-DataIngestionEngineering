import os
from dotenv import load_dotenv
from src.sections import load_corpus
from src.chunking import by_paragraph
from src.embeddings import MyEmbedder
from src.store import PgVectorStore

load_dotenv()
emb = MyEmbedder()
print(emb.model_name, emb.dimensions, "max_tokens", emb.max_tokens)
B = [c for p in load_corpus() for c in by_paragraph(p, 1000)]
print("chunk B vượt giới hạn token:", emb.count_truncated([c.text for c in B]))
store = PgVectorStore(os.environ["DATABASE_URL"], emb.dimensions)
store.create_schema()
store.upsert("B", B, emb.embed_documents([c.text for c in B]))
store.upsert("B", B, emb.embed_documents([c.text for c in B]))   # nạp lại lần 2
print("số dòng sau nạp 2 lần:", store.count("B"), "(phải bằng", len(B), ")")
for h in store.search("B", emb.embed_query("What is transformational leadership?"), 3):
    print(round(h["score"], 3), h["metadata"]["section_id"], h["page"], h["text"][:80])