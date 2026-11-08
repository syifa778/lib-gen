# Lib Gen

Lib Gen is a local document library with retrieval-augmented chat. Users ingest PDF resources, find the most related documents for a query, then chat only against a selected set of those documents. This repository contains both the **frontend** and the **backend**.

## Problem

Loose PDFs are hard to search and even harder to question as a group. Lib Gen turns uploaded files into a searchable library, then binds a **Project** to the documents the user actually wants to talk about.

## Product principles

- Answers come from selected documents, not from general model knowledge.
- Search is semantic: the user asks in natural language and gets the `k` most related documents.
- A Project is the unit of work. Chat never runs against the whole library unless the user selected the whole library.
- Frontend and backend stay separate. The UI does not embed, index, or call the LLM directly.

## Core concepts

| Concept | Meaning |
| --- | --- |
| **Resource / Document** | One ingested PDF, plus extracted text, metadata, and embeddings. |
| **Library** | All ingested documents available for search and selection. |
| **Query** | A natural-language search string. |
| **k** | User-chosen count of related documents to return. Default is small (for example 5); the UI must let the user change it. |
| **Selection** | The document set chosen for a Project. Built from search results, from a manual library pick, or both. |
| **Project** | Named workspace bound to a selection. Owns chat history and cites only those documents. |
| **Chat** | Multi-turn Q&A grounded in the Project’s selected documents. |

Hierarchy: **Library → Documents → Selection → Project → Chat**.

## Modalities (v1)

### 1. Ingest

- Accept PDF uploads from the frontend.
- Extract text, split into chunks, generate embeddings, store metadata and vectors.
- Persist original filename, page count if available, ingest status, and timestamps.
- Reject or surface a clear error for empty, corrupt, or unreadable PDFs.
- Reject a second upload of the same PDF **bytes** (content hash, not filename). Return `409` `{ "error": "duplicate_pdf", "message": "..." }` naming the existing file so the Library UI can notify the user.
- Show ingest progress: received → extracting → embedding → ready (or failed).

### 2. Related

- Accept a query string and `k`.
- Embed the query with the same model used at ingest.
- Return the `k` most related **documents** (not raw chunks as the primary result), with score and a short snippet.
- Let the user adjust `k` before searching and select any subset of the results.
- Also support listing/filtering the library so the user can pick documents without a semantic query.

### 3. Chat

- Chat is available only inside a Project that has at least one selected document.
- Selection sources: (a) documents picked from search results, (b) documents picked manually from the library.
- Retrieve relevant chunks **only from the Project selection**, then generate an answer with citations (document name and, when possible, page or chunk).
- If the selection does not contain enough evidence, the assistant must say so instead of inventing an answer.

## User flows

1. **Build a library:** upload one or more PDFs → wait until status is `ready` → documents appear in the library.
2. **Find related work:** enter a query, set `k`, inspect ranked results, tick the ones that matter.
3. **Open a Project:** create or update a Project from the current selection, optionally add more documents later.
4. **Ask the Project:** chat about the selection; each turn shows which documents were used.

## Functional requirements

- Upload PDF and list documents with status.
- Semantic search with configurable `k` (integer `k >= 1`, with a documented upper bound).
- Create, rename, open, and delete a Project.
- Attach/detach documents on a Project without losing chat history unless the user confirms a reset.
- Stream or incrementally display chat replies when the backend supports it.
- Surface backend, ingest, embedding, and LLM errors in the UI without crashing the page.

## Non-goals (v1)

- Formats other than PDF.
- Multi-user auth, sharing, or permissions.
- Editing PDF content.
- Unbounded general chat (no selected documents).
- Replacing the experimental scripts in the sibling `vdb-rag-llm` repo; Lib Gen is the product app. It may reuse the same local embedding/LLM/vector stack.

## Default architecture

Keep this unless `APP.md` is explicitly changed.

| Layer | Default |
| --- | --- |
| Frontend | React SPA (Vite) talking to the backend over HTTP/JSON. |
| Backend | Python FastAPI. Owns ingest, search, projects, and chat. |
| Metadata | SQLite at `backend/data/libgen.sqlite3` (documents, projects, messages). Override with `LIBGEN_DATA_DIR`. |
| Files | Original PDFs at `backend/data/uploads/{document_id}.pdf`. |
| Vectors | Qdrant (server), later. Chunk embeddings, filtered by Project document ids at chat time. |
| Embeddings + LLM | Later: local OpenAI-compatible `llama.cpp` servers in `model-embedding/` and `model-text/`. v1 chat/search are keyword-stub, not LLM-backed. |
| Tracing | Local Langfuse in `langfuse/` (Docker). Embedding/text calls through LiteLLM on ports 4000/4001 are traced; FastAPI is not wired to those servers yet. |

Logical API (names may match implementation, not the other way around):

- `POST /documents` — upload PDF; `409 duplicate_pdf` if the bytes already exist
- `GET /documents` — library list
- `GET /documents/{id}` — metadata + status
- `GET /documents/{id}/file` — original PDF (inline)
- `POST /search` — `{ query, k }` → ranked documents
- `POST /projects` — create from `{ name, document_ids }`
- `PATCH /projects/{id}` — rename or change selection
- `GET /projects` / `GET /projects/{id}`
- `POST /projects/{id}/chat` — `{ message }` → grounded answer + citations

## Data rules

- A document is not searchable or selectable for chat until ingest status is `ready`.
- Search scores are similarity scores; do not present them as certainty.
- Chat context is the Project selection, never “whatever the last search returned” unless those ids were saved on the Project.
- Persist PDFs on disk and metadata in SQLite. Do not keep the library only in process memory.
- Reject a new upload whose file bytes match an existing PDF. Tell the user the existing filename.
- Do not store secrets in the repo. Use `.env` locally.

## UX rules

- The three modalities are first-class: Ingest (Library), Related, Projects/Chat.
- `k` is visible and editable on the Related view. Leaving Related resets the query and ranked list (full library again). Long result/chip lists are swipeable. Long PDF filenames wrap inside catalog cards (then ellipsis); chips truncate with `…` and show the full name on hover.
- The create-project selection bar uses the same swipeable chip strip as Project chat (`‹` `›`, ellipsis, × to drop a file). Create Project sits beside the strip on wide viewports and below on narrow ones.
- Selected documents stay visible while chatting (swipeable chips). Enter sends a turn; Shift+Enter inserts a newline. Clicking a chip or citation opens the original PDF beside chat (`GET /documents/{id}/file`).
- Duplicate upload: show the API message that names the existing PDF.
- Empty states: no documents, no search hits, Project with no documents, ingest failed.

## Success criteria

- A user can upload PDFs, search with a chosen `k`, put some results (or manual picks) into a Project, and get answers that cite those files.
- Changing the Project selection changes what the chatbot is allowed to use.
- Failures in PDF parse, embedding, retrieval, or generation are diagnosable from logs and the UI.

## Open decisions

Record a choice here when it is made; do not silently fork the spec.

- Chunk size / overlap: not used yet (stub retrieval scores full document text).
- Hard max: `k` is 1–20 (default 5). PDF upload max is 25 MB.
- Chat streaming: v1 returns a full JSON message; the UI appends it when the request completes.
- v1 is single-user local-only.
- Persistence: SQLite + `backend/data/uploads` (not MongoDB for v1 — no extra daemon, files stay as files).
