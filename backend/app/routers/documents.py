from __future__ import annotations

import threading

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..services import new_id, now_iso, process_document
from ..store import pdf_content_hash, public_document, store

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.get("/documents")
def list_documents():
    return {"documents": store.list_documents()}


@router.get("/documents/{doc_id}/file")
def get_document_file(doc_id: str):
    doc = store.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Document not found."},
        )
    path = store.pdf_path(doc_id)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail={"error": "file_missing", "message": "The original PDF is not on disk."},
        )
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=doc["filename"],
        content_disposition_type="inline",
    )


@router.get("/documents/{doc_id}")
def get_document(doc_id: str):
    doc = store.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Document not found."},
        )
    return public_document(doc)


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_type", "message": "Only PDF files are accepted."},
        )
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_file", "message": "The PDF is empty."},
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail={"error": "too_large", "message": "Each PDF must be 25 MB or smaller."},
        )

    digest = pdf_content_hash(data)
    existing = store.find_by_content_hash(digest)
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "duplicate_pdf",
                "message": (
                    f'A PDF with the same content is already uploaded as "{existing["filename"]}".'
                ),
            },
        )

    stamp = now_iso()
    doc_id = new_id()
    store.save_pdf(doc_id, data)
    doc = {
        "id": doc_id,
        "filename": filename,
        "page_count": None,
        "status": "received",
        "error": None,
        "text": "",
        "content_hash": digest,
        "created_at": stamp,
        "updated_at": stamp,
    }
    store.put_document(doc)
    threading.Thread(target=process_document, args=(doc_id, data), daemon=True).start()
    return public_document(doc)
