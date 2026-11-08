from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services import search_documents

router = APIRouter()

K_MIN = 1
K_MAX = 20


class SearchBody(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=K_MIN, le=K_MAX)


@router.post("/search")
def search(body: SearchBody):
    query = body.query.strip()
    if not query:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_query", "message": "Query must not be empty."},
        )
    return {"documents": search_documents(query, body.k)}
