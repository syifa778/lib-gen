# Langfuse (local)

Self-hosted Langfuse for tracing the local llama.cpp servers. Start this stack **before** `model-embedding/` or `model-text/` so the Docker network `libgen` exists. Those stacks declare `libgen` as **external**; compose fails with “network libgen not found” if you skip this.

The Lib Gen FastAPI app does not talk to Langfuse yet. You browse **only** [http://127.0.0.1:3000](http://127.0.0.1:3000). MinIO, Postgres, ClickHouse, and Redis are supporting stores.

## What the six containers are

```
LiteLLM (embed :4000 / text :4001)
        │  traces over Docker network `libgen`
        ▼
 langfuse-web  :3000   UI + API     ← you open this
        │
        ├── postgres     users, orgs, projects, API keys
        ├── clickhouse   traces / spans / scores
        ├── redis        background job queue
        └── minio        S3 blobs (events + media)
               ▲
 langfuse-worker         drains Redis, writes ClickHouse, reads/writes MinIO
```

| Service | Role | Open it? |
| --- | --- | --- |
| **langfuse-web** | UI + API. `HOSTNAME=0.0.0.0` so Docker Desktop can reach it. | Yes — http://127.0.0.1:3000 |
| **langfuse-worker** | Background ingest / ClickHouse writes. | No |
| **postgres** | Login, org `libgen`, project `lib-gen`, API keys. | No |
| **clickhouse** | Trace rows. | Optional: http://127.0.0.1:8123/ping |
| **redis** | Job queue. Password `myredissecret`. | No |
| **minio** | Local S3. Bucket `langfuse`. | Optional console: http://127.0.0.1:9091 (`minio` / `miniosecret`) |

## Run

From the **lib-gen repo root**:

```powershell
cd langfuse
docker compose up -d
docker compose ps
```

Wait until `langfuse-web` shows `healthy` (first pull can take several minutes). Confirm from PowerShell (do **not** use `curl` — that is `Invoke-WebRequest`):

```powershell
Invoke-RestMethod http://127.0.0.1:3000/api/public/health
# expect: status = OK
```

Then open [http://127.0.0.1:3000](http://127.0.0.1:3000).

| | |
| --- | --- |
| Email | `local@libgen.local` |
| Password | `LibgenLocal1!` |
| Public key | `pk-lf-libgen-local` |
| Secret key | `sk-lf-libgen-local` |

Keys are created on first boot (`LANGFUSE_INIT_*`). LiteLLM in the model folders already uses them.

## Ports

| Port | Service |
| --- | --- |
| `127.0.0.1:3000` | Langfuse UI / API |
| `127.0.0.1:9090` | MinIO S3 API |
| `127.0.0.1:9091` | MinIO console |
| `127.0.0.1:8123` | ClickHouse HTTP ping |

Postgres and Redis are not published on the host. Values here are local-only.

## Stop

```powershell
cd langfuse
docker compose down
```

Named volumes keep traces and login. `docker compose down -v` wipes them. Neither touches `backend/data/`.

## Network

Creates Docker network `libgen`. Embedding/text LiteLLM join it and post to `http://langfuse-web:3000`.
