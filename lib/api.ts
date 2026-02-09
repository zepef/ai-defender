import type {
  DashboardStats,
  HoneyToken,
  Interaction,
  Session,
  SessionDetail,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getStats(): Promise<DashboardStats> {
  return fetchApi<DashboardStats>("/api/stats");
}

export async function getSessions(params?: {
  escalation_level?: number;
  since?: string;
  limit?: number;
  offset?: number;
}): Promise<{ sessions: Session[]; total: number; limit: number; offset: number }> {
  const qs = new URLSearchParams();
  if (params?.escalation_level !== undefined) qs.set("escalation_level", String(params.escalation_level));
  if (params?.since) qs.set("since", params.since);
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return fetchApi(`/api/sessions${query ? `?${query}` : ""}`);
}

export async function getSession(id: string): Promise<SessionDetail> {
  return fetchApi<SessionDetail>(`/api/sessions/${id}`);
}

export async function getSessionInteractions(
  id: string,
  params?: { limit?: number; offset?: number }
): Promise<{ interactions: Interaction[]; total: number }> {
  const qs = new URLSearchParams();
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return fetchApi(`/api/sessions/${id}/interactions${query ? `?${query}` : ""}`);
}

export async function getSessionTokens(
  id: string
): Promise<{ tokens: HoneyToken[]; total: number }> {
  return fetchApi(`/api/sessions/${id}/tokens`);
}

export async function getTokens(params?: {
  token_type?: string;
  limit?: number;
  offset?: number;
}): Promise<{ tokens: HoneyToken[]; total: number; limit: number; offset: number }> {
  const qs = new URLSearchParams();
  if (params?.token_type) qs.set("token_type", params.token_type);
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return fetchApi(`/api/tokens${query ? `?${query}` : ""}`);
}
