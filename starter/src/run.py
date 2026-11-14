"""Pipeline entry point: Document -> Normalize -> Chunk -> Embed -> Store -> Retrieve -> Evaluate."""
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf
from .store import PgVectorStore

ROOT = Path(__file__).resolve().parents[1]   # starter/
REPO = ROOT.parent                           # repo root
DATA = REPO / "data"
RESULTS = REPO / "results"

load_dotenv(ROOT / ".env")


def _load_pages(manifest: dict) -> list:
    pages = []
    for s in manifest["sources"]:
        path = REPO / s["source_path_or_url"]
        doc_meta = {
            "year": s.get("year"),
            "document_type": s.get("document_type"),
            "language": "en",
            "title": s.get("title"),
        }
        pgs = load_pdf(
            path, s["source_id"], s["source_id"],
            doc_metadata=doc_meta, section_map=s.get("sections"),
        )
        keep = {int(x) for x in s.get("content_page_ids", [])}
        pages.extend([p for p in pgs if p.page in keep])
    return pages


def _strategies(pages):
    # A: fixed-size, no filter | B: paragraph, no filter | C: paragraph + metadata filter
    return {
        "A": [c for p in pages for c in fixed_size(p, size=500, overlap=50)],
        "B": [c for p in pages for c in by_paragraph(p, max_size=800)],
        "C": [c for p in pages for c in by_paragraph(p, max_size=800)],
    }


def main() -> None:
    manifest = json.loads((DATA / "manifest.json").read_text("utf-8"))
    questions = json.loads((REPO / "benchmark" / "questions.json").read_text("utf-8"))["questions"]

    pages = _load_pages(manifest)
    content = [p for p in pages if len(p.text) >= 200]
    assert len(content) >= 30, f"Chỉ có {len(content)} trang nội dung (<30)"
    print(f"[corpus] pages={len(pages)} content_pages={len(content)} questions={len(questions)}")

    embedder = MyEmbedder(os.environ.get("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b"))
    store = PgVectorStore(os.environ["DATABASE_URL"], embedder.dimensions)
    store.create_schema()

    traces: list[dict] = []
    ingest_log: dict = {}
    for name, chunks in _strategies(pages).items():
        t0 = time.time()
        vectors = embedder.embed_documents([c.text for c in chunks])
        store.upsert(name, chunks, vectors)
        elapsed = time.time() - t0
        lengths = [len(c.text) for c in chunks]
        ingest_log[name] = {
            "chunks": len(chunks),
            "chars": sum(lengths),
            "length_min": min(lengths) if lengths else 0,
            "length_avg": round(sum(lengths) / len(lengths), 1) if lengths else 0,
            "length_max": max(lengths) if lengths else 0,
            "ingest_seconds": round(elapsed, 1),
        }
        print(f"[{name}] chunks={len(chunks)} ingest={elapsed:.1f}s")

        for q in questions:
            qv = embedder.embed_query(q["question"])
            filters = q.get("filter") if name == "C" else None
            hits = store.search(name, qv, top_k=3, filters=filters)
            tr = evaluate_query(q, hits)
            tr["strategy"] = name
            tr["filter_applied"] = filters
            traces.append(tr)

    stats = summarize(traces)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "traces.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2), "utf-8")
    (RESULTS / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), "utf-8")
    ingest_log["_meta"] = {
        "model": embedder.model_name,
        "dimensions": embedder.dimensions,
        "store": "pgvector/cosine",
        "db_chunk_counts": store.count_by_strategy(),
    }
    ingest_log["corpus"] = {
        "pages": len(pages),
        "content_pages": len(content),
        "empty_pages": sorted(f"{p.document_id}:p{p.page}" for p in pages if p.metadata.get("is_empty")),
        "errors": [],
    }
    (RESULTS / "ingest_log.json").write_text(json.dumps(ingest_log, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()