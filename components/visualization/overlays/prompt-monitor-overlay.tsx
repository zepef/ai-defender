"use client";

import { useState, useEffect, useRef } from "react";
import { useLiveEventContext } from "@/lib/live-event-context";
import type { LiveEvent } from "@/lib/types";

const glassPanel =
  "bg-zinc-950/70 backdrop-blur-xl border border-white/10 rounded-xl";

const MAX_ENTRIES = 30;

interface MonitorEntry {
  id: number;
  type: "prompt" | "injection" | "token";
  text: string;
  timestamp: string;
}

const ENTRY_STYLES: Record<string, string> = {
  prompt: "bg-red-500/10 border-l-2 border-red-500/50",
  injection: "bg-emerald-500/10 border-l-2 border-emerald-500/50",
  token: "bg-cyan-500/10 border-l-2 border-cyan-500/50",
};

const ENTRY_LABELS: Record<string, { text: string; color: string }> = {
  prompt: { text: "PROMPT", color: "text-red-400" },
  injection: { text: "LURE", color: "text-emerald-400" },
  token: { text: "TOKEN", color: "text-cyan-400" },
};

export function PromptMonitorOverlay() {
  const { subscribe } = useLiveEventContext();
  const [entries, setEntries] = useState<MonitorEntry[]>([]);
  const nextId = useRef(0);

  useEffect(() => {
    const unsubscribe = subscribe((event: LiveEvent) => {
      const newEntries: MonitorEntry[] = [];

      if (event.type === "interaction") {
        const { prompt_summary, injection, timestamp } = event.data;

        if (prompt_summary) {
          newEntries.push({
            id: nextId.current++,
            type: "prompt",
            text: prompt_summary,
            timestamp,
          });
        }

        if (injection) {
          newEntries.push({
            id: nextId.current++,
            type: "injection",
            text: injection,
            timestamp,
          });
        }
      }

      if (event.type === "token_deployed") {
        const { count, tool_name, timestamp } = event.data;
        newEntries.push({
          id: nextId.current++,
          type: "token",
          text: `${count} credential${count > 1 ? "s" : ""} deployed via ${tool_name}`,
          timestamp,
        });
      }

      if (newEntries.length > 0) {
        setEntries((prev) => {
          const next = [...newEntries, ...prev];
          return next.length > MAX_ENTRIES
            ? next.slice(0, MAX_ENTRIES)
            : next;
        });
      }
    });

    return unsubscribe;
  }, [subscribe]);

  if (entries.length === 0) return null;

  return (
    <div
      className={`fixed bottom-6 left-6 z-20 w-[340px] max-h-[320px] overflow-hidden ${glassPanel} p-4`}
    >
      <h3 className="text-xs font-medium text-zinc-400 mb-3 flex items-center gap-2">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
        Prompt Injection Monitor
      </h3>
      <div className="space-y-1.5 overflow-y-auto max-h-[260px] scrollbar-thin">
        {entries.map((entry) => (
          <MonitorItem key={entry.id} entry={entry} />
        ))}
      </div>
    </div>
  );
}

function MonitorItem({ entry }: { entry: MonitorEntry }) {
  const style = ENTRY_STYLES[entry.type];
  const label = ENTRY_LABELS[entry.type];

  return (
    <div className={`${style} rounded px-2.5 py-1.5`}>
      <div className="flex items-center gap-2 mb-0.5">
        <span className={`text-[9px] font-bold tracking-wider ${label.color}`}>
          {label.text}
        </span>
        <span className="text-[9px] text-zinc-600 font-mono">
          {new Date(entry.timestamp).toLocaleTimeString()}
        </span>
      </div>
      <p className="text-[11px] text-zinc-300 font-mono leading-tight truncate">
        {entry.text}
      </p>
    </div>
  );
}
