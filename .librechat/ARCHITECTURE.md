# LibreChat ↔ OpenClaw Architecture

## Overview

LibreChat is the web frontend (chat UI). OpenClaw is the AI agent backend. A FastAPI proxy sits between them to add tool activity streaming and abort support.

## Request Chain

```
User (browser)
  → LibreChat frontend (React, port 3210 via nginx)
    → LibreChat backend (Node.js, port 3080)
      → OpenClaw Proxy (FastAPI/Python, port 18793 on host)
        → OpenClaw Gateway (Node.js, port 18789 on host)
          → LLM providers (Anthropic, OpenRouter, etc.)
```

## Networking

LibreChat runs in Docker. The proxy and OpenClaw gateway run on the host.

- Docker containers reach the host via `host.docker.internal`
- Proxy URL from inside Docker: `http://host.docker.internal:18793/v1`
- Gateway URL from host: `http://127.0.0.1:18789`
- Gateway WebSocket: `ws://127.0.0.1:18789`
- nginx reverse proxies port 3210 → librechat:3080

## Docker Services

Defined in `/Users/kokayi/librechat/docker-compose.yml`:

| Service | Container | Port |
|---------|-----------|------|
| nginx | librechat-nginx | 3210→80 |
| librechat | librechat | 3080 (internal) |
| mongodb | librechat-mongodb | 27017 (internal) |
| meilisearch | librechat-meilisearch | 7700 |

## Host Services (not in Docker)

| Service | Port | Description |
|---------|------|-------------|
| OpenClaw Gateway | 18789 | AI agent runtime (WS + HTTP) |
| OpenClaw Proxy | 18793 | FastAPI proxy with tool streaming + abort |

## Endpoints (librechat.yaml)

Config: `/Users/kokayi/librechat/librechat.yaml`

All built-in endpoints (openAI, anthropic, google, assistants) are disabled. Only custom endpoints are used:

### 'suelo (main agent)
- baseURL: `http://host.docker.internal:18793/v1`
- Model: `'suelo`
- Session key header: `x-openclaw-session-key: librechat:{conversationId}`
- Routes through proxy → OpenClaw gateway → main agent

### devin (developer agent)
- baseURL: `http://host.docker.internal:18793/v1`
- Model: `devin`
- Session key header: `x-openclaw-session-key: agent:developer:librechat-dev:{conversationId}`
- Routes through proxy → OpenClaw gateway → developer agent

### OpenCode
- baseURL: `http://host.docker.internal:18791/v1`
- Separate proxy, not covered here

### ClaudeCode
- baseURL: `http://host.docker.internal:18792/v1`
- Separate proxy, not covered here

## OpenClaw Proxy (`/Users/kokayi/librechat/openclaw-proxy/proxy.py`)

The proxy does three things:

1. **Tool activity streaming**: Tails OpenClaw's log file for tool start/end events and streams them as `:::thinking` blocks that LibreChat renders as collapsible UI
2. **Passive abort**: When the client disconnects mid-stream (e.g., user hits stop), the proxy detects the broken connection and sends `chat.abort` to the gateway via WebSocket
3. **Explicit abort endpoint**: `POST /v1/chat/abort` accepts `{session_key}` and sends `chat.abort` to the gateway

### Proxy endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /v1/chat/completions | Forward to gateway with tool streaming |
| POST | /v1/chat/abort | Abort an OpenClaw session |
| GET | /v1/models | Passthrough to gateway |
| GET | /health | Health check |

### Running the proxy

```bash
cd /Users/kokayi/librechat/openclaw-proxy
python3 -m uvicorn proxy:app --host 0.0.0.0 --port 18793
```

## Abort Flow

When user clicks "Stop generating":

1. **Frontend**: Calls `POST /api/agents/chat/abort` with `{conversationId}`
2. **LibreChat backend** (`agents/index.js`):
   - `GenerationJobManager.abortJob()` — aborts the local AbortController, kills the HTTP fetch to proxy
   - Looks up endpoint name from job metadata, constructs session key
   - Fire-and-forget POST to proxy's `/v1/chat/abort` with the session key
3. **Proxy** (explicit path): Receives abort request, opens WS to gateway, sends `chat.abort` RPC
4. **Proxy** (passive path): Detects client disconnect in streaming generator's finally block, sends `chat.abort` RPC
5. **Gateway**: `chat.abort` handler aborts the AbortController for the agent run, stopping the LLM call

Both paths (explicit + passive) fire for belt-and-suspenders reliability.

## Authentication

- **LibreChat → Proxy**: Bearer token (`OPENCLAW_API_KEY` env var, same as gateway token)
- **Proxy → Gateway HTTP**: Bearer token forwarded from LibreChat
- **Proxy → Gateway WS** (for abort): Token from `OPENCLAW_GATEWAY_TOKEN` env or `~/.openclaw/openclaw.json`
- **Gateway auth**: Token mode, configured in `openclaw.json` at `gateway.auth.token`

## OpenClaw Gateway Config

Config: `/Users/kokayi/.openclaw/openclaw.json`

Key settings:
- `gateway.port`: 18789
- `gateway.auth.mode`: token
- `gateway.http.endpoints.chatCompletions.enabled`: true (OpenAI-compatible endpoint)
- `agents.list`: main (suelo) + developer (devin)

## Session Keys

OpenClaw uses session keys to track conversations. The pattern is defined in `librechat.yaml` headers:

| Endpoint | Session Key Pattern |
|----------|-------------------|
| 'suelo | `librechat:{conversationId}` |
| devin | `agent:developer:librechat-dev:{conversationId}` |

The `{conversationId}` is substituted at request time via `{{LIBRECHAT_BODY_CONVERSATIONID}}` template.

## Key Files

| File | Purpose |
|------|---------|
| `/Users/kokayi/librechat/librechat.yaml` | Endpoint config, models, headers |
| `/Users/kokayi/librechat/.env` | API keys, DB config |
| `/Users/kokayi/librechat/docker-compose.yml` | Docker services |
| `/Users/kokayi/librechat/openclaw-proxy/proxy.py` | Proxy with tool streaming + abort |
| `/Users/kokayi/librechat/source/api/server/routes/agents/index.js` | Abort route + OpenClaw abort wiring |
| `/Users/kokayi/librechat/source/client/src/data-provider/SSE/mutations.ts` | Frontend abort mutation |
| `/Users/kokayi/librechat/source/client/src/hooks/Chat/useChatHelpers.ts` | Stop button handler |
| `/Users/kokayi/.openclaw/openclaw.json` | Gateway config |

## Rebuilding

After modifying LibreChat source:

```bash
cd /Users/kokayi/librechat
docker compose build librechat
docker compose up -d
```

The proxy runs on the host (not in Docker), so changes to `proxy.py` just need a restart:

```bash
# Kill existing proxy, then:
cd /Users/kokayi/librechat/openclaw-proxy
python3 -m uvicorn proxy:app --host 0.0.0.0 --port 18793
```
