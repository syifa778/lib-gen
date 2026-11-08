from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from uuid import uuid4

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .store import public_document, store


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid4())


def extract_pdf(data: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(BytesIO(data))
    except PdfReadError as exc:
        raise ValueError("The PDF could not be read.") from exc

    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError("The PDF has no extractable text.")
    return text, len(reader.pages)


def process_document(doc_id: str, data: bytes | None = None) -> None:
    stamp = now_iso()
    store.update_document(doc_id, status="extracting", updated_at=stamp)
    payload = data if data is not None else store.read_pdf(doc_id)
    if payload is None:
        store.update_document(
            doc_id,
            status="failed",
            error="The original PDF is missing from disk.",
            updated_at=now_iso(),
        )
        return
    try:
        text, page_count = extract_pdf(payload)
        store.update_document(
            doc_id,
            status="embedding",
            page_count=page_count,
            text=text,
            updated_at=now_iso(),
        )
        store.update_document(
            doc_id,
            status="ready",
            updated_at=now_iso(),
            error=None,
        )
    except Exception as exc:
        store.update_document(
            doc_id,
            status="failed",
            error=str(exc),
            updated_at=now_iso(),
        )


def snippet_for(text: str, query: str, size: int = 220) -> str:
    lowered = text.lower()
    terms = [t for t in query.lower().split() if t]
    idx = -1
    for term in terms:
        idx = lowered.find(term)
        if idx >= 0:
            break
    if idx < 0:
        idx = 0
    start = max(0, idx - 40)
    end = min(len(text), start + size)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def score_document(query: str, text: str) -> float:
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return 0.0
    blob = text.lower()
    hits = sum(blob.count(term) for term in terms)
    return hits / (len(terms) + len(blob.split()) / 400)


def search_documents(query: str, k: int) -> list[dict[str, Any]]:
    ranked = []
    for doc in store.list_documents():
        full = store.get_document(doc["id"])
        if not full or full["status"] != "ready" or not full.get("text"):
            continue
        score = score_document(query, full["text"])
        if score <= 0:
            continue
        item = public_document(full)
        item["score"] = round(score, 4)
        item["snippet"] = snippet_for(full["text"], query)
        ranked.append(item)
    ranked.sort(key=lambda d: d["score"], reverse=True)
    return ranked[:k]


def passages_from_selection(document_ids: list[str], question: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for doc_id in document_ids:
        full = store.get_document(doc_id)
        if not full or full["status"] != "ready" or not full.get("text"):
            continue
        score = score_document(question, full["text"])
        if score <= 0:
            continue
        hits.append(
            {
                "document_id": full["id"],
                "document_name": full["filename"],
                "page": None,
                "snippet": snippet_for(full["text"], question, 320),
                "score": score,
            }
        )
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:3]


def answer_from_passages(question: str, passages: list[dict[str, Any]]) -> str:
    if not passages:
        return (
            "The selected documents do not contain enough evidence to answer that. "
            "Try a more specific question, or attach other files to this Project."
        )
    names = ", ".join(p["document_name"] for p in passages)
    clips = " ".join(p["snippet"] for p in passages)
    return (
        f"From {names}: {clips} "
        "(Stub retrieval only — grounded in Project documents, not general knowledge.)"
    )
