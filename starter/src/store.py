"""Lưu và tìm vector với PostgreSQL + pgvector (cosine, exact search)."""
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .models import Chunk

TABLE = "ingest_chunks"
FILTER_COLUMNS = {"chapter": "chapter", "section_id": "section_id",
                  "page": "page", "document_id": "document_id"}


def _vec(v: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions phải > 0")
        self.url, self.dim = database_url, dimensions

    def _conn(self):
        return psycopg.connect(self.url)

    def create_schema(self) -> None:
        with self._conn() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    strategy TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    chapter INTEGER,
                    section_id TEXT,
                    text TEXT NOT NULL,
                    metadata JSONB NOT NULL,
                    embedding vector({self.dim}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id))""")
            conn.execute(f"CREATE INDEX IF NOT EXISTS {TABLE}_filter_idx "
                         f"ON {TABLE} (strategy, chapter, section_id)")

    def upsert(self, strategy: str, chunks: list[Chunk],
               vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunk nhưng {len(vectors)} vector")
        for v in vectors:
            if len(v) != self.dim:
                raise ValueError(f"vector {len(v)} chiều, store cần {self.dim}")
        ids = [c.chunk_id for c in chunks]
        docs = sorted({c.document_id for c in chunks})
        rows = [(strategy, c.chunk_id, c.document_id, c.source, c.page,
                 c.metadata.get("chapter"), c.metadata.get("section_id"),
                 c.text, Jsonb(c.metadata), _vec(v))
                for c, v in zip(chunks, vectors)]
        with self._conn() as conn, conn.cursor() as cur:
            # xóa chunk cũ của cùng chiến lược + tài liệu không còn tồn tại
            cur.execute(f"DELETE FROM {TABLE} WHERE strategy=%s AND document_id = ANY(%s) "
                        f"AND chunk_id <> ALL(%s)", (strategy, docs, ids))
            cur.executemany(f"""
                INSERT INTO {TABLE} (strategy, chunk_id, document_id, source, page,
                    chapter, section_id, text, metadata, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
                ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                    document_id=EXCLUDED.document_id, source=EXCLUDED.source,
                    page=EXCLUDED.page, chapter=EXCLUDED.chapter,
                    section_id=EXCLUDED.section_id, text=EXCLUDED.text,
                    metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding""", rows)

    def count(self, strategy: str) -> int:
        with self._conn() as conn:
            return conn.execute(f"SELECT count(*) FROM {TABLE} WHERE strategy=%s",
                                (strategy,)).fetchone()[0]

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if len(query_vector) != self.dim:
            raise ValueError(f"query {len(query_vector)} chiều, store cần {self.dim}")
        where, params = ["strategy = %s"], [strategy]
        for k, val in (filters or {}).items():
            if k not in FILTER_COLUMNS:
                raise ValueError(f"filter không được phép: {k}")
            where.append(f"{FILTER_COLUMNS[k]} = %s")
            params.append(val)
        qv = _vec(query_vector)
        sql = (f"SELECT chunk_id, text, source, page, document_id, metadata, "
               f"embedding <=> %s::vector AS distance FROM {TABLE} "
               f"WHERE {' AND '.join(where)} ORDER BY distance, chunk_id LIMIT %s")
        with self._conn() as conn:
            rows = conn.execute(sql, [qv, *params, top_k]).fetchall()
        return [{"chunk_id": r[0], "text": r[1], "source": r[2], "page": r[3],
                 "document_id": r[4], "metadata": r[5],
                 "distance": float(r[6]), "score": 1.0 - float(r[6])}   # score = cosine similarity
                for r in rows]