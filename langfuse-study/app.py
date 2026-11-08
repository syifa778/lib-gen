"""Two traced paths to the same local llama.cpp chat model.

A) /chat/direct  — FastAPI → llama.cpp :30000
                   llama.cpp has no tracer. This process opens a Langfuse
                   generation and writes input/output itself (so thinking
                   text is not dropped).

B) /chat/litellm — FastAPI → LiteLLM :4001 → llama.cpp
                   LiteLLM already has callbacks: [langfuse_otel]. Do not
                   wrap this client with langfuse.openai (double-trace).

Qwen3.5 often fills reasoning_content first and leaves content empty when
max_tokens is small. Direct tracing used to log only content, which looked
blank in Langfuse. We now store both fields, and turn thinking off on the
direct call so content is a normal reply.

Local Langfuse keys match langfuse/docker-compose.yaml (dev only).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-lf-libgen-local")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-lf-libgen-local")
os.environ.setdefault("LANGFUSE_BASE_URL", "http://127.0.0.1:3000")

from langfuse import get_client

LLAMA_MODEL = "/models/Qwen3.5-4B-Q4_K_M.gguf"
LITELLM_MODEL = "qwen35-4b"

llama = OpenAI(base_url="http://127.0.0.1:30000/v1", api_key="dummy")
proxy = OpenAI(base_url="http://127.0.0.1:4001/v1", api_key="dummy")


class ChatIn(BaseModel):
    message: str
    max_tokens: int = 64


class ChatOut(BaseModel):
    via: str
    content: str | None
    reasoning: str | None


def _message_parts(msg) -> tuple[str | None, str | None]:
    return msg.content, getattr(msg, "reasoning_content", None)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    get_client().flush()


app = FastAPI(title="Langfuse study", version="0.1.0", lifespan=lifespan)


@app.get("/")
def index():
    return {
        "direct": "POST /chat/direct  → llama.cpp :30000, trace from this FastAPI",
        "litellm": "POST /chat/litellm → LiteLLM :4001, trace from the proxy",
        "docs": "/docs",
    }


@app.post("/chat/direct", response_model=ChatOut)
def chat_direct(body: ChatIn) -> ChatOut:
    messages = [{"role": "user", "content": body.message}]
    lf = get_client()
    with lf.start_as_current_observation(
        as_type="generation",
        name="chat-direct",
        model=LLAMA_MODEL,
        input=messages,
        model_parameters={"max_tokens": body.max_tokens, "enable_thinking": False},
    ) as gen:
        out = llama.chat.completions.create(
            model=LLAMA_MODEL,
            messages=messages,
            max_tokens=body.max_tokens,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        content, reasoning = _message_parts(out.choices[0].message)
        usage = out.usage
        gen.update(
            output={
                "role": "assistant",
                "content": content,
                "reasoning_content": reasoning,
            },
            usage_details=(
                None
                if usage is None
                else {"input": usage.prompt_tokens, "output": usage.completion_tokens}
            ),
        )
    return ChatOut(
        via="llama.cpp :30000 (manual Langfuse generation)",
        content=content,
        reasoning=reasoning,
    )


@app.post("/chat/litellm", response_model=ChatOut)
def chat_litellm(body: ChatIn) -> ChatOut:
    out = proxy.chat.completions.create(
        model=LITELLM_MODEL,
        messages=[{"role": "user", "content": body.message}],
        max_tokens=body.max_tokens,
    )
    content, reasoning = _message_parts(out.choices[0].message)
    return ChatOut(
        via="LiteLLM :4001 (proxy callback)",
        content=content,
        reasoning=reasoning,
    )
