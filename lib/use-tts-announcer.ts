import { useEffect, useRef } from "react";
import type { LiveEvent } from "./types";

const MIN_INTERVAL_MS = 4000;
const MAX_QUEUE = 5;

function formatToolName(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/sql/gi, "SQL")
    .replace(/\bmap\b/gi, "map");
}

const HIGH_VALUE_TOOLS = new Set([
  "sqlmap_scan",
  "shell_exec",
  "file_read",
  "browser_navigate",
]);

export function useTTSAnnouncer(
  subscribe: (cb: (event: LiveEvent) => void) => () => void,
) {
  const lastSpoke = useRef(0);
  const queue = useRef<string[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    function speak(text: string) {
      const now = Date.now();
      const elapsed = now - lastSpoke.current;

      if (elapsed >= MIN_INTERVAL_MS && queue.current.length === 0) {
        doSpeak(text);
      } else {
        if (queue.current.length < MAX_QUEUE) {
          queue.current.push(text);
        }
        scheduleNext();
      }
    }

    function doSpeak(text: string) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.1;
      utterance.pitch = 0.9;
      utterance.volume = 0.8;
      window.speechSynthesis.speak(utterance);
      lastSpoke.current = Date.now();
    }

    function scheduleNext() {
      if (timerRef.current) return;
      const elapsed = Date.now() - lastSpoke.current;
      const wait = Math.max(0, MIN_INTERVAL_MS - elapsed);
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        const next = queue.current.shift();
        if (next) {
          doSpeak(next);
          if (queue.current.length > 0) scheduleNext();
        }
      }, wait);
    }

    const unsubscribe = subscribe((event: LiveEvent) => {
      switch (event.type) {
        case "session_new": {
          const name = event.data.client_info?.name || "unknown agent";
          speak(`New session detected. Agent: ${name}`);
          break;
        }
        case "session_update": {
          if (event.data.escalation_level >= 2) {
            speak(`Session escalated to level ${event.data.escalation_level}`);
          }
          break;
        }
        case "interaction": {
          const tool = event.data.tool_name;
          const level = event.data.escalation_level;
          if (level >= 2 || (tool && HIGH_VALUE_TOOLS.has(tool))) {
            const toolLabel = tool ? formatToolName(tool) : "unknown";
            speak(`Alert. Escalation level ${level}. Tool: ${toolLabel}`);
          }
          break;
        }
      }
    });

    return () => {
      unsubscribe();
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      window.speechSynthesis.cancel();
    };
  }, [subscribe]);
}
