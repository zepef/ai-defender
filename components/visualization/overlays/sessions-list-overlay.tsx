"use client";

import { useMemo } from "react";
import type { SessionNodeData } from "../session-nodes";

const GLASS = "bg-zinc-950/70 backdrop-blur-xl border border-white/10 rounded-xl";

const ESCALATION_COLORS: Record<number, string> = {
  0: "text-emerald-400",
  1: "text-yellow-400",
  2: "text-orange-400",
  3: "text-red-400",
};

const ESCALATION_BG: Record<number, string> = {
  0: "bg-emerald-500/10",
  1: "bg-yellow-500/10",
  2: "bg-orange-500/10",
  3: "bg-red-500/10",
};

const ESCALATION_LABELS = ["None", "Low", "Medium", "Critical"];

export function SessionsListOverlay({
  sessions,
  selectedId,
  onSelect,
}: {
  sessions: Map<string, SessionNodeData>;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const sorted = useMemo(() => {
    const arr = Array.from(sessions.values());
    arr.sort((a, b) => {
      if (b.escalation_level !== a.escalation_level)
        return b.escalation_level - a.escalation_level;
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    });
    return arr;
  }, [sessions]);

  if (sorted.length === 0) return null;

  return (
    <div
      className={`fixed top-20 left-4 z-20 w-[260px] max-h-[calc(100vh-420px)] ${GLASS} p-4 flex flex-col gap-3 animate-in slide-in-from-left-4 duration-200`}
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-300">Live Sessions</h2>
        <span className="text-[10px] text-zinc-500 font-mono">{sorted.length}</span>
      </div>

      <div className="overflow-y-auto space-y-1.5 scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
        {sorted.map((s) => (
          <SessionRow
            key={s.session_id}
            data={s}
            selected={s.session_id === selectedId}
            onClick={() => onSelect(s.session_id)}
          />
        ))}
      </div>
    </div>
  );
}

function SessionRow({
  data,
  selected,
  onClick,
}: {
  data: SessionNodeData;
  selected: boolean;
  onClick: () => void;
}) {
  const level = data.escalation_level;
  const name = data.client_info?.name || "Unknown";
  const prefix = data.session_id.slice(0, 8);

  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-lg px-3 py-2 transition-colors ${
        selected
          ? "bg-white/10 border border-white/20"
          : "bg-white/[0.03] border border-transparent hover:bg-white/[0.06]"
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-zinc-200 font-medium truncate max-w-[140px]">
          {name}
        </span>
        <span
          className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${ESCALATION_BG[level]} ${ESCALATION_COLORS[level]}`}
        >
          {ESCALATION_LABELS[level] ?? `L${level}`}
        </span>
      </div>
      <div className="flex items-center gap-3 text-[10px] text-zinc-500 font-mono">
        <span>{prefix}</span>
        <span className="flex items-center gap-1">
          <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
          </svg>
          {data.interaction_count}
        </span>
        <span className={ESCALATION_COLORS[level]}>
          &#x25B2; {level}
        </span>
      </div>
    </button>
  );
}
