import { NextRequest } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:5000";
const API_KEY = process.env.DASHBOARD_API_KEY || "";

function baseHeaders(request: NextRequest): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: request.headers.get("accept") || "application/json",
  };
  if (API_KEY) {
    headers["Authorization"] = `Bearer ${API_KEY}`;
  }
  return headers;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const upstream = `${API_URL}/api/${path.join("/")}${request.nextUrl.search}`;
  const headers = baseHeaders(request);

  // SSE: stream the response through
  if (path[0] === "events") {
    const res = await fetch(upstream, { headers });
    if (!res.ok) {
      return new Response(JSON.stringify({ error: "upstream error" }), {
        status: res.status,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(res.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  }

  const res = await fetch(upstream, { headers });
  const data = await res.text();
  return new Response(data, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") || "application/json" },
  });
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const upstream = `${API_URL}/api/${path.join("/")}`;
  const headers = baseHeaders(request);
  headers["Content-Type"] = "application/json";

  const body = await request.text();
  const res = await fetch(upstream, { method: "POST", headers, body });
  const data = await res.text();
  return new Response(data, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("content-type") || "application/json" },
  });
}
