from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .routers import documents, projects, search
from .store import store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.resume_pending()
    yield


app = FastAPI(title="Lib Gen", version="0.1.0", lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def http_error(_request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "message": str(detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "invalid_request", "message": str(exc.errors()[0]["msg"])},
    )


@app.get("/health")
def health():
    return {"status": "ok", "data_dir": str(store.data_dir)}


app.include_router(documents.router)
app.include_router(search.router)
app.include_router(projects.router)
