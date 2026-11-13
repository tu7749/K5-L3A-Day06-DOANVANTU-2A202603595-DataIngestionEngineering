"""Local embedder: sentence-transformers. Không fallback sang vector giả."""
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    # bge: query cần prefix này, document thì không
    QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)      # lần đầu sẽ tải model
        self.dimensions = self.model.get_sentence_embedding_dimension()
        self.max_tokens = self.model.max_seq_length

    def count_truncated(self, texts: list[str]) -> int:
        """Số text dài hơn giới hạn token (sẽ bị cắt âm thầm nếu không kiểm tra)."""
        tok = self.model.tokenizer
        return sum(len(tok.encode(t, add_special_tokens=True)) > self.max_tokens for t in texts)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, batch_size=32, normalize_embeddings=True,
                                 show_progress_bar=False).tolist()

    def embed_query(self, question: str) -> list[float]:
        return self.model.encode([self.QUERY_PREFIX + question],
                                 normalize_embeddings=True)[0].tolist()