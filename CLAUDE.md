# AI Defender - Project Context

## Overview

AI Defender is a honeypot MCP server that traps and monitors malicious AI agents. It exposes realistic-looking tools via JSON-RPC 2.0, tracks every interaction, injects traceable honey tokens, and visualizes attacks in real time through a 3D dashboard.

## Architecture

- **Backend**: Python 3.12 / Flask on port 5000, SQLite (WAL mode), in-process EventBus for SSE
- **Frontend**: Next.js 16 / React 19 on port 3000, Three.js/R3F 3D visualization, TailwindCSS 4
- **Protocol**: MCP (Model Context Protocol) over JSON-RPC 2.0 at `POST /mcp`
- **Dashboard API**: REST + SSE at `/api/*` and `/api/events/live`

### Fly.io Deployment (Two Apps)

| App | URL | Purpose |
|-----|-----|---------|
| `ai-defender` | https://ai-defender.fly.dev | Next.js frontend (public) |
| `ai-defender-api` | https://ai-defender-api.fly.dev | Flask backend (public MCP endpoint + health) |

- Frontend proxies `/api/*` to backend over Fly internal network (`ai-defender-api.internal:5000`)
- MCP endpoint publicly reachable at `POST https://ai-defender-api.fly.dev/mcp`
- SQLite persisted on a Fly volume mounted at `/data`
- Both apps use `shared-cpu-1x` / 256MB, auto-stop when idle, auto-start on request

## Honeypot Tools (10)

| Tool | Category | Tokens Injected | Key Behavior |
|------|----------|-----------------|--------------|
| `nmap_scan` | Recon | None | Scans 5-host simulated network, tracks hosts/ports |
| `file_read` | Credential theft | Up to 3 per .env | Path-based dispatch, highest token density for .env |
| `shell_exec` | Credential theft | None | Command dispatch table, dangerous command detection |
| `sqlmap_scan` | Credential theft | Varies by table | Progressive stages: test -> databases -> tables -> columns -> dump |
| `browser_navigate` | Credential theft | Up to 2 | Internal DevOps portal with admin panel, API endpoints |
| `dns_lookup` | Recon | None | Internal *.corp.internal zone, A/MX/TXT/SRV/CNAME records |
| `aws_cli` | Credential use | AWS_ACCESS_KEY, DB, API | S3/IAM/SecretsManager/Lambda/EC2 command parsing |
| `kubectl` | Lateral movement | DB, API, SSH, ADMIN | K8s get/describe/logs/exec, 4 secrets with different token types |
| `vault_cli` | Lateral movement | All 5 types | HashiCorp Vault sim, highest density (all 5 TokenTypes) |
| `docker_registry` | Lateral movement | DB, API | Container registry list/inspect/pull, tokens in image env vars |

## Token Types (5)

| Type | Format | Traceability |
|------|--------|-------------|
| `AWS_ACCESS_KEY` | `AKIA` + session hash + random | 8-char SHA256 of session_id |
| `API_TOKEN` | JWT-like with session hash in payload | Same |
| `DB_CREDENTIAL` | PostgreSQL connection string | Session hash in password |
| `ADMIN_LOGIN` | `admin:Adm1n` + session hash | Same |
| `SSH_KEY` | OpenSSH private key format | Session hash in key body |

## Key Patterns

### Backend Simulator Pattern
All simulators extend `ToolSimulator` ABC in `backend/honeypot/simulators/base.py`:
- Properties: `name`, `description`, `input_schema`
- Method: `simulate(arguments: dict, session: SessionContext) -> SimulationResult`
- Token injection: `HoneyTokenGenerator.generate()` -> `log_honey_token()` -> `session.add_credential()`

### Registry Dispatch Flow
`registry.py` handles: dispatch -> simulate -> capture output -> enrich_output (breadcrumbs) -> detect injection -> log interaction -> publish SSE events

### SSE Event Fields
The `interaction` event includes:
- `session_id`, `tool_name`, `arguments`, `escalation_delta`, `escalation_level`, `timestamp`
- `arguments`: raw tool call parameters dict (full key-value pairs sent to the simulator)
- `prompt_summary`: human-readable summary of the tool call (fallback when arguments absent)
- `injection`: breadcrumb/lure text injected by the engagement engine (or null)

