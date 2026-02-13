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
  toolName?: string;
  arguments?: Record<string, unknown>;
  timestamp: string;
}

const TOOL_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  nmap_scan: { bg: "bg-blue-500/15", text: "text-blue-400", border: "border-blue-500/40" },
  file_read: { bg: "bg-purple-500/15", text: "text-purple-400", border: "border-purple-500/40" },
  shell_exec: { bg: "bg-amber-500/15", text: "text-amber-400", border: "border-amber-500/40" },
  sqlmap_scan: { bg: "bg-red-500/15", text: "text-red-400", border: "border-red-500/40" },
  browser_navigate: { bg: "bg-cyan-500/15", text: "text-cyan-400", border: "border-cyan-500/40" },
  dns_lookup: { bg: "bg-teal-500/15", text: "text-teal-400", border: "border-teal-500/40" },
  aws_cli: { bg: "bg-orange-500/15", text: "text-orange-400", border: "border-orange-500/40" },
  kubectl: { bg: "bg-indigo-500/15", text: "text-indigo-400", border: "border-indigo-500/40" },
  vault_cli: { bg: "bg-yellow-500/15", text: "text-yellow-400", border: "border-yellow-500/40" },
  docker_registry: { bg: "bg-sky-500/15", text: "text-sky-400", border: "border-sky-500/40" },
};

const DEFAULT_TOOL_COLOR = { bg: "bg-zinc-500/15", text: "text-zinc-400", border: "border-zinc-500/40" };

const ENTRY_STYLES: Record<string, string> = {
  prompt: "bg-red-500/10 border-l-2 border-red-500/50",
  injection: "bg-emerald-500/10 border-l-2 border-emerald-500/50",
  token: "bg-cyan-500/10 border-l-2 border-cyan-500/50",
};

const ENTRY_LABELS: Record<string, { text: string; color: string }> = {
  prompt: { text: "ATTACKER", color: "text-red-400" },
  injection: { text: "HONEYPOT LURE", color: "text-emerald-400" },
  token: { text: "TOKEN DEPLOYED", color: "text-cyan-400" },
};

/** Strip common prefixes from engagement engine breadcrumbs */
function cleanInjectionText(text: string): string {
  return text
    .replace(/^Breadcrumb:\s*/i, "")
    .replace(/^Hint:\s*/i, "")
    .replace(/^Note:\s*/i, "");
}

export function PromptMonitorOverlay() {
  const { subscribe } = useLiveEventContext();
  const [entries, setEntries] = useState<MonitorEntry[]>([]);
  const nextId = useRef(0);

  useEffect(() => {
    const unsubscribe = subscribe((event: LiveEvent) => {
      const newEntries: MonitorEntry[] = [];

      if (event.type === "interaction") {
        const { prompt_summary, injection, timestamp, tool_name, arguments: args } = event.data;

        if (prompt_summary) {
          newEntries.push({
            id: nextId.current++,
            type: "prompt",
            text: prompt_summary,
            toolName: tool_name,
            arguments: args,
            timestamp,
          });
        }

        if (injection) {
          newEntries.push({
            id: nextId.current++,
            type: "injection",
            text: cleanInjectionText(injection),
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
      className={`fixed bottom-6 left-6 z-20 w-[380px] max-h-[320px] overflow-hidden ${glassPanel} p-4`}
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
        <span className="inline-block w-1 h-1 rounded-full bg-current opacity-70" style={{ color: "inherit" }} />
        <span className={`text-[9px] font-bold tracking-wider ${label.color}`}>
          {label.text}
        </span>
        <span className="text-[9px] text-zinc-600 font-mono">
          {new Date(entry.timestamp).toLocaleTimeString()}
        </span>
      </div>

      {entry.type === "prompt" && entry.arguments ? (
        <ToolArgumentsBlock toolName={entry.toolName} arguments={entry.arguments} />
      ) : (
        <p className="text-[11px] text-zinc-300 font-mono leading-tight">
          {entry.text}
        </p>
      )}
    </div>
  );
}

function ToolArgumentsBlock({
  toolName,
  arguments: args,
}: {
  toolName?: string;
  arguments: Record<string, unknown>;
}) {
  const color = TOOL_COLORS[toolName ?? ""] ?? DEFAULT_TOOL_COLOR;
  const argEntries = Object.entries(args);

  return (
    <div className={`${color.bg} border ${color.border} rounded mt-1 px-2 py-1.5`}>
      <span className={`text-[10px] font-bold ${color.text}`}>
        {toolName ?? "unknown"}
      </span>
      {argEntries.length > 0 && (
        <div className="mt-1 space-y-px">
          {argEntries.map(([key, value]) => (
            <div key={key} className="text-[11px] font-mono leading-tight">
              <span className="text-zinc-500">{key}: </span>
              <span className="text-zinc-300">{String(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
