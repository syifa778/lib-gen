# Embedding server

CPU `llama.cpp` for **Qwen3 Embedding 0.6B**, plus LiteLLM on **4000** that forwards `/v1/embeddings` and traces to local Langfuse.

FastAPI does not call this yet.

On Windows PowerShell, `curl` is an alias for `Invoke-WebRequest`. Use **`curl.exe`** only for downloads, and **`Invoke-RestMethod`** for the smoke tests below.

## 1. Langfuse first

From the **lib-gen repo root**:

```powershell
cd langfuse
docker compose up -d
Invoke-RestMethod http://127.0.0.1:3000/api/public/health
# expect: status = OK
```

If compose later says `network libgen not found`, this step was skipped. `libgen` is an external network created by the Langfuse stack.

## 2. Download the GGUF

Save **in this folder**, next to `docker-compose.yaml` (compose mounts `.` → `/models`). Not a `models/` subfolder.

**Path:** `lib-gen/model-embedding/Qwen3-Embedding-0.6B-Q8_0.gguf`  
**Source:** [Qwen/Qwen3-Embedding-0.6B-GGUF](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF) (~639 MB)

```powershell
cd ..\model-embedding
curl.exe -L -o Qwen3-Embedding-0.6B-Q8_0.gguf `
  https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/main/Qwen3-Embedding-0.6B-Q8_0.gguf
```

Optional Hugging Face CLI (must write the file in **this** folder, same name):

```powershell
huggingface-cli download Qwen/Qwen3-Embedding-0.6B-GGUF Qwen3-Embedding-0.6B-Q8_0.gguf --local-dir .
```

Do not commit `*.gguf`.

## 3. Start

Still in `model-embedding`:

```powershell
docker compose up -d
docker compose ps
```

Wait until llama answers health (model load takes a short time):

```powershell
do {
  Start-Sleep -Seconds 2
  try { $h = Invoke-RestMethod http://127.0.0.1:8080/health } catch { $h = $null }
} until ($h.status -eq "ok")
$h
```

| Endpoint | URL | Traced |
| --- | --- | --- |
| llama.cpp | http://127.0.0.1:8080 | no |
| LiteLLM | http://127.0.0.1:4000 | yes |

LiteLLM `api_base` is `http://llama:8080/v1` in `litellm.yaml` (Docker DNS). `depends_on` only starts llama first.

## 4. Smoke test (traced)

```powershell
$r = Invoke-RestMethod http://127.0.0.1:4000/v1/embeddings -Method Post -ContentType "application/json" -Body '{"model":"qwen3-embedding","input":"hello from lib-gen"}'
"dims=$($r.data[0].embedding.Count) tokens=$($r.usage.total_tokens)"
# expect: dims=1024
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000) → project **lib-gen** → traces.

`curl.exe -d '{...}'` often sends broken JSON under PowerShell; `Invoke-RestMethod` is the path that works here.

## Stop

```powershell
cd model-embedding
docker compose down
```

## Layout

| File | Role |
| --- | --- |
| `docker-compose.yaml` | `llama` (:8080) and `litellm` (:4000) |
| `litellm.yaml` | `qwen3-embedding` → `http://llama:8080/v1` |
| `Qwen3-Embedding-0.6B-Q8_0.gguf` | weights, gitignored |
