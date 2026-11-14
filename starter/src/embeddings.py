"""Real embedding provider: OpenRouter (OpenAI-compatible) via qwen3-embedding-8b."""
import os
import time
from typing import Protocol

from openai import OpenAI


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """OpenRouter embeddings adapter. No mock/random fallback."""

    def __init__(self, model_name: str, batch_size: int = 64) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY missing: set it in starter/.env")
        self._client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        # Probe once to learn the real vector size (must match vector(N) in DB).
        probe = self._embed_raw(["dimension probe"])
        self.dimensions = len(probe[0])
        print(f"[embed] {self.model_name} dimensions={self.dimensions}")

    def _embed_raw(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(5):
            try:
                resp = self._client.embeddings.create(model=self.model_name, input=texts)
                data = sorted(resp.data, key=lambda d: getattr(d, "index", 0))
                return [d.embedding for d in data]
            except Exception as exc:  # retry on transient provider/network errors
                if attempt == 4:
                    raise
                print(f"[embed] retry {attempt + 1}: {type(exc).__name__}: {str(exc)[:120]}")
                time.sleep(2 * (attempt + 1))
        raise RuntimeError("unreachable")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(self._embed_raw(texts[i:i + self.batch_size]))
        return out

    def embed_query(self, question: str) -> list[float]:
        return self._embed_raw([question])[0]