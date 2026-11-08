from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services import answer_from_passages, new_id, now_iso, passages_from_selection
from ..store import store

router = APIRouter()


class CreateProjectBody(BaseModel):
    name: str = Field(min_length=1)
    document_ids: list[str]


class PatchProjectBody(BaseModel):
    name: str | None = None
    document_ids: list[str] | None = None


class ChatBody(BaseModel):
    message: str = Field(min_length=1)


def _project_or_404(project_id: str):
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Project not found."},
        )
    return project


def _validate_ids(document_ids: list[str]) -> list[str]:
    unique = []
    for doc_id in document_ids:
        doc = store.get_document(doc_id)
        if not doc:
            raise HTTPException(
                status_code=400,
                detail={"error": "unknown_document", "message": f"Unknown document: {doc_id}"},
            )
        if doc["status"] != "ready":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "not_ready",
                    "message": f"{doc['filename']} is not ready for a Project.",
                },
            )
        if doc_id not in unique:
            unique.append(doc_id)
    return unique


@router.get("/projects")
def list_projects():
    return {"projects": store.list_projects()}


@router.post("/projects", status_code=201)
def create_project(body: CreateProjectBody):
    document_ids = _validate_ids(body.document_ids)
    if not document_ids:
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_selection", "message": "A Project needs at least one ready document."},
        )
    stamp = now_iso()
    project = {
        "id": new_id(),
        "name": body.name.strip() or "Untitled project",
        "document_ids": document_ids,
        "messages": [],
        "created_at": stamp,
        "updated_at": stamp,
    }
    store.put_project(project)
    return project


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    return _project_or_404(project_id)


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, body: PatchProjectBody):
    _project_or_404(project_id)
    fields = {"updated_at": now_iso()}
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_name", "message": "Project name must not be empty."},
            )
        fields["name"] = name
    if body.document_ids is not None:
        fields["document_ids"] = _validate_ids(body.document_ids)
    updated = store.update_project(project_id, **fields)
    return updated


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    _project_or_404(project_id)
    store.delete_project(project_id)
    return {"ok": True}


@router.post("/projects/{project_id}/chat")
def chat(project_id: str, body: ChatBody):
    project = _project_or_404(project_id)
    document_ids = list(project.get("document_ids") or [])
    if not document_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "empty_selection",
                "message": "Chat requires at least one document on this Project.",
            },
        )
    question = body.message.strip()
    passages = passages_from_selection(document_ids, question)
    citations = [
        {
            "document_id": p["document_id"],
            "document_name": p["document_name"],
            "page": p["page"],
            "snippet": p["snippet"],
        }
        for p in passages
    ]
    user_msg = {
        "id": new_id(),
        "role": "user",
        "content": question,
        "citations": [],
        "created_at": now_iso(),
    }
    assistant_msg = {
        "id": new_id(),
        "role": "assistant",
        "content": answer_from_passages(question, passages),
        "citations": citations,
        "created_at": now_iso(),
    }
    store.append_messages(project_id, [user_msg, assistant_msg])
    store.update_project(project_id, updated_at=now_iso())
    return assistant_msg
