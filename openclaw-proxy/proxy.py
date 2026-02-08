"""
OpenClaw proxy — sits between LibreChat and OpenClaw to surface tool
activity as :::thinking blocks in the streamed response.

LibreChat parses :::thinking\n{content}\n::: from the text and renders
it in a collapsible UI (lightbulb icon, expand/collapse).

Strategy: OpenClaw's /v1/chat/completions blocks during the agent tool
loop and only starts streaming text afterward. The proxy concurrently
tails OpenClaw's log file for tool events and streams them to the client
as :::thinking content while waiting for upstream text to begin.

Run:  python3 -m uvicorn proxy:app --host 0.0.0.0 --port 18793
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from glob import glob

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()

OPENCLAW_BASE = os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789")
OPENCLAW_LOG_DIR = os.getenv("OPENCLAW_LOG_DIR", "/tmp/openclaw")

# Retry config for gateway restarts
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3.0  # wait for gateway to come back after restart

TOOL_RE = re.compile(
    r"embedded run tool (start|end): runId=(\S+) tool=(\S+) toolCallId=(\S+)"
)
TOOLS_DETAIL_RE = re.compile(r"^\[tools\]\s+(\S+)\s+failed:\s*(.*)", re.DOTALL)


def _latest_log_file() -> str | None:
    files = sorted(glob(os.path.join(OPENCLAW_LOG_DIR, "openclaw-*.log")))
    return files[-1] if files else None


def _make_chunk(completion_id: str, created: int, model: str, content: str, finish_reason=None):
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"content": content} if content else {},
            "finish_reason": finish_reason,
        }],
    }


def _sse(data) -> str:
    return "data: " + json.dumps(data) + "\n\n"


async def _wait_for_openclaw(timeout: float = 15.0) -> bool:
    """Wait for OpenClaw gateway to be reachable after a restart."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{OPENCLAW_BASE}/v1/models")
                if resp.status_code == 200:
                    return True
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            pass
        await asyncio.sleep(0.5)
    return False


async def _tail_log_for_tools(
    log_path: str,
    tool_queue: asyncio.Queue,
    stop_event: asyncio.Event,
    start_offset: int,
):
    """Tail the log file and push structured tool events to the queue."""
    try:
        with open(log_path, "r") as f:
            f.seek(start_offset)
            while not stop_event.is_set():
                line = f.readline()
                if not line:
                    await asyncio.sleep(0.05)
                    continue
                line = line.strip()
                if not line:
                    continue
                if "embedded run tool" not in line and "[tools]" not in line:
                    continue
                try:
                    data = json.loads(line)

                    # Check field "1" for tool start/end events
                    msg1 = data.get("1", "")
                    m = TOOL_RE.search(msg1)
                    if m:
                        phase, _rid, tool_name, call_id = m.groups()
                        await tool_queue.put({
                            "type": phase,
                            "tool": tool_name,
                            "call_id": call_id,
                        })
                        continue

                    # Check field "0" for [tools] failure details
                    msg0 = data.get("0", "")
                    dm = TOOLS_DETAIL_RE.search(msg0)
                    if dm:
                        tool_name = dm.group(1)
                        detail = dm.group(2).strip()
                        await tool_queue.put({
                            "type": "detail",
                            "tool": tool_name,
                            "message": detail,
                        })
                except (json.JSONDecodeError, KeyError):
                    pass
    except Exception:
        pass


