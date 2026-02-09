"use client";

import { useEffect, useRef, useState } from "react";
import type { DashboardStats } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export function useEventStream(interval = 2) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const url = `${API_BASE}/api/events?interval=${interval}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as DashboardStats;
        setStats(data);
      } catch {
        // Ignore parse errors (e.g. heartbeats)
      }
    };

    es.onerror = () => {
      setConnected(false);
    };

    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, [interval]);

  return { stats, connected };
}
