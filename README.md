# Lib Gen

Local PDF library with retrieval-backed chat. Ingest files, find the `k` most related documents, then ask questions only against a saved **Project** (the selected set).

Product spec: [`APP.md`](APP.md). Agent/implementation notes: [`AGENTS.md`](AGENTS.md). Behavior, run/stop, and agent-workflow changes belong in those files in the same change as the code.

## What it does

1. **Library** — upload PDFs; ingest status goes `received` → `extracting` → `embedding` → `ready` (or `failed`).
2. **Related** — natural-language query plus a user-chosen `k` (1–20, default 5), or browse the full PDF list. Tick items to build a selection.
3. **Projects** — a Project is that saved selection plus chat history. The assistant may use only those documents.

Chat is not general Q&A. If the selection does not support an answer, the app should say so.

## Stack (v1)

| Layer | Choice |
| --- | --- |
| Frontend | React + Vite (`frontend/`), proxied `/api` → backend |
| Backend | FastAPI (`backend/`) |
| Metadata | SQLite — `backend/data/libgen.sqlite3` |
| Files | Original PDFs — `backend/data/uploads/{document_id}.pdf` |
| Retrieval | Keyword stub over extracted text (embeddings / Qdrant / `llama.cpp` come later) |
| Local models | `model-embedding/` and `model-text/` llama.cpp servers (optional; not wired to FastAPI yet) |
| Tracing | Local Langfuse at `langfuse/` — LiteLLM proxies send traces from the model servers |

Data in `backend/data/` survives process restart. Override the folder with `LIBGEN_DATA_DIR`. Do not commit that directory.

## Run locally

Needs two terminals. Python 3 and Node.js.

**Backend**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Frontend**

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The UI talks only to `/api`; it does not open SQLite or the uploads folder itself.

## Stop a process on a port

If you see `WinError 10048` / “only one usage of each socket address”, something is already bound to that port. Backend is **8000**; Vite is **5173**. Replace `$port` with the one you need.

```powershell
$port = 8000
netstat -ano | findstr ":$port"
taskkill /PID <pid> /F
```

Use the PID in the last column of the `LISTENING` row. To kill whatever is listening without copying the PID:

```powershell
$port = 8000
Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

Then start uvicorn or `npm run dev` again. Data in `backend/data/` is not deleted.

## Local models and Langfuse (optional)

Sidecars. FastAPI does not call them yet. **Langfuse first** — it creates Docker network `libgen`. The model stacks mark that network `external: true`.

Per-folder steps (PowerShell, verified on this repo): [`langfuse/README.md`](langfuse/README.md), [`model-embedding/README.md`](model-embedding/README.md), [`model-text/README.md`](model-text/README.md).

GGUF next to each compose file (not a `models/` subfolder; do not commit `*.gguf`):

| Save as | Download |
| --- | --- |
| `model-embedding/Qwen3-Embedding-0.6B-Q8_0.gguf` | [Qwen](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF) (~639 MB) |
| `model-text/Qwen3.5-4B-Q4_K_M.gguf` | [Unsloth](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF) (~2.7 GB) |

From the **lib-gen repo root**:

```powershell
cd langfuse
docker compose up -d
Invoke-RestMethod http://127.0.0.1:3000/api/public/health

cd ..\model-embedding
curl.exe -L -o Qwen3-Embedding-0.6B-Q8_0.gguf `
  https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/main/Qwen3-Embedding-0.6B-Q8_0.gguf
docker compose up -d

cd ..\model-text
curl.exe -L -o Qwen3.5-4B-Q4_K_M.gguf `
  https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf
docker compose up -d
```

On Windows PowerShell, `curl` is **not** curl — use `curl.exe` for downloads and `Invoke-RestMethod` for JSON APIs (see the folder READMEs). Text llama.cpp is **CPU** (no NVIDIA GPU in Docker/WSL).

Wait until each llama `/health` is `ok` before the smoke tests:

```powershell
(Invoke-RestMethod http://127.0.0.1:8080/health).status
(Invoke-RestMethod http://127.0.0.1:30000/health).status
```

```powershell
$emb = Invoke-RestMethod http://127.0.0.1:4000/v1/embeddings -Method Post -ContentType "application/json" -Body '{"model":"qwen3-embedding","input":"hello from lib-gen"}'
"dims=$($emb.data[0].embedding.Count)"

$body = '{"model":"qwen35-4b","messages":[{"role":"user","content":"Say hi in one sentence."}],"max_tokens":16}'
$chat = Invoke-RestMethod http://127.0.0.1:4001/v1/chat/completions -Method Post -ContentType "application/json" -Body $body
"finish=$($chat.choices[0].finish_reason) tokens=$($chat.usage.total_tokens)"
```

| Service | URL |
| --- | --- |
| Langfuse UI | http://127.0.0.1:3000 — `local@libgen.local` / `LibgenLocal1!` |
| Embedding llama.cpp | http://127.0.0.1:8080 (no traces) |
| Embedding LiteLLM | http://127.0.0.1:4000 (traced) |
| Text llama.cpp | http://127.0.0.1:30000 (no traces) |
| Text LiteLLM | http://127.0.0.1:4001 (traced) |

Keys: `pk-lf-libgen-local` / `sk-lf-libgen-local`. Stop with `docker compose down` in each folder.

## Limits

- PDF only, 25 MB per file
- Same PDF bytes as an existing file are rejected (`409`); the UI names the original filename
- Single-user, local
- No login or sharing
- Search/chat are not yet embedding- or LLM-backed

## Layout

```
lib-gen/
  APP.md
  AGENTS.md
  README.md
  frontend/          Vite + React
  backend/           FastAPI, SQLite, uploads
  langfuse/          local Langfuse (Docker)
  langfuse-study/    optional FastAPI tracing demo (not wired to the product)
  model-embedding/   llama.cpp embeddings + LiteLLM
  model-text/        llama.cpp chat + LiteLLM
  .cursor/rules/
```
