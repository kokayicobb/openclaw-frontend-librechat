"""
Claude Code proxy — translates OpenAI-compatible API requests into
`claude -p` subprocess calls so LibreChat can use Claude Code
as a custom endpoint.

Run:  uvicorn proxy:app --host 0.0.0.0 --port 18792
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()

CLAUDE_BIN = os.getenv("CLAUDE_BIN", "/Users/kokayi/.local/bin/claude")
CLAUDE_CWD = os.getenv("CLAUDE_CWD", "/Users/kokayi/Dev/consuelo_on_call_coaching")
PROXY_KEY = os.getenv("CLAUDE_PROXY_KEY", "")

MODEL_MAP = {
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}


def _check_auth(authorization: Optional[str]):
    if not PROXY_KEY:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[len("Bearer "):]
    if token != PROXY_KEY:
        raise HTTPException(status_code=403, detail="Invalid bearer token")


def _build_prompt(messages: list[dict]) -> str:
    """Concatenate conversation messages into a single prompt for claude -p."""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [
                p.get("text", "") for p in content if p.get("type") == "text"
            ]
            content = "\n".join(text_parts)
        if not content:
            continue
        if role == "system":
            parts.append(f"[System]: {content}")
        elif role == "assistant":
            parts.append(f"[Assistant]: {content}")
        else:
            parts.append(f"[User]: {content}")
    return "\n\n".join(parts)


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
            {"id": model_id, "object": "model", "created": now, "owned_by": "claude-code"}
            for model_id in MODEL_MAP
        ],
    }


async def _stream_claude(prompt: str, model: str, completion_id: str):
    """Run claude -p with stream-json output and yield SSE chunks."""
    claude_model = MODEL_MAP.get(model, "sonnet")
    created = int(time.time())

    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "-p", prompt,
        "--model", claude_model,
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--no-session-persistence",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=CLAUDE_CWD,
    )

    # Send initial chunk with role
    role_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"role": "assistant", "content": ""},
            "finish_reason": None,
        }],
    }
    yield "data: " + json.dumps(role_chunk) + "\n\n"

    try:
        async for line in proc.stdout:
            line = line.decode("utf-8").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            # Token-level streaming: stream_event with content_block_delta
            if event_type == "stream_event":
                inner = event.get("event", {})
                if inner.get("type") == "content_block_delta":
                    delta = inner.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            chunk = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": text},
                                    "finish_reason": None,
                                }],
                            }
                            yield "data: " + json.dumps(chunk) + "\n\n"

            elif event_type == "result":
                break

        # Send final stop chunk
        final_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }],
        }
        yield "data: " + json.dumps(final_chunk) + "\n\n"
        yield "data: [DONE]\n\n"
    finally:
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()


async def _run_claude(prompt: str, model: str) -> dict:
    """Run claude -p with json output and return the parsed result."""
    claude_model = MODEL_MAP.get(model, "sonnet")

    proc = await asyncio.create_subprocess_exec(
        CLAUDE_BIN, "-p", prompt,
        "--model", claude_model,
        "--output-format", "json",
        "--no-session-persistence",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=CLAUDE_CWD,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode("utf-8").strip() if stderr else "Unknown error"
        raise HTTPException(status_code=502, detail=f"Claude process failed: {error_msg}")

    try:
        result = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError:
        # Fallback: treat raw stdout as text
        result = {"result": stdout.decode("utf-8").strip()}

    return result


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    _check_auth(authorization)

    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    model = body.get("model", "claude-sonnet")

    prompt = _build_prompt(messages)
    if not prompt:
        raise HTTPException(status_code=400, detail="No message content found")

    completion_id = "chatcmpl-%s" % uuid.uuid4().hex[:12]

    if stream:
        return StreamingResponse(
            _stream_claude(prompt, model, completion_id),
            media_type="text/event-stream",
        )

    # Non-streaming
    result = await _run_claude(prompt, model)
    assistant_text = result.get("result", "(No response from Claude)")

    usage = result.get("usage", {})

    return JSONResponse(content={
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": assistant_text,
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        },
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18792)
