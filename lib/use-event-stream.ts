"use client";

import { useEffect, useRef, useState } from "react";
import type { DashboardStats } from "./types";

const MAX_RETRIES = 8;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export function useEventStream(interval = 2) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const retryCount = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function connect() {
      // Clean up any existing connection
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }

      const url = `/api/events?interval=${interval}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.onopen = () => {
        setConnected(true);
        setError(null);
        retryCount.current = 0;
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as DashboardStats;
          setStats(data);
        } catch {
          // Ignore parse errors (e.g. heartbeats)
        }
      };

      es.addEventListener("reconnect", () => {
        // Server asked us to reconnect (max duration reached)
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
  }, [interval]);

  return { stats, connected, error };
}
