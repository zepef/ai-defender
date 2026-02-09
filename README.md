# AI Defender

A honeypot MCP (Model Context Protocol) server designed to detect, monitor, and analyze malicious AI agent behavior. It exposes realistic-looking tools (network scanning, file reading, shell execution, SQL injection, browser automation) that produce fake but convincing output, while tracking every interaction for security analysis.

## Architecture

```
┌─────────────────┐        MCP/JSON-RPC         ┌──────────────────────┐
│   AI Agent      │ ──────────────────────────── │  Flask Backend       │
│  (adversary)    │        POST /mcp             │  ├─ Protocol Handler │
└─────────────────┘                              │  ├─ Tool Registry    │
                                                 │  ├─ Simulators (5)   │
┌─────────────────┐        REST + SSE            │  ├─ Engagement Engine│
│  Next.js        │ ──────────────────────────── │  └─ Session Manager  │
│  Dashboard      │      GET /api/*              └──────────────────────┘
└─────────────────┘                                       │
                                                    SQLite DB
```

**Backend** (Python/Flask): Implements MCP Streamable HTTP transport. AI agents connect via `POST /mcp` and interact through JSON-RPC 2.0. Five tool simulators produce fake output while the engagement engine tracks escalation levels and injects honey tokens.

**Frontend** (Next.js 16/React): Real-time dashboard with SSE streaming for monitoring active sessions, interaction timelines, escalation levels, and deployed honey tokens.

## Honeypot Tools

| Tool | Description |
|------|-------------|
| `nmap_scan` | Simulated network port scanning with fake host/service discovery |
| `file_read` | Fake filesystem with realistic config files, credentials, and logs |
| `shell_exec` | Command execution simulator (whoami, ps, env, docker, etc.) |
| `sqlmap_scan` | SQL injection scanner returning fake vulnerable endpoints |
| `browser_navigate` | Web browser automation with simulated page content |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m honeypot.app
```

The MCP server starts on `http://localhost:5000`.

### Frontend

```bash
npm install
npm run dev
```

The dashboard opens at `http://localhost:3000`.

### Docker

```bash
docker compose up
```

## Configuration

Copy `.env.example` to `.env` and adjust values. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `HONEYPOT_DB_PATH` | `./honeypot.db` | SQLite database path |
| `HONEYPOT_PORT` | `5000` | Backend listen port |
| `DASHBOARD_API_KEY` | *(empty)* | API key for dashboard auth |
| `DASHBOARD_CORS_ORIGIN` | `http://localhost:3000` | Allowed CORS origin |
| `MCP_RATE_LIMIT` | `60` | Max MCP requests per window |
| `NEXT_PUBLIC_API_URL` | `http://localhost:5000` | Backend URL for frontend |

## Testing

```bash
# Backend
cd backend && python -m pytest

# Frontend
npm test
```

## Project Structure

```
ai-defender/
├── app/                    # Next.js pages (dashboard UI)
├── components/             # React components
├── lib/                    # Frontend utilities and API client
├── backend/
│   ├── honeypot/
│   │   ├── app.py          # Flask application factory
│   │   ├── protocol.py     # JSON-RPC 2.0 MCP handler
│   │   ├── registry.py     # Tool registry and dispatch
│   │   ├── session.py      # Session management
│   │   ├── engagement.py   # Escalation scoring engine
│   │   ├── tokens.py       # Honey token generator
│   │   └── simulators/     # Tool simulators
│   ├── shared/
│   │   ├── config.py       # Environment configuration
│   │   └── db.py           # SQLite schema and CRUD
│   └── tests/              # Backend test suite
├── __tests__/              # Frontend test suite
├── docker-compose.yml
├── Dockerfile
└── .github/workflows/ci.yml
```

## License

Private - All rights reserved.
