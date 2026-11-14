"""Store and search vectors using PostgreSQL + pgvector."""
import json
from typing import Any

import psycopg

from .models import Chunk


def _vec_literal(vec: list[float]) -> str:
    """list[float] -> pgvector literal '[0.1,0.2,...]' for cast ::vector."""
    return "[" + ",".join(format(float(x), ".10g") for x in vec) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        self.database_url = database_url
        self.dimensions = dimensions

    def _conn(self):
        return psycopg.connect(self.database_url)

    def create_schema(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    strategy TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    page INT NOT NULL,
                    section TEXT,
                    year INT,
                    text TEXT NOT NULL,
                    metadata JSONB DEFAULT '{{}}'::jsonb,
                    embedding vector({self.dimensions}) NOT NULL
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_strategy ON chunks (strategy);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks (document_id);")
            conn.commit()

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        assert len(chunks) == len(vectors), "số chunk và số vector phải khớp"
        for v in vectors:
            assert len(v) == self.dimensions, f"dimension mismatch: {len(v)} != {self.dimensions}"
        doc_ids = sorted({c.document_id for c in chunks})
        with self._conn() as conn, conn.cursor() as cur:
            # remove obsolete chunks of this (strategy, document) before re-inserting
            cur.execute(
                "DELETE FROM chunks WHERE strategy = %s AND document_id = ANY(%s);",
                (strategy, doc_ids),
            )
            for chunk, vec in zip(chunks, vectors):
                cur.execute(
                    """INSERT INTO chunks
                       (id, strategy, document_id, source, page, section, year, text, metadata, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
                       ON CONFLICT (id) DO UPDATE SET
                         text = EXCLUDED.text, embedding = EXCLUDED.embedding;""",
                    (
                        f"{strategy}:{chunk.chunk_id}", strategy, chunk.document_id, chunk.source,
                        chunk.page, chunk.metadata.get("section"),
                        chunk.metadata.get("year"), chunk.text,
                        json.dumps(chunk.metadata), _vec_literal(vec),
                    ),
                )
            conn.commit()

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        where, params = ["strategy = %s"], [strategy]
        allowed = {"section", "year", "document_id", "source"}  # whitelist
        for key, value in (filters or {}).items():
            if key not in allowed:
                raise ValueError(f"filter không được phép: {key}")
            where.append(f"{key} = %s")
            params.append(value)
        where_sql = " AND ".join(where)
        sql = f"""
            SELECT id, document_id, source, page, section, year, text,
                   1 - (embedding <=> %s::vector) AS score
            FROM chunks
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, [_vec_literal(query_vector), *params, _vec_literal(query_vector), top_k])
            rows = cur.fetchall()
        return [
            {"chunk_id": r[0], "document_id": r[1], "source": r[2], "page": r[3],
             "section": r[4], "year": r[5], "text": r[6], "score": r[7]}
            for r in rows
        ]

    def count_by_strategy(self) -> dict[str, int]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT strategy, COUNT(*) FROM chunks GROUP BY strategy ORDER BY strategy;")
            return {row[0]: row[1] for row in cur.fetchall()}