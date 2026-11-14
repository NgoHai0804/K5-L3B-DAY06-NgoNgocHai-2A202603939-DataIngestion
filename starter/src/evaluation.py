"""Evaluate retrieved evidence and preserve per-query traces."""
from typing import Any


def _is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    """Automated proxy: same source/page as gold AND contains the evidence quote.

    A human grader may confirm equivalent evidence; this proxy can be stricter.
    """
    same_source = (
        hit.get("source") == question["gold_source_id"]
        or hit.get("document_id") == question["gold_source_id"]
    )
    same_page = hit.get("page") == question["gold_page"]
    contains = question["evidence_quote"].strip().lower() in hit.get("text", "").strip().lower()
    return bool(same_source and same_page and contains)


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    top3 = hits[:3]
    return {
        "question_id": question["id"],
        "split": question["split"],
        "type": question.get("type"),
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "top3": [
            {
                "chunk_id": h["chunk_id"],
                "document_id": h.get("document_id"),
                "source": h.get("source"),
                "page": h.get("page"),
                "section": h.get("section"),
                "score": h.get("score"),
                "text": h.get("text", "")[:500],
            }
            for h in top3
        ],
        "hit_at_1": bool(top3) and _is_hit(question, top3[0]),
        "evidence_hit_at_3": any(_is_hit(question, h) for h in top3),
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for t in traces:
        key = f"{t['strategy']}/{t['split']}"
        b = out.setdefault(key, {"n": 0, "hit1": 0, "hit3": 0})
        b["n"] += 1
        b["hit1"] += int(t["hit_at_1"])
        b["hit3"] += int(t["evidence_hit_at_3"])
    for b in out.values():
        b["hit_at_1"] = f"{b['hit1']}/{b['n']}"
        b["evidence_hit_at_3"] = f"{b['hit3']}/{b['n']}"
        b["hit1_rate"] = round(b["hit1"] / b["n"], 3) if b["n"] else 0.0
        b["hit3_rate"] = round(b["hit3"] / b["n"], 3) if b["n"] else 0.0
    return out