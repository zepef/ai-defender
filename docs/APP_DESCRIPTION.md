# AI Defender -- Technical Application Description

AI Defender is a honeypot MCP server that traps and monitors malicious AI agents.
It exposes realistic-looking tools over the Model Context Protocol (JSON-RPC 2.0),
tracks every interaction an attacker makes, injects traceable honey tokens into
tool outputs, and visualizes attacks in real time through a 3D dashboard.

Two independent processes serve the application:

| Process | Runtime | Default port | Purpose |
|---------|---------|-------------|---------|
| Backend | Python 3.12 / Flask | 5000 | MCP endpoint, REST API, SSE streams, SQLite persistence |
| Frontend | Next.js 16 / React 19 | 3000 | Dashboard pages, 3D visualization, API proxy |

The browser never talks directly to Flask. All traffic flows through Next.js, which
proxies `/api/*` requests to the backend.

---

## Table of contents

1. [Directory layout](#1-directory-layout)
2. [Backend: how the server starts](#2-backend-how-the-server-starts)
3. [The MCP endpoint and protocol routing](#3-the-mcp-endpoint-and-protocol-routing)
4. [Tool registry and dispatch flow](#4-tool-registry-and-dispatch-flow)
5. [Simulator pattern](#5-simulator-pattern)
6. [Honey token generation and traceability](#6-honey-token-generation-and-traceability)
7. [Engagement engine: escalation and breadcrumbs](#7-engagement-engine-escalation-and-breadcrumbs)
8. [Session management](#8-session-management)
9. [EventBus and real-time streaming](#9-eventbus-and-real-time-streaming)
10. [Dashboard REST API](#10-dashboard-rest-api)
11. [SQLite database schema](#11-sqlite-database-schema)
12. [Frontend: how pages are served](#12-frontend-how-pages-are-served)
13. [API proxy layer](#13-api-proxy-layer)
14. [Two SSE data paths](#14-two-sse-data-paths)
15. [Provider architecture](#15-provider-architecture)
16. [3D visualization architecture](#16-3d-visualization-architecture)
17. [Dashboard pages](#17-dashboard-pages)
18. [Security model](#18-security-model)
19. [Deployment](#19-deployment)
20. [End-to-end request walkthrough](#20-end-to-end-request-walkthrough)

---

## 1. Directory layout

```
ai-defender/
├── backend/
│   ├── honeypot/                     # Main application package
│   │   ├── app.py                    # Flask factory, routes, rate limiting, CORS, security headers
│   │   ├── protocol.py               # JSON-RPC 2.0 method router
│   │   ├── registry.py               # Tool dispatch, SSE event publishing, prompt summary builder
│   │   ├── session.py                # SessionManager (in-memory cache + SQLite write-through)
│   │   ├── engagement.py             # Escalation scoring, breadcrumb injection, transient errors
│   │   ├── tokens.py                 # HoneyTokenGenerator with 5 token types
│   │   ├── api.py                    # Flask Blueprint for /api/* REST + SSE endpoints
│   │   ├── simulators/
│   │   │   ├── base.py               # ToolSimulator ABC, SimulationResult dataclass
│   │   │   ├── nmap.py               # Network scanner simulator
│   │   │   ├── file_read.py          # File reader simulator
│   │   │   ├── shell_exec.py         # Shell command simulator
│   │   │   ├── sqlmap.py             # SQL injection simulator
│   │   │   ├── browser.py            # DevOps portal simulator
│   │   │   ├── dns_lookup.py         # Internal DNS zone simulator
│   │   │   ├── aws_cli.py            # AWS CLI simulator
│   │   │   ├── kubectl.py            # Kubernetes CLI simulator
│   │   │   ├── vault_cli.py          # HashiCorp Vault simulator
│   │   │   └── docker_registry.py    # Container registry simulator
│   │   └── Dockerfile                # Python 3.12-slim, Gunicorn
│   ├── shared/
│   │   ├── config.py                 # Frozen dataclass Config, env var loading
│   │   ├── db.py                     # SQLite schema, CRUD, WAL mode
│   │   ├── event_bus.py              # Thread-safe bounded deque pub/sub
│   │   └── validators.py             # SESSION_ID_RE regex, input validation
│   └── tests/                        # 20 test modules, 346 tests
├── app/                              # Next.js App Router
│   ├── layout.tsx                    # Root layout: dark mode, Geist fonts, <Providers>
│   ├── page.tsx                      # Homepage: LiveEventProvider + dynamic 3D import
│   ├── globals.css                   # TailwindCSS 4
│   ├── api/[...path]/route.ts        # Catch-all proxy to Flask backend
│   └── (dashboard)/                  # Route group with sidebar layout
│       ├── layout.tsx                # Sidebar + main area
│       ├── sessions/page.tsx         # Paginated sessions table
│       ├── sessions/[id]/page.tsx    # Session detail with tabs
│       ├── stats/page.tsx            # Aggregated analytics
│       └── tokens/page.tsx           # Global token inventory
├── components/
│   ├── providers.tsx                 # Wraps children in EventStreamProvider
│   ├── sidebar.tsx                   # Responsive sidebar with mobile hamburger
│   ├── visualization/
│   │   ├── attack-visualization.tsx  # Main container: Canvas + useReducer + overlays
│   │   ├── scene-setup.tsx           # Lighting, OrbitControls, post-processing bloom
│   │   ├── honeypot-core.tsx         # Central animated distorted sphere
│   │   ├── session-nodes.tsx         # Instanced orbiting nodes colored by escalation
│   │   ├── session-labels.tsx        # HTML labels floating above nodes
│   │   ├── connection-edges.tsx      # Animated lines from core to nodes
│   │   ├── particle-system.tsx       # Arc-trajectory particles colored by tool type
│   │   ├── orbital-utils.ts          # Math for distributing nodes in orbital rings
│   │   └── overlays/
│   │       ├── stats-overlay.tsx
│   │       ├── event-feed-overlay.tsx
│   │       ├── sessions-list-overlay.tsx
│   │       ├── session-detail-panel.tsx
│   │       └── prompt-monitor-overlay.tsx
│   └── ui/                           # Shadcn: badge, card, scroll-area, table, tabs
├── lib/
│   ├── types.ts                      # TypeScript interfaces
│   ├── api.ts                        # Server-side fetch helpers (SSR data loading)
│   ├── live-event-context.tsx        # React context wrapping useLiveStream
│   ├── event-stream-context.tsx      # React context wrapping useEventStream
│   ├── use-live-stream.ts            # EventSource: /api/events/live (event-driven)
│   ├── use-event-stream.ts           # EventSource: /api/events (polling-based)
│   ├── use-tts-announcer.ts          # Text-to-speech for attack events
│   └── utils.ts                      # cn(), formatRelativeTime()
├── docker-compose.yml                # frontend + honeypot services, persistent volume
├── Dockerfile                        # Multi-stage Next.js standalone build
├── next.config.ts                    # output: "standalone"
└── fly.toml                          # Fly.io deployment config
```

---

## 2. Backend: how the server starts

Entry point: `backend/honeypot/app.py`, function `create_app()`.

The factory builds every component the backend needs, in this order:

1. **Load configuration.** `shared/config.py` defines a frozen `Config` dataclass. Each
   field reads from an environment variable with a sensible default. Key fields:
   `db_path`, `host`, `port`, `session_ttl_seconds`, `dashboard_api_key`,
   `mcp_rate_limit`, `mcp_rate_window`, `cors_origin`. The `server_name` is
   `"internal-devops-tools"` and the `protocol_version` is `"2025-11-25"`.

2. **Initialize the database.** `shared/db.py` function `init_db()` creates the SQLite
   file, runs the schema DDL (WAL mode, foreign keys, three tables), and restricts
   file permissions to `0o600`.

3. **Create the EventBus.** `shared/event_bus.py` -- a thread-safe in-process pub/sub
   with a bounded `deque` of 200 events and monotonic IDs.

4. **Create the SessionManager.** `backend/honeypot/session.py` -- holds an in-memory
   `dict` cache of `SessionContext` objects with a write-through pattern to SQLite.
   Starts a background daemon thread that runs every 60 seconds to evict sessions
   older than `session_ttl_seconds` (default 3600s).

5. **Create the ToolRegistry.** `backend/honeypot/registry.py` -- holds a `dict` of
   simulator instances and an `EngagementEngine`. The call to `register_defaults()`
   imports and instantiates all 10 simulators.

6. **Create the ProtocolHandler.** `backend/honeypot/protocol.py` -- maps JSON-RPC
   method strings to handler functions.

7. **Create RateLimiters.** Two instances of the sliding-window `RateLimiter` class
   defined in `app.py`: one for the MCP endpoint (default 60 requests per 60 seconds
   per session) and one for the dashboard API (120 requests per 60 seconds per IP).

8. **Register the API Blueprint.** `backend/honeypot/api.py` is a Flask `Blueprint`
   mounted at `/api`.

9. **Add security headers.** An `@after_request` hook sets CORS, CSP, X-Frame-Options,
   X-Content-Type-Options, and Referrer-Policy on every response.

10. **Define routes.** Two routes on the app itself:
    - `GET /health` -- returns `{"status": "ok", ...}`
    - `POST /mcp` -- the MCP endpoint (see next section)

The app enforces a 1 MB request body limit via Flask's `MAX_CONTENT_LENGTH`.

---

## 3. The MCP endpoint and protocol routing

**File:** `backend/honeypot/app.py`, route `POST /mcp`.

When a request arrives at `/mcp`:

1. Validate that `Content-Type` contains `application/json`. Return JSON-RPC parse
   error (code -32700) if not.

2. Parse the JSON body. Return parse error if invalid.

3. Extract the `Mcp-Session-Id` header. If present, validate it against the regex
   `^[0-9a-f]{32}$` (defined in `shared/validators.py`). Return invalid request
   error (code -32600) if it does not match.

4. Rate-limit the request using the session ID as key (or the client IP if no
   session exists yet).

5. Pass the body and session ID to `ProtocolHandler.handle()`.

**File:** `backend/honeypot/protocol.py`, class `ProtocolHandler`.

The handler maintains a dispatch map:

| JSON-RPC method | Handler | Behavior |
|-----------------|---------|----------|
| `initialize` | `_handle_initialize` | Creates a new session via `SessionManager.create()`. Returns server capabilities and info. Sets the `Mcp-Session-Id` response header. |
| `notifications/initialized` | `_handle_notification_initialized` | Touches the session (increments interaction count). Returns HTTP 204 with no body (notification -- no `id` field). |
| `ping` | `_handle_ping` | Returns an empty result object. |
| `tools/list` | `_handle_tools_list` | Returns all 10 tools from `registry.list_tools()`. |
| `tools/call` | `_handle_tools_call` | Extracts `name` and `arguments` from `params`, touches the session, then calls `registry.dispatch()`. Returns the result as MCP content. |

Notifications (requests with no `id` field) receive no JSON response body -- the
route returns HTTP 204. Regular requests receive a standard JSON-RPC 2.0 response.

---

## 4. Tool registry and dispatch flow

**File:** `backend/honeypot/registry.py`, class `ToolRegistry`.

The `dispatch()` method is the central pipeline for every tool call. It executes the
following steps in sequence:

1. **Look up the simulator** by `tool_name` in the internal `_tools` dict. Return an
   error result if not found.

2. **Retrieve the session** from `SessionManager.get()`, which checks the in-memory
   cache first and falls back to SQLite.

3. **Count tokens before** the call by querying `get_session_token_count()` from the
   database.

4. **Call `simulator.simulate(arguments, session)`**, which returns a `SimulationResult`
   containing the output text, error flag, injected token IDs, and escalation delta.

5. **Count tokens after** the call (same query). The difference tells the registry how
   many new tokens were injected during the simulation.

6. **Capture output before enrichment** for injection detection.

7. **Compute escalation.** The `EngagementEngine.compute_escalation()` method evaluates
   the session's discovered hosts, files, credentials, and interaction count. If the
   computed level exceeds the current level, it is raised.

8. **Enrich output.** The `EngagementEngine.enrich_output()` method may prepend a
   transient error (10% chance after 5+ interactions) or append a contextual breadcrumb
   (30% chance, selected by escalation level).

9. **Detect injection.** By comparing the output before and after enrichment, the
   registry extracts the injected breadcrumb text (if any) for event publishing.

10. **Build prompt summary.** A `match`/`case` block in `_build_prompt_summary()` formats
    a short human-readable description of the tool call (for example, `"file_read: /etc/passwd"`).

11. **Log the interaction** to SQLite via `log_interaction()`.

12. **Publish SSE events** to the EventBus:
    - `interaction` event -- always published, includes `session_id`, `tool_name`,
      `arguments`, `escalation_delta`, `escalation_level`, `timestamp`,
      `prompt_summary`, and `injection` (the breadcrumb text or null).
    - `token_deployed` event -- published only if new tokens were injected, includes
      `session_id`, `tool_name`, `count`, and `total_tokens`.
    - `session_update` event -- published only if escalation changed, includes
      `session_id`, `escalation_level`, and `interaction_count`.

13. **Persist session state** back to SQLite.

---

## 5. Simulator pattern

**File:** `backend/honeypot/simulators/base.py`.

All 10 simulators extend the `ToolSimulator` abstract base class:

```python
class ToolSimulator(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    def simulate(self, arguments: dict, session: SessionContext) -> SimulationResult: ...
```

Each simulator's constructor receives the `Config` object. The `simulate()` method:

- Parses tool arguments according to the tool's domain logic.
- Produces realistic-looking fake output (file contents, scan results, command output).
- Calls `HoneyTokenGenerator.generate()` to create traceable credentials.
- Calls `log_honey_token()` to persist the token to SQLite.
- Calls `session.add_credential()` (and `add_host()`, `add_file()`, etc.) to update
  the session's discovery state (which drives escalation scoring).
- Returns a `SimulationResult` with `output`, `is_error`, `injected_token_ids`, and
  `escalation_delta`.

The 10 simulators:

| File | Tool name | Category | Token density |
|------|-----------|----------|---------------|
| `nmap.py` | `nmap_scan` | Recon | None |
| `file_read.py` | `file_read` | Credential theft | Up to 3 per .env file |
| `shell_exec.py` | `shell_exec` | Credential theft | None |
| `sqlmap.py` | `sqlmap_scan` | Credential theft | Varies by table |
| `browser.py` | `browser_navigate` | Credential theft | Up to 2 |
| `dns_lookup.py` | `dns_lookup` | Recon | None |
| `aws_cli.py` | `aws_cli` | Credential use | AWS key, DB, API |
| `kubectl.py` | `kubectl` | Lateral movement | DB, API, SSH, Admin |
| `vault_cli.py` | `vault_cli` | Lateral movement | All 5 types |
| `docker_registry.py` | `docker_registry` | Lateral movement | DB, API |

---

## 6. Honey token generation and traceability

**File:** `backend/honeypot/tokens.py`, class `HoneyTokenGenerator`.

Five token types are defined as the `TokenType` enum:

| Type | Format | Traceability |
|------|--------|-------------|
| `AWS_ACCESS_KEY` | `AKIA` + 8-char session hash (uppercased) + 12 random chars | Session hash in key ID |
| `API_TOKEN` | JWT-like: `eyJ{header}.{tag + random}.{signature}` | Session hash in payload segment |
| `DB_CREDENTIAL` | `postgresql://admin:{tag + random}@db-internal.corp.local:5432/production` | Session hash in password |
| `ADMIN_LOGIN` | `admin:Adm1n{tag}{random}` | Session hash in password |
| `SSH_KEY` | OpenSSH private key format with tag embedded at offset 16 in key body | Session hash in key material |

The `tag` is the first 8 characters of the SHA-256 hex digest of the `session_id`.
This allows any token observed in the wild to be traced back to the specific
attacker session that received it.

---

## 7. Engagement engine: escalation and breadcrumbs

**File:** `backend/honeypot/engagement.py`, class `EngagementEngine`.

### Escalation scoring

The engine computes an escalation level (0-3) from the session's accumulated state:

| Condition | Points |
|-----------|--------|
| 2+ discovered hosts | +1 |
| 2+ discovered files | +1 |
| 1+ discovered credentials | +1 |
| 10+ interactions | +1 |

The score is capped at 3.

### Breadcrumb injection

When `enrich_output()` is called, two things can happen (mutually exclusive):

1. **Transient error injection** (10% chance, only after 5+ interactions). A realistic
   error message like `"503 Service Temporarily Unavailable"` is prepended to the
   output. This adds realism.

2. **Breadcrumb injection** (30% chance, if no transient error). A contextual hint is
   appended as a comment line (`# Breadcrumb: ...`). Breadcrumbs are organized by
   escalation level, guiding the attacker deeper. Level 0 breadcrumbs hint at network
   ranges; level 3 breadcrumbs point to production databases and root SSH keys.

---

## 8. Session management

**File:** `backend/honeypot/session.py`.

### SessionContext

A dataclass that holds all mutable state for one attacker session:

- `session_id` -- 32 hex chars (UUID4 without dashes)
- `client_info` -- the `clientInfo` dict from the MCP `initialize` request
- `escalation_level` -- integer 0-3
- `discovered_hosts`, `discovered_ports`, `discovered_files`, `discovered_credentials` -- lists
- `interaction_count` -- incremented on every `touch()`

### SessionManager

Uses a write-through cache pattern:

- **`create(client_info)`** -- generates a UUID4 hex session ID, creates a
  `SessionContext`, caches it in memory, writes it to SQLite, and publishes a
  `session_new` SSE event.

- **`get(session_id)`** -- checks the in-memory `_cache` dict first. On a miss,
  loads from SQLite, reconstructs the `SessionContext`, and re-caches it.

- **`touch(session_id)`** -- increments `interaction_count` and refreshes the cache
  timestamp. Used by protocol handlers for `tools/list`, `tools/call`, and
  `notifications/initialized`.

- **`persist(session_id)`** -- writes the current in-memory state back to SQLite
  via `update_session()`.

A background daemon thread runs every 60 seconds. It evicts cache entries whose
timestamp is older than `session_ttl_seconds` (default 3600). The `shutdown()` method
signals the thread to stop and joins it with a 5-second timeout. The thread is stopped
on `SIGTERM` and via `atexit`.

---

## 9. EventBus and real-time streaming

**File:** `backend/shared/event_bus.py`, class `EventBus`.

The bus is a thread-safe in-process pub/sub mechanism that connects the backend
dispatch pipeline to the SSE endpoints.

- **Bounded deque.** Holds a maximum of 200 events. Older events are discarded
  automatically by the `deque(maxlen=200)`.

- **Monotonic IDs.** Each event gets an auto-incrementing integer ID from
  `itertools.count(1)`. These IDs serve as SSE `id:` fields and support
  `Last-Event-ID` reconnection.

- **Subscribers.** Each SSE connection calls `subscribe()`, which returns a
  `threading.Event` object and the current last event ID. The SSE generator loop
  calls `notify.wait(timeout=1.0)` and then `events_since(last_id)` to collect
  any new events. When the bus publishes, it calls `.set()` on every subscriber's
  `threading.Event`, waking them up.

- **Unsubscribe.** Called in the SSE generator's `finally` block to clean up when
  the client disconnects or the stream reaches its maximum duration.

Event types published by the backend:

| Event type | Published by | Data fields |
|------------|-------------|-------------|
| `session_new` | `SessionManager.create()` | `session_id`, `client_info`, `escalation_level`, `timestamp` |
| `interaction` | `ToolRegistry.dispatch()` | `session_id`, `tool_name`, `arguments`, `escalation_delta`, `escalation_level`, `timestamp`, `prompt_summary`, `injection` |
| `token_deployed` | `ToolRegistry.dispatch()` | `session_id`, `tool_name`, `count`, `total_tokens`, `timestamp` |
| `session_update` | `ToolRegistry.dispatch()` | `session_id`, `escalation_level`, `interaction_count` |

---

## 10. Dashboard REST API

**File:** `backend/honeypot/api.py`, Blueprint `api_bp` at prefix `/api`.

### Request-level middleware

Two `@before_request` hooks run on every API request:

1. **Rate limiting.** Uses the `DASHBOARD_RATE_LIMITER` (120 requests per 60 seconds
   per client IP).

2. **API key authentication.** If `DASHBOARD_API_KEY` is set in the config, the request
   must include `Authorization: Bearer <key>`. Comparison uses `secrets.compare_digest`
   to prevent timing attacks.

### REST endpoints

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/stats` | GET | Aggregated counts: total/active sessions, avg escalation, total interactions, total tokens, tool usage breakdown, token type breakdown, escalation distribution |
| `/api/sessions` | GET | Paginated session list. Supports `escalation_level`, `since` (ISO 8601), `limit`, `offset` query params |
| `/api/sessions/<id>` | GET | Single session with `interaction_count` and `token_count` |
| `/api/sessions/<id>/interactions` | GET | Paginated interaction list for a session |
| `/api/sessions/<id>/tokens` | GET | All honey tokens deployed in a session |
| `/api/tokens` | GET | Paginated global token list. Supports `token_type` filter |
| `/api/admin/reset` | POST | Deletes all sessions (cascades to interactions and tokens), clears session cache, publishes zeroed stats via EventBus |
| `/api/admin/simulate` | POST | Accepts `{"count": N}` (clamped 1-20). Creates N sessions with random attacker names from a 16-name pool, spawns background threads that run 4-8 tool calls each with 1-2 second random delays. Returns immediately with `{"launched": N, "session_ids": [...]}` |

Pagination is clamped: limit between 1 and 200, offset minimum 0.

### SSE endpoints

| Endpoint | Mechanism | Purpose |
|----------|-----------|---------|
| `/api/events` | Polling-based | Queries the database every N seconds (default 2, configurable 2-30). Sends `stats` snapshots when they change, heartbeats otherwise. |
| `/api/events/live` | Event-driven via EventBus | Pushes individual typed events (`interaction`, `session_new`, `session_update`, `token_deployed`) with sub-second latency. Supports `Last-Event-ID` for reconnection catch-up. Sends initial `stats` snapshot on connect. |

Both SSE endpoints enforce:
- Maximum 10 concurrent connections (tracked per-app via `SSE_STATE` dict with a lock).
- Maximum 5-minute connection lifetime. A `reconnect` event is sent when the limit
  is reached, prompting the client to reconnect.
- 1-second heartbeat interval (live) or configurable poll interval (events).

---

## 11. SQLite database schema

**File:** `backend/shared/db.py`.

Three tables with WAL mode and foreign keys:

```sql
CREATE TABLE sessions (
    id                     TEXT PRIMARY KEY,
    client_info            TEXT NOT NULL DEFAULT '{}',
    started_at             TEXT NOT NULL,
    last_seen_at           TEXT NOT NULL,
    escalation_level       INTEGER NOT NULL DEFAULT 0,
    discovered_hosts       TEXT NOT NULL DEFAULT '[]',
    discovered_ports       TEXT NOT NULL DEFAULT '[]',
    discovered_files       TEXT NOT NULL DEFAULT '[]',
    discovered_credentials TEXT NOT NULL DEFAULT '[]',
    metadata               TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE interactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    timestamp        TEXT NOT NULL,
    method           TEXT NOT NULL,
    tool_name        TEXT,
    params           TEXT NOT NULL DEFAULT '{}',
    response         TEXT NOT NULL DEFAULT '{}',
    escalation_delta INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE honey_tokens (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    token_type     TEXT NOT NULL,
    token_value    TEXT NOT NULL,
    context        TEXT NOT NULL DEFAULT '',
    deployed_at    TEXT NOT NULL,
    interaction_id INTEGER REFERENCES interactions(id) ON DELETE SET NULL
);
```

Indexes on `interactions.session_id`, `honey_tokens.session_id`, and
`honey_tokens.token_value`.

List and dict columns (`client_info`, `discovered_*`, `params`, `response`,
`metadata`) are stored as JSON text and parsed on read.

---

## 12. Frontend: how pages are served

**File:** `app/layout.tsx` (root layout), `app/page.tsx` (homepage).

The frontend is a Next.js 16 application using the App Router with React 19.
The `next.config.ts` sets `output: "standalone"` for minimal production builds.

### Root layout (`app/layout.tsx`)

Every page is wrapped in:

```
<html lang="en" className="dark">
  <body className="{GeistSans.variable} {GeistMono.variable} antialiased">
    <Providers>{children}</Providers>
  </body>
</html>
```

The `<Providers>` component (`components/providers.tsx`) wraps all children in an
`EventStreamProvider`, which opens the polling-based SSE connection to `/api/events`
for global stats and connection status.

### Two rendering modes

1. **Client-only (the homepage).** `app/page.tsx` dynamically imports the
   `AttackVisualization` component with `ssr: false` and wraps it in a
   `LiveEventProvider`. This ensures Three.js and React Three Fiber never run on the
   server. A loading screen with a spinner is shown while the 3D module loads.

2. **Server-side rendered (dashboard pages).** Pages under `app/(dashboard)/` fetch
   data from Flask via `lib/api.ts` server-side helpers (using `fetch()` with
   `cache: "no-store"`). These pages render complete HTML on the server before
   sending it to the browser.

---

## 13. API proxy layer

**File:** `app/api/[...path]/route.ts`.

This is a Next.js catch-all route handler that proxies every `/api/*` request from
the browser to Flask on port 5000. The upstream URL is configured via the `API_URL`
environment variable (default `http://localhost:5000`).

For **SSE endpoints** (any path starting with `events`): the handler fetches the
upstream response and streams its body through as-is, setting the `Content-Type` to
`text/event-stream`.

For **JSON GET endpoints**: the handler fetches the upstream response, reads the body as
text, and forwards it with the original status code and content type.

For **POST endpoints** (e.g. admin actions): the handler reads the request body as text,
forwards it to Flask with `Content-Type: application/json`, and returns the upstream
response.

If `DASHBOARD_API_KEY` is configured, the proxy injects an `Authorization: Bearer`
header into the upstream request. This means the browser does not need the API key --
it is handled server-side by the proxy. A shared `baseHeaders()` helper constructs the
common headers for both GET and POST handlers.

---

## 14. Two SSE data paths

The application uses two separate SSE connections for different purposes:

### Path 1: Polling-based SSE (global stats)

```
Browser EventSource(/api/events)
  -> Next.js proxy (app/api/[...path]/route.ts)
    -> Flask GET /api/events
      -> polls SQLite every 2s
      -> sends stats snapshots when changed
```

- **Frontend hook:** `lib/use-event-stream.ts`, function `useEventStream()`
- **Context:** `lib/event-stream-context.tsx`, `EventStreamProvider`
- **Wraps:** all pages (via root layout `<Providers>`)
- **Provides:** `stats`, `connected`, `error`
- **Purpose:** global connection status indicator and stats counters on every page

### Path 2: Event-driven SSE (live interactions)

```
Browser EventSource(/api/events/live)
  -> Next.js proxy (app/api/[...path]/route.ts)
    -> Flask GET /api/events/live
      -> subscribes to EventBus
      -> pushes typed events (interaction, session_new, session_update, token_deployed)
```

- **Frontend hook:** `lib/use-live-stream.ts`, function `useLiveStream()`
- **Context:** `lib/live-event-context.tsx`, `LiveEventProvider`
- **Wraps:** homepage only
- **Provides:** `stats`, `connected`, `error`, `recentInteractions`, `subscribe()`
- **Purpose:** real-time 3D visualization updates

Both hooks implement exponential backoff reconnection: base delay of 1 second, maximum
delay of 30 seconds, maximum 8 retries. Both handle the server's `reconnect` event
(sent when the 5-minute SSE connection lifetime expires) by reconnecting immediately.

The `useLiveStream` hook maintains a ring buffer of the 50 most recent
`InteractionEvent` objects in `recentInteractions`. It also exposes a `subscribe()`
function that returns an unsubscribe callback. Subscribers receive every `LiveEvent`
(a discriminated union type) as it arrives.

---

## 15. Provider architecture

Two nested React context providers manage SSE connections:

```
RootLayout
  └── <Providers>                          (components/providers.tsx)
        └── <EventStreamProvider>          (lib/event-stream-context.tsx)
              │   Opens EventSource to /api/events
              │   Provides: stats, connected, error
              │
              └── {children}               (all pages)

Homepage (app/page.tsx)
  └── <LiveEventProvider>                  (lib/live-event-context.tsx)
        │   Opens EventSource to /api/events/live
        │   Provides: stats, connected, error, recentInteractions, subscribe()
        │
        └── <AttackVisualization />
```

The `subscribe()` function exposed by `LiveEventProvider` is the primary mechanism
for components to receive real-time events. Components call `subscribe(callback)` and
receive an unsubscribe function in return. The following consumers use this pattern:

- `attack-visualization.tsx` -- dispatches `useReducer` actions to update session node
  state
- `prompt-monitor-overlay.tsx` -- appends entries to the prompt monitor feed
- `use-tts-announcer.ts` -- speaks attack events via the Web Speech API

---

## 16. 3D visualization architecture

**Files:** `components/visualization/`.

The homepage renders a full-screen `<Canvas>` (React Three Fiber) with absolute-positioned
HTML overlays on top.

### Inside the Canvas

| Component | File | Purpose |
|-----------|------|---------|
| `SceneSetup` | `scene-setup.tsx` | Ambient and directional lighting, `OrbitControls` (zoom range 8-40), post-processing bloom via `EffectComposer` |
| `HoneypotCore` | `honeypot-core.tsx` | Central animated sphere with displacement distortion and emissive glow, representing the honeypot server |
| `SessionNodes` | `session-nodes.tsx` | Instanced mesh rendering of orbiting spherical nodes. Each node represents an attacker session. Color is determined by escalation level: green (0), yellow (1), orange (2), red (3) |
| `ConnectionEdges` | `connection-edges.tsx` | Animated lines from the honeypot core to each session node |
| `SessionLabels` | `session-labels.tsx` | HTML labels floating above each session node showing truncated session ID |
| `ParticleSystem` | `particle-system.tsx` | Object-pooled particles that travel in arc trajectories from session nodes toward the core. Each particle is colored by tool type |

### Outside the Canvas (HTML overlays)

| Overlay | Position | Content |
|---------|----------|---------|
| `StatsOverlay` | Top bar | Connection status dot (green/red), session count, interaction count, token count |
| `EventFeedOverlay` | Top right | Scrolling list of last 50 interactions with tool-colored badges and timestamps |
| `SessionsListOverlay` | Left panel | Active sessions sorted by escalation level descending. Clicking a session selects it |
| `SessionDetailPanel` | Left panel (replaces list on select) | Detailed view of the selected session: interactions, client info, close button |
| `PromptMonitorOverlay` | Bottom left | Three entry types: ATTACKER (tool call with arguments), HONEYPOT LURE (breadcrumb injection), TOKEN DEPLOYED (credential injection) |
| `ControlBar` | Bottom center | Admin controls: Reset button (double-click confirmation with 3s timeout), count input (1-20), Launch button (triggers simulated attacks). Loading spinner while requests are in-flight |
| `NavButton` | Bottom right | Link to the dashboard stats page |

### State management

The `attack-visualization.tsx` component manages state with `useReducer`. The state
is a `Map<string, SessionNodeData>` plus an optional `selectedSessionId`.

| Action | Source | Effect |
|--------|--------|--------|
| `INIT` | REST `fetch("/api/sessions?limit=200")` on mount | Populates the map with existing sessions |
| `SESSION_NEW` | `session_new` SSE event via `subscribe()` | Adds a new session node to the map |
| `SESSION_UPDATE` | `session_update` SSE event | Updates escalation level and interaction count |
| `INTERACTION` | `interaction` SSE event | Increments interaction count and updates escalation level |
| `SELECT_SESSION` | User click on session node or list entry | Sets the selected session ID for detail panel |

---

## 17. Dashboard pages

**File:** `app/(dashboard)/layout.tsx` provides a sidebar + main content area layout.

| Page | File | Rendering | Data source |
|------|------|-----------|-------------|
| Sessions list | `sessions/page.tsx` | Server-side | `fetchApi("/api/sessions")` with pagination and escalation filter |
| Session detail | `sessions/[id]/page.tsx` | Server-side | `fetchApi("/api/sessions/{id}")`, `/interactions`, `/tokens` |
| Stats | `stats/page.tsx` | Server-side | `fetchApi("/api/stats")` |
| Tokens | `tokens/page.tsx` | Server-side | `fetchApi("/api/tokens")` with type filter |

The `lib/api.ts` file provides `fetchApi()`, a helper that builds a URL to the Flask
backend (server-to-server, no proxy needed), sets `cache: "no-store"`, and injects
the `DASHBOARD_API_KEY` Bearer token if configured.

---

## 18. Security model

### Network isolation

- The browser communicates only with Next.js on port 3000.
- Next.js proxies API requests to Flask on port 5000 (server-to-server).
- Flask is not directly exposed to external clients in production.

### Request validation

- MCP session IDs are validated against `^[0-9a-f]{32}$`.
- Pagination params are clamped to safe ranges (limit 1-200, offset >= 0).
- ISO date params are validated before use.
- Token type params are checked against an allowlist of 5 values.
- Request body size is limited to 1 MB.

### Rate limiting

- MCP endpoint: 60 requests per 60 seconds per session (configurable).
- Dashboard API: 120 requests per 60 seconds per client IP.
- SSE endpoints: maximum 10 concurrent connections, 5-minute lifetime.

### Authentication

- Dashboard API supports optional Bearer token auth via `DASHBOARD_API_KEY`.
- The Next.js proxy injects this token on the server side, so the browser never
  holds the key.

### Response headers

Every Flask response includes:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
- `Referrer-Policy: no-referrer`
- CORS is restricted to the configured origin (default `http://localhost:3000`).

### Data protection

- SQLite file permissions are set to `0o600` (owner read/write only).
- API key comparison uses `secrets.compare_digest` (timing-safe).
- HTML metadata includes `robots: { index: false, follow: false }`.

---

## 19. Deployment

### Docker Compose (`docker-compose.yml`)

Two services:

**`honeypot`** (backend):
- Built from `backend/honeypot/Dockerfile`.
- Multi-stage build: `python:3.12-slim` builder installs deps, then copies into a
  clean runtime image.
- Runs as non-root `honeypot` user.
- Gunicorn with 2 workers, 4 threads per worker (`gthread` worker class), 310-second
  timeout (accommodates 300-second SSE streams).
- Health check: Python urllib request to `http://localhost:5000/health` every 30 seconds.
- Persistent volume at `/data` for the SQLite database.

**`frontend`** (Next.js):
- Built from the root `Dockerfile`.
- Multi-stage build: `node:20-alpine` installs deps, builds the standalone Next.js
  output, then copies into a clean runtime image.
- Runs as non-root `nextjs` user.
- Depends on honeypot service health check passing.

### Fly.io (Two-App Architecture)

The application is deployed as two separate Fly apps:

**`ai-defender`** (frontend) -- configured in `fly.toml` at project root:
- Public URL: https://ai-defender.fly.dev
- Amsterdam region, `shared-cpu-1x`, 256 MB RAM.
- Env var `API_URL=http://ai-defender-api.internal:5000` routes API proxy to backend over Fly's internal private network.
- Auto-stop when idle, auto-start on request.

**`ai-defender-api`** (backend) -- configured in `backend/fly.toml`:
- Public URL: https://ai-defender-api.fly.dev
- Amsterdam region, `shared-cpu-1x`, 256 MB RAM.
- Persistent volume `honeypot_data` at `/data` for SQLite.
- Health checks every 30 seconds on `GET /health`.
- CORS origin set to `https://ai-defender.fly.dev`.
- MCP endpoint (`POST /mcp`) publicly accessible for AI agents.
- Auto-stop when idle, auto-start on request.

The frontend proxies all `/api/*` browser requests to the backend over the internal network. The browser never talks directly to Flask.

---

## 20. End-to-end request walkthrough

This section traces what happens when an AI agent connects to the honeypot and
makes a tool call, and how that activity appears on the dashboard.

### Step 1: The agent initializes a session

The agent sends a JSON-RPC 2.0 request to `POST /mcp`:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "clientInfo": { "name": "rogue-agent", "version": "1.0" }
  }
}
```

- `app.py` validates the content type and parses JSON.
- `ProtocolHandler.handle()` routes to `_handle_initialize()`.
- `SessionManager.create()` generates a UUID4 hex ID (e.g., `a1b2c3...`), creates
  a `SessionContext`, caches it in memory, writes it to SQLite, and publishes a
  `session_new` event to the EventBus.
- The response includes capabilities and the new session ID as an `Mcp-Session-Id`
  header.

On the dashboard: if anyone is viewing the 3D visualization, the `session_new` SSE
event flows through the EventBus, into the `/api/events/live` SSE stream, through
the Next.js proxy, into the browser's `useLiveStream` hook, through the `subscribe()`
callbacks, and into the `useReducer` dispatch as a `SESSION_NEW` action. A new node
appears in the 3D scene.

### Step 2: The agent lists available tools

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {},
  "Mcp-Session-Id": "a1b2c3..."
}
```

The handler calls `registry.list_tools()`, which iterates over all 10 registered
simulators and returns their `name`, `description`, and `inputSchema`. The session is
touched (interaction count incremented).

### Step 3: The agent calls a tool

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "file_read",
    "arguments": { "path": "/app/.env" }
  }
}
```

- `ProtocolHandler` routes to `_handle_tools_call()`.
- `ToolRegistry.dispatch("file_read", {"path": "/app/.env"}, "a1b2c3...")` runs.
- `FileReadSimulator.simulate()` produces fake `.env` file contents with up to 3
  embedded honey tokens (e.g., `AWS_ACCESS_KEY`, `DB_CREDENTIAL`, `API_TOKEN`).
- Each token is generated with the session's 8-char SHA-256 tag, logged to SQLite,
  and added to the session's `discovered_credentials` list.
- Back in `dispatch()`: escalation is computed (now 1+ credential => level increases),
  output is enriched (possible breadcrumb like `"# Breadcrumb: Admin panel at /admin
  uses default credentials from config.yaml"`), the interaction is logged, and SSE
  events are published.

On the dashboard:
- The `interaction` event appears in the event feed overlay as a purple `file_read`
  badge with `/app/.env`.
- The prompt monitor shows an ATTACKER entry with the tool call, possibly a HONEYPOT
  LURE entry with the breadcrumb, and TOKEN DEPLOYED entries for each credential.
- The session node changes color if the escalation level increased.
- A particle arcs from the session node toward the honeypot core.
- The TTS announcer may speak the event aloud.

### Step 4: Ongoing monitoring

As the agent continues calling tools, each interaction follows the same pipeline. The
escalation level rises as the agent discovers more hosts, files, and credentials. The
engagement engine injects increasingly valuable breadcrumbs, guiding the attacker
toward simulated production databases, Kubernetes APIs, and root SSH keys -- all
monitored, all traceable.

Dashboard operators can click on a session node in the 3D view to open the detail
panel, or navigate to the `/sessions/{id}` page for a complete timeline, token
inventory, and discovery state. The `/stats` page shows aggregate analytics across
all sessions.