### Frontend Event Consumption
`useLiveEventContext().subscribe(eventType, callback)` pattern via `lib/live-event-context.tsx`

## Dashboard Overlays

| Overlay | Position | Purpose |
|---------|----------|---------|
| Stats | Top bar | Connection status, session/interaction/token counts |
| Event Feed | Top right | Scrolling interactions with color-coded tool badges |
| Sessions List | Left | Active sessions sorted by escalation |
| Session Detail | Left (on select) | Selected session interactions and client info |
| Prompt Monitor | Bottom left (380px) | ATTACKER entries with color-coded tool badge + full arguments, HONEYPOT LURE entries (cleaned breadcrumbs), TOKEN DEPLOYED entries |
| Control Bar | Bottom center | Reset (confirmation required), attack count input (1-20), Launch button. Calls `POST /api/admin/reset` and `POST /api/admin/simulate` |

## Admin API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/admin/reset` | POST | Wipes all sessions/interactions/tokens, clears session cache, publishes zeroed stats via SSE |
| `/api/admin/simulate` | POST | Accepts `{"count": N}` (1-20), creates N sessions with random attacker names, spawns background threads running 4-8 tool calls each with 1-2s delays |

### Attack Simulation Sequence
Each simulated attack picks a random subset (4-8 steps) from:
1. `nmap_scan` (target: "10.0.1.0/24") -- recon
2. `dns_lookup` (domain: "corp.internal") -- recon
3. `file_read` (path: "/app/.env") -- credential harvest
4. `shell_exec` (command: "whoami") -- system info
5. `sqlmap_scan` (action: "test") -- vuln testing
6. `sqlmap_scan` (action: "dump", table: "users") -- credential dump
7. `browser_navigate` (url: "/api/config") -- lateral movement
8. `aws_cli` (command: "s3 ls") -- cloud access

## Particle Colors by Tool

| Tool | Color | Hex |
|------|-------|-----|
| nmap_scan | Blue | #3b82f6 |
| file_read | Purple | #a855f7 |
| shell_exec | Amber | #f59e0b |
| sqlmap_scan | Red | #ef4444 |
| browser_navigate | Cyan | #06b6d4 |
| dns_lookup | Teal | #14b8a6 |
| aws_cli | Orange | #f97316 |
| kubectl | Indigo | #6366f1 |
| vault_cli | Yellow | #eab308 |
| docker_registry | Sky | #0ea5e9 |

## Escalation Levels

| Level | Name | Trigger |
|-------|------|---------|
| 0 | Reconnaissance | Default |
| 1 | Network Mapping | 2+ hosts or 2+ files |
| 2 | Credential Harvesting | 1+ credential |
| 3 | Lateral Movement | 10+ interactions + credentials |

## Test Suite

346 backend tests across 20 modules, all passing. Run with:
```bash
cd backend && .venv/bin/python -m pytest -v
```

## Development

```bash
# Backend (local)
cd backend && source .venv/bin/activate && python -m honeypot.app

# Frontend (local)
npm run dev
```

## Deployment (Fly.io)

```bash
# Deploy backend
cd backend && fly deploy

# Deploy frontend
cd .. && fly deploy

# Verify
curl https://ai-defender-api.fly.dev/health
curl https://ai-defender.fly.dev/
```

## Key Directories

```
backend/
  honeypot/
    app.py              # Flask app factory
    registry.py         # Tool dispatch + SSE events
    session.py          # Session manager + context
    engagement.py       # Escalation scoring + breadcrumbs
    tokens.py           # HoneyTokenGenerator + TokenType enum
    simulators/         # 10 tool simulators (base.py + one per tool)
  shared/
    db.py               # SQLite operations
  tests/                # 20 test modules
components/
  visualization/        # 3D scene (R3F), overlays, particles
lib/
  types.ts              # TypeScript interfaces
  live-event-context.tsx # SSE provider + subscribe pattern
  use-live-stream.ts    # SSE connection with reconnect
docs/
  USER_MANUAL.md        # Full reference documentation
fly.toml                # Fly.io config for frontend (ai-defender)
backend/fly.toml        # Fly.io config for backend (ai-defender-api)
```
