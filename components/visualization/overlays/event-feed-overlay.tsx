"use client";

import type { InteractionEvent } from "@/lib/types";

const glassPanel = "bg-zinc-950/70 backdrop-blur-xl border border-white/10 rounded-xl";

const TOOL_COLORS: Record<string, string> = {
  nmap_scan: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  file_read: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  shell_exec: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  sqlmap: "bg-red-500/20 text-red-400 border-red-500/30",
  browser_navigate: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
};

export function EventFeedOverlay({
  interactions,
}: {
  interactions: InteractionEvent[];
}) {
  if (interactions.length === 0) return null;

  return (
    <div
      className={`fixed top-20 right-4 z-20 w-[272px] max-h-[calc(100vh-120px)] overflow-hidden ${glassPanel} p-4`}
    >
      <h3 className="text-xs font-medium text-zinc-400 mb-3">Live Events</h3>
      <div className="space-y-2 overflow-y-auto max-h-[calc(100vh-200px)] scrollbar-thin">
        {interactions.map((evt, i) => (
          <EventItem key={`${evt.session_id}-${evt.timestamp}-${i}`} event={evt} />
        ))}
      </div>
    </div>
  );
}

function EventItem({ event }: { event: InteractionEvent }) {
  const colorClass = TOOL_COLORS[event.tool_name] ?? "bg-zinc-500/20 text-zinc-400 border-zinc-500/30";

  return (
    <div className="flex items-start gap-2 py-1">
      <span
        className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-mono ${colorClass}`}
      >
        {event.tool_name}
      </span>
      <div className="min-w-0 flex-1">
        <span className="text-[10px] font-mono text-zinc-500 truncate block">
          {event.session_id.slice(0, 8)}
        </span>
        {event.escalation_delta > 0 && (
          <span className="text-[10px] text-red-400">
            +{event.escalation_delta} esc
          </span>
        )}
      </div>
    </div>
  );
}
