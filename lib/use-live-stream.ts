"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type {
  DashboardStats,
  InteractionEvent,
  LiveEvent,
} from "./types";

const MAX_RETRIES = 8;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;
const RING_BUFFER_SIZE = 50;

type LiveEventCallback = (event: LiveEvent) => void;

export function useLiveStream() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentInteractions, setRecentInteractions] = useState<InteractionEvent[]>([]);
  const esRef = useRef<EventSource | null>(null);
  const retryCount = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const subscribersRef = useRef<Set<LiveEventCallback>>(new Set());

  const subscribe = useCallback((callback: LiveEventCallback) => {
    subscribersRef.current.add(callback);
    return () => {
      subscribersRef.current.delete(callback);
    };
  }, []);

  const notify = useCallback((event: LiveEvent) => {
    for (const cb of subscribersRef.current) {
      cb(event);
    }
  }, []);

  useEffect(() => {
    function connect() {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }

      const es = new EventSource("/api/events/live");
      esRef.current = es;

      es.onopen = () => {
        setConnected(true);
        setError(null);
        retryCount.current = 0;
      };

      es.addEventListener("stats", (e) => {
        try {
          const data = JSON.parse(e.data) as DashboardStats;
          setStats(data);
          notify({ type: "stats", data });
        } catch { /* ignore */ }
      });

      es.addEventListener("interaction", (e) => {
        try {
          const data = JSON.parse(e.data) as InteractionEvent;
          setRecentInteractions((prev) => {
            const next = [data, ...prev];
            return next.length > RING_BUFFER_SIZE ? next.slice(0, RING_BUFFER_SIZE) : next;
          });
          setStats((prev) => prev ? {
            ...prev,
            total_interactions: prev.total_interactions + 1,
            tool_usage: {
              ...prev.tool_usage,
              [data.tool_name]: (prev.tool_usage[data.tool_name] || 0) + 1,
            },
          } : prev);
          notify({ type: "interaction", data });
        } catch { /* ignore */ }
      });

      es.addEventListener("session_new", (e) => {
        try {
          const data = JSON.parse(e.data);
          setStats((prev) => prev ? {
            ...prev,
            total_sessions: prev.total_sessions + 1,
            active_sessions: prev.active_sessions + 1,
          } : prev);
          notify({ type: "session_new", data });
        } catch { /* ignore */ }
      });

      es.addEventListener("session_update", (e) => {
        try {
          const data = JSON.parse(e.data);
          notify({ type: "session_update", data });
        } catch { /* ignore */ }
      });

      es.addEventListener("token_deployed", (e) => {
        try {
          const data = JSON.parse(e.data);
          setStats((prev) => prev ? {
            ...prev,
            total_tokens: prev.total_tokens + data.count,
          } : prev);
          notify({ type: "token_deployed", data });
        } catch { /* ignore */ }
      });

      es.addEventListener("reconnect", () => {
        es.close();
        retryCount.current = 0;
        retryTimer.current = setTimeout(connect, BASE_DELAY_MS);
      });

      es.onerror = () => {
        setConnected(false);
        es.close();
        esRef.current = null;

        if (retryCount.current < MAX_RETRIES) {
          const delay = Math.min(
            BASE_DELAY_MS * Math.pow(2, retryCount.current),
            MAX_DELAY_MS
          );
          setError(`Connection lost. Retrying in ${Math.round(delay / 1000)}s...`);
          retryCount.current += 1;
          retryTimer.current = setTimeout(connect, delay);
        } else {
          setError("Connection lost. Max retries exceeded.");
        }
      };
    }

    connect();

    return () => {
      if (retryTimer.current) {
        clearTimeout(retryTimer.current);
        retryTimer.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      setConnected(false);
    };
  }, [notify]);

  return { stats, connected, error, recentInteractions, subscribe };
}
