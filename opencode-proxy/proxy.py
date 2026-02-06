"""
OpenCode proxy — translates OpenAI-compatible API requests into
OpenCode serve (localhost:4096) calls so LibreChat can use OpenCode
as a custom endpoint.

Run:  uvicorn proxy:app --host 0.0.0.0 --port 18791
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()

OPENCODE_BASE = os.getenv("OPENCODE_BASE_URL", "http://localhost:4096")
PROXY_KEY = os.getenv("OPENCODE_PROXY_KEY", "")

MODEL_MAP = {
    "glm-4.7": "zai-coding-plan/glm-4.7",
    "glm-4.7-flash": "zai-coding-plan/glm-4.7-flash",
    "glm-4.5": "zai-coding-plan/glm-4.5",
    "glm-4.7-free": "opencode/glm-4.7-free",
    "kimi-k2.5-free": "opencode/kimi-k2.5-free",
    "minimax-m2.1-free": "opencode/minimax-m2.1-free",
    "trinity-large-preview-free": "opencode/trinity-large-preview-free",
    "gpt-5-nano": "opencode/gpt-5-nano",
    "big-pickle": "opencode/big-pickle",
    "opencode": "zai-coding-plan/glm-4.7",
}


def _check_auth(authorization: Optional[str]):
    if not PROXY_KEY:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[len("Bearer "):]
    if token != PROXY_KEY:
        raise HTTPException(status_code=403, detail="Invalid bearer token")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models(authorization: Optional[str] = Header(default=None)):
    _check_auth(authorization)
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {"id": model_id, "object": "model", "created": now, "owned_by": "opencode"}
            for model_id in MODEL_MAP
            if model_id != "opencode"  # skip the alias
        ],
    }


def _extract_text_from_parts(parts):
    """Extract text content from OpenCode Part[] array."""
    texts = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type", "")
        if part_type == "text":
            text = part.get("text", "")
            if text:
                texts.append(text)
    return "\n\n".join(texts)


async def _stream_response(completion_id: str, assistant_text: str, model: str = "opencode"):
    """Yield streaming chunks to keep LibreChat connection alive."""
    created = int(time.time())

    # Split response into words to simulate streaming
    words = assistant_text.split()

    for i, word in enumerate(words):
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": word + " "},
                    "finish_reason": None,
                }
            ],
        }
        yield "data: " + json.dumps(chunk) + "\n\n"

    # Final chunk
    final_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield "data: " + json.dumps(final_chunk) + "\n\n"
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    _check_auth(authorization)

    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", False)

    # Extract the last user message
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = [
                    p.get("text", "") for p in content if p.get("type") == "text"
                ]
                user_message = "\n".join(text_parts)
            else:
                user_message = content
            break

    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")

    async with httpx.AsyncClient(base_url=OPENCODE_BASE, timeout=300.0) as client:
        # 0. Switch to the requested model
        model_name = body.get("model", "opencode")
        opencode_model = MODEL_MAP.get(model_name, MODEL_MAP["opencode"])
        await client.patch("/config", json={"model": opencode_model})

        # 1. Create a new session
        session_resp = await client.post("/session", json={})
        if session_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Failed to create OpenCode session: %s" % session_resp.text,
            )
        session_data = session_resp.json()
        session_id = session_data.get("id", "")
        if not session_id:
            raise HTTPException(status_code=502, detail="No session ID returned")

        # 2. Send the message
        msg_resp = await client.post(
            "/session/%s/message" % session_id,
            json={
                "parts": [
                    {"type": "text", "text": user_message}
                ]
            },
        )
        if msg_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Failed to send message to OpenCode: %s" % msg_resp.text,
            )
        msg_data = msg_resp.json()

        # 3. Extract assistant text
        parts = msg_data.get("parts", [])
        assistant_text = _extract_text_from_parts(parts)

        if not assistant_text:
            info = msg_data.get("info", {})
            error = info.get("error")
            if error:
                assistant_text = "(OpenCode error: %s)" % error
            else:
                assistant_text = "(No response from OpenCode)"

    completion_id = "chatcmpl-%s" % uuid.uuid4().hex[:12]

    # 4. Return streaming or non-streaming response
    if stream:
        return StreamingResponse(
            _stream_response(completion_id, assistant_text, model=model_name),
            media_type="text/plain",
        )
    else:
        return JSONResponse(
            content={
                "id": completion_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": assistant_text,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=18791)
