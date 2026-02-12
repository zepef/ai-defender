"use client";

import type { DashboardStats } from "@/lib/types";

const glassPanel = "bg-zinc-950/70 backdrop-blur-xl border border-white/10 rounded-xl";

export function StatsOverlay({
  stats,
  connected,
}: {
  stats: DashboardStats | null;
  connected: boolean;
}) {
  return (
    <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-20 ${glassPanel} px-6 py-3 flex items-center gap-6`}>
      <div className="flex items-center gap-2">
        <div
          className={`h-2 w-2 rounded-full ${
            connected ? "bg-emerald-400 animate-pulse" : "bg-red-400"
          }`}
        />
        <span className="text-xs text-zinc-400">
          {connected ? "Live" : "Offline"}
        </span>
      </div>

      {stats && (
        <>
          <Pill label="Sessions" value={stats.total_sessions} />
          <Pill label="Active" value={stats.active_sessions} />
          <Pill label="Interactions" value={stats.total_interactions} />
          <Pill label="Tokens" value={stats.total_tokens} />
          <Pill label="Escalation" value={stats.avg_escalation.toFixed(1)} />
        </>
      )}
    </div>
  );
}

function Pill({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className="font-mono text-sm text-zinc-200">{value}</span>
    </div>
  );
}
