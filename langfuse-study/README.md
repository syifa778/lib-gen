# Langfuse study (not the Lib Gen product)

Tiny FastAPI app that shows **two ways** to call the local Qwen text model and still get traces in Langfuse.

```
A) FastAPI  --manual Langfuse generation-->  llama.cpp :30000
B) FastAPI  --plain OpenAI-->  LiteLLM :4001 --> llama.cpp
                              LiteLLM sends the trace
```

**Why a direct trace can show empty `content`:** Qwen3.5 is a thinking model. With a small `max_tokens` it spends the budget on `reasoning_content` and returns `content: ""`. The Langfuse OpenAI wrapper only stores `message.content`, so Langfuse looked blank even though the server did generate tokens.

`/chat/direct` now opens a generation itself and writes both `content` and `reasoning_content`. It also sends `enable_thinking: false` so a normal reply lands in `content`.

Lib Gen FastAPI (`backend/`, port 8000) is unchanged.

## Before this

Langfuse + text server must already be up (`langfuse/README.md`, `model-text/README.md`).

```powershell
Invoke-RestMethod http://127.0.0.1:3000/api/public/health   # status = OK
Invoke-RestMethod http://127.0.0.1:30000/health             # status = ok
Invoke-RestMethod http://127.0.0.1:4001/health              # LiteLLM; ignore body if odd
```

## Run

From the **lib-gen repo root**:

```powershell
cd langfuse-study
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8010
```

Open [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs).

## Smoke (PowerShell)

```powershell
Invoke-RestMethod http://127.0.0.1:8010/chat/direct -Method Post -ContentType "application/json" -Body '{"message":"Say hi in one sentence."}'
Invoke-RestMethod http://127.0.0.1:8010/chat/litellm -Method Post -ContentType "application/json" -Body '{"message":"Say hi in one sentence."}'
```

Then Langfuse UI → project **lib-gen** → traces. Direct output should include a non-empty `content` (thinking is off on that route). LiteLLM traces still come from the proxy.

Restart uvicorn after pulling this change.
