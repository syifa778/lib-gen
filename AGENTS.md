# Agent instructions — Lib Gen

This file tells agents how to **implement and update** Lib Gen. Product behavior lives in [`APP.md`](APP.md). Debugging lives in [`.cursor/rules/debugging.mdc`](.cursor/rules/debugging.mdc).

## Before writing code

1. Read `APP.md`. Treat it as the spec. Do not add modalities, file types, auth, or extra pages that are not in v1.
2. If the request conflicts with `APP.md`, update `APP.md` first (or ask), then implement.
3. Keep frontend and backend separated. The UI talks only to FastAPI (`/api`). FastAPI owns SQLite and the uploads folder. Do not have the browser open those, and do not wire the UI to Qdrant or `llama.cpp` when those land later.

## Repository layout (target)

```
lib-gen/
  APP.md             # product spec
  AGENTS.md          # how agents implement
  README.md          # how humans run/stop the app
  frontend/          # Vite + React SPA
  backend/           # FastAPI app
  langfuse/          # local Langfuse (Docker)
  langfuse-study/    # tiny FastAPI tracing demo (not the product)
  model-embedding/   # llama.cpp embedding server + LiteLLM
  model-text/        # llama.cpp chat server + LiteLLM
  .cursor/rules/     # Cursor rules (debugging, stack)
```

Do not dump experimental notebooks or sibling `vdb-rag-llm` scripts into this repo. Reuse the **stack pattern** (OpenAI-compatible local embeddings/LLM, Qdrant, metadata DB), not the one-off files.

## Local run

Frontend: `cd frontend && npm install && npm run dev` → http://localhost:5173  
Backend (needed for ingest/search/chat): `cd backend && .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`  
Vite proxies `/api` to that backend. Library data lives in `backend/data/` (SQLite + uploaded PDFs) and survives process restart. Retrieval is still a keyword stub, not the full embedding stack.

If port **8000** (API) or **5173** (Vite) is already bound (`WinError 10048`), stop the listener then restart. Commands live in [`README.md`](README.md) (`$port`, `netstat` / `taskkill`, or `Get-NetTCPConnection`). Killing the process does not delete `backend/data/`.

Optional local model stack (not used by FastAPI yet): Langfuse on **3000**, embedding llama.cpp on **8080** / traced LiteLLM **4000**, text llama.cpp on **30000** / traced LiteLLM **4001**. Text is **CPU** (`llama.cpp:server`) because Docker/WSL has no NVIDIA GPU; switch to `full-cuda` + `gpus: all` + `-ngl 99` if a GPU appears. Start `langfuse/` first so the `libgen` Docker network exists (`external: true` on the model stacks). Place the GGUF next to each compose file. Do not commit `.gguf` files. On Windows PowerShell use `curl.exe` for downloads and `Invoke-RestMethod` for JSON (plain `curl` is an alias).

## Implementation order

Ship in this order so each slice is demoable:

1. Backend health check + document upload/list (ingest pipeline can be stubbed, then filled in).
2. Ingest for real: PDF → text → chunks → embeddings → `ready`/`failed`.
3. `POST /search` with configurable `k`.
4. Projects: create, list, attach/detach document ids.
5. Chat scoped to the Project selection, with citations.
6. Frontend screens for the three modalities, wired to those APIs.

Do not start with chat UI if ingest and search are missing.

## Contracts

- Match the logical API in `APP.md`. If you rename a route, update `APP.md` in the same change.
- JSON errors: `{ "error": "<stable_code>", "message": "<human>" }` plus HTTP status.
- Duplicate PDF (same file bytes as an existing document): `409` with `error: "duplicate_pdf"` and a message that names the existing filename.
- Document statuses: `received` | `extracting` | `embedding` | `ready` | `failed`.
- Search returns documents, not a bag of orphan chunks. Chunks are an internal retrieval detail.
- Chat must filter retrieval by `project.document_ids`. If the list is empty, return a 4xx; do not search the whole library.

## When updating existing code

- Change one layer per bugfix when possible (UI **or** API **or** retrieval **or** prompt). See the debugging rule.
- Preserve Project selection semantics. A search result is not in the chat context until it is saved on the Project.
- Keep `k` user-controlled. Do not hardcode `k` in the client without an input.
- After a behavior change, add or adjust a backend test (or a minimal script) for the affected endpoint.
- **Update the related markdown in the same change** (do not leave docs for later):
  - [`APP.md`](APP.md) — product behavior, API contracts, data/UX rules.
  - [`README.md`](README.md) — how to run, stop, or operate the app (ports, data dir, limits).
  - [`AGENTS.md`](AGENTS.md) — implementation workflow, contracts, and local-run notes for agents.
- Do not commit `.env`, credentials, PDF corpora, or vector-store data dumps.

## Frontend rules

- Three primary views: Ingest / Library, Related, Project + Chat.
- Show ingest status and selection chips while chatting.
- Verify UI flows in the browser when tools are available: upload, search with a changed `k`, create a Project, send a chat turn.
- Prefer existing components and the existing API client. Do not add a second HTTP stack.

## Backend rules

- FastAPI routers by domain: `documents`, `search`, `projects`, `chat`.
- Embedding model for queries **must** be the same as ingest.
- Timeouts and failures from `llama.cpp` / Qdrant must become API errors, not hung requests with no body.
- Local config via environment variables: `LIBGEN_DATA_DIR`, `QDRANT_URL`, `LLAMA_BASE_URL`, model names.
- Do not commit `backend/data/` (SQLite DB or uploaded PDFs).

## Out of scope unless the user asks

- Non-PDF ingest, cloud LLM providers, multi-tenant auth, rewriting `vdb-rag-llm`.
- Drive-by refactors, new markdown docs, or extra Cursor rules.
