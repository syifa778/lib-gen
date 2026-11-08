# Text server

CPU `llama.cpp` for **Qwen3.5 4B**, plus LiteLLM on **4001** that forwards `/v1/chat/completions` and traces to local Langfuse.

This Docker/WSL host has **no NVIDIA GPU**, so the image is `llama.cpp:server`, not `full-cuda`. Context is `-c 8192`. Replies are slow; Qwen3.5 may fill `reasoning_content` before `content`. FastAPI does not call this yet.

On Windows PowerShell, `curl` is `Invoke-WebRequest`. Use **`curl.exe`** for the GGUF download and **`Invoke-RestMethod`** for smoke tests.

## 1. Langfuse first

From the **lib-gen repo root**:

```powershell
cd langfuse
docker compose up -d
Invoke-RestMethod http://127.0.0.1:3000/api/public/health
# expect: status = OK
```

If compose later says `network libgen not found`, start Langfuse first.

## 2. Download the GGUF

Save **in this folder**, next to `docker-compose.yaml`.

**Path:** `lib-gen/model-text/Qwen3.5-4B-Q4_K_M.gguf`  
**Source:** [unsloth/Qwen3.5-4B-GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF) (~2.7 GB)

```powershell
cd ..\model-text
curl.exe -L -o Qwen3.5-4B-Q4_K_M.gguf `
  https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf
```

Optional:

```powershell
huggingface-cli download unsloth/Qwen3.5-4B-GGUF Qwen3.5-4B-Q4_K_M.gguf --local-dir .
```

Do not commit `*.gguf`.

## 3. Start

Still in `model-text`:

```powershell
docker compose up -d
docker compose ps
```

Wait until llama is up (first load of 4B can take a minute):

```powershell
do {
  Start-Sleep -Seconds 3
  try { $h = Invoke-RestMethod http://127.0.0.1:30000/health } catch { $h = $null }
} until ($h.status -eq "ok")
$h
```

| Endpoint | URL | Traced |
| --- | --- | --- |
| llama.cpp | http://127.0.0.1:30000 | no |
| LiteLLM | http://127.0.0.1:4001 | yes |

Model names: `qwen35-4b` or `Qwen3.5-4B-Q4_K_M.gguf`.

## 4. Smoke test (traced)

Keep `max_tokens` small so the request finishes on CPU. A 200 with `choices` is success even if `content` is empty (thinking tokens).

```powershell
$body = '{"model":"qwen35-4b","messages":[{"role":"user","content":"Say hi in one sentence."}],"max_tokens":16}'
$r = Invoke-RestMethod http://127.0.0.1:4001/v1/chat/completions -Method Post -ContentType "application/json" -Body $body
"finish=$($r.choices[0].finish_reason) tokens=$($r.usage.total_tokens)"
$r.choices[0].message.content
$r.choices[0].message.reasoning_content
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000) → project **lib-gen** → traces.

Do not use PowerShell `curl -d '{...}'`; it corrupts JSON. `Invoke-RestMethod` is the working client here.

If you later have a GPU in Docker: image `ghcr.io/ggml-org/llama.cpp:full-cuda`, `gpus: all`, `-ngl 99`. Without a GPU that fails with `no adapters were found`.

## Stop

```powershell
cd model-text
docker compose down
```

## Layout

| File | Role |
| --- | --- |
| `docker-compose.yaml` | `llama` (host 30000) and `litellm` (host 4001) |
| `litellm.yaml` | `qwen35-4b` → `http://llama:8080/v1` |
| `Qwen3.5-4B-Q4_K_M.gguf` | weights, gitignored |
