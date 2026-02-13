import { useEffect, useRef } from "react";
import type { LiveEvent } from "./types";

const MIN_INTERVAL_MS = 3000;
const MAX_QUEUE = 8;

function formatToolName(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\bsqlmap\b/gi, "SQL map")
    .replace(/\bnmap\b/gi, "N map");
}

export function useTTSAnnouncer(
  subscribe: (cb: (event: LiveEvent) => void) => () => void,
  muted: boolean = false,
) {
  const lastSpoke = useRef(0);
  const queue = useRef<string[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mutedRef = useRef(muted);
  mutedRef.current = muted;

  // Cancel speech immediately when muted
  useEffect(() => {
    if (muted && typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
      queue.current = [];
    }
  }, [muted]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    function speak(text: string) {
      if (mutedRef.current) return;
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
      if (mutedRef.current) return;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      const voices = window.speechSynthesis.getVoices();
      const usVoice = voices.find(
        (v) => v.lang === "en-US" && v.localService,
      );
      if (usVoice) utterance.voice = usVoice;
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
        if (mutedRef.current) {
          queue.current = [];
          return;
        }
        const next = queue.current.shift();
        if (next) {
          doSpeak(next);
          if (queue.current.length > 0) scheduleNext();
        }
      }, wait);
    }

    const unsubscribe = subscribe((event: LiveEvent) => {
      switch (event.type) {
        // --- Threat events ---
        case "session_new": {
          const name = event.data.client_info?.name || "unknown agent";
          speak(`Threat detected. New session from agent: ${name}`);
          break;
        }
        case "interaction": {
          const tool = event.data.tool_name;
          const level = event.data.escalation_level;
          const delta = event.data.escalation_delta;
          const toolLabel = tool ? formatToolName(tool) : "unknown tool";
          if (delta > 0) {
            speak(`Threat escalation. Tool: ${toolLabel}. Level now ${level}`);
          } else {
            speak(`Activity detected. Tool: ${toolLabel}. Level ${level}`);
          }
          break;
        }
        case "session_update": {
          const level = event.data.escalation_level;
          if (level >= 3) {
            speak(`Critical alert. Session reached escalation level ${level}`);
          } else if (level >= 2) {
            speak(`Warning. Session escalated to level ${level}`);
          } else {
            speak(`Session updated. Escalation level ${level}`);
          }
          break;
        }
        // --- Defensive actions ---
        case "token_deployed": {
          const count = event.data.count;
          const tool = formatToolName(event.data.tool_name);
          const total = event.data.total_tokens;
          const plural = count > 1 ? "tokens" : "token";
          speak(`Defense active. ${count} honey ${plural} deployed via ${tool}. Total: ${total}`);
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
