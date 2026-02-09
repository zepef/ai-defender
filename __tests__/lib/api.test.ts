import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { getStats, getSessions, getSession, getSessionInteractions, getSessionTokens, getTokens } from "@/lib/api";

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(data),
  });
}

describe("fetchApi internals", () => {
  it("throws on non-ok response", async () => {
    mockFetch.mockReturnValue(jsonResponse({}, 500));
    await expect(getStats()).rejects.toThrow("API error: 500");
  });

  it("calls correct base URL", async () => {
    mockFetch.mockReturnValue(jsonResponse({ total_sessions: 0, active_sessions: 0, avg_escalation: 0, total_interactions: 0, total_tokens: 0, tool_usage: {}, token_type_breakdown: {}, escalation_distribution: {} }));
    await getStats();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/stats"),
      expect.objectContaining({ cache: "no-store" }),
    );
  });
});

describe("getStats", () => {
  it("returns dashboard stats", async () => {
    const stats = { total_sessions: 5, active_sessions: 2, avg_escalation: 1.5, total_interactions: 42, total_tokens: 7, tool_usage: { nmap_scan: 3 }, token_type_breakdown: { aws_access_key: 2 }, escalation_distribution: { "0": 3 } };
    mockFetch.mockReturnValue(jsonResponse(stats));
    const result = await getStats();
    expect(result).toEqual(stats);
  });
});

describe("getSessions", () => {
  it("builds query string from params", async () => {
    mockFetch.mockReturnValue(jsonResponse({ sessions: [], total: 0, limit: 50, offset: 0 }));
    await getSessions({ escalation_level: 2, limit: 10, offset: 5 });
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("escalation_level=2");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=5");
  });

  it("omits empty params", async () => {
    mockFetch.mockReturnValue(jsonResponse({ sessions: [], total: 0, limit: 50, offset: 0 }));
    await getSessions();
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toMatch(/\/api\/sessions$/);
  });

  it("includes since param", async () => {
    mockFetch.mockReturnValue(jsonResponse({ sessions: [], total: 0, limit: 50, offset: 0 }));
    await getSessions({ since: "2025-01-01T00:00:00Z" });
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("since=");
  });
});

describe("getSession", () => {
  it("fetches session by id", async () => {
    const session = { id: "abc123", client_info: {}, started_at: "", last_seen_at: "", escalation_level: 0, discovered_hosts: [], discovered_ports: [], discovered_files: [], discovered_credentials: [], metadata: {}, interaction_count: 0, token_count: 0 };
    mockFetch.mockReturnValue(jsonResponse(session));
    const result = await getSession("abc123");
    expect(result.id).toBe("abc123");
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("/api/sessions/abc123");
  });
});

describe("getSessionInteractions", () => {
  it("fetches interactions with pagination", async () => {
    mockFetch.mockReturnValue(jsonResponse({ interactions: [], total: 0 }));
    await getSessionInteractions("abc123", { limit: 20, offset: 10 });
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("/api/sessions/abc123/interactions");
    expect(url).toContain("limit=20");
    expect(url).toContain("offset=10");
  });
});

describe("getSessionTokens", () => {
  it("fetches tokens for a session", async () => {
    const tokens = { tokens: [{ id: 1, token_type: "aws_access_key", token_value: "AKIA...", context: "env", deployed_at: "", interaction_id: null }], total: 1 };
    mockFetch.mockReturnValue(jsonResponse(tokens));
    const result = await getSessionTokens("abc123");
    expect(result.total).toBe(1);
  });
});

describe("getTokens", () => {
  it("fetches all tokens with type filter", async () => {
    mockFetch.mockReturnValue(jsonResponse({ tokens: [], total: 0, limit: 50, offset: 0 }));
    await getTokens({ token_type: "aws_access_key", limit: 5 });
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("token_type=aws_access_key");
    expect(url).toContain("limit=5");
  });

  it("fetches all tokens without filters", async () => {
    mockFetch.mockReturnValue(jsonResponse({ tokens: [], total: 0, limit: 50, offset: 0 }));
    await getTokens();
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toMatch(/\/api\/tokens$/);
  });
});