async def _stream_with_tools(request_body: dict, headers: dict):
    """Forward request to OpenClaw, concurrently tail log for tools, merge into SSE."""
    model = request_body.get("model", "unknown")
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    tool_queue: asyncio.Queue = asyncio.Queue()
    stop_event = asyncio.Event()

    # Record log position before making the request
    log_path = _latest_log_file()
    log_offset = 0
    if log_path:
        try:
            log_offset = os.path.getsize(log_path)
        except OSError:
            log_offset = 0

    # Start log tailer immediately (before upstream request)
    tail_task = None
    if log_path:
        tail_task = asyncio.create_task(
            _tail_log_for_tools(log_path, tool_queue, stop_event, log_offset)
        )

    thinking_open = False  # whether we're currently inside a :::thinking block
    # Track the currently active (started but not ended) tool call
    active_tool: dict | None = None  # {"tool": str, "call_id": str}
    failed_calls: set[str] = set()  # call_ids that had a failure detail

    # Emit role chunk
    role_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield _sse(role_chunk)

    retries = 0
    success = False

    try:
        while retries <= MAX_RETRIES and not success:
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=30.0, read=1800.0, write=30.0, pool=30.0)
                ) as client:
                    async with client.stream(
                        "POST",
                        f"{OPENCLAW_BASE}/v1/chat/completions",
                        json=request_body,
                        headers=headers,
                    ) as upstream:
                        if upstream.status_code != 200:
                            body = await upstream.aread()
                            error_text = body.decode()[:500]
                            # If it looks like a restart/temporary error, retry
                            if upstream.status_code >= 500 and retries < MAX_RETRIES:
                                retries += 1
                                if thinking_open:
                                    yield _sse(_make_chunk(completion_id, created, model,
                                        f"\n⚡ gateway returned {upstream.status_code}, retrying ({retries}/{MAX_RETRIES})...\n"))
                                else:
                                    yield _sse(_make_chunk(completion_id, created, model, ":::thinking\n"))
                                    thinking_open = True
                                    yield _sse(_make_chunk(completion_id, created, model,
                                        f"⚡ gateway returned {upstream.status_code}, retrying ({retries}/{MAX_RETRIES})...\n"))
                                await asyncio.sleep(RETRY_DELAY_SECONDS)
                                await _wait_for_openclaw()
                                continue
                            # Non-retryable error
                            yield _sse(_make_chunk(completion_id, created, model, f"Error: {error_text}"))
                            yield _sse(_make_chunk(completion_id, created, model, "", finish_reason="stop"))
                            yield "data: [DONE]\n\n"
                            return

                        # Read upstream SSE lines
                        upstream_iter = upstream.aiter_lines().__aiter__()
                        upstream_done = False
                        pending_line_task = None

                        while not upstream_done:
                            if pending_line_task is None:
                                pending_line_task = asyncio.create_task(upstream_iter.__anext__())

                            done_tasks, _ = await asyncio.wait(
                                [pending_line_task],
                                timeout=0.1,
                            )

                            # Drain any tool events
                            while not tool_queue.empty():
                                event = tool_queue.get_nowait()
                                if not thinking_open:
                                    yield _sse(_make_chunk(completion_id, created, model, ":::thinking\n"))
                                    thinking_open = True

                                etype = event["type"]
                                if etype == "start":
                                    active_tool = {"tool": event["tool"], "call_id": event["call_id"]}
                                    yield _sse(_make_chunk(completion_id, created, model, f"[{event['tool']}] started\n"))
                                elif etype == "detail":
                                    if active_tool and active_tool["tool"] == event["tool"]:
                                        failed_calls.add(active_tool["call_id"])
                                    yield _sse(_make_chunk(completion_id, created, model, f"[{event['tool']}] FAILED: {event['message']}\n"))
                                elif etype == "end":
                                    if event["call_id"] not in failed_calls:
                                        yield _sse(_make_chunk(completion_id, created, model, f"[{event['tool']}] completed\n"))
                                    active_tool = None

                            if not done_tasks:
                                continue

                            pending_line_task = None
                            try:
                                raw_line = done_tasks.pop().result()
                            except StopAsyncIteration:
                                upstream_done = True
                                break

                            if not raw_line.startswith("data: "):
                                continue
                            payload = raw_line[6:]
                            if payload.strip() == "[DONE]":
                                upstream_done = True
                                break

                            try:
                                chunk = json.loads(payload)
                            except json.JSONDecodeError:
                                continue

                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            text = delta.get("content", "")
                            finish = choices[0].get("finish_reason")

                            if finish:
                                if thinking_open:
                                    yield _sse(_make_chunk(completion_id, created, model, "\n:::\n"))
                                    thinking_open = False
                                yield _sse(_make_chunk(completion_id, created, model, "", finish_reason="stop"))
                                upstream_done = True
                                success = True
                                break

                            if not text:
                                continue

                            if thinking_open:
                                yield _sse(_make_chunk(completion_id, created, model, "\n:::\n"))
                                thinking_open = False

                            yield _sse(_make_chunk(completion_id, created, model, text))

                        if upstream_done:
                            success = True

            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                # Gateway is down (probably restarting)
                retries += 1
                if retries <= MAX_RETRIES:
                    if not thinking_open:
                        yield _sse(_make_chunk(completion_id, created, model, ":::thinking\n"))
                        thinking_open = True
                    yield _sse(_make_chunk(completion_id, created, model,
                        f"⚡ gateway connection lost, waiting for restart ({retries}/{MAX_RETRIES})...\n"))
                    # Wait for gateway to come back
                    came_back = await _wait_for_openclaw(timeout=20.0)
                    if came_back:
                        yield _sse(_make_chunk(completion_id, created, model,
                            "✅ gateway back online, retrying request...\n"))
                        continue
                    else:
                        if thinking_open:
                            yield _sse(_make_chunk(completion_id, created, model, "\n:::\n"))
                            thinking_open = False
                        yield _sse(_make_chunk(completion_id, created, model,
                            f"\n\n[proxy error: gateway did not come back after {MAX_RETRIES} retries]\n"))
                        yield _sse(_make_chunk(completion_id, created, model, "", finish_reason="stop"))
                        yield "data: [DONE]\n\n"
                        return
                else:
                    if thinking_open:
                        yield _sse(_make_chunk(completion_id, created, model, "\n:::\n"))
                        thinking_open = False
                    yield _sse(_make_chunk(completion_id, created, model,
                        f"\n\n[proxy error: {type(exc).__name__}: {exc}]\n"))
                    yield _sse(_make_chunk(completion_id, created, model, "", finish_reason="stop"))
                    yield "data: [DONE]\n\n"
                    return

            except (httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
                # Connection was active but got dropped mid-stream
                retries += 1
                if retries <= MAX_RETRIES:
                    if not thinking_open:
                        yield _sse(_make_chunk(completion_id, created, model, ":::thinking\n"))
                        thinking_open = True
                    yield _sse(_make_chunk(completion_id, created, model,
                        f"⚡ connection dropped ({type(exc).__name__}), retrying ({retries}/{MAX_RETRIES})...\n"))
                    came_back = await _wait_for_openclaw(timeout=20.0)
                    if came_back:
                        yield _sse(_make_chunk(completion_id, created, model,
                            "✅ gateway back, retrying...\n"))
                        continue
                    else:
                        if thinking_open:
                            yield _sse(_make_chunk(completion_id, created, model, "\n:::\n"))
                            thinking_open = False
                        yield _sse(_make_chunk(completion_id, created, model,
                            f"\n\n[proxy error: gateway did not recover]\n"))
                        yield _sse(_make_chunk(completion_id, created, model, "", finish_reason="stop"))
                        yield "data: [DONE]\n\n"
                        return
                else:
                    if thinking_open:
                        yield _sse(_make_chunk(completion_id, created, model, "\n:::\n"))
                        thinking_open = False
                    yield _sse(_make_chunk(completion_id, created, model,
                        f"\n\n[proxy error: {type(exc).__name__}: {exc}]\n"))
                    yield _sse(_make_chunk(completion_id, created, model, "", finish_reason="stop"))
                    yield "data: [DONE]\n\n"
                    return

        # Close thinking block if still open
        if thinking_open:
            yield _sse(_make_chunk(completion_id, created, model, "\n:::\n"))

        yield "data: [DONE]\n\n"

    finally:
        stop_event.set()
        if tail_task:
            tail_task.cancel()
            try:
                await tail_task
            except asyncio.CancelledError:
                pass


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models(request: Request):
    """Pass through to OpenClaw."""
    fwd_headers = {}
    if auth := request.headers.get("authorization"):
        fwd_headers["Authorization"] = auth
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{OPENCLAW_BASE}/v1/models", headers=fwd_headers)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    stream = body.get("stream", False)

    # Build headers to forward
    fwd_headers = {"Content-Type": "application/json"}
    if auth := request.headers.get("authorization"):
        fwd_headers["Authorization"] = auth
    if session_key := request.headers.get("x-openclaw-session-key"):
        fwd_headers["x-openclaw-session-key"] = session_key

    if not stream:
        # Non-streaming: simple passthrough with retry
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=30.0, read=1800.0, write=30.0, pool=30.0)
                ) as client:
                    resp = await client.post(
                        f"{OPENCLAW_BASE}/v1/chat/completions",
                        json=body,
                        headers=fwd_headers,
                    )
                    return JSONResponse(content=resp.json(), status_code=resp.status_code)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError):
                if attempt < MAX_RETRIES:
                    await _wait_for_openclaw(timeout=15.0)
                    continue
                raise HTTPException(status_code=502, detail="Gateway unavailable after retries")

    return StreamingResponse(
        _stream_with_tools(body, fwd_headers),
        media_type="text/event-stream",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18793)
