export interface Session {
  id: string;
  client_info: Record<string, string>;
  started_at: string;
  last_seen_at: string;
  escalation_level: number;
  interaction_count: number;
  token_count: number;
}

export interface SessionDetail {
  id: string;
  client_info: Record<string, string>;
  started_at: string;
  last_seen_at: string;
  escalation_level: number;
  discovered_hosts: string[];
  discovered_ports: string[];
  discovered_files: string[];
  discovered_credentials: string[];
  metadata: Record<string, unknown>;
  interaction_count: number;
  token_count: number;
}

export interface Interaction {
  id: number;
  timestamp: string;
  method: string;
  tool_name: string | null;
  params: Record<string, unknown>;
  response: Record<string, unknown>;
  escalation_delta: number;
}

export interface HoneyToken {
  id: number;
  session_id?: string;
  token_type: string;
  token_value: string;
  context: string;
  deployed_at: string;
  interaction_id: number | null;
}

export interface DashboardStats {
  total_sessions: number;
  active_sessions: number;
  avg_escalation: number;
  total_interactions: number;
  total_tokens: number;
  tool_usage: Record<string, number>;
  token_type_breakdown: Record<string, number>;
  escalation_distribution: Record<string, number>;
}

export interface InteractionEvent {
  session_id: string;
  tool_name: string;
  arguments?: Record<string, unknown>;
  escalation_delta: number;
  escalation_level: number;
  timestamp: string;
  prompt_summary?: string;
  injection?: string;
}

export interface SessionNewEvent {
  session_id: string;
  client_info: Record<string, string>;
  escalation_level: number;
  timestamp: string;
}

export interface SessionUpdateEvent {
  session_id: string;
  escalation_level: number;
  interaction_count: number;
}

export interface TokenDeployedEvent {
  session_id: string;
  tool_name: string;
  count: number;
  total_tokens: number;
  timestamp: string;
}

export type LiveEvent =
  | { type: "interaction"; data: InteractionEvent }
  | { type: "session_new"; data: SessionNewEvent }
  | { type: "session_update"; data: SessionUpdateEvent }
  | { type: "token_deployed"; data: TokenDeployedEvent }
  | { type: "stats"; data: DashboardStats };
